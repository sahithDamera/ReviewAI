import asyncio
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewContext:
    business_name: str
    category: str
    rating: int
    attributes: list[tuple[str, str]]
    comment: str | None
    tone: str


class ReviewProvider(Protocol):
    async def generate(
        self, context: ReviewContext, recent_openings: Sequence[str], variation_seed: str
    ) -> list[dict[str, str]]: ...


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def generate_review_options(context: ReviewContext) -> list[dict[str, str]]:
    """Deterministic local provider for development and tests.

    It only repeats customer-supplied facts; Phase 5 can replace this adapter with
    a hosted structured-output provider without changing the route contract.
    """
    if context.rating >= 4:
        opening = "I had a positive experience"
    elif context.rating == 3:
        opening = "I had a balanced experience"
    else:
        opening = "I had a mixed experience"
    topics = [label for label, polarity in context.attributes if polarity != "negative"]
    improvements = [label for label, polarity in context.attributes if polarity == "negative"]
    details = " and ".join(topics[:3])
    if details:
        detail_sentence = f" I especially noticed {details}."
    else:
        detail_sentence = ""
    if improvements:
        detail_sentence += f" There is room to improve {', '.join(improvements[:2])}."
    comment = _clean(context.comment or "")
    if comment:
        detail_sentence += f" {comment}"
    base = _clean(
        f"{opening} at {context.business_name}.{detail_sentence} "
        f"Overall, I would rate it {context.rating} out of 5."
    )
    rating_word = (
        "good" if context.rating >= 4 else "okay" if context.rating == 3 else "disappointing"
    )
    variants = [
        base,
        _clean(
            f"My visit to {context.business_name} was {rating_word}. "
            f"{detail_sentence} I would give it {context.rating} out of 5."
        ),
        _clean(
            f"{context.business_name}: {context.rating}/5. {detail_sentence} "
            "This reflects my own experience."
        ),
    ]
    results = [{"id": str(index), "text": text[:500]} for index, text in enumerate(variants, 1)]
    if len({item["text"] for item in results}) != 3 or any(not item["text"] for item in results):
        raise HTTPException(503, "AI_OUTPUT_INVALID")
    if any(len(item["text"].split()) > 65 for item in results):
        raise HTTPException(503, "AI_OUTPUT_INVALID")
    return results


class TemplateProvider:
    async def generate(self, context, recent_openings=(), variation_seed=""):
        return generate_review_options(context)


def _validate_provider_output(value: object) -> list[dict[str, str]]:
    if not isinstance(value, dict) or not isinstance(value.get("reviews"), list):
        raise ValueError("invalid structured output")
    reviews = value["reviews"]
    if len(reviews) != 3:
        raise ValueError("expected three reviews")
    result = []
    for index, item in enumerate(reviews, 1):
        if not isinstance(item, dict) or str(item.get("id")) != str(index):
            raise ValueError("invalid review id")
        text = _clean(str(item.get("text", "")))
        if not text or len(text) > 500 or len(text.split()) > 65:
            raise ValueError("review outside bounds")
        if any(term in text.lower() for term in ("overall,", "would definitely come back")):
            raise ValueError("unsupported closing pattern")
        result.append({"id": str(index), "text": text})
    if len({item["text"] for item in result}) != 3:
        raise ValueError("duplicate reviews")
    return result


class LLMProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 6):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _prompt(self, context: ReviewContext, recent_openings: Sequence[str], seed: str) -> str:
        facts = (
            ", ".join(f"{label} ({polarity})" for label, polarity in context.attributes) or "none"
        )
        openings = "; ".join(recent_openings) or "none"
        return (
            "Write three Google review options as JSON only: "
            '{"reviews":[{"id":"1","text":"..."},{"id":"2","text":"..."},{"id":"3","text":"..."}]}.'
            f" Business: {context.business_name}. Category: {context.category}. "
            f"Rating: {context.rating}/5. Topics: {facts}. "
            f"Customer words: {context.comment or 'none'}. Tone: {context.tone}. "
            f"Do not begin like any of these recent openings: {openings}. "
            "Option lengths should be roughly 12, 25, and 45 words. "
            "Rotate structures: specific detail, service/people, then one plain sentence. "
            "Lowercase starts, fragments, and no closing summary are allowed. "
            "Never invent dishes, staff, prices, wait times, or experiences. "
            "Preserve customer intent, keep the chosen rating, and avoid defamatory, "
            "discriminatory, abusive, or spam-like language. "
            "Avoid 'Overall, ... would definitely come back' and similar closers."
        )

    async def generate(self, context, recent_openings=(), variation_seed=""):
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}
        payload = {
            "model": self.model,
            "max_tokens": 120,
            "temperature": 0.9,
            "messages": [
                {"role": "user", "content": self._prompt(context, recent_openings, variation_seed)}
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            last_error = None
            for _ in range(2):
                try:
                    async with asyncio.timeout(self.timeout_seconds):
                        response = await client.post(
                            "https://api.anthropic.com/v1/messages", headers=headers, json=payload
                        )
                    response.raise_for_status()
                    content = response.json().get("content", [])
                    raw = "".join(
                        item.get("text", "") for item in content if isinstance(item, dict)
                    )
                    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
                    return _validate_provider_output(json.loads(raw))
                except Exception as exc:
                    last_error = exc
            logger.warning(
                "llm_generation_failed model=%s error_type=%s",
                self.model,
                type(last_error).__name__,
            )
            raise RuntimeError("LLM provider unavailable") from None

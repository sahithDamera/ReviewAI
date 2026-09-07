import pytest

from app.services.ai_service import (
    LLMProvider,
    ReviewContext,
    _validate_provider_output,
    generate_review_options,
)
from app.services.qr_service import review_qr


def test_local_ai_returns_three_distinct_bounded_options_without_inventing_topics():
    options = generate_review_options(
        ReviewContext(
            business_name="Test Cafe",
            category="Cafe",
            rating=4,
            attributes=[("Service", "positive")],
            comment="The staff were kind.",
            tone="friendly",
        )
    )
    assert [item["id"] for item in options] == ["1", "2", "3"]
    assert len({item["text"] for item in options}) == 3
    assert all(len(item["text"]) <= 500 and len(item["text"].split()) <= 65 for item in options)
    assert all("food" not in item["text"].lower() for item in options)


def test_qr_outputs_are_real_png_and_svg_assets():
    url = "http://localhost:3000/r/test-public-identifier-123456"
    png, png_type, png_ext = review_qr(url, "png")
    svg, svg_type, svg_ext = review_qr(url, "svg")
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"<svg" in svg
    assert (png_type, png_ext) == ("image/png", "png")
    assert (svg_type, svg_ext) == ("image/svg+xml", "svg")


def test_provider_output_validation_rejects_duplicates_and_accepts_three_items():
    valid = {"reviews": [{"id": str(i), "text": f"Review option {i}"} for i in range(1, 4)]}
    assert _validate_provider_output(valid)[2]["id"] == "3"
    with pytest.raises(ValueError):
        _validate_provider_output({"reviews": [{"id": "1", "text": "same"}] * 3})


def test_provider_output_removes_em_and_en_dashes():
    value = {
        "reviews": [
            {"id": "1", "text": "Friendly service — quick visit."},
            {"id": "2", "text": "A calm atmosphere – worth visiting."},
            {"id": "3", "text": "Good food and kind staff."},
        ]
    }
    output = _validate_provider_output(value)
    assert all("—" not in item["text"] and "–" not in item["text"] for item in output)


def test_anthropic_prompt_contains_recent_openings():
    provider = LLMProvider("test-key", "test-model")
    prompt = provider._prompt(
        ReviewContext("Cafe", "Cafe", 4, [], "Nice service", "friendly"),
        ["Great service today"],
        "seed",
    )
    assert "Great service today" in prompt

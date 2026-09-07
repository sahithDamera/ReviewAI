"""Selection and handoff persistence."""
# ruff: noqa: E501
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.handoff import EventInput, SelectionInput
from app.services.reviews import load_session


async def save_selection(session: AsyncSession, raw_token: str, data: SelectionInput):
    row, _ = await load_session(session, raw_token)
    final_text = data.final_text.strip()
    if data.source == "manual" and (data.generation_id is not None or data.option_id is not None):
        raise HTTPException(422, "SELECTION_INVALID")
    selected_text = None
    if data.source == "ai":
        if data.generation_id is None or data.option_id is None:
            raise HTTPException(422, "SELECTION_INVALID")
        generation = (
            (
                await session.execute(
                    text(
                        "SELECT session_id,status,reviews FROM reviewflow.review_generations "
                        "WHERE id=:id"
                    ),
                    {"id": data.generation_id},
                )
            )
            .mappings()
            .first()
        )
        if (
            generation is None
            or generation["session_id"] != row["id"]
            or generation["status"] != "succeeded"
        ):
            raise HTTPException(422, "SELECTION_INVALID")
        selected_text = next(
            (item["text"] for item in generation["reviews"] if item["id"] == data.option_id),
            None,
        )
        if selected_text is None:
            raise HTTPException(422, "SELECTION_INVALID")
    selection_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO reviewflow.review_selections
              (id,session_id,generation_id,option_id,source,final_text,is_edited)
            VALUES (:id,:session,:generation,:option,:source,:text,:edited)
            ON CONFLICT (session_id) DO UPDATE SET generation_id=EXCLUDED.generation_id,
              option_id=EXCLUDED.option_id,source=EXCLUDED.source,final_text=EXCLUDED.final_text,
              is_edited=EXCLUDED.is_edited,updated_at=now()
            RETURNING id,is_edited,final_text
        """),
        {
            "id": selection_id,
            "session": row["id"],
            "generation": data.generation_id,
            "option": data.option_id,
            "source": data.source,
            "text": final_text,
            "edited": selected_text is not None and final_text != selected_text,
        },
    )
    saved = (
        (
            await session.execute(
                text(
                    "SELECT id,is_edited,final_text FROM reviewflow.review_selections "
                    "WHERE session_id=:session"
                ),
                {"session": row["id"]},
            )
        )
        .mappings()
        .one()
    )
    await session.execute(
        text(
            "UPDATE reviewflow.review_sessions SET selected_at=COALESCE(selected_at, now()), final_text_len=:length, was_edited=:edited WHERE id=:session"
        ),
        {
            "session": row["id"],
            "length": len(final_text),
            "edited": selected_text is not None and final_text != selected_text,
        },
    )
    await session.execute(
        text(
            "INSERT INTO reviewflow.analytics_events "
            "(business_id,session_id,event_type) VALUES (:business,:session,'REVIEW_SELECTED')"
        ),
        {"business": row["business_id"], "session": row["id"]},
    )
    await session.commit()
    return {
        "selection_id": saved["id"],
        "final_text": saved["final_text"],
        "is_edited": saved["is_edited"],
    }


async def record_event(session: AsyncSession, raw_token: str, event_type: str, data: EventInput):
    row, _ = await load_session(session, raw_token)
    if data.selection_id is not None:
        owns = await session.scalar(
            text(
                "SELECT 1 FROM reviewflow.review_selections "
                "WHERE id=:selection AND session_id=:session"
            ),
            {"selection": data.selection_id, "session": row["id"]},
        )
        if owns is None:
            raise HTTPException(422, "SELECTION_INVALID")
    metadata = {"outcome": data.outcome} if data.outcome else {}
    await session.execute(
        text("""
            INSERT INTO reviewflow.analytics_events
              (id,business_id,session_id,event_type,dedupe_key,metadata)
            VALUES (:id,:business,:session,:event,:dedupe,CAST(:metadata AS jsonb))
            ON CONFLICT (business_id,dedupe_key) DO NOTHING
        """),
        {
            "id": uuid4(),
            "business": row["business_id"],
            "session": row["id"],
            "event": event_type,
            "dedupe": f"{event_type}:{data.event_id}",
            "metadata": json.dumps(metadata),
        },
    )
    milestone = {"COPY_SUCCEEDED": "copied_at", "GOOGLE_OPENED": "google_opened_at"}.get(event_type)
    if milestone:
        await session.execute(
            text(
                f"UPDATE reviewflow.review_sessions SET {milestone}=COALESCE({milestone}, now()) WHERE id=:session"
            ),
            {"session": row["id"]},
        )
    await session.commit()

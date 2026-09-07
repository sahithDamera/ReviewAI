from fastapi import HTTPException
from sqlalchemy import text

PROFILE = """
SELECT b.id,b.name,b.category_id,c.name AS category_name,b.description,b.brand_tone,
       b.status,b.public_identifier,b.public_slug,d.url AS google_review_url,
       (d.owner_confirmed_at IS NOT NULL) AS destination_confirmed
FROM reviewflow.businesses b
JOIN reviewflow.business_categories c ON c.id=b.category_id
JOIN reviewflow.business_google_destinations d ON d.business_id=b.id
WHERE b.owner_id=:owner
"""


async def owned_profile(session, owner_id, app_url, business_id=None):
    sql = PROFILE + (" AND b.id=:business" if business_id else "")
    row = (
        (await session.execute(text(sql), {"owner": owner_id, "business": business_id}))
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "BUSINESS_NOT_FOUND")
    return {**row, "review_url": f"{app_url}/r/{row['public_slug']}"}

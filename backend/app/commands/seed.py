import asyncio
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import create_database_engine
from app.core.runtime import event_loop_factory
from app.models import BusinessCategory, ExperienceAttribute

DEFAULTS = {
    "Restaurant": ["Food", "Service", "Atmosphere", "Drinks", "Value"],
    "Cafe": ["Coffee", "Food", "Service", "Atmosphere", "Value"],
    "Retail": ["Product", "Staff", "Selection", "Price", "Store Experience"],
    "Salon": ["Service", "Stylist", "Quality", "Atmosphere", "Value"],
    "Beauty": ["Service", "Treatment", "Staff", "Atmosphere", "Value"],
    "Hotel": ["Room", "Cleanliness", "Staff", "Location", "Amenities"],
    "Home Services": ["Communication", "Work Quality", "Punctuality", "Professionalism", "Value"],
    "Professional Services": [
        "Communication",
        "Service",
        "Professionalism",
        "Responsiveness",
        "Value",
    ],
    "Healthcare": ["Communication", "Staff", "Scheduling", "Environment", "Overall Experience"],
    "Fitness": ["Equipment", "Classes", "Staff", "Environment", "Value"],
    "Other": ["Service", "Quality", "Staff", "Experience", "Value"],
}


def slugify(value: str) -> str:
    return value.lower().replace(" ", "-")


async def seed_defaults(session: AsyncSession) -> None:
    """Insert missing defaults without overwriting later administrator changes."""
    for order, (name, labels) in enumerate(DEFAULTS.items()):
        slug = slugify(name)
        statement = insert(BusinessCategory).values(
            id=uuid5(NAMESPACE_URL, f"reviewflow:category:{slug}"),
            slug=slug,
            name=name,
            display_order=order,
            is_active=True,
        )
        # Return the existing row's ID even if it predates this seed command.
        category_id = await session.scalar(
            statement.on_conflict_do_update(
                index_elements=["slug"], set_={"slug": statement.excluded.slug}
            ).returning(BusinessCategory.id)
        )
        for position, label in enumerate(labels):
            attribute_slug = slugify(label)
            await session.execute(
                insert(ExperienceAttribute)
                .values(
                    id=uuid5(NAMESPACE_URL, f"reviewflow:attribute:{slug}:{attribute_slug}"),
                    category_id=category_id,
                    slug=attribute_slug,
                    label=label,
                    display_order=position,
                )
                .on_conflict_do_nothing(index_elements=["category_id", "slug"])
            )


async def main() -> None:
    engine = create_database_engine(get_settings())
    try:
        async with AsyncSession(engine) as session, session.begin():
            await seed_defaults(session)
        print("Category defaults seeded successfully (11 categories, 55 default attributes).")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=event_loop_factory)

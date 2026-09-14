"""Explicitly load validated synthetic organizations without overwriting records."""

import argparse
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert

from counterparty.config import Settings
from counterparty.database import create_engine_for_settings
from counterparty.organizations import Organization


class SyntheticOrganization(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=255)
    is_synthetic: Literal[True]


def seed_organizations(engine: Engine, fixture_path: Path) -> int:
    organizations = TypeAdapter(list[SyntheticOrganization]).validate_json(fixture_path.read_text())
    inserted = 0
    with engine.begin() as connection:
        # All importers acquire row locks in the same order, even if files differ.
        for organization in sorted(organizations, key=lambda item: item.slug):
            statement = (
                insert(Organization)
                .values(**organization.model_dump())
                .on_conflict_do_nothing(index_elements=[Organization.slug])
                .returning(Organization.id)
            )
            inserted += connection.execute(statement).scalar_one_or_none() is not None
            is_synthetic = connection.scalar(
                select(Organization.is_synthetic)
                .where(Organization.slug == organization.slug)
                .with_for_update()
            )
            if is_synthetic is not True:
                raise ValueError("Fixture slug conflicts with a non-synthetic organization")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    engine = create_engine_for_settings(Settings())
    try:
        inserted = seed_organizations(engine, args.fixture)
        print(f"Synthetic organizations inserted: {inserted}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

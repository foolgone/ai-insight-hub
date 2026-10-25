"""B-203 ORM 基类单测。"""
from __future__ import annotations

import pytest

from app.models.base import NAMING_CONVENTION, Base

pytestmark = pytest.mark.unit


def test_base_metadata_uses_naming_convention() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"


def test_naming_convention_covers_all_constraints() -> None:
    assert set(NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}

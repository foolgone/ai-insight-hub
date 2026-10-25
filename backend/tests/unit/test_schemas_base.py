"""B-207 Schema 基类测试（camelCase 入参 / snake_case 响应 / 分页 / 错误结构）。"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.base import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    BaseSchema,
    ErrorResponse,
    ORMSchema,
    Page,
    Pagination,
)
from tests.factories import UserFactory

pytestmark = pytest.mark.unit


class _SampleInput(BaseSchema):
    user_name: str
    page_size: int = DEFAULT_PAGE_SIZE


class _SampleOutput(ORMSchema):
    id: str
    email: str
    is_active: bool


def test_camel_case_input_is_accepted() -> None:
    item = _SampleInput(userName="alice", pageSize=50)

    assert item.user_name == "alice"
    assert item.page_size == 50


def test_snake_case_input_also_accepted() -> None:
    item = _SampleInput(user_name="alice", page_size=10)

    assert item.user_name == "alice"


def test_orm_schema_reads_attributes() -> None:
    user = UserFactory(id="uuid-1", email="a@example.com", is_active=True)

    output = _SampleOutput.model_validate(user)

    assert output.id == "uuid-1"
    assert output.email == "a@example.com"
    assert output.is_active is True


def test_serialization_by_alias_vs_plain() -> None:
    item = _SampleInput(user_name="alice")

    assert item.model_dump() == {"user_name": "alice", "page_size": 20}
    assert item.model_dump(by_alias=True)["userName"] == "alice"


@pytest.mark.parametrize(
    ("page", "limit", "total", "pages", "has_next", "has_prev"),
    [
        (1, 20, 0, 0, False, False),
        (1, 20, 20, 1, False, False),
        (1, 20, 21, 2, True, False),
        (2, 20, 41, 3, True, True),
        (3, 20, 41, 3, False, True),
    ],
)
def test_pagination_build(page, limit, total, pages, has_next, has_prev) -> None:
    pagination = Pagination.build(page=page, limit=limit, total=total)

    assert pagination.pages == pages
    assert pagination.has_next is has_next
    assert pagination.has_prev is has_prev


def test_pagination_limits() -> None:
    with pytest.raises(ValueError):
        Pagination.build(page=1, limit=MAX_PAGE_SIZE + 1, total=0)

    assert DEFAULT_PAGE_SIZE == 20
    assert MAX_PAGE_SIZE == 100


def test_page_generic_serialization() -> None:
    page = Page[_SampleOutput](
        items=[_SampleOutput(id="1", email="a@example.com", is_active=True)],
        pagination=Pagination.build(page=1, limit=20, total=1),
    )

    payload = page.model_dump()

    assert payload["items"][0]["id"] == "1"
    assert payload["pagination"]["has_next"] is False
    assert set(payload["pagination"]) == {
        "page",
        "limit",
        "total",
        "pages",
        "has_next",
        "has_prev",
    }


def test_error_response_schema() -> None:
    body = ErrorResponse.model_validate(
        {
            "error": {
                "code": "DATASOURCE_NOT_FOUND",
                "message": "Data source not found",
                "details": {"datasource_id": "550e8400"},
            }
        }
    )

    assert body.error.code == "DATASOURCE_NOT_FOUND"
    assert body.error.details == {"datasource_id": "550e8400"}


def test_route_with_response_model_by_alias_false_returns_snake_case() -> None:
    test_app = FastAPI()

    @test_app.get(
        "/sample",
        response_model=Page[_SampleOutput],
        response_model_by_alias=False,
    )
    async def sample() -> Page[_SampleOutput]:
        return Page[_SampleOutput](
            items=[_SampleOutput(id="1", email="a@example.com", is_active=True)],
            pagination=Pagination.build(page=1, limit=20, total=1),
        )

    response = TestClient(test_app).get("/sample")
    payload = response.json()

    assert response.status_code == 200
    assert set(payload["pagination"]) == {
        "page",
        "limit",
        "total",
        "pages",
        "has_next",
        "has_prev",
    }
    assert payload["items"][0]["is_active"] is True

"""RAG 评测数据集服务（Phase 1）。

职责边界：
- 归属校验（admin 全通，其余仅本人）；
- 版本状态机：``draft`` 可写 → ``published`` 只读 → ``archived`` 只读；
- 导入校验：**先全量校验、后写入**，任何一条不合格则整批不落库；
- checksum：发布时对条目做规范化哈希，范围与序列化规则见 ``compute_checksum``。

不做：调用 RAG、算指标、跑实验（Phase 2/3/4）。
"""
from __future__ import annotations

import hashlib
import re
import json
import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    QaDatasetImmutableError,
    QaDatasetImportInvalidError,
    QaDatasetNameExistsError,
    QaDatasetNotFoundError,
)
from app.core.ownership import assert_owner
from app.core.pagination import PaginationParams
from app.models import QaDataset, QaDatasetItem, QaDatasetVersion, User
from app.repositories import qa_dataset as repo
from app.schemas.base import Pagination
from app.schemas.qa_dataset import (
    EvidenceCoverage,
    ItemSplit,
    QaDatasetCreate,
    QaDatasetItemCreate,
    QaDatasetItemUpdate,
    QaDatasetStats,
    QaDatasetUpdate,
    SplitCounts,
)

DRAFT = "draft"
PUBLISHED = "published"
ARCHIVED = "archived"

# checksum 覆盖的字段（顺序无关，序列化时按字段名排序）
CHECKSUM_FIELDS: tuple[str, ...] = (
    "item_key",
    "query",
    "gold_answer",
    "gold_evidence",
    "category",
    "difficulty",
    "source",
    "split",
    "metadata",
)


# --------------------------------------------------------------------------- checksum


def _canonical_evidence(evidence: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """证据顺序不影响 checksum：按稳定键排序后输出固定结构。"""
    normalized = [
        {
            "document_id": item.get("document_id") or None,
            "chunk_id": item.get("chunk_id") or None,
            "evidence_text": (item.get("evidence_text") or "").strip(),
            "page_number": item.get("page_number"),
            "metadata": item.get("metadata") or {},
        }
        for item in evidence
    ]
    return sorted(
        normalized,
        key=lambda entry: (
            entry["document_id"] or "",
            entry["chunk_id"] or "",
            entry["evidence_text"],
            entry["page_number"] or 0,
        ),
    )


def canonical_item(item: Mapping[str, Any]) -> dict[str, Any]:
    """把一条样本规范化为 checksum 输入结构（字段齐全、顺序固定）。"""
    return {
        "item_key": item.get("item_key") or "",
        "query": (item.get("query") or "").strip(),
        "gold_answer": (item.get("gold_answer") or None),
        "gold_evidence": _canonical_evidence(item.get("gold_evidence") or []),
        "category": item.get("category") or None,
        "difficulty": item.get("difficulty") or None,
        "source": item.get("source") or None,
        "split": item.get("split") or "test",
        "metadata": item.get("metadata") or {},
    }


def compute_checksum(items: Sequence[Mapping[str, Any]]) -> str:
    """计算版本 checksum（sha256）。

    范围：``CHECKSUM_FIELDS`` 列出的 9 个字段（不含 id / created_at）；
    规则：
    1. 条目按 ``item_key`` 升序；
    2. 证据按 (document_id, chunk_id, evidence_text, page_number) 升序；
    3. ``json.dumps(ensure_ascii=False, sort_keys=True, separators=(",", ":"))``；
    4. UTF-8 编码后 sha256。

    因此「条目顺序变化」「证据顺序变化」不会改变 checksum，只有内容变化才会。
    """
    payload = [canonical_item(item) for item in items]
    payload.sort(key=lambda entry: entry["item_key"])
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def item_to_canonical(row: QaDatasetItem) -> dict[str, Any]:
    """ORM 条目 → checksum 输入结构（metadata 列名为 metadata，属性为 item_metadata）。"""
    return {
        "item_key": row.item_key,
        "query": row.query,
        "gold_answer": row.gold_answer,
        "gold_evidence": list(row.gold_evidence or []),
        "category": row.category,
        "difficulty": row.difficulty,
        "source": row.source,
        "split": row.split,
        "metadata": dict(row.item_metadata or {}),
    }


# --------------------------------------------------------------------------- 归属 / 查找


async def _dataset_or_404(session: AsyncSession, dataset_id: uuid.UUID, user: User) -> QaDataset:
    dataset = await repo.get_dataset(session, dataset_id)
    if dataset is None:
        raise QaDatasetNotFoundError(details={"dataset_id": str(dataset_id)})
    assert_owner(dataset.user_id, user)
    return dataset


async def _version_or_404(
    session: AsyncSession, dataset: QaDataset, version_id: uuid.UUID
) -> QaDatasetVersion:
    version = await repo.get_version(session, version_id)
    if version is None or version.dataset_id != dataset.id:
        raise QaDatasetNotFoundError(
            details={"dataset_id": str(dataset.id), "version_id": str(version_id)}
        )
    return version


def _ensure_draft(version: QaDatasetVersion) -> None:
    if version.status != DRAFT:
        raise QaDatasetImmutableError(
            details={"version_id": str(version.id), "status": version.status}
        )


# --------------------------------------------------------------------------- 数据集


async def create_dataset(
    session: AsyncSession, *, user: User, payload: QaDatasetCreate
) -> QaDataset:
    existed = await repo.get_dataset_by_name(session, user.id, payload.name)
    if existed is not None:
        raise QaDatasetNameExistsError(
            details={"name": payload.name, "dataset_id": str(existed.id)}
        )
    dataset = QaDataset(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        source_type=payload.source_type,
    )
    return await repo.add_dataset(session, dataset)


async def update_dataset(
    session: AsyncSession, *, user: User, dataset_id: uuid.UUID, payload: QaDatasetUpdate
) -> QaDataset:
    dataset = await _dataset_or_404(session, dataset_id, user)
    if payload.name is not None and payload.name != dataset.name:
        existed = await repo.get_dataset_by_name(session, dataset.user_id, payload.name)
        if existed is not None and existed.id != dataset.id:
            raise QaDatasetNameExistsError(details={"name": payload.name})
        dataset.name = payload.name
    if payload.description is not None:
        dataset.description = payload.description
    if payload.source_type is not None:
        dataset.source_type = payload.source_type
    await session.flush()
    await session.refresh(dataset)
    return dataset


async def get_dataset_detail(
    session: AsyncSession, *, user: User, dataset_id: uuid.UUID
) -> tuple[QaDataset, list[QaDatasetVersion]]:
    dataset = await _dataset_or_404(session, dataset_id, user)
    versions = await repo.list_versions(session, dataset.id)
    return dataset, versions


async def list_datasets(
    session: AsyncSession,
    *,
    user: User,
    keyword: str | None,
    params: PaginationParams,
) -> tuple[list[QaDataset], Pagination]:
    scope: uuid.UUID | None = None if user.role == "admin" else user.id
    return await repo.list_datasets(session, user_id=scope, keyword=keyword, params=params)


# --------------------------------------------------------------------------- 版本


async def create_version(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID,
    note: str | None,
    from_version_id: uuid.UUID | None,
) -> QaDatasetVersion:
    dataset = await _dataset_or_404(session, dataset_id, user)

    source_items: list[QaDatasetItem] = []
    if from_version_id is not None:
        source = await _version_or_404(session, dataset, from_version_id)
        source_items = await repo.list_all_items(session, source.id)

    number = await repo.next_version_number(session, dataset.id)
    version = QaDatasetVersion(
        dataset_id=dataset.id,
        version=number,
        status=DRAFT,
        item_count=len(source_items),
        note=note,
    )
    await repo.add_version(session, version)

    if source_items:
        clones = [
            QaDatasetItem(
                version_id=version.id,
                item_key=row.item_key,
                query=row.query,
                gold_answer=row.gold_answer,
                gold_evidence=list(row.gold_evidence or []),
                category=row.category,
                difficulty=row.difficulty,
                source=row.source,
                split=row.split,
                item_metadata=dict(row.item_metadata or {}),
            )
            for row in source_items
        ]
        await repo.add_items(session, clones)
        logger.info(
            "qa dataset version copied dataset={} from={} to={} items={}",
            dataset.id,
            from_version_id,
            version.id,
            len(clones),
        )
    return version


async def publish_version(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
) -> QaDatasetVersion:
    dataset = await _dataset_or_404(session, dataset_id, user)
    version = await _version_or_404(session, dataset, version_id)
    _ensure_draft(version)

    rows = await repo.list_all_items(session, version.id)
    if not rows:
        raise QaDatasetImportInvalidError(
            "空版本不能发布", details={"version_id": str(version.id), "item_count": 0}
        )

    version.item_count = len(rows)
    version.checksum = compute_checksum([item_to_canonical(row) for row in rows])
    version.status = PUBLISHED
    version.published_at = _now_naive()
    await session.flush()
    await session.refresh(version)
    logger.info(
        "qa dataset version published dataset={} version={} items={} checksum={}",
        dataset.id,
        version.id,
        version.item_count,
        version.checksum[:12],
    )
    return version


# --------------------------------------------------------------------------- 导入


def _snake_case(name: str) -> str:
    """Pydantic 报错 loc 用的是 camelCase 别名，转回 snake_case 便于前端定位。"""
    if not name or name.isdigit():
        return name
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for detail in exc.errors():
        loc = [_snake_case(str(part)) for part in detail.get("loc") or () if part != "items"]
        errors.append(
            {
                "field": ".".join(loc) or "item",
                "message": str(detail.get("msg") or "invalid value"),
            }
        )
    return errors


def validate_import_payload(
    raw_items: Sequence[Mapping[str, Any]], *, existing_keys: set[str]
) -> tuple[list[QaDatasetItemCreate], list[dict[str, Any]]]:
    """逐条校验导入数据，返回 ``(合格条目, 错误列表)``。

    错误列表元素形如 ``{"index": 3, "field": "gold_evidence.0.evidence_text", "message": ...}``；
    ``index`` 是 1-based 行号（对应请求 ``items`` 的下标 + 1）。
    """
    validated: list[QaDatasetItemCreate] = []
    errors: list[dict[str, Any]] = []
    seen: dict[str, int] = {}

    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, Mapping):
            errors.append({"index": index, "field": "item", "message": "条目必须是对象"})
            continue
        try:
            item = QaDatasetItemCreate.model_validate(dict(raw))
        except ValidationError as exc:
            for detail in _validation_errors(exc):
                errors.append({"index": index, **detail})
            continue

        if item.item_key in seen:
            errors.append(
                {
                    "index": index,
                    "field": "item_key",
                    "message": f"与第 {seen[item.item_key]} 行重复：{item.item_key}",
                }
            )
            continue
        if item.item_key in existing_keys:
            errors.append(
                {
                    "index": index,
                    "field": "item_key",
                    "message": f"版本内已存在：{item.item_key}",
                }
            )
            continue

        seen[item.item_key] = index
        validated.append(item)

    return validated, errors


async def import_items(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    raw_items: Sequence[Mapping[str, Any]],
) -> tuple[int, int]:
    """导入条目：全量校验 → 全部写入 → 更新计数；任何错误整批不写。"""
    dataset = await _dataset_or_404(session, dataset_id, user)
    version = await _version_or_404(session, dataset, version_id)
    _ensure_draft(version)

    existing = await repo.existing_item_keys(session, version.id)
    validated, errors = validate_import_payload(raw_items, existing_keys=existing)
    if errors:
        raise QaDatasetImportInvalidError(
            details={
                "version_id": str(version.id),
                "errors": errors,
                "error_count": len(errors),
                "imported": 0,
            }
        )

    rows = [
        QaDatasetItem(
            version_id=version.id,
            item_key=item.item_key,
            query=item.query,
            gold_answer=item.gold_answer,
            gold_evidence=[entry.model_dump() for entry in item.gold_evidence],
            category=item.category,
            difficulty=item.difficulty,
            source=item.source,
            split=item.split,
            item_metadata=item.metadata,
        )
        for item in validated
    ]
    try:
        await repo.add_items(session, rows)
    except IntegrityError as exc:  # 并发导入同一 item_key
        logger.warning("qa dataset import conflict version={} error={}", version.id, exc)
        raise QaDatasetImportInvalidError(
            details={
                "version_id": str(version.id),
                "errors": [],
                "error_count": 1,
                "message": "并发导入冲突，请重试",
            }
        ) from exc

    version.item_count = await repo.count_items(session, version.id)
    await session.flush()
    logger.info(
        "qa dataset imported dataset={} version={} count={}",
        dataset.id,
        version.id,
        len(rows),
    )
    return len(rows), version.item_count


# --------------------------------------------------------------------------- 条目读写


async def list_items(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    split: ItemSplit | None,
    category: str | None,
    keyword: str | None,
    params: PaginationParams,
) -> tuple[list[QaDatasetItem], Pagination]:
    dataset = await _dataset_or_404(session, dataset_id, user)
    version = await _version_or_404(session, dataset, version_id)
    return await repo.list_items(
        session,
        version_id=version.id,
        split=split,
        category=category,
        keyword=keyword,
        params=params,
    )


async def get_item(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    item_id: uuid.UUID,
) -> QaDatasetItem:
    dataset = await _dataset_or_404(session, dataset_id, user)
    version = await _version_or_404(session, dataset, version_id)
    item = await repo.get_item(session, item_id)
    if item is None or item.version_id != version.id:
        raise QaDatasetNotFoundError(details={"item_id": str(item_id)})
    return item


async def update_item(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: QaDatasetItemUpdate,
) -> QaDatasetItem:
    dataset = await _dataset_or_404(session, dataset_id, user)
    version = await _version_or_404(session, dataset, version_id)
    _ensure_draft(version)
    item = await repo.get_item(session, item_id)
    if item is None or item.version_id != version.id:
        raise QaDatasetNotFoundError(details={"item_id": str(item_id)})

    if payload.query is not None:
        item.query = payload.query
    if payload.gold_answer is not None:
        item.gold_answer = payload.gold_answer
    if payload.gold_evidence is not None:
        item.gold_evidence = [entry.model_dump() for entry in payload.gold_evidence]
    if payload.category is not None:
        item.category = payload.category
    if payload.difficulty is not None:
        item.difficulty = payload.difficulty
    if payload.source is not None:
        item.source = payload.source
    if payload.split is not None:
        item.split = payload.split
    if payload.metadata is not None:
        item.item_metadata = payload.metadata
    await session.flush()
    await session.refresh(item)
    return item


async def delete_item(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    item_id: uuid.UUID,
) -> None:
    dataset = await _dataset_or_404(session, dataset_id, user)
    version = await _version_or_404(session, dataset, version_id)
    _ensure_draft(version)
    item = await repo.get_item(session, item_id)
    if item is None or item.version_id != version.id:
        raise QaDatasetNotFoundError(details={"item_id": str(item_id)})
    await repo.delete_item(session, item)
    version.item_count = await repo.count_items(session, version.id)
    await session.flush()


async def stats(
    session: AsyncSession,
    *,
    user: User,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
) -> QaDatasetStats:
    dataset = await _dataset_or_404(session, dataset_id, user)
    version = await _version_or_404(session, dataset, version_id)

    total = await repo.count_items(session, version.id)
    by_split = await repo.counts_by_split(session, version.id)
    by_category = await repo.counts_by_category(session, version.id)
    with_evidence = await repo.count_with_evidence(session, version.id)

    return QaDatasetStats(
        dataset_id=dataset.id,
        version_id=version.id,
        item_count=total,
        split_counts=SplitCounts(
            train=by_split.get("train", 0),
            valid=by_split.get("valid", 0),
            test=by_split.get("test", 0),
        ),
        category_counts=by_category,
        evidence=EvidenceCoverage(
            with_evidence=with_evidence,
            without_evidence=total - with_evidence,
            coverage_rate=round(with_evidence / total, 4) if total else 0.0,
        ),
    )


# --------------------------------------------------------------------------- 工具


def _now_naive():  # noqa: ANN202 - 与其它 service 保持一致
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)


__all__ = [
    "CHECKSUM_FIELDS",
    "DRAFT",
    "PUBLISHED",
    "canonical_item",
    "compute_checksum",
    "create_dataset",
    "create_version",
    "delete_item",
    "get_dataset_detail",
    "get_item",
    "import_items",
    "item_to_canonical",
    "list_datasets",
    "list_items",
    "publish_version",
    "stats",
    "update_dataset",
    "update_item",
    "validate_import_payload",
]

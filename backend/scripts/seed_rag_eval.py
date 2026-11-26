"""Seed a small QA dataset for M2 P0 RAG workbench acceptance (idempotent).

Usage (from backend/):
    .\\venv\\Scripts\\python.exe scripts\\seed_rag_eval.py

Creates:
- dataset "M2 P0 验收数据集" (owner: admin@aiinsight.com)
- a published version with 5 items (mock-adapter friendly)

Reuses an existing published version with >=5 items; never deletes data.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.tenancy import attach_tenant_context, system_context  # noqa: E402
from app.models import QaDatasetVersion, User  # noqa: E402
from app.repositories import qa_dataset as repo  # noqa: E402
from app.schemas.qa_dataset import QaDatasetCreate  # noqa: E402
from app.services import qa_dataset_service as service  # noqa: E402

DATASET_NAME = "M2 P0 验收数据集"
ADMIN_EMAIL = "admin@aiinsight.com"
ITEMS = [
    {
        "item_key": "M2P0-01",
        "query": "退款申请提交后多久审批？",
        "gold_answer": "提交退款申请后，审批人在 1 个工作日内确认，确认后原路退回。",
        "category": "refund",
        "difficulty": "easy",
        "source": "m2p0_seed",
        "split": "test",
        "gold_evidence": [
            {
                "document_id": "mock-doc-approval",
                "chunk_id": "mock-chunk-approval-1",
                "evidence_text": "提交退款申请后，审批人在 1 个工作日内确认，确认后原路退回。",
            }
        ],
    },
    {
        "item_key": "M2P0-02",
        "query": "审批未通过怎么办？",
        "gold_answer": "审批未通过时，系统会展示拒绝原因，可修改后重新提交。",
        "category": "refund",
        "difficulty": "easy",
        "source": "m2p0_seed",
        "split": "test",
        "gold_evidence": [
            {
                "document_id": "mock-doc-approval",
                "chunk_id": "mock-chunk-approval-2",
                "evidence_text": "审批未通过时，系统会展示拒绝原因，可修改后重新提交。",
            }
        ],
    },
    {
        "item_key": "M2P0-03",
        "query": "发票什么时候开具？",
        "gold_answer": "发票在订单完成后 24 小时内自动开具，可在订单详情下载。",
        "category": "invoice",
        "difficulty": "easy",
        "source": "m2p0_seed",
        "split": "test",
        "gold_evidence": [
            {
                "document_id": "mock-doc-invoice",
                "chunk_id": "mock-chunk-invoice-1",
                "evidence_text": "发票在订单完成后 24 小时内自动开具，可在订单详情下载。",
            }
        ],
    },
    {
        "item_key": "M2P0-04",
        "query": "退款确认后多久到账？",
        "gold_answer": "审批确认后按原支付渠道退回，通常 1-3 个工作日到账。",
        "category": "refund",
        "difficulty": "medium",
        "source": "m2p0_seed",
        "split": "test",
        "gold_evidence": [],
    },
    {
        "item_key": "M2P0-05",
        "query": "订单完成后如何下载发票？",
        "gold_answer": "在订单详情中下载电子发票。",
        "category": "invoice",
        "difficulty": "easy",
        "source": "m2p0_seed",
        "split": "test",
        "gold_evidence": [],
    },
]


async def main() -> None:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if user is None:
            raise SystemExit(f"admin user not found: {ADMIN_EMAIL}; run scripts/seed_data.py first")
        attach_tenant_context(user, system_context(user.tenant_id, actor_user_id=user.id))

        dataset = await repo.get_dataset_by_name(session, user.id, DATASET_NAME)
        if dataset is None:
            dataset = await service.create_dataset(
                session,
                user=user,
                payload=QaDatasetCreate(
                    name=DATASET_NAME,
                    description="M2 P0 RAG 评测工作台验收数据（mock 适配器）",
                    source_type="mixed",
                ),
            )
            await session.commit()
            print(f"created dataset {dataset.id}")
        else:
            print(f"reuse dataset {dataset.id}")

        versions = (
            await session.scalars(
                select(QaDatasetVersion)
                .where(
                    QaDatasetVersion.dataset_id == dataset.id,
                    QaDatasetVersion.status == "published",
                )
                .order_by(QaDatasetVersion.version.desc())
            )
        ).all()
        for version in versions:
            if version.item_count >= len(ITEMS):
                print(
                    json.dumps(
                        {
                            "dataset_id": str(dataset.id),
                            "version_id": str(version.id),
                            "version": version.version,
                            "item_count": version.item_count,
                            "reused": True,
                        },
                        ensure_ascii=False,
                    )
                )
                return

        version = await service.create_version(
            session,
            user=user,
            dataset_id=dataset.id,
            note="M2 P0 seed",
            from_version_id=None,
        )
        await session.commit()

        inserted, skipped = await service.import_items(
            session,
            user=user,
            dataset_id=dataset.id,
            version_id=version.id,
            raw_items=ITEMS,
        )
        await session.commit()

        published = await service.publish_version(
            session,
            user=user,
            dataset_id=dataset.id,
            version_id=version.id,
        )
        await session.commit()
        print(f"imported={inserted} skipped={skipped}")
        print(
            json.dumps(
                {
                    "dataset_id": str(dataset.id),
                    "version_id": str(published.id),
                    "version": published.version,
                    "item_count": published.item_count,
                    "reused": False,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

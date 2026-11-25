"""Seed a 120-item dataset for M3 P1-2 pagination acceptance (idempotent).

Usage (from backend/):
    .\\venv\\Scripts\\python.exe scripts\\seed_rag_eval_large.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import QaDatasetVersion, User  # noqa: E402
from app.repositories import qa_dataset as repo  # noqa: E402
from app.schemas.qa_dataset import QaDatasetCreate  # noqa: E402
from app.services import qa_dataset_service as service  # noqa: E402

DATASET_NAME = "M3 P1-2 分页验收数据集"
ADMIN_EMAIL = "admin@aiinsight.com"
COUNT = 120

TEMPLATES = [
    ("退款申请提交后多久审批？", "提交退款申请后，审批人在 1 个工作日内确认，确认后原路退回。", "refund"),
    ("审批未通过怎么办？", "审批未通过时，系统会展示拒绝原因，可修改后重新提交。", "refund"),
    ("发票什么时候开具？", "发票在订单完成后 24 小时内自动开具，可在订单详情下载。", "invoice"),
    ("退款确认后多久到账？", "审批确认后按原支付渠道退回，通常 1-3 个工作日到账。", "refund"),
    ("订单完成后如何下载发票？", "在订单详情中下载电子发票。", "invoice"),
]


def build_items() -> list[dict]:
    items = []
    for index in range(COUNT):
        query, gold, category = TEMPLATES[index % len(TEMPLATES)]
        key = f"P12-{index + 1:03d}"
        items.append(
            {
                "item_key": key,
                "query": f"{query}（样本 {index + 1}）",
                "gold_answer": gold,
                "category": category,
                "difficulty": "easy" if index % 2 == 0 else "medium",
                "source": "m3p12_seed",
                "split": "test",
                "gold_evidence": [],
            }
        )
    return items


async def main() -> None:
    items = build_items()
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if user is None:
            raise SystemExit("admin user missing; run scripts/seed_data.py first")

        dataset = await repo.get_dataset_by_name(session, user.id, DATASET_NAME)
        if dataset is None:
            dataset = await service.create_dataset(
                session,
                user=user,
                payload=QaDatasetCreate(
                    name=DATASET_NAME,
                    description="M3 P1-2 对比分页验收（120 条）",
                    source_type="mixed",
                ),
            )
            await session.commit()

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
            if version.item_count >= len(items):
                print(
                    json.dumps(
                        {
                            "dataset_id": str(dataset.id),
                            "version_id": str(version.id),
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
            note="M3 P1-2 120 items",
            from_version_id=None,
        )
        await session.commit()
        inserted, skipped = await service.import_items(
            session,
            user=user,
            dataset_id=dataset.id,
            version_id=version.id,
            raw_items=items,
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
                    "item_count": published.item_count,
                    "reused": False,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

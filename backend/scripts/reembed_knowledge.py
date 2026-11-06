"""回填 ``knowledge_base.embedding``（embedding 离线化后执行一次）。

用法（在 ``backend/`` 目录）：

    python scripts/reembed_knowledge.py                  # 只补 embedding 为空的 FAQ
    python scripts/reembed_knowledge.py --force          # 全部重算
    python scripts/reembed_knowledge.py --datasource-id <uuid>
    python scripts/reembed_knowledge.py --batch-size 16 --dry-run

说明：
- 只处理 ``knowledge_base``；``cleaned_data.embedding`` 当前没有写入逻辑；
- 模型不可用时以非 0 退出，并提示检查镜像/``EMBEDDING_CACHE_DIR``；
- 每批提交一次，可重复执行（默认只补 NULL）。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# 允许 `python scripts/reembed_knowledge.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update  # noqa: E402

from app.core.database import SessionLocal, dispose_engine  # noqa: E402
from app.models import KnowledgeBase  # noqa: E402
from app.services import embedding_service  # noqa: E402


def _embedding_text(row) -> str:  # noqa: ANN001 - SQLAlchemy Row
    text = str(row.question or "")
    if row.variations:
        text = f"{text} {' '.join(str(item) for item in row.variations)}"
    return text.strip()


async def run(args: argparse.Namespace) -> int:
    try:
        async with SessionLocal() as session:
            stmt = select(
                KnowledgeBase.id,
                KnowledgeBase.question,
                KnowledgeBase.variations,
            ).order_by(KnowledgeBase.created_at)
            if not args.force:
                stmt = stmt.where(KnowledgeBase.embedding.is_(None))
            if args.datasource_id:
                stmt = stmt.where(
                    KnowledgeBase.datasource_id == uuid.UUID(args.datasource_id)
                )
            rows = list((await session.execute(stmt)).all())
            print(f"待处理 FAQ：{len(rows)} 条（force={args.force}）")
            if args.dry_run or not rows:
                return 0

            done = 0
            for start in range(0, len(rows), args.batch_size):
                chunk = rows[start : start + args.batch_size]
                texts = [_embedding_text(row) for row in chunk]
                vectors = await embedding_service.encode_texts(
                    texts, batch_size=args.batch_size
                )
                for row, vector in zip(chunk, vectors):
                    await session.execute(
                        update(KnowledgeBase)
                        .where(KnowledgeBase.id == row.id)
                        .values(embedding=vector)
                    )
                await session.commit()
                done += len(chunk)
                print(f"已回填 {done}/{len(rows)}")
            print("完成")
            return 0
    finally:
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description="回填 knowledge_base.embedding")
    parser.add_argument("--datasource-id", default=None, help="只处理指定数据源")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--force", action="store_true", help="重算全部（默认只补 NULL）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except embedding_service.EmbeddingError as exc:
        print(f"embedding 模型不可用：{exc}", file=sys.stderr)
        print(
            "请确认镜像已预下载模型，或 EMBEDDING_CACHE_DIR 指向本地模型目录。",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

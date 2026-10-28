"""演示数据种子（BYOK 作品集场景；覆盖 5 组产出）。

用法（在 backend/ 目录）：
    python scripts/seed_demo.py            # 幂等补齐（已存在则跳过）
    python scripts/seed_demo.py --reset    # 先删除 demo 数据源再重建（级联清空）

覆盖：
- 数据源 + raw_data + cleaned_data（数据源/清洗页）
- analysis_results 质量评估 1 条（质量评估页）
- knowledge_base 3 条 FAQ + 1 条盲区（知识库页）
- reports 1 份 markdown 综合报告（报告页）
- Dashboard 统计由上述数据自然产生

约束：固定 uuid5 保证幂等；不调 LLM；不生成 PDF/Excel 文件。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 允许 `python scripts/seed_demo.py` 直接运行（与 prod_env_check.py 一致）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, dispose_engine  # noqa: E402
from app.models import (  # noqa: E402
    AnalysisResult,
    CleanedData,
    DataSource,
    KnowledgeBase,
    RawData,
    Report,
    User,
)

DEMO_EMAIL = "demo@example.com"
DEMO_DATASOURCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")

DEMO_DIALOGUES = [
    ("订单什么时候发货？", "您好，订单一般在付款后 48 小时内发出，节假日顺延 1-2 天。", 88.0),
    ("我要退款", "您好，退款申请会在 3-5 个工作日内处理，请稍等。", 72.0),
    ("产品有质量保证吗？", "我们所有产品均提供一年质保，请放心购买。", 91.0),
]


def _now_naive() -> datetime:
    """库内 DateTime 列无时区；写库前统一转 naive（asyncpg 不接受 aware datetime）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _ensure_datasource(session) -> tuple[User, DataSource]:
    user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        raise SystemExit("demo 账号不存在：请先执行 alembic upgrade head")

    datasource = await session.get(DataSource, DEMO_DATASOURCE_ID)
    if datasource is not None:
        return user, datasource

    datasource = DataSource(
        id=DEMO_DATASOURCE_ID,
        user_id=user.id,
        name="电商客服示例数据集（2026年Q3）",
        description="预置的 AI 客服对话样例，含清洗结果、质量评估、知识库与报告，供体验展示",
        type="customer_service",
        status="active",
        workflow_status="ready",
    )
    session.add(datasource)
    await session.flush()
    return user, datasource


async def _seed_dialogues(session, datasource: DataSource) -> None:
    base_time = _now_naive() - timedelta(days=1)
    for index, (user_message, ai_response, score) in enumerate(DEMO_DIALOGUES, start=1):
        raw_id = uuid.uuid5(DEMO_DATASOURCE_ID, f"raw-{index}")
        raw = await session.get(RawData, raw_id)
        if raw is None:
            raw = RawData(
                id=raw_id,
                datasource_id=datasource.id,
                raw_content={"format": "txt", "content": f"{user_message}\n{ai_response}"},
                status="completed",
                processed_at=base_time,
            )
            session.add(raw)
            await session.flush()

        dialogue_id = uuid.uuid5(DEMO_DATASOURCE_ID, f"dialogue-{index}")
        exists = await session.scalar(
            select(CleanedData.id).where(CleanedData.dialogue_id == dialogue_id)
        )
        if exists is not None:
            continue
        session.add(
            CleanedData(
                datasource_id=datasource.id,
                raw_data_id=raw.id,
                dialogue_id=dialogue_id,
                timestamp=base_time + timedelta(minutes=index),
                user_message=user_message,
                ai_response=ai_response,
                metadata_={"agent": "cleaning_agent", "demo": True},
                quality_score=score,
                issues=[],
            )
        )


async def _seed_analysis(session, datasource: DataSource) -> None:
    analysis_id = uuid.uuid5(DEMO_DATASOURCE_ID, "analysis-quality-1")
    if await session.get(AnalysisResult, analysis_id) is not None:
        return
    cleaned = await session.scalar(
        select(CleanedData).where(
            CleanedData.dialogue_id == uuid.uuid5(DEMO_DATASOURCE_ID, "dialogue-1")
        )
    )
    session.add(
        AnalysisResult(
            id=analysis_id,
            datasource_id=datasource.id,
            data_id=cleaned.id if cleaned else uuid.uuid5(DEMO_DATASOURCE_ID, "dialogue-1"),
            analysis_type="quality",
            result={
                "overall_score": 83.7,
                "dimensions": {
                    "accuracy": 86,
                    "completeness": 80,
                    "politeness": 90,
                    "efficiency": 78,
                    "compliance": 85,
                },
                "summary": "服务应答整体规范，退款时效表述可更具体。",
                "issues": ["退款处理时效未给出明确工作日上限"],
            },
            agent_name="evaluation_agent",
            agent_version="v1.0.0",
            ai_model="deepseek-flash",
            confidence=0.86,
            processing_duration=1.2,
        )
    )


async def _seed_faqs(session, datasource: DataSource) -> None:
    faqs = [
        ("订单什么时候发货？", "付款后 48 小时内发出，节假日顺延 1-2 天。", "物流"),
        ("退款多久到账？", "审核通过后 3-5 个工作日原路退回。", "售后"),
        ("产品有质保吗？", "所有产品提供一年质保。", "售后"),
    ]
    for index, (question, answer, category) in enumerate(faqs, start=1):
        faq_id = uuid.uuid5(DEMO_DATASOURCE_ID, f"faq-{index}")
        if await session.get(KnowledgeBase, faq_id) is not None:
            continue
        session.add(
            KnowledgeBase(
                id=faq_id,
                datasource_id=datasource.id,
                question=question,
                answer=answer,
                category=category,
                frequency=index,
                quality_score=88.0,
                confidence=0.9,
                source="extracted",
                is_seed=True,
            )
        )

    gap_id = uuid.uuid5(DEMO_DATASOURCE_ID, "faq-gap-1")
    if await session.get(KnowledgeBase, gap_id) is None:
        session.add(
            KnowledgeBase(
                id=gap_id,
                datasource_id=datasource.id,
                question="可以开专票吗？",
                answer="（待补充）",
                category="发票",
                frequency=12,
                quality_score=40.0,
                confidence=0.2,
                source="manual",
                status="needs_review",
            )
        )


async def _seed_report(session, user: User, datasource: DataSource) -> None:
    report_id = uuid.uuid5(DEMO_DATASOURCE_ID, "report-comprehensive-1")
    if await session.get(Report, report_id) is not None:
        return
    session.add(
        Report(
            id=report_id,
            datasource_id=datasource.id,
            user_id=user.id,
            title="电商客服质量综合报告（示例）",
            report_type="comprehensive",
            format="markdown",
            status="completed",
            data={
                "summary": "整体质量 83.7 分；退款时效与专票问答为主要短板。",
                "sections": [
                    {"title": "质量概览", "content": "平均 83.7 分，好评率 67%。"},
                    {"title": "主要问题", "content": "退款时效表述模糊；发票类问题缺少标准答案。"},
                    {"title": "建议", "content": "补充退款时效 FAQ；将专票问题纳入知识库。"},
                ],
            },
            config={},
            generation_duration=2.4,
            completed_at=_now_naive(),
        )
    )


async def seed(reset: bool) -> None:
    async with SessionLocal() as session:
        if reset:
            existing = await session.get(DataSource, DEMO_DATASOURCE_ID)
            if existing is not None:
                await session.delete(existing)  # raw/cleaned/analysis/kb/report 由外键级联删除
            await session.commit()

        user, datasource = await _ensure_datasource(session)
        await _seed_dialogues(session, datasource)
        await _seed_analysis(session, datasource)
        await _seed_faqs(session, datasource)
        await _seed_report(session, user, datasource)

        statistics = dict(datasource.statistics or {})
        statistics.update(
            {
                "total_records": len(DEMO_DIALOGUES),
                "cleaned_records": len(DEMO_DIALOGUES),
                "quality_score_avg": round(
                    sum(score for _, _, score in DEMO_DIALOGUES) / len(DEMO_DIALOGUES), 2
                ),
                "last_processed_at": _now_naive().isoformat(),
            }
        )
        datasource.statistics = statistics
        await session.commit()

    await dispose_engine()
    print(f"demo data seeded (reset={reset})")


def main() -> None:
    parser = argparse.ArgumentParser(description="seed demo data for BYOK showcase")
    parser.add_argument("--reset", action="store_true", help="先清空 demo 数据源再重建")
    args = parser.parse_args()
    asyncio.run(seed(reset=args.reset))


if __name__ == "__main__":
    main()

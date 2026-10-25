"""种子知识库（B-502；10-知识库冷启动处理 §2.2）。

12 条通用客服 FAQ，``source="seed"``、``is_seed=TRUE``；按数据源幂等：
该数据源已初始化过种子知识时直接返回 0。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeBase

SEED_KNOWLEDGE: tuple[dict[str, Any], ...] = (
    {
        "question": "商品支持七天无理由退货吗？",
        "answer": "支持。签收后 7 天内，商品保持完好、不影响二次销售可申请无理由退货。",
        "category": "售后",
        "variations": ["可以七天无理由吗", "退货政策是什么"],
    },
    {
        "question": "多久可以发货？",
        "answer": "现货商品在付款后 48 小时内发出；预售商品按商品页标注时间发货。",
        "category": "物流",
        "variations": ["什么时候发货", "发货时间"],
    },
    {
        "question": "可以开发票吗？",
        "answer": "可以。下单时填写发票抬头与税号，电子发票将在发货后开具并发送至预留邮箱。",
        "category": "发票",
        "variations": ["能开票吗", "怎么开发票"],
    },
    {
        "question": "保修期是多久？",
        "answer": "整机保修一年，主要部件按国家三包政策执行；人为损坏不在保修范围内。",
        "category": "售后",
        "variations": ["保修多久", "质保期"],
    },
    {
        "question": "支持分期付款吗？",
        "answer": "支持花呗分期，部分商品支持 12 期免息，具体以结算页展示为准。",
        "category": "支付",
        "variations": ["可以分期吗", "花呗分期"],
    },
    {
        "question": "如何申请退款？",
        "answer": "在订单详情页点击「申请退款」，填写原因后提交；审核通过后 1-3 个工作日退回原支付渠道。",
        "category": "售后",
        "variations": ["怎么退款", "退款流程"],
    },
    {
        "question": "可以修改收货地址吗？",
        "answer": "未发货前可在订单详情页修改收货地址；已发货订单请联系快递或客服协助处理。",
        "category": "订单",
        "variations": ["改地址", "修改地址"],
    },
    {
        "question": "运费怎么计算？",
        "answer": "单笔订单满 99 元包邮，未满收取 8 元运费；偏远地区运费以结算页展示为准。",
        "category": "物流",
        "variations": ["运费多少", "包邮吗"],
    },
    {
        "question": "支持以旧换新吗？",
        "answer": "支持。在结算页选择「以旧换新」，按估价抵扣；旧机回收完成后抵扣金额原路退回。",
        "category": "售后",
        "variations": ["以旧换新", "旧机回收"],
    },
    {
        "question": "订单多久能到货？",
        "answer": "一般发货后 2-4 天送达，偏远地区 5-7 天；可在订单详情页查看物流轨迹。",
        "category": "物流",
        "variations": ["多久到货", "物流时效"],
    },
    {
        "question": "优惠券怎么使用？",
        "answer": "在结算页选择可用优惠券，每笔订单限用一张；优惠券不可叠加、不找零、不兑现。",
        "category": "支付",
        "variations": ["优惠券用法", "怎么用券"],
    },
    {
        "question": "如何联系人工客服？",
        "answer": "在对话中输入「转人工」即可接入人工客服；服务时间 9:00-21:00。",
        "category": "其他",
        "variations": ["转人工", "联系客服"],
    },
)


async def seed_knowledge(session: AsyncSession, datasource_id: uuid.UUID) -> int:
    """初始化种子知识；已初始化过则返回 0（幂等）。"""
    existing = int(
        await session.scalar(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(
                KnowledgeBase.datasource_id == datasource_id,
                KnowledgeBase.is_seed.is_(True),
            )
        )
        or 0
    )
    if existing:
        return 0

    for item in SEED_KNOWLEDGE:
        session.add(
            KnowledgeBase(
                datasource_id=datasource_id,
                question=item["question"],
                answer=item["answer"],
                category=item["category"],
                variations=list(item.get("variations") or []),
                frequency=1,
                quality_score=80.0,
                confidence=1.0,
                source="seed",
                is_seed=True,
                status="active",
            )
        )
    await session.flush()
    return len(SEED_KNOWLEDGE)


__all__ = ["SEED_KNOWLEDGE", "seed_knowledge"]

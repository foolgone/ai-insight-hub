"""种子知识库（B-502；10-知识库冷启动处理 §2.2）。

32 条通用客服 FAQ（覆盖售后/物流/发票/支付/订单/商品/会员/服务 8 类），
``source="seed"``、``is_seed=TRUE``；按数据源幂等：该数据源已初始化过种子知识时直接返回 0。
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
    {
        "question": "尺码怎么选？",
        "answer": "商品详情页有尺码对照表，可按身高体重选择；拿不准时提供身高体重，客服可推荐尺码。",
        "category": "商品",
        "variations": ["选多大码", "尺码推荐", "尺寸怎么选"],
    },
    {
        "question": "商品什么时候补货？",
        "answer": "缺货商品可点击「到货提醒」，补货后第一时间通知；具体到货时间以采购计划为准。",
        "category": "商品",
        "variations": ["什么时候有货", "补货时间", "缺货"],
    },
    {
        "question": "支持货到付款吗？",
        "answer": "部分地区支持货到付款，下单时可在支付方式中选择；不支持的地区仅支持在线支付。",
        "category": "支付",
        "variations": ["可以到付吗", "货到付款"],
    },
    {
        "question": "可以修改订单里的商品吗？",
        "answer": "订单未发货前可取消后重新下单；已发货订单不支持修改商品，可申请退货后重新购买。",
        "category": "订单",
        "variations": ["改商品", "换货怎么操作", "订单改商品"],
    },
    {
        "question": "快递公司可以指定吗？",
        "answer": "默认按下单地址匹配最优快递，暂不支持指定快递公司；如需指定请联系客服确认可行性。",
        "category": "物流",
        "variations": ["指定快递", "发什么快递"],
    },
    {
        "question": "收到商品破损怎么办？",
        "answer": "请拍照保留外包装与商品，在订单页申请售后并上传凭证；审核通过后补发或退款。",
        "category": "售后",
        "variations": ["包装破损", "商品坏了", "破损怎么赔"],
    },
    {
        "question": "少发、漏发商品怎么办？",
        "answer": "核对包裹清单后，在订单页提交「少件/漏发」售后并上传开箱照片，核实后补发缺失商品。",
        "category": "售后",
        "variations": ["少发", "漏发", "少件"],
    },
    {
        "question": "商品有质量问题怎么处理？",
        "answer": "签收后 15 天内可申请质量问题售后，提供照片/视频凭证，审核通过后换新或退款。",
        "category": "售后",
        "variations": ["质量问题", "有瑕疵", "坏了怎么办"],
    },
    {
        "question": "可以补开发票吗？",
        "answer": "可以。订单完成后 90 天内联系客服提供订单号与开票信息，可补开电子发票。",
        "category": "发票",
        "variations": ["补开发票", "发票怎么补"],
    },
    {
        "question": "可以开增值税专用发票吗？",
        "answer": "支持。下单后联系客服提交一般纳税人资质与开票信息，专票将在 5 个工作日内寄出。",
        "category": "发票",
        "variations": ["专票", "增值税发票"],
    },
    {
        "question": "会员积分怎么获得和使用？",
        "answer": "确认收货后按实付金额累计积分，100 积分抵 1 元；下单结算页可勾选使用积分。",
        "category": "会员",
        "variations": ["积分怎么用", "积分规则"],
    },
    {
        "question": "如何取消订单？",
        "answer": "未发货订单可在订单详情页点击「取消订单」并选择原因，款项按原支付渠道退回。",
        "category": "订单",
        "variations": ["取消订单", "不想要了"],
    },
    {
        "question": "退款多久到账？",
        "answer": "审核通过后 1-3 个工作日退回原支付渠道，银行卡到账可能延迟 1-2 天。",
        "category": "售后",
        "variations": ["退款到账时间", "退款多久"],
    },
    {
        "question": "支持哪些支付方式？",
        "answer": "支持微信、支付宝、银行卡与花呗分期，具体以结算页展示为准。",
        "category": "支付",
        "variations": ["怎么付款", "支付方式"],
    },
    {
        "question": "现在有什么优惠活动？",
        "answer": "可在店铺首页查看当期活动，或咨询客服获取可用优惠券；活动价以下单时结算页为准。",
        "category": "支付",
        "variations": ["有优惠吗", "活动价", "便宜点"],
    },
    {
        "question": "怎么查询物流信息？",
        "answer": "在订单详情页点击「查看物流」可看实时轨迹；物流长时间未更新请联系客服协助查询。",
        "category": "物流",
        "variations": ["查物流", "物流信息", "快递到哪了"],
    },
    {
        "question": "可以指定送达时间吗？",
        "answer": "下单时可备注期望送达时间，快递员会尽量配合；大件商品可预约送货时间。",
        "category": "物流",
        "variations": ["指定时间送达", "预约配送"],
    },
    {
        "question": "商品安装怎么预约？",
        "answer": "需要安装的商品在订单页点击「预约安装」，选择时间后由服务网点联系上门。",
        "category": "服务",
        "variations": ["预约安装", "上门安装"],
    },
    {
        "question": "赠品少发或没有收到怎么办？",
        "answer": "赠品以订单页展示为准；如参与活动未收到赠品，提供订单号与活动截图，核实后补发。",
        "category": "售后",
        "variations": ["赠品没收到", "赠品少发", "活动赠品"],
    },
    {
        "question": "可以申请价格保护吗？",
        "answer": "签收后 7 天内同商品降价可申请价保，提交订单号与降价截图，审核通过后退差价。",
        "category": "售后",
        "variations": ["价保", "降价退差价", "价格保护"],
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

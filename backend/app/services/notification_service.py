"""通知服务（#5）：SMTP 邮件发送。

- 未配置（``SMTP_USER`` 为空）时完全 no-op，返回 False，不影响业务；
- 发送在后台线程执行（smtplib 是阻塞库），超时受 ``SMTP_TIMEOUT`` 控制；
- 只做最基础的能力：主题 + 纯文本正文，收件人缺省为 ``SMTP_USER``。
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from loguru import logger

from app.core.config import settings


def smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(subject: str, body: str, *, to: str | None = None) -> bool:
    """发送纯文本邮件；未配置返回 False，发送失败抛异常由调用方决定是否吞掉。"""
    if not smtp_configured():
        logger.info("SMTP 未配置，跳过邮件：{}", subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = to or settings.SMTP_USER
    message.set_content(body)

    logger.info("发送邮件 to={} subject={}", message["To"], subject)
    with smtplib.SMTP(
        settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT
    ) as smtp:
        smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message)
    return True


__all__: list[Any] = ["send_email", "smtp_configured"]

"""端口（Port）：业务代码依赖的抽象接口。

这里是「六边形架构」里的内圈边界：application / agents 依赖这些 Protocol，
而不是依赖具体实现（DeepSeek、千问 ASR）。

当前端口（都对应**真实的替换需求**，不是为抽象而抽象）：

| 端口 | 现有实现 | 为什么需要 |
| --- | --- | --- |
| ``LLMPort`` | ``app.core.llm.LLMClient`` | 单测注入 fake；BYOK 每用户 Key 需要不同实例 |
| ``TranscriberPort`` | ``app.services.media_service`` | 供应商协议差异大（whisper / 千问）；单测注入 fake |

**签名一致性由 mypy 保证**（注入点都带 ``LLMPort`` / ``TranscriberPort`` 注解），
``runtime_checkable`` 的 ``isinstance`` 只校验「方法名存在」，不要用它当签名检查。

刻意**没有**做的端口：

- ``StoragePort``：存储只在 ``minio`` / ``local`` 之间切换，且是模块内部按
  ``STORAGE_BACKEND`` 决定的，没有运行时替换需求。早期版本定义过一个，
  但生产代码 0 调用、且静态上不可满足（模块函数 vs 带 self 的方法），已删除。
"""
from app.ports.asr import AsrConfig, TranscriberPort
from app.ports.llm import LLMPort

__all__ = ["AsrConfig", "LLMPort", "TranscriberPort"]

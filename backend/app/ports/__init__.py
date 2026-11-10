"""端口（Port）：业务代码依赖的抽象接口。

这里是「六边形架构」里的内圈边界：application / agents / services 依赖这些
Protocol，而不是依赖具体实现（MinIO、DeepSeek、千问）。

好处：
- 换供应商只改 ``infrastructure`` 侧的实现，业务代码不动；
- 测试可以传 fake 对象，不需要 mock 具体类的内部细节；
- import-linter 可以约束「端口不得依赖实现」。

当前实现映射（用结构类型匹配，无需继承）：

| 端口 | 现有实现 |
| --- | --- |
| ``LLMPort`` | ``app.core.llm.LLMClient`` |
| ``StoragePort`` | ``app.services.storage_service``（模块级函数） |
| ``TranscriberPort`` | ``app.services.media_service.transcribe_media`` 所属模块 |
"""
from app.ports.asr import AsrConfig, TranscriberPort
from app.ports.llm import LLMPort
from app.ports.storage import StoragePort, StoredFileLike

__all__ = ["AsrConfig", "LLMPort", "StoragePort", "StoredFileLike", "TranscriberPort"]

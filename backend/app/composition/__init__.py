"""组合根（Composition Root）。

装配代码不属于任何一层：它知道所有 service / adapter，负责把实现接到端口上。
刻意放在 ``app.composition`` 而不是 ``app.application``——否则 ``application``
永远依赖 ``services``，分层契约就写不出来。
"""
from app.composition import executors

__all__ = ["executors"]

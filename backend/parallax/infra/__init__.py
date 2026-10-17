"""基础设施适配器。

刻意保持极薄：核心机制层只依赖 ports 里的协议，具体实现（模型客户端、
向量库、缓存、队列）都可以在这里替换而不触及 core/。

当前提供：
    llm_openai_compat  真实模型客户端（OpenAI / 任意兼容端点）
    llm_fake           离线脚本化客户端，供单测与对照实验使用
"""

from parallax.infra.llm_fake import FakeLLMClient, RecordingLLMClient
from parallax.infra.llm_openai_compat import OpenAICompatClient

__all__ = ["FakeLLMClient", "OpenAICompatClient", "RecordingLLMClient"]

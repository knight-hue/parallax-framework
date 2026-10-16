"""领域异常。"""

from __future__ import annotations


class ParallaxError(Exception):
    """框架内所有异常的基类。"""


class ConfigurationError(ParallaxError):
    """配置缺失或非法。"""


class AdapterError(ParallaxError):
    """证据适配器失败（读不到来源、格式不可解析等）。"""


class ReaderError(ParallaxError):
    """Reader 执行失败。"""


class LLMError(ParallaxError):
    """模型调用失败（网络、限流、鉴权等）。"""


class SchemaValidationError(LLMError):
    """模型返回内容不满足约定 schema。

    单独成类是有意的：它是多智能体系统里最常见、也最该被重试和归因的失败，
    不能和网络错误混在一起（两者的退避策略完全不同）。
    """

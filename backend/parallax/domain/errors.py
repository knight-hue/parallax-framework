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


class OutputBudgetExceeded(LLMError):
    """模型把单次输出预算耗在推理上，正文为空（`finish_reason='length'`）。

    单独成类的原因：这是**可恢复**的——把批次拆小重发就能重新拿到正文。
    早先它和普通 LLMError 混在一起，被当成「这一次调用失败了」，整批发现直接丢弃。
    实测 2026-10-29 的 S2 集中臂 12 次调用里 7 次死于此，召回 4/10 是残值；
    而两臂失败数不等，使得召回对比彻底失效，约 ¥110 的数据因此作废。

    与 `SchemaValidationError` 的区别：那个是「写出来了但格式不对」，重发同一批有意义；
    这个是「根本没写完」，必须减量重发。
    """


class SchemaValidationError(LLMError):
    """模型返回内容不满足约定 schema。

    单独成类是有意的：它是多智能体系统里最常见、也最该被重试和归因的失败，
    不能和网络错误混在一起（两者的退避策略完全不同）。
    """

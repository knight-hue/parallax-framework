"""全局配置。

所有参数都显式、可环境变量覆盖，没有隐藏魔法数字——
实验报告里出现的每个阈值都必须能在这里找到出处。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PARALLAX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 模型 ----
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.0
    llm_timeout_s: float = 90.0
    llm_max_retries: int = 3
    llm_use_json_mode: bool = True
    """优先使用服务端的 JSON 输出模式（DeepSeek / OpenAI 兼容端点均支持）。"""
    llm_max_output_tokens: int = 16000
    """单次调用允许的最大输出长度。

    ⚠️ 必须显式设置。若置 0（交给服务端默认），当 Reader 分到的证据多、产出条目多时
    输出会被静默截断，返回的 JSON 不完整 → schema 校验失败 → 该 Reader 的发现全部丢失。
    这会**系统性偏袒分片更小的实验组**，让对照结果不可信。

    **为什么从 8000 提到 16000**：在真实仓库上实测到 8000 不够。
    anyio / urllib3 的文件平均 11,500 字符（合成语料只有 1,521，差 8 倍），
    模型对**哪怕 2 个文件**的完整答复就会超过 8000 token（约 23,500 字符）而被截断。
    实测该端点接受 `max_tokens` 至 32000，故取 16000 留一半余量。

    提高它**不影响已发布的合成语料结果**：那批运行的输出远低于 8000，从未触碰上限。
    """

    # ---- 盲读与聚合 ----
    n_readers: int = 3
    redundancy: int = 2
    """每条证据分给几个 Reader。1 = 《最终方案》字面的严格分区（此时无法交叉验证）。"""
    support_threshold: int = 2
    """多少个独立 Agent 报出同一主体才算高置信。"""
    max_rounds: int = 3
    seed: int = 0
    max_concurrency: int = 4
    max_schema_retries: int = 2
    max_evidence_per_call: int = 6
    """单次模型调用最多读入几条证据。

    这不是性能参数，而是**正确性参数**：一个 Reader 分到的全部证据若一次塞进模型，
    模型必须在单次响应里吐出全部分发现，一旦超过输出上限就会截断 →
    JSON 不完整 → schema 校验失败 → **该 Reader 的发现全部丢失**。
    分批调用把失败范围限制在单批之内。

    但只按条数分批在真实仓库上不够——那里的文件平均大 8 倍。
    因此另有 `llm_max_batch_chars` 作为字符维度的上限，两者取先到者。
    """
    llm_max_batch_chars: int = 24000
    """单批证据的累计字符上限，与 `max_evidence_per_call` 共同生效（任一先到即断批）。

    默认 24,000 是**兼容性取值**：
      - 合成语料平均 1,521 字符/文件 → 6 文件/批 ≈ 9,126 字符，远低于上限，行为不变；
      - 真实仓库平均 11,500 字符/文件 → 收到约 2 文件/批，配合 16000 的输出上限不再截断。

    置 0 可关闭，退化为"只按条数分批"。"""
    initial_focus_count: int = 0
    """首轮只切前 K 个审视维度（0 = 不限，切全部）。

    用于**固定预算对照实验**：当预算只够每个 Reader 读 K 个维度时，
    「所有 Reader 读同样的 K 个」与「各读不同的 K 个」花费相同，
    但唯一覆盖面相差 n_readers 倍。默认 0 不影响正常使用。"""
    reader_visibility: str = "blind"
    """`"blind"` = 框架正常模式（Reader 互不可见）；
    `"shared"` = 传统多智能体协作，作为实验对照组。见 core/reader_pool.py。"""

    # ---- 覆盖率 ----
    min_evidence_fill_rate: float = 1.0
    """证据覆盖率硬要求：多大比例的证据必须被 >= coverage_min_support 个独立 Reader 看过。"""
    max_dispute_rate: float = 0.5
    coverage_min_support: int = 2
    """证据被看过几次才算「覆盖到」。默认与 support_threshold 对齐。"""

    # ---- 预算护栏（0 = 不限）----
    max_llm_calls: int = 0
    max_tokens: int = 0

    # ---- 运行产物 ----
    runs_dir: Path = Field(default=Path("runs"))

    def is_llm_configured(self) -> bool:
        return bool(self.llm_api_key)


def load_settings(**overrides: object) -> Settings:
    """加载配置。overrides 用于测试与实验分组覆盖。"""
    if overrides:
        return Settings(**overrides)  # type: ignore[arg-type]
    return Settings()

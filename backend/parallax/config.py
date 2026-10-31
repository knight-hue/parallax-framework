"""全局配置。

所有参数都显式、可环境变量覆盖，没有隐藏魔法数字——
实验报告里出现的每个阈值都必须能在这里找到出处。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PARALLAX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # ---- 模型 ----
    # 默认使用 OpenAI 的兼容端点；部署时仍可通过 PARALLAX_LLM_BASE_URL
    # 切换到经过批准的 OpenAI-compatible 服务。
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("PARALLAX_LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("PARALLAX_LLM_API_KEY"),
        repr=False,
    )
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY"),
        repr=False,
    )
    api_key_source: str = Field(default="", repr=False)
    """实际生效的密钥来源，由 `merge_api_keys` 回填；不含密钥本身。"""
    """`OPENAI_API_KEY` 只作为回退。

    为什么拆成两个字段：`AliasChoices` 在 dotenv 源与进程环境源下的优先级不完全一致，
    实测同一份 .env 里两个都填时，优先级可能落到 `OPENAI_API_KEY` 上——那会把旧供应商的
    密钥发到新端点。把优先级写成显式合并后，行为不再依赖库的别名解析顺序。
    """
    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("PARALLAX_LLM_MODEL", "OPENAI_MODEL"),
    )
    llm_provider: Literal["auto", "openai", "openai_compat", "deepseek"] = "auto"
    """模型供应商。`auto` 按 base_url 域名推断；显式指定时优先。

    差异只影响请求参数（是否发 temperature / reasoning_effort / response_format、
    用哪个 token 字段），不改协议。见 infra/provider.py。
    """
    llm_temperature: float = 0.0
    llm_reasoning_effort: Literal["low", "medium", "high"] | None = None
    """只在显式配置时发送；需由兼容端点实际验收支持程度。"""
    llm_reasoning: bool | None = None
    """显式声明该模型是否为推理模型；`None` = 按模型名自动判断。

    **为什么必须有这个开关**：自动判断靠模型名里的关键字
    （`reasoner` / `reasoning` / `-r1` / `think`），盖不住所有命名。
    2026-10-29 实测 `deepseek-flash` 会返回 `reasoning_content`（它就是推理模型），
    但名字里一个关键字都没有，于是被判成普通模型，继续向它发 `temperature`
    与 `response_format`，并且对它用 `max_tokens`。

    **为什么不直接改自动判断**：分类会改变请求体形状（是否发 temperature、
    是否发 response_format、用哪个 token 字段），猜错会直接 400 或改变输出的
    JSON 可靠性。开关先做出来，待真实端点逐项验收后再定自动规则。
    """

    llm_timeout_s: float = 90.0
    llm_max_retries: int = 3
    llm_use_json_mode: bool = True
    """优先使用服务端的 JSON 输出模式（OpenAI-compatible 端点均支持）。"""
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
    semantic_partitioning: bool = False
    partition_assignment: Literal["hash", "greedy"] = "hash"
    """分组到 Reader 的分配算法。

    `hash`（默认）：按 `(seed, 轮次, 分组)` 哈希旋转——旧行为，已发布结果不变。
    `greedy`：按负载贪心，使各 Reader 的条数近似相等。

    默认保留 `hash` 是因为它决定「哪些文件落到同一个 Reader 手里」，
    改它会改变所有历史结果的可比性。但当分组数少时哈希会严重失衡：实测各切片在
    `group_depth=2` 下只有 4~5 个分组，配 3 个 Reader 时最坏出现 `1 / 25 / 0`——
    一个 Reader 空转、两个负载差 25 倍。那种分布下「每个 Reader 预算相同」不成立，
    受控对比会被分区不均讲圆，所以做「均匀曝光」的实验必须显式选 `greedy`。
    """
    semantic_closure_hops: int = Field(default=1, ge=1, le=4)
    semantic_max_context_units: int = Field(default=8, ge=1, le=64)
    max_concurrency: int = 4
    worker_lease_seconds: float = 300.0
    """跨进程任务租约时长；失联 worker 超时后可被其他副本接管。"""
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
    max_units_per_reader: int = 0
    """单个 Reader **在一轮内最多读入的证据条数**。0 = 不限（默认，旧行为完全不变）。

    与 `max_evidence_per_call` 是两个不同维度的上限，不能互相替代：
      - `max_evidence_per_call` 控制**一次模型调用**读几条，防的是单次输出被截断；
      - 本项控制**一个 Reader 整轮**总共读几条，限定的是曝光量（预算）。

    为什么要单独加这一项（实测教训）：S4 切片 26 个文件、每批 6 条、3 个 Reader，
    共 6 次调用就把全部文件读完了——`stop_reason=budget_exhausted` 发生在**读完之后**。
    于是 `redundancy=all` 的臂里「每个 Reader 读多少」根本不是变量，
    「集中 vs 分散」的对照在数据上不成立。要构造这个对照，必须能强制每个 Reader
    只读固定条数。

    截断规则：按 `evidence_id` 排序后取前 N 条。排序而非随机，是为了让同一份语料
    在任何臂、任何并发顺序下截断到**同一批**证据，否则截断噪声会污染两臂的差异。
      - `redundancy=all`（集中）：所有 Reader 拿到同一批前 N 条 → 联合覆盖 = N；
      - `redundancy=1`（分散）：各分区不相交，分区条数 ≤ N 时不被截断 → 联合覆盖 = 全集。
    """
    equal_exposure: bool = False
    """是否让每个 Reader 的曝光量严格相等，即自动取 `ceil(语料条数 / Reader 数)`。

    开启后 `max_units_per_reader` 的正数值被忽略（0 仍表示不限制）。

    为什么要自动推导而不写死一个数字：受控对比要求「每人预算相同」**随语料规模伸缩**。
    手写一个固定值，换个切片就不再是「每人 N/R」，而是一个既非平均、也非全部的数，
    两臂的差异里就混进了「语料变大而预算没变」这个混淆因素。

    配套使用 `partition_assignment=greedy`：如果分散臂的分区本身就不均匀
    （实测出现过 `1 / 25 / 0`），再怎么设上限也无法让「每人预算相同」成立。
    """
    max_split_depth: int = 3
    """因「单次输出预算耗尽、正文为空」而拆批重发的最大深度。

    拆批是**乘法**：6 个文件一批若每次都写不完，会拆成 3+3 → 2+1+2+1……，
    总调用数最高可到原批次的十几倍，且这些调用全部照付。不封顶的话，
    一个系统性的模型问题会把账单静默放大一个数量级——正是 2026-10-29 事故的形态。

    深度 3 意味着 6 → 3 → 1；到上限仍写不出来就如实记成丢批（`dropped_chunks`），
    让实验闸门拦住，而不是继续烧钱。
    """
    prior_claim_path: str = ""
    """E2 污染剂量实验：要注入给共享臂的「既有结论」JSON 文件路径。空 = 不注入。

    只在 `visibility="shared"` 的臂上生效——`ReaderPool.run_round` 只在共享路径
    把 `prior_claims` 拼进注入块，盲读路径直接忽略。这正是要测的自变量：
    **外面已经流通着（错误的）结论时，能被同伴结论污染与不能，召回差多少。**

    文件格式：`{"claims": [ <parallax Claim JSON>, ... ]}`，或直接一个数组。
    每条 claim 必须带至少一个 `source_ref`（账本硬约束）。

    为什么必须从文件读而不是现场生成：污染内容是自变量，它得能被审计、
    能被换掉、能在两臂之间保持完全一致；写死在代码里就只能测一个剂量。
    """
    report_max_items: int = 40
    """报告每个结论档位最多列出多少条。

    此前该值硬编码在 `render_markdown` 里且**静默生效**——真实仓库上「待验证 646 条」
    的报告只看得到 40 条，评审会以为总数就是 40。现在有两道保障：
      1. 发生截断时报告里会显式打印「共 N 条，仅列出前 M 条」；
      2. 完整清单另存为同目录的 `*.claims.json`，不受此上限影响。

    交付评审时可调到 0 表示不限制，但默认保留上限以控制报告体量。"""

    initial_focus_count: int = 0
    """首轮只切前 K 个审视维度（0 = 不限，切全部）。

    用于**固定预算对照实验**：当预算只够每个 Reader 读 K 个维度时，
    「所有 Reader 读同样的 K 个」与「各读不同的 K 个」花费相同，
    但唯一覆盖面相差 n_readers 倍。默认 0 不影响正常使用。"""
    reader_visibility: str = "blind"
    """`"blind"` = 框架正常模式（Reader 互不可见）；
    `"shared"` = 传统多智能体协作，作为实验对照组。见 core/reader_pool.py。"""

    # ---- 独立性运行约束 ----
    max_evidence_overlap_rate: float = 1.0
    """允许的 Reader 证据重叠率上限（0..1）。超过后运行会标记约束违例。"""
    min_independent_support: int = 0
    """每条 Claim 允许进入高置信前所需的最小独立支持数；0 表示沿用 support_threshold。"""
    independence_gate: Literal["off", "observe", "enforce"] = "observe"
    """独立性准入闸门。

    `off` 只记录；`observe` 报告本应如何处置（默认，安全）；
    `enforce` 在独立度不足时先提高冗余重分区，用尽尝试后把高置信结论降级。
    闸门只在显式设置了阈值时才真正可能触发，因此默认配置不会改变现有行为。
    """
    min_effective_channels: float = Field(default=0.0, ge=0.0)
    """有效独立通道数下限（0 = 不要求）。"""
    min_normalized_independence: float = Field(default=0.0, ge=0.0, le=1.0)
    """归一化独立性下限（0 = 不要求）。"""
    max_independence_attempts: int = Field(default=1, ge=0, le=3)
    """为提高独立性最多重分区几次。"""
    arbitrator: Literal["null", "blind", "llm", "llm-blind"] = "null"
    """争议仲裁器。

    `null`：不仲裁，争议原样保留为 disputed（默认，最诚实）；
    `blind`：规则型结论剥离仲裁，只拿指针/引用/可证伪条件回证据重推；
    `llm`：模型仲裁，会把双方结论一并发给模型；
    `llm-blind`：模型仲裁但**不把结论交给模型**，只给立场与证据。
    命令行 `--arbitrator` 与此等价。
    """

    # ---- 覆盖率 ----
    min_evidence_fill_rate: float = 1.0
    """证据覆盖率硬要求：多大比例的证据必须被 >= coverage_min_support 个独立 Reader 看过。"""
    max_dispute_rate: float = 0.5
    coverage_min_support: int = 2
    """证据被看过几次才算「覆盖到」。默认与 support_threshold 对齐。"""
    adaptive_scheduling: bool = False
    """是否启用确定性的缺口优先补检排序。"""

    # ---- 预算护栏（0 = 不限）----
    max_llm_calls: int = 0
    max_tokens: int = 0
    enable_reproduction: bool = False
    """是否执行 Claim 提供的最小复现命令；生产环境应在隔离 worker 中显式开启。"""
    reproduction_image: str = "parallax-repro:local"
    reproduction_timeout_s: float = Field(default=20.0, gt=0, le=300)
    enable_repair: bool = False
    """允许人工审阅后在隔离副本应用补丁与运行回归；永不直接写回原始仓库。"""
    enable_llm_falsifier: bool = False
    """是否启用独立的真实模型反证调用；默认关闭以保持成本和离线行为可控。"""
    falsifier_max_evidence_chars: int = 24000
    """单条 Claim 反证提示最多携带的证据字符数。"""

    # ---- 运行产物 ----
    runs_dir: Path = Field(default=Path("runs"))
    artifact_store: Literal["off", "local", "s3"] = "off"
    """运行产物镜像目标。`off` 只写本地 runs 目录（默认）；`local` 额外镜像到另一个目录；`s3` 镜像到 S3 兼容端点。"""
    artifact_local_root: Path | None = None
    """`local` 模式的根目录；留空则用 `<runs_dir>/_artifacts`。"""
    artifact_s3_bucket: str = ""
    artifact_s3_prefix: str = ""
    artifact_s3_endpoint: str = ""
    artifact_s3_region: str = ""
    artifact_s3_access_key: str = ""
    artifact_s3_secret_key: str = Field(default="", repr=False)

    # ---- 输入边界 ----
    audit_root: str = ""
    """允许提交审查的仓库根目录。

    空值表示开发模式不限制路径；生产容器应设置为 ``/workspace``，
    防止 HTTP 调用方借 ``repo_path`` 读取服务进程上的任意目录。
    路径会先 resolve，再做祖先关系检查以阻断符号链接逃逸。
    """
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # ---- 完成回调（Java 网关的平台能力）----
    callback_url: str = ""
    """一次审查结束后把用量回报给网关的地址。**默认留空 = 不回调**。

    为什么默认关闭：脱离网关单独跑本服务时那个地址根本不存在，
    默认打开会让每一次运行都白等一次超时。走 compose 的 gateway profile 时由 .env 显式打开。

    回调失败**只记 WARN，绝不让一次成功的审查因此变成失败**——
    记账是平台层的事，不该反过来影响编排层的成败。
    """
    callback_token: str = ""
    gateway_internal_token: str = Field(default="", repr=False)
    """回调时携带的 `X-Internal-Token`，与网关的 `PARALLAX_GATEWAY_INTERNAL_TOKEN` 一致。"""
    callback_timeout_s: float = 5.0
    """回调超时。放得很短：回调是尽力而为，不能拖住运行收尾。"""

    # ---- Git provider webhook ----
    webhook_secret: str = ""
    """GitHub webhook 的 HMAC secret；为空时 webhook 端点保持关闭。"""

    # ---- Java platform worker ----
    platform_url: str = ""
    """Fixed Java origin used by the platform worker; empty keeps the worker disabled."""
    platform_source_hosts: list[str] = Field(default_factory=list)
    platform_heartbeat_seconds: float = Field(default=20.0, ge=0.01, le=60)
    platform_replay_seconds: float = Field(default=5.0, ge=0.01, le=60)
    """Exact HTTPS Git hosts permitted for platform source retrieval."""
    platform_execution_mode: Literal["inline", "process", "container"] = "inline"
    """`process` runs the engine in a killable child process; `container` adds a container boundary."""
    platform_max_concurrent_tasks: int = Field(default=2, ge=1, le=32)
    """Bound concurrent platform executions; excess work waits for a slot."""
    platform_process_terminate_grace_seconds: float = Field(default=2.0, ge=0.1, le=30)
    """Time allowed for a killed child process to exit before force-kill is considered done."""

    # ---- Container isolation (platform_execution_mode=container) ----
    platform_container_image: str = "parallax-engine-sandbox:local"
    """Image containing this backend; see backend/docker/sandbox.Dockerfile."""
    platform_container_memory_mb: int = Field(default=768, ge=128, le=8192)
    platform_container_cpus: float = Field(default=1.0, gt=0, le=8)
    platform_container_pids: int = Field(default=128, ge=16, le=4096)
    platform_container_tmpfs_mb: int = Field(default=64, ge=8, le=1024)

    def is_llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @field_validator("llm_reasoning_effort", mode="before")
    @classmethod
    def empty_reasoning_effort(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def merge_api_keys(self):
        """`PARALLAX_LLM_API_KEY` 优先；没填时才用 `OPENAI_API_KEY`。"""
        if self.llm_api_key:
            object.__setattr__(self, "api_key_source", "PARALLAX_LLM_API_KEY")
        elif self.openai_api_key:
            object.__setattr__(self, "llm_api_key", self.openai_api_key)
            object.__setattr__(self, "api_key_source", "OPENAI_API_KEY")
        else:
            object.__setattr__(self, "api_key_source", "")
        return self

    def effective_min_independent_support(self) -> int:
        return self.min_independent_support or self.support_threshold


def load_settings(**overrides: object) -> Settings:
    """加载配置。overrides 用于测试与实验分组覆盖。"""
    if overrides:
        return Settings(**overrides)  # type: ignore[arg-type]
    return Settings()

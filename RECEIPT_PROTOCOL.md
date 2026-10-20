# Parallax Receipt Protocol v1

Parallax 的 Receipt 是一次运行中可复核动作的不可变事实记录。它与 SSE 事件分开：事件服务于实时进度，Receipt 服务于离线复盘、导出和第三方编排器接入。

每条 Receipt 都是一个 JSON 对象，必须包含：

```json
{
  "protocol_version": "parallax.receipt/v1",
  "receipt_id": "唯一字符串",
  "kind": "ingest|partition|reader|claim|coverage|verification|arbitration",
  "run_id": "运行 ID",
  "round_index": 0,
  "actor_id": "可选的 Reader/仲裁器 ID",
  "evidence_ids": [],
  "claim_ids": [],
  "payload": {},
  "at": "RFC 3339 UTC 时间"
}
```

实现约束如下：

- `receipt_id` 在一次运行内唯一；
- `evidence_ids` 与 `claim_ids` 只引用同一运行中已出现的对象；
- `payload` 保存该动作的配置快照或结构化结果，禁止把 API key 放入其中；
- Receipt 创建后不可变，修正应追加新 Receipt；
- `verification` 只记录反证结果，不能直接改写多数票；`arbitration` 通过 `arbitrated_by` 血缘边指向 Claim；
- 未知 `kind` 必须被消费者拒绝，避免把未来事件静默解释成旧语义。

接入外部编排器时，只需实现上述 JSON 的写入和读取，不需要依赖 LangGraph、FastAPI 或 Java 网关。`RunManifest.receipts` 是一次运行的完整 Receipt 列表，报告中的 Provenance Graph 可以由这些记录重建。

## 参考适配器

`parallax.ports.receipts` 提供 JSONL import/export、显式事件映射的 CallbackReceiptAdapter 和 ReceiptBundle。
Bundle 验证版本、重复 ID、run 一致性、证据/Claim 引用和 Reader 分区，再输出独立性画像与血缘图。
外部生产者未声明输出隔离时显示 unknown；这些是生产者声明的事实，不是远程证明。

`EvidenceUnit.kind` 区分 raw、summary、tool_output，derived_from 保存传递上游 ID。共享原始源码按
重叠率衡量，共享摘要/工具结果合并支持通道；缺失上游、循环或过深血缘不得计入独立支持。

```text
parallax receipts bundle.json --out audit.json
GET /api/v1/audits/{run_id}/receipts  -> JSONL
```

Callback 接口可挂接其他编排器的节点/工具钩子，不依赖它们的 SDK；不声称已经逐一验收所有框架。

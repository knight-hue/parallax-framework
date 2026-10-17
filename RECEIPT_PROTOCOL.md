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

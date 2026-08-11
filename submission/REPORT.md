# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: K4 Observability Team
- Repository URL: (điền khi nộp)
- Commit SHA cuối: (điền khi nộp)
- Thành viên và vai trò: Full-stack (Logging, PII, Tracing, Dashboard, Challenge)

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (all PASSED)
- Tổng số traces: **19+ traces** trên Langfuse (baseline + candidate + challenge)
- Số PII leak còn lại: **0**
- Link/đường dẫn dashboard: Dashboard contract tại `config/dashboard.yaml`, validated 6/6 panel

## 3. Logging và tracing

- Evidence correlation ID: Mỗi request có correlation ID unique format `req-<8-char-hex>` (ví dụ: `req-69d85829`, `req-d9904add`). Correlation ID được tạo trong `CorrelationIdMiddleware`, bind vào structlog contextvars, trả về trong header `x-request-id` và ghi vào mọi log record. Contextvars được clear trước mỗi request để tránh rò rỉ.
- Evidence PII redaction: Email `student@vinuni.edu.vn` → `[REDACTED_EMAIL]`, số điện thoại `0987654321` → `[REDACTED_PHONE_VN]`, credit card `4111 1111 1111 1111` → `[REDACTED_CREDIT_CARD]`. PII scrub processor được đặt trước `JsonlFileProcessor` để dữ liệu được che trước khi ghi xuống file.
- Evidence trace waterfall: Traces hiện trên Langfuse tại `https://us.cloud.langfuse.com` với đầy đủ generation span có `model`, `usage_details`, `cost_details`, `prompt` metadata.
- Giải thích một span đáng chú ý: Trong challenge, span `LabAgent.run` có duration ~2656ms (bình thường ~155ms). Nguyên nhân do RAG retrieval (`mock_rag.retrieve`) bị inject thêm `time.sleep(2.5)` khi `rag_slow=True`, khiến toàn bộ pipeline bị chậm.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: Version 1 (v4 after rollback), labels `baseline` + `production`. Template: `Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}`
- Version/label candidate: Version 2 (v3 on Langfuse), label `candidate`. Template: `[Feature]: {{feature}}\n[Context Documents]:\n{{docs}}\n[User Question]: {{message}}\nPlease provide a concise and accurate answer.`
- Trace ID của mỗi version:
  - **Baseline** (`LANGFUSE_PROMPT_LABEL=baseline`): `req-b803ace4` — cùng input "What is your refund policy?", trace metadata ghi `prompt_label=baseline`, `prompt_source=langfuse`
  - **Candidate** (`LANGFUSE_PROMPT_LABEL=candidate`): `req-ec08f6d8` — cùng input "What is your refund policy?", trace metadata ghi `prompt_label=candidate`, `prompt_source=langfuse`
- Bằng chứng đổi label hoặc rollback:
  1. Ban đầu: `production` label gắn với version 1
  2. Đổi label: `production` chuyển sang version 3 (nội dung v2)
  3. Rollback: `production` quay về version 4 (nội dung giống v1)
  Trace metadata ghi nhận `prompt_source=langfuse` khi fetch thành công, `prompt_source=local-fallback` khi Langfuse trả lỗi.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **HỢP LỆ: 6/6 panel** có trong dashboard contract
- Evidence dashboard: Dashboard contract tại `config/dashboard.yaml` với 6 panel:
  1. **Latency percentiles**: P50/P95/P99 từ `response_sent.latency_ms`, threshold P95 ≤ 3000ms
  2. **Request traffic**: count + rate/phút từ `request_received`, threshold ≥ 1 req/min
  3. **Error rate and breakdown**: error_rate_pct + count_by(error_type), threshold ≤ 2%
  4. **Cost over time**: sum(cost_usd) theo phút và tổng, threshold ≤ $2.50
  5. **Input and output tokens**: sum(tokens_in), sum(tokens_out), threshold ≤ 50000
  6. **Quality proxy**: mean(quality_score), threshold ≥ 0.75
- SLO đã chọn và lý do:
  - latency_p95_ms ≤ 3000ms (99.5%): Đảm bảo trải nghiệm người dùng, 3s là ngưỡng chấp nhận được cho AI API
  - error_rate_pct ≤ 2% (99.0%): Giữ tỷ lệ lỗi thấp để đảm bảo service reliability
  - daily_cost_usd ≤ $2.50 (100%): Kiểm soát chi phí vận hành
  - quality_score_avg ≥ 0.75 (95%): Đảm bảo chất lượng câu trả lời đủ tốt
- Alert rules và runbook: 3 alerts đầy đủ tại `config/alert_rules.yaml` với runbook chi tiết tại `docs/alerts.md`

## 6. Điều tra challenge

- Challenge ID: `day13-k4-observability-v1`
- Triệu chứng từ metrics:
  - **Latency P95 tăng vọt**: từ ~155ms (baseline) lên ~2656ms (challenge), vượt ngưỡng SLO 3000ms
  - **Traffic**: 19 requests, tất cả thành công (error_rate = 0%)
  - **Quality vẫn ổn**: avg 0.86, trên ngưỡng 0.75
- Trace ID liên quan:
  - `req-5348dd4f`: latency 2659ms, feature=monitoring, session=k4-challenge-s03
  - `req-027a66a4`: latency 2656ms, feature=monitoring, session=k4-challenge-s02
  - `req-39bcbcff`: latency 2656ms, feature=monitoring, session=k4-challenge-s05
  - `req-44bf84a7`: latency 2655ms, feature=monitoring, session=k4-challenge-s04
  - `req-c766ce31`: latency 2656ms, feature=monitoring, session=k4-challenge-s01
- Log line/correlation ID liên quan:
  ```json
  {"event": "response_sent", "correlation_id": "req-5348dd4f", "latency_ms": 2659, "feature": "monitoring"}
  {"event": "response_sent", "correlation_id": "req-027a66a4", "latency_ms": 2656, "feature": "monitoring"}
  ```
  Tất cả challenge requests đều có feature=`monitoring` và latency > 2500ms.
- Root cause: Incident `rag_slow` được kích hoạt, khiến hàm `retrieve()` trong `app/mock_rag.py` thêm `time.sleep(2.5)` vào mỗi lần truy vấn RAG. Điều này làm tăng latency của toàn bộ pipeline từ ~155ms lên ~2656ms. Chỉ các request có query match keyword trong CORPUS (như "monitoring") bị ảnh hưởng nặng vì phải chờ thêm 2.5 giây cho RAG retrieval.
- Fix action: Tắt incident bằng `POST /incidents/rag_slow/disable`. Trong production thật, cần điều tra nguyên nhân vector store chậm (network issue, resource exhaustion, index corruption).
- Preventive measure:
  1. Thêm timeout cho RAG retrieval với circuit breaker pattern
  2. Thiết lập alert `high_latency_p95` với threshold 3000ms và duration 5 phút
  3. Cache kết quả RAG cho các query phổ biến
  4. Thêm health check cho vector store trong `/health` endpoint

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| (Tên) | Toàn bộ: middleware, logging, PII, tracing, prompt versioning, dashboard, SLO, alerts, challenge investigation | (commit SHA khi nộp) | Cách xây dựng observability pipeline hoàn chỉnh: từ correlation ID xuyên suốt request, PII redaction trước khi ghi log, đến việc dùng 3 tầng Metrics → Traces → Logs để điều tra incident. Hiểu rõ prompt versioning và rollback trên Langfuse. |

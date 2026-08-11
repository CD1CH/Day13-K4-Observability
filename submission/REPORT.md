# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`:
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence correlation ID:
- Evidence PII redaction:
- Evidence trace waterfall:
- Giải thích một span đáng chú ý:

## 4. Prompt versioning

- Prompt name: day13-chat
- Version/label baseline: v1 (production, baseline)
- Version/label candidate: v2 (candidate)
- Trace ID của mỗi version: v1: e4b89ad34ce3c7d216ae3e354ce775bc, v2: d79157273d33e662a26d800e0d29d933
- Bằng chứng đổi label hoặc rollback: ![Rollback evidence](evidence/rollback.png)

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

## 6. Điều tra challenge

- **Challenge ID:** day13-k4-observability-v1 (Cohort K4)
- **Incident:** `rag_slow`
- **Affected feature:** `monitoring`
- **Latency threshold:** 2000ms

### Bước 1 – Triệu chứng từ metrics

Sau khi chạy `load_test.py --challenge` với incident `rag_slow` đang bật:

| Metric | Baseline (bình thường) | Incident |
|---|---|---|
| Latency P50 | ~800ms | **3293ms** |
| Latency P95 | ~830ms | **3452ms** |
| Latency P99 | ~830ms | **3452ms** |
| Error rate | 0% | 0% |
| Traffic | 5 requests | 5 requests |

P95 vượt ngưỡng 2000ms → SLO breach rõ ràng.

### Bước 2 – Khoanh vùng span bất thường qua trace

Từ Langfuse, trace của các request trong giai đoạn incident cho thấy span `retrieve` (RAG retrieval) bị block ~2500ms — chiếm phần lớn total latency ~3300ms. Các span `llm.generate` và routing vẫn bình thường.

### Bước 3 – Log chứng minh root cause

Từ `data/logs.jsonl`, thứ tự sự kiện:

```
event: incident_enabled   → correlation_id: req-0d01ca0d
event: response_sent      → correlation_id: req-f8f05ffa  → latency_ms: 3293
event: response_sent      → correlation_id: req-555f43c1  → latency_ms: 3374
event: response_sent      → correlation_id: req-a7a81bdc  → latency_ms: 3452
event: response_sent      → correlation_id: req-30add260  → latency_ms: 3375
event: response_sent      → correlation_id: req-e65eb355  → latency_ms: 3362
event: incident_disabled  → correlation_id: req-0621dcea
```

Trước `incident_enabled`: latency ~800ms. Ngay sau khi enable `rag_slow` → mọi request đều tăng +2500ms (đúng với `time.sleep(2.5)` trong `mock_rag.py:retrieve()`).

- **Correlation IDs trong incident:** req-f8f05ffa, req-555f43c1, req-a7a81bdc, req-30add260, req-e65eb355

### Bước 4 – Root cause

Hàm `retrieve()` trong `app/mock_rag.py` kiểm tra `STATE["rag_slow"]`. Khi được bật, hàm gọi `time.sleep(2.5)` trước khi trả kết quả, làm cho mọi RAG call bị delay 2.5 giây — root cause của latency spike.

```python
# app/mock_rag.py
if STATE["rag_slow"]:
    time.sleep(2.5)  # ← đây là nguyên nhân
```

### Bước 5 – Fix action và biện pháp phòng ngừa

- **Fix action:** Gọi `POST /incidents/rag_slow/disable` để tắt incident, latency về bình thường ngay lập tức.
- **Preventive measure:**
  1. Đặt **timeout** cho RAG call (ví dụ: 1000ms) để tránh blocking toàn bộ request khi vector store chậm.
  2. Thêm **circuit breaker**: nếu RAG liên tiếp timeout → fallback về general answer.
  3. Thêm **alert rule** (đã có trong `config/alert_rules.yaml`) với threshold P95 > 2000ms → on-call notification.
  4. Monitor `latency_p95` trên dashboard để phát hiện sớm trước khi SLO breach.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| | | | |

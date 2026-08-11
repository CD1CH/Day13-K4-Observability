# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: high_latency_p95
- Severity: warning
- SLI/SLO liên quan: latency_p95_ms ≤ 3000ms (target 99.5%)
- Điều kiện và thời gian duy trì: latency_p95_ms > 3000ms liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng trải nghiệm thời gian chờ lâu, có thể timeout
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra `/metrics` endpoint để xác nhận P95 latency hiện tại
  2. Mở trace waterfall trên Langfuse, tìm span có duration bất thường (đặc biệt RAG retrieval)
  3. Kiểm tra log với correlation ID của request chậm để xác định root cause
- Mitigation tạm thời: Tắt incident nếu đang bật (`/incidents/rag_slow/disable`), scale up hoặc giảm concurrency
- Owner: observability-team

## Alert 2

- Tên: high_error_rate
- Severity: critical
- SLI/SLO liên quan: error_rate_pct ≤ 2% (target 99.0%)
- Điều kiện và thời gian duy trì: error_rate_pct > 2% liên tục trong 3 phút
- Ảnh hưởng tới người dùng: Request bị lỗi, người dùng nhận HTTP 500, không có câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra `/metrics` endpoint để xem error_breakdown theo loại lỗi
  2. Tìm log có event `request_failed` và xem `error_type` phổ biến nhất
  3. Mở trace có lỗi trên Langfuse, kiểm tra span nào gây exception (ví dụ: tool_fail → Vector store timeout)
- Mitigation tạm thời: Tắt incident gây lỗi (`/incidents/tool_fail/disable`), kiểm tra kết nối vector store
- Owner: observability-team

## Alert 3

- Tên: cost_spike
- Severity: warning
- SLI/SLO liên quan: daily_cost_usd ≤ $2.50 (target 100%)
- Điều kiện và thời gian duy trì: tổng cost_usd trong ngày vượt $2.50
- Ảnh hưởng tới người dùng: Không ảnh hưởng trực tiếp, nhưng chi phí vận hành tăng bất thường
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra `/metrics` endpoint để xem total_cost_usd và avg_cost_usd
  2. So sánh tokens_out trung bình hiện tại với baseline — cost_spike thường do output tokens tăng gấp 4x
  3. Mở trace trên Langfuse, kiểm tra usage_details xem có generation nào tốn token bất thường
- Mitigation tạm thời: Tắt incident cost_spike (`/incidents/cost_spike/disable`), giới hạn max_tokens trong generation
- Owner: observability-team

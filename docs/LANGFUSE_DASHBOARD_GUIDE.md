# Hướng dẫn tạo Dashboard trên Langfuse

## Tổng quan

Bài lab yêu cầu 6 panel dashboard (nguồn chuẩn là `data/logs.jsonl`), nhưng Langfuse cũng có dashboard riêng để theo dõi traces/generations. Hướng dẫn này giải thích cách tạo **widgets trên Langfuse** để bổ trợ cho dashboard chính, và giải thích tại sao dữ liệu hiển thị được.

---

## Dữ liệu app gửi lên Langfuse

Trước khi tạo widget, cần hiểu app gửi gì lên Langfuse (xem `app/agent.py`):

```python
# 1. Trace metadata (cho mỗi request)
langfuse_client.update_current_trace(
    user_id=hash_user_id(user_id),      # user ID đã hash
    session_id=session_id,               # session identifier
    tags=["lab", feature, self.model],   # tags để filter
    metadata={                           # metadata tùy chỉnh
        "prompt_name": prompt.name,
        "prompt_label": prompt.label,
        "prompt_version": prompt.version,
        "prompt_source": prompt.source,
    },
)

# 2. Generation metadata (cho mỗi LLM call)
langfuse_client.update_current_generation(
    model=self.model,                    # model name → Langfuse tự tính cost
    usage_details={                      # token usage
        "prompt_tokens": ...,
        "completion_tokens": ...,
    },
    cost_details={"total": cost_usd},    # cost tùy chỉnh
    prompt=prompt.managed_prompt,        # link đến prompt version
)
```

> **Quan trọng**: `quality_score` hiện chỉ ghi vào log file, KHÔNG gửi lên Langfuse. Để hiển thị trên dashboard Langfuse, cần gửi thêm bằng `create_score()` (xem phần Quality bên dưới).

---

## Widget 1: Trace Count (Traffic)

### Mục đích
Đếm số lượng traces (= số requests) theo thời gian. Tương ứng panel **Traffic** trong `dashboard.yaml`.

### Cách tạo trên Langfuse
1. Vào project → **Dashboards** → **New Dashboard** (hoặc dùng dashboard mặc định)
2. Click **New Widget**
3. Cấu hình:
   - **Data Source**: Traces
   - **Metric**: Count
   - **Chart Type**: Time series (Line chart)
   - **Time Range**: Last 1 hour
   - **Dimension**: Time (auto-binned)

### Filter hữu ích
| Filter | Giá trị | Mục đích |
|---|---|---|
| Tags | `lab` | Chỉ đếm traces từ lab app |
| Tags | `qa` hoặc `summary` | Lọc theo feature |
| User ID | (hash cụ thể) | Xem traffic của 1 user |

### Cách test
```bash
# Chạy API
uv run uvicorn app.main:app --reload --env-file .env

# Gửi 10 requests
uv run python scripts/load_test.py --concurrency 5

# Kiểm tra: Mở Langfuse → Dashboards → widget Trace Count
# Phải thấy 10 traces trong khoảng thời gian vừa chạy
```

### Tại sao hoạt động
- Decorator `@observe(as_type="generation")` trên `LabAgent.run()` tự động tạo **1 trace + 1 generation span** cho mỗi lần gọi.
- Langfuse SDK gửi trace data async (background thread) nên không block request.
- Widget đếm số trace objects trong khoảng thời gian đã chọn.

---

## Widget 2: Latency Distribution

### Mục đích
Hiển thị phân bố latency (P50/P95/P99) của traces. Tương ứng panel **Latency percentiles**.

### Cách tạo trên Langfuse
1. **New Widget**
2. Cấu hình:
   - **Data Source**: Traces
   - **Metric**: Latency (P50, P95, P99)
   - **Chart Type**: Time series hoặc Histogram
   - **Time Range**: Last 1 hour

### Filter hữu ích
| Filter | Giá trị | Mục đích |
|---|---|---|
| Tags | `monitoring` | Xem latency của feature "monitoring" (bị ảnh hưởng bởi rag_slow) |
| Name | `LabAgent.run` | Chỉ xem generation span (bỏ qua overhead HTTP) |

### Cách test
```bash
# 1. Baseline: chạy load test bình thường
uv run python scripts/load_test.py
# → Expect: latency ~150-800ms

# 2. Inject rag_slow incident
uv run python scripts/inject_incident.py --scenario rag_slow

# 3. Chạy lại load test
uv run python scripts/load_test.py
# → Expect: latency ~2600-3000ms

# 4. Mở Langfuse → widget Latency
# Phải thấy latency tăng vọt sau khi inject incident

# 5. Tắt incident
uv run python scripts/inject_incident.py --scenario rag_slow --disable
```

### Tại sao hoạt động
- `@observe()` tự động đo `start_time` và `end_time` của span.
- Langfuse tính `duration = end_time - start_time` cho mỗi trace/observation.
- Widget tính percentile trên tập duration values trong time window.
- Khi `rag_slow=True`, `mock_rag.retrieve()` thêm `time.sleep(2.5)` → span duration tăng → percentile tăng.

---

## Widget 3: Cost Over Time

### Mục đích
Theo dõi chi phí LLM theo thời gian. Tương ứng panel **Cost over time**.

### Cách tạo trên Langfuse
1. **New Widget**
2. Cấu hình:
   - **Data Source**: Generations (observations)
   - **Metric**: Total Cost (sum)
   - **Chart Type**: Time series (Bar chart)
   - **Time Range**: Last 1 hour

### Filter hữu ích
| Filter | Giá trị | Mục đích |
|---|---|---|
| Model | `claude-sonnet-4-5` | Lọc theo model (app chỉ dùng 1 model) |
| Tags | `lab` | Chỉ traces từ lab |

### Cách test
```bash
# 1. Baseline
uv run python scripts/load_test.py
# → Expect: cost thấp (~$0.001-0.003/request)

# 2. Inject cost_spike
uv run python scripts/inject_incident.py --scenario cost_spike

# 3. Chạy load test
uv run python scripts/load_test.py
# → Expect: cost tăng ~4x (vì output_tokens *= 4)

# 4. Kiểm tra Langfuse → widget Cost
# Phải thấy cost bars cao hơn rõ rệt

# 5. Tắt
uv run python scripts/inject_incident.py --scenario cost_spike --disable
```

### Tại sao hoạt động
- Code gửi `cost_details={"total": cost_usd}` trong `update_current_generation()`.
- Cost được tính bởi `_estimate_cost()`: `(tokens_in / 1M) * $3 + (tokens_out / 1M) * $15`.
- Khi `cost_spike=True`, `output_tokens *= 4` → cost tăng tương ứng.
- Langfuse aggregates cost values theo thời gian và hiển thị sum.

---

## Widget 4: Token Usage

### Mục đích
Theo dõi tổng input/output tokens. Tương ứng panel **Input and output tokens**.

### Cách tạo trên Langfuse
1. **New Widget**
2. Cấu hình:
   - **Data Source**: Generations
   - **Metric**: Total Tokens (hoặc Input Tokens, Output Tokens riêng)
   - **Chart Type**: Stacked bar chart (input vs output)
   - **Time Range**: Last 1 hour

### Filter hữu ích
| Filter | Giá trị | Mục đích |
|---|---|---|
| Model | `claude-sonnet-4-5` | Lọc model |
| Prompt | `day13-chat` | Chỉ xem tokens cho prompt cụ thể |

### Cách test
```bash
# Chạy load test
uv run python scripts/load_test.py --concurrency 5
# Mở Langfuse → Generations table
# Mỗi generation hiển thị prompt_tokens và completion_tokens
# Widget tổng hợp sum(input) và sum(output)
```

### Tại sao hoạt động
- `usage_details={"prompt_tokens": ..., "completion_tokens": ...}` được gửi trong `update_current_generation()`.
- Langfuse map `prompt_tokens` → Input, `completion_tokens` → Output.
- Widget aggregates tổng tokens theo time window.
- `FakeLLM.generate()` trả `input_tokens = len(prompt)//4`, `output_tokens = random(80, 180)`.

---

## Widget 5: Model Usage Breakdown

### Mục đích
Phân tích usage theo model. Hữu ích khi có nhiều model (lab chỉ dùng 1 model nhưng cấu trúc đúng).

### Cách tạo trên Langfuse
1. **New Widget**
2. Cấu hình:
   - **Data Source**: Generations
   - **Metric**: Count
   - **Chart Type**: Pivot table hoặc Bar chart
   - **Dimension**: Model
   - **Time Range**: Last 1 hour

### Tại sao hoạt động
- `model=self.model` trong `update_current_generation()` gắn model name vào generation.
- Langfuse tự nhóm theo model field và đếm/sum theo từng nhóm.

---

## Widget 6: Quality Score ⚠️ (Cần thêm code)

### Mục đích
Theo dõi quality proxy score. Tương ứng panel **Quality proxy**.

### Vấn đề hiện tại
`quality_score` **chỉ ghi vào log file** (`data/logs.jsonl`), **không gửi lên Langfuse**. Để hiển thị trên dashboard Langfuse, cần gửi score qua API.

### Cách thêm code (trong `app/agent.py`)

Thêm sau dòng `langfuse_client.update_current_generation(...)`:

```python
# Gửi quality score lên Langfuse
langfuse_client.create_score(
    name="quality-score",
    value=quality_score,
    data_type="NUMERIC",
    comment="Heuristic quality proxy",
)
```

### Cách tạo widget trên Langfuse (sau khi thêm code)
1. **New Widget**
2. Cấu hình:
   - **Data Source**: Scores
   - **Score Name**: `quality-score`
   - **Metric**: Average
   - **Chart Type**: Time series (Line chart)
   - **Time Range**: Last 1 hour

### Filter hữu ích
| Filter | Giá trị | Mục đích |
|---|---|---|
| Score Name | `quality-score` | Chỉ lấy score quality |
| Tags | `qa` vs `summary` | So sánh quality giữa features |

### Cách test
```bash
# Chạy load test (sau khi thêm code create_score)
uv run python scripts/load_test.py --concurrency 5

# Mở Langfuse → Scores tab
# Phải thấy scores tên "quality-score" gắn vào từng trace
# Widget hiển thị mean(quality_score) theo thời gian
```

### Tại sao hoạt động
- `create_score()` tạo một Score object liên kết với trace hiện tại.
- Langfuse lưu score với `name`, `value` (numeric), và `trace_id`.
- Widget lọc scores theo name và tính mean/percentile.
- Quality được tính bởi `_heuristic_quality()`: base 0.5 + 0.2 (docs) + 0.1 (answer length) + 0.1 (token overlap).

---

## Widget 7: Prompt Version Comparison

### Mục đích
So sánh hiệu năng giữa các prompt versions. Liên quan đến phần prompt versioning.

### Cách tạo trên Langfuse
1. **New Widget**
2. Cấu hình:
   - **Data Source**: Traces
   - **Metric**: Latency (P50) hoặc Count
   - **Chart Type**: Bar chart
   - **Dimension**: Prompt Version (từ metadata)
   - **Filter**: Metadata `prompt_source` = `langfuse` (loại bỏ local fallback)

### Cách xem (không cần widget)
- Vào **Traces** → click vào 1 trace → xem **Metadata** tab
- Kiểm tra: `prompt_name`, `prompt_label`, `prompt_version`, `prompt_source`
- Vào **Prompts** → click prompt `day13-chat` → tab **Linked Traces**
- Langfuse tự động liên kết traces với prompt version qua `prompt=prompt.managed_prompt`

### Tại sao hoạt động
- `prompt=prompt.managed_prompt` trong `update_current_generation()` tạo liên kết giữa generation và prompt object trên Langfuse.
- Metadata `prompt_version`, `prompt_label` được ghi vào cả trace và generation.
- Langfuse cho phép filter/group theo metadata fields.

---

## Tóm tắt: Bảng ánh xạ Dashboard Contract ↔ Langfuse

| Panel (dashboard.yaml) | Nguồn chuẩn | Widget Langfuse tương ứng | Dữ liệu từ |
|---|---|---|---|
| Latency percentiles | `data/logs.jsonl` | Trace Latency (P50/P95/P99) | `@observe()` auto duration |
| Request traffic | `data/logs.jsonl` | Trace Count over time | `@observe()` auto trace |
| Error rate | `data/logs.jsonl` | *(Langfuse tự hiện trace status)* | Trace status ERROR |
| Cost over time | `data/logs.jsonl` | Generation Cost sum | `cost_details={"total": ...}` |
| Input/output tokens | `data/logs.jsonl` | Generation Token usage | `usage_details={...}` |
| Quality proxy | `data/logs.jsonl` | Scores average | `create_score()` **(cần thêm)** |

> **Lưu ý**: Nguồn chuẩn để chấm điểm là `data/logs.jsonl`, nhưng Langfuse dashboard giúp bạn drill-down vào từng trace để điều tra incident.

---

## Cách tạo Dashboard hoàn chỉnh (step-by-step)

1. Mở Langfuse project → sidebar **Dashboards**
2. Click **New Dashboard** → đặt tên "Day 13 AI Observability"
3. Thêm lần lượt 6 widgets theo hướng dẫn trên
4. Với mỗi widget, set time range = **Last 1 hour**
5. Sắp xếp layout: Latency + Traffic ở hàng 1, Errors + Cost ở hàng 2, Tokens + Quality ở hàng 3
6. Chạy `uv run python scripts/load_test.py --concurrency 5` để có dữ liệu
7. Screenshot dashboard → lưu vào `submission/evidence/`

import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Day 13 AI Observability", layout="wide")
st.title("Day 13 AI Observability Dashboard")

# Read data
def load_data():
    try:
        with open("data/logs.jsonl", "r") as f:
            data = [json.loads(line) for line in f if line.strip()]
        df = pd.DataFrame(data)
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'])
        return df
    except Exception as e:
        st.error(f"Error reading logs: {e}")
        return pd.DataFrame()

df = load_data()
if df.empty:
    st.warning("No data found in data/logs.jsonl")
    st.stop()

# Helpers
def plot_metric_with_threshold(label, value, threshold, operator='lte'):
    color = "normal"
    if operator == 'lte':
        if value > threshold: color = "inverse"
    else: # gte
        if value < threshold: color = "inverse"
    st.metric(label=label, value=value, delta=f"Threshold: {threshold}", delta_color=color)

# 1. Latency percentiles
st.header("Latency percentiles (ms)")
df_resp = df[df['event'] == 'response_sent'].copy()
if not df_resp.empty and 'latency_ms' in df_resp.columns:
    p50 = df_resp['latency_ms'].quantile(0.50)
    p95 = df_resp['latency_ms'].quantile(0.95)
    p99 = df_resp['latency_ms'].quantile(0.99)
    col1, col2, col3 = st.columns(3)
    col1.metric("P50", f"{p50:.1f}")
    with col2:
        plot_metric_with_threshold("P95", round(p95, 1), 3000, 'lte')
    col3.metric("P99", f"{p99:.1f}")

# 2. Request traffic
st.header("Request traffic")
df_req = df[df['event'] == 'request_received'].copy()
if not df_req.empty:
    total_reqs = len(df_req)
    time_span_min = (df_req['ts'].max() - df_req['ts'].min()).total_seconds() / 60.0
    rate = total_reqs / time_span_min if time_span_min > 0 else total_reqs
    col1, col2 = st.columns(2)
    col1.metric("Total Count", total_reqs)
    with col2:
        plot_metric_with_threshold("Rate per minute", round(rate, 2), 1, 'gte')

# 3. Error rate and breakdown
st.header("Error rate and breakdown")
failed_count = len(df[df['event'] == 'request_failed'])
received_count = len(df_req)
error_rate = (failed_count / received_count * 100) if received_count > 0 else 0
col1, col2 = st.columns(2)
with col1:
    plot_metric_with_threshold("Error Rate (%)", round(error_rate, 2), 2, 'lte')
with col2:
    if failed_count > 0 and 'error_type' in df.columns:
        st.write(df[df['event'] == 'request_failed']['error_type'].value_counts())
    else:
        st.write("No errors")

# 4. Cost over time
st.header("Cost over time (USD)")
if not df_resp.empty and 'cost_usd' in df_resp.columns:
    total_cost = df_resp['cost_usd'].sum()
    plot_metric_with_threshold("Total Cost", round(total_cost, 4), 2.5, 'lte')
    cost_by_min = df_resp.set_index('ts').resample('1min')['cost_usd'].sum()
    st.line_chart(cost_by_min)

# 5. Input and output tokens
st.header("Input and output tokens")
if not df_resp.empty:
    in_tok = df_resp['tokens_in'].sum() if 'tokens_in' in df_resp.columns else 0
    out_tok = df_resp['tokens_out'].sum() if 'tokens_out' in df_resp.columns else 0
    total_tok = in_tok + out_tok
    col1, col2, col3 = st.columns(3)
    col1.metric("Tokens In", in_tok)
    col2.metric("Tokens Out", out_tok)
    with col3:
        plot_metric_with_threshold("Total Tokens", total_tok, 50000, 'lte')

# 6. Quality proxy
st.header("Quality proxy")
if not df_resp.empty and 'quality_score' in df_resp.columns:
    mean_quality = df_resp['quality_score'].mean()
    plot_metric_with_threshold("Mean Quality Score", round(mean_quality, 3), 0.75, 'gte')

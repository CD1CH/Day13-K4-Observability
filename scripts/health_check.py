#!/usr/bin/env python3
import json
import urllib.request
import urllib.error
import sys

BASE_URL = "http://localhost:8000"

def check_health():
    try:
        req = urllib.request.Request(f"{BASE_URL}/health")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            print(f"✅ Health Check Passed: {data}")
            if any(data.get("incidents", {}).values()):
                print("⚠️ Warning: There are active incidents!")
            return True
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return False

def check_metrics():
    try:
        req = urllib.request.Request(f"{BASE_URL}/metrics")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            print(f"✅ Metrics Check Passed")
            error_rate = data.get("error_rate_pct", 0)
            if error_rate > 2:
                print(f"🚨 Critical: High Error Rate ({error_rate}%)")
            else:
                print(f"ℹ️ Current Error Rate: {error_rate}%")
            return True
    except Exception as e:
        print(f"❌ Metrics Check Failed: {e}")
        return False

if __name__ == "__main__":
    print("--- Running System Health Check ---")
    health_ok = check_health()
    metrics_ok = check_metrics()
    if not (health_ok and metrics_ok):
        sys.exit(1)
    print("--- All Checks Completed Successfully ---")

#!/usr/bin/env python3
"""Verify GLM-5.1 routing through Z.AI (not OpenRouter).

Two-layer verification:
  1. DB check  — confirm routing_rules + routing_targets point to z.ai/glm-5.1
  2. Runtime check — POST /v1/chat/completions with model=GLM-5.1,
     then assert x-bf-provider == "z.ai"

Usage:
    python verify_glm_routing.py          # both layers
    python verify_glm_routing.py --db     # DB only
    python verify_glm_routing.py --runtime  # runtime only
"""

import argparse
import sqlite3
import sys
import urllib.request
import urllib.error
import json
import time

BIFROST_DB = r"C:\Users\brsth\AppData\Roaming\bifrost\config.db"
BIFROST_URL = "http://localhost:8080"
ROUTE_ID = "route_glm_5_1"
MODEL_NAME = "GLM-5.1"


def check_db() -> dict:
    """Read routing_rules + routing_targets from the SQLite DB."""
    result = {"route_id": ROUTE_ID, "model": MODEL_NAME, "provider": None, "model_target": None, "ok": False}
    try:
        conn = sqlite3.connect(BIFROST_DB)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT provider, model FROM routing_targets WHERE rule_id = ?",
            (ROUTE_ID,)
        )
        row = c.fetchone()
        conn.close()
        if row:
            result["provider"] = row["provider"]
            result["model_target"] = row["model"]
            result["ok"] = row["provider"] == "z.ai" and row["model"] == "glm-5.1"
        else:
            result["error"] = "No routing target found for route_glm_5_1"
    except Exception as e:
        result["error"] = str(e)
    return result


def check_runtime() -> dict:
    """Send a minimal chat completion request and read the x-bf-provider response header."""
    result = {"url": f"{BIFROST_URL}/v1/chat/completions", "model": MODEL_NAME, "provider": None, "ok": False}
    payload = json.dumps({
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 5,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BIFROST_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # Wait for Bifrost to bind port (up to 15s)
    for _ in range(30):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result["status"] = resp.status
                body = json.loads(resp.read().decode("utf-8"))
                extra = body.get("extra_fields", {})
                result["provider"] = extra.get("provider", "")
                result["model_requested"] = extra.get("model_requested", "")
                result["cel_match"] = extra.get("cel_match", None)
                result["ok"] = result["provider"] == "z.ai"
            return result
        except urllib.error.URLError as e:
            if "Connection refused" in str(e):
                time.sleep(0.5)
                continue
            result["error"] = str(e)
            return result
    result["error"] = "Connection refused after 15s — Bifrost may not be running"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify GLM-5.1 routing through Z.AI")
    parser.add_argument("--db", action="store_true", help="DB layer only")
    parser.add_argument("--runtime", action="store_true", help="Runtime layer only")
    args = parser.parse_args()

    run_db = not args.runtime
    run_runtime = not args.db

    if run_db:
        db_result = check_db()
        print(f"[DB]   route_id={db_result['route_id']}  provider={db_result['provider']}  model={db_result['model_target']}  ok={db_result['ok']}")
        if "error" in db_result:
            print(f"       ERROR: {db_result['error']}")

    if run_runtime:
        rt_result = check_runtime()
        print(f"[RT]   provider={rt_result.get('provider','N/A')}  model_requested={rt_result.get('model_requested','N/A')}  ok={rt_result['ok']}")
        if "error" in rt_result:
            print(f"       ERROR: {rt_result['error']}")
        elif "status" in rt_result:
            print(f"       HTTP {rt_result['status']}")

    # Exit code
    db_ok = check_db()["ok"] if run_db else True
    rt_ok = check_runtime()["ok"] if run_runtime else True

    if db_ok and rt_ok:
        print("\nPASS: GLM-5.1 routes through z.ai")
        return 0
    else:
        print("\nFAIL: GLM-5.1 routing does NOT target z.ai")
        return 1


if __name__ == "__main__":
    sys.exit(main())
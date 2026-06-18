#!/usr/bin/env python3
"""
Comprehensive Automated Regression Test Suite for 家装智能自动报价系统
========================================================================
Tests ALL core functionality against the running backend at localhost:8100.

Each test:
  - Prints PASS/FAIL clearly
  - On FAIL: shows actual vs expected value
  - Continues to next test (doesn't stop on failure)
  - Return exit code 0 if all pass, 1 if any fail

Usage:
    python3 regression_test.py          # run all tests
    python3 regression_test.py -v       # verbose (detailed output)
    python3 regression_test.py -n 3     # run only test #3

Requirements: requests (pip install requests)
"""

import json
import os
import sys
import traceback

BASE_URL = "http://localhost:8100"

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
BASELINE_PATH = os.path.join(SCRIPT_DIR, "baseline.json")
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "backend", "uploads")

# ── Test state ─────────────────────────────────────────────────────────────
passed = 0
failed = 0
failures = []
results_header = []

# ── Helpers ────────────────────────────────────────────────────────────────

def _import_requests():
    """Import the requests library, with a helpful error message if missing."""
    try:
        import requests as req
        return req
    except ImportError:
        print("FATAL: 'requests' library is required. Install with: pip install requests")
        sys.exit(2)


def wait_for_idle(timeout=60):
    """Wait until system task_state returns to 'idle'. Returns True if idle, False if timeout."""
    import time
    req = _import_requests()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = req.get(f"{BASE_URL}/api/system/status", timeout=5)
            data = r.json()
            state = data.get("data", {}).get("task_state", "")
            if state == "idle":
                return True
            print(f"  ⏳ 等待系统空闲... (当前状态: {state})")
            time.sleep(2)
        except Exception:
            time.sleep(1)
    return False


def ensure_idle_or_reset(timeout=60):
    """If system is stuck non-idle, restart the backend server."""
    import subprocess, time
    req = _import_requests()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = req.get(f"{BASE_URL}/api/system/status", timeout=5)
            state = r.json().get("data", {}).get("task_state", "")
            if state == "idle":
                return True
            print(f"  ⏳ 等待系统空闲... (当前状态: {state})")
            time.sleep(3)
        except Exception:
            time.sleep(2)
    print("  ⚠️  系统卡死，重启后端...")
    subprocess.run(["fuser", "-k", "8100/tcp"], capture_output=True)
    time.sleep(2)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.Popen(["bash", os.path.join(root, "start.sh")], cwd=root,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(10)
    return True


def api_get(path, **kwargs):
    """GET request helper. Returns (response_json, status_code, error_string)."""
    req = _import_requests()
    try:
        r = req.get(f"{BASE_URL}{path}", timeout=kwargs.pop("timeout", 30), **kwargs)
        return r.json(), r.status_code, None
    except Exception as e:
        return None, 0, str(e)


def api_post(path, files=None, data=None, timeout=120):
    """POST request helper (multipart/form-data). Returns (response_json, status_code, error_string)."""
    req = _import_requests()
    try:
        r = req.post(f"{BASE_URL}{path}", files=files, data=data, timeout=timeout)
        return r.json(), r.status_code, None
    except Exception as e:
        return None, 0, str(e)


def check(condition, msg):
    """Assert a condition; count pass/fail."""
    global passed, failed, failures
    if condition:
        passed += 1
        print(f"  ✓ PASS: {msg}")
    else:
        failed += 1
        failures.append(msg)
        print(f"  ✗ FAIL: {msg}")
    return condition

def check_eq(actual, expected, label=""):
    """Check equality; print actual vs expected on failure."""
    if label:
        label = f" ({label})"
    ok = actual == expected
    if ok:
        check(True, f"Expected {expected!r}{label}")
    else:
        check(False, f"Expected {expected!r}, got {actual!r}{label}")
    return ok


def check_approx(actual, expected, tolerance=0.01, label=""):
    """Check approximate float equality."""
    ok = abs(actual - expected) <= tolerance
    if ok:
        check(True, f"Expected ~{expected}{label}")
    else:
        check(False, f"Expected ~{expected}, got {actual}{label}")
    return ok


def safe_int(val):
    """Convert val to int safely (handles both int and string)."""
    if isinstance(val, float):
        return int(round(val))
    return int(val)


def heading(num, title):
    """Print a section heading."""
    h = f"\n{'─'*60}\n── [{num}] {title}\n{'─'*60}"
    print(h)
    results_header.append(f"[{num}] {title}")


# ── Test functions ─────────────────────────────────────────────────────────

def test_health_check():
    """1. 健康检查: GET /api/system/health → 200, status=healthy"""
    heading(1, "健康检查 — GET /api/system/health")
    data, status, err = api_get("/api/system/health")
    if check(err is None, f"Request succeeded (no error)"):
        check_eq(status, 200, "HTTP status")
        if data and "data" in data:
            check_eq(data["data"].get("status"), "healthy", "status=healthy")
        elif data:
            check_eq(data.get("status"), "healthy", "status=healthy (top-level)")


def test_system_status():
    """2. 系统状态: GET /api/system/status → task_state=idle"""
    heading(2, "系统状态 — GET /api/system/status")
    data, status, err = api_get("/api/system/status")
    if check(err is None, "Request succeeded"):
        check_eq(status, 200, "HTTP status")
        if data and "data" in data:
            check_eq(data["data"].get("task_state"), "idle", "task_state=idle")


def test_dxf_parse_baseline():
    """3. DXF解析基线: POST /api/analyze_full → match baseline"""
    heading(3, "DXF解析基线 — POST /api/analyze_full")

    # 等待系统空闲
    if not wait_for_idle(timeout=120):
        check(False, "System did not become idle within timeout")
        return

    # Locate the DXF file
    dxf_path = os.path.join(UPLOADS_DIR, "73e7fb280299_cad.dxf")
    if not os.path.exists(dxf_path):
        check(False, f"DXF file not found at {dxf_path}")
        return

    # Load baseline
    if not os.path.exists(BASELINE_PATH):
        check(False, f"Baseline file not found at {BASELINE_PATH}")
        return

    with open(BASELINE_PATH) as f:
        baseline = json.load(f).get("dxf_baseline", {})

    exp_spaces = baseline.get("spaces_count", 106)
    exp_area = baseline.get("total_area", 997.29)

    # Upload & parse
    data, status, err = api_post(
        "/api/analyze_full",
        files={"cad_file": ("baseline.dxf", open(dxf_path, "rb"), "application/dxf")},
        data={"project_name": "RegressionTest_Baseline"},
        timeout=600,
    )

    if check(err is None, "Upload request succeeded"):
        check_eq(status, 200, "HTTP status")
        if data and data.get("data"):
            d = data["data"]
            actual_spaces = d.get("space_count") or len(d.get("spaces", []))
            actual_area = d.get("total_area", 0)

            spaces_ok = check_eq(safe_int(actual_spaces), safe_int(exp_spaces),
                                 f"space_count ({actual_spaces} vs expected {exp_spaces})")
            area_ok = check_approx(actual_area, exp_area, tolerance=0.1,
                                   label=f"total_area ({actual_area:.4f} vs expected {exp_area:.4f})")
            check_eq(data.get("task_status"), "idle", "task status returns to idle")
        else:
            check(False, f"No data in response: {data}")


def test_image_analyze():
    """4. 效果图识别: POST /api/analyze with an image → success, idle"""
    heading(4, "效果图识别 — POST /api/analyze")

    # 等待系统空闲（上一步DXF解析可能仍在跑）
    if not wait_for_idle(timeout=120):
        check(False, "System did not become idle within timeout")
        return

    # Find an image file
    img_files = [f for f in os.listdir(UPLOADS_DIR) if f.endswith("_img.jpg")]
    if not img_files:
        check(False, "No _img.jpg files found in uploads directory")
        return

    img_path = os.path.join(UPLOADS_DIR, img_files[0])
    data, status, err = api_post(
        "/api/analyze",
        files={"image_file": ("test.jpg", open(img_path, "rb"), "image/jpeg")},
        timeout=180,
    )

    if check(err is None, "Image upload request succeeded"):
        check_eq(status, 200, "HTTP status")
        check_eq(data.get("success"), True, "success=True")
        check_eq(data.get("task_status"), "idle", "task status back to idle")
        if data.get("data"):
            check(data["data"].get("image_result_id") is not None,
                  "image_result_id is present")


def test_drawings_list():
    """5. 图纸列表: GET /api/drawings → return list"""
    heading(5, "图纸列表 — GET /api/drawings")
    data, status, err = api_get("/api/drawings")
    if check(err is None, "Request succeeded"):
        check_eq(status, 200, "HTTP status")
        drawings = data.get("data", []) if data else []
        check(isinstance(drawings, list), f"data is a list (got {len(drawings)} items)")
        if drawings:
            check("id" in drawings[0], "first item has 'id' field")
            check("filename" in drawings[0], "first item has 'filename' field")


def test_data_merge():
    """6. 融合报价: POST /api/data_merge → verify returns result"""
    heading(6, "融合报价 — POST /api/data_merge")

    # Get the first completed drawing_id
    data, _, _ = api_get("/api/drawings")
    if not data:
        check(False, "Cannot get drawings list")
        return

    drawings = data.get("data", [])
    # Find a completed drawing (prefer the one we just uploaded)
    drawing_id = None
    for d in drawings:
        if d.get("parse_status") == "completed":
            drawing_id = d["id"]
            break

    if drawing_id is None:
        check(False, "No completed drawing found")
        return

    resp, status, err = api_post(
        "/api/data_merge",
        data={"cad_result_id": str(drawing_id), "image_result_ids": "[]"},
        timeout=120,
    )

    if check(err is None, "Data merge request succeeded"):
        check_eq(status, 200, "HTTP status")
        check_eq(resp.get("success"), True, "success=True")
        d = resp.get("data", {})
        check(d.get("quote_id") is not None, f"quote_id is present (got {d.get('quote_id')})")
        check(d.get("final_price") is not None, "final_price is present")
        check_eq(resp.get("task_status"), "idle", "task status returns to idle")


def test_export_excel():
    """7. Excel导出: POST /api/export_excel → verify file"""
    heading(7, "Excel导出 — POST /api/export_excel")

    # Get a quote_id from history
    data, _, _ = api_get("/api/history")
    if not data:
        check(False, "Cannot get history")
        return

    quotes = data.get("data", {}).get("quotes", {}).get("items", [])
    if not quotes:
        check(False, "No quotes found in history")
        return

    quote_id = quotes[0]["id"]

    resp, status, err = api_post(
        "/api/export_excel",
        data={"quote_id": str(quote_id)},
        timeout=60,
    )

    if check(err is None, "Export request succeeded"):
        check_eq(status, 200, "HTTP status")
        check_eq(resp.get("success"), True, "success=True")
        d = resp.get("data", {})
        check(d.get("filename") is not None, f"filename is present ({d.get('filename')})")
        check(d.get("export_path") is not None, "export_path is present")
        sheets = d.get("sheets", [])
        check(len(sheets) >= 3, f"at least 3 sheets in export (got {len(sheets)})")


def test_history():
    """8. 历史记录: GET /api/history → return list"""
    heading(8, "历史记录 — GET /api/history")
    data, status, err = api_get("/api/history")
    if check(err is None, "Request succeeded"):
        check_eq(status, 200, "HTTP status")
        quotes = data.get("data", {}).get("quotes", {}) if data else {}
        items = quotes.get("items", [])
        check(isinstance(items, list), f"quotes.items is a list (got {len(items)} items)")
        if items:
            check("id" in items[0], "first quote has 'id' field")
            check("final_price" in items[0], "first quote has 'final_price' field")


def test_logs():
    """9. 操作日志: GET /api/logs → return list"""
    heading(9, "操作日志 — GET /api/logs")
    data, status, err = api_get("/api/logs")
    if check(err is None, "Request succeeded"):
        check_eq(status, 200, "HTTP status")
        logs = data.get("data", {}).get("logs", {}) if data else {}
        items = logs.get("items", [])
        check(isinstance(items, list), f"logs.items is a list (got {len(items)} items)")
        if items:
            check("id" in items[0], "first log has 'id' field")
            check("task_type" in items[0], "first log has 'task_type' field")


def test_pricing_config():
    """10. 定价配置: GET /api/settings/pricing → return config"""
    heading(10, "定价配置 — GET /api/settings/pricing")
    data, status, err = api_get("/api/settings/pricing")
    if check(err is None, "Request succeeded"):
        check_eq(status, 200, "HTTP status")
        d = data.get("data", {}) if data else {}
        check("base_unit_price" in d, f"has base_unit_price ({d.get('base_unit_price')})")
        check("manage_fee_rate" in d, f"has manage_fee_rate ({d.get('manage_fee_rate')})")
        check("tax_rate" in d, f"has tax_rate ({d.get('tax_rate')})")
        check("loss_rate" in d, f"has loss_rate ({d.get('loss_rate')})")


def test_pricing_templates():
    """11. 报价模板: GET /api/pricing/templates → return list"""
    heading(11, "报价模板 — GET /api/pricing/templates")
    data, status, err = api_get("/api/pricing/templates")
    if check(err is None, "Request succeeded"):
        check_eq(status, 200, "HTTP status")
        templates = data.get("data", []) if data else []
        check(isinstance(templates, list), f"data is a list (got {len(templates)} items)")
        if templates:
            check("id" in templates[0], "first template has 'id' field")
            check("name" in templates[0], "first template has 'name' field")


def test_space_breakdown():
    """12. 分层明细: Use a drawing_id from /api/drawings → GET /api/spaces/{id}/breakdown"""
    heading(12, "分层明细 — GET /api/spaces/{drawing_id}/breakdown")

    data, _, _ = api_get("/api/drawings")
    if not data:
        check(False, "Cannot get drawings list")
        return

    drawings = data.get("data", [])
    drawing_id = None
    for d in drawings:
        if d.get("parse_status") == "completed" and d.get("cad_result_json") is not None:
            drawing_id = d["id"]
            break

    if drawing_id is None:
        check(False, "No completed drawing with CAD results found")
        return

    resp, status, err = api_get(f"/api/spaces/{drawing_id}/breakdown", timeout=30)

    if check(err is None, f"Breakdown request for drawing_id={drawing_id} succeeded"):
        check_eq(status, 200, "HTTP status")
        check_eq(resp.get("success"), True, "success=True")
        d = resp.get("data", {})
        check(d.get("space_count", 0) > 0, f"space_count > 0 (got {d.get('space_count')})")
        spaces = d.get("spaces", [])
        check(len(spaces) > 0, f"spaces list is non-empty (got {len(spaces)})")
        if spaces:
            check("id" in spaces[0], "first space has 'id' field")
            check("space_name" in spaces[0], "first space has 'space_name' field")
            check("area" in spaces[0], "first space has 'area' field")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    global passed, failed, failures, results_header

    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    # Parse optional test number filter
    test_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("-n") and len(arg) > 2:
            test_filter = int(arg[2:])
        elif arg == "-n" and len(sys.argv) > sys.argv.index(arg) + 1:
            idx = sys.argv.index(arg) + 1
            test_filter = int(sys.argv[idx])

    print(f"{'='*60}")
    print("  家装智能自动报价系统 — 综合回归测试套件")
    print(f"  服务器: {BASE_URL}")
    print(f"  Baseline: {BASELINE_PATH}")
    print(f"{'='*60}")

    # Test order (fast tests first, slow DXF at the end)
    tests = [
        ("健康检查", test_health_check),
        ("系统状态", test_system_status),
        ("效果图识别", test_image_analyze),
        ("图纸列表", test_drawings_list),
        ("融合报价", test_data_merge),
        ("Excel导出", test_export_excel),
        ("历史记录", test_history),
        ("操作日志", test_logs),
        ("定价配置", test_pricing_config),
        ("报价模板", test_pricing_templates),
        ("分层明细", test_space_breakdown),
        ("DXF解析基线", test_dxf_parse_baseline),
    ]

    # 确保系统空闲（锁死则自动重启）
    ensure_idle_or_reset(timeout=30)
    
    for i, (name, func) in enumerate(tests, start=1):
        if test_filter is not None and i != test_filter:
            continue
        try:
            func()
        except Exception as e:
            global failed, failures
            failed += 1
            failures.append(f"Test #{i} ({name}) raised exception: {e}")
            print(f"  ! EXCEPTION in test #{i} ({name}):")
            if verbose:
                traceback.print_exc()
            else:
                print(f"    {e}")
        finally:
            # Flush output
            sys.stdout.flush()

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  测试完成")

    if test_filter is not None:
        test_name = tests[test_filter - 1][0] if test_filter <= len(tests) else "?"
        print(f"  (仅运行测试 #{test_filter}: {test_name})")

    total = passed + failed
    print(f"  总计: {total}  通过: {passed}  失败: {failed}")
    if failures:
        print(f"\n  失败明细:")
        for f in failures:
            print(f"    • {f}")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

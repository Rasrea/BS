#!/usr/bin/env bash
# =============================================================================
# BuildSight Quality Gate — 提交前门禁检查
# 每次 git commit 前自动运行，所有检查通过才能提交
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
PASS=0
FAIL=0
ERRORS=()

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       BuildSight Quality Gate  V1.0             ║${NC}"
echo -e "${CYAN}║       提交前门禁检查 — 自动运行                  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────
check() {
    local name="$1"
    shift
    echo -n "  🔍 $name ... "
    if "$@" > /tmp/gate_$$.log 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}❌ FAIL${NC}"
        FAIL=$((FAIL + 1))
        ERRORS+=("$name")
        cat /tmp/gate_$$.log | sed 's/^/      /'
    fi
}

section() {
    echo ""
    echo -e "${YELLOW}━━━ $1 ━━━${NC}"
}

# ──────────────────────────────────────────────
# 阶段1：静态检查（不需要服务）
# ──────────────────────────────────────────────
section "阶段1：静态检查"

check "Python 语法检查" python3 -c "
import py_compile
files = ['backend/main.py', 'backend/pdf_parser.py', 'backend/cad_parser.py',
         'backend/db.py', 'backend/excel_export.py', 'backend/fusion_validator.py',
         'backend/image_recognizer.py', 'backend/quantity_estimator.py',
         'backend/deduct_rule.py', 'backend/image_preprocessor.py',
         'backend/space_synonyms.py']
all_ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f'  ✓ {f}')
    except py_compile.PyCompileError as e:
        print(f'  ✗ {f}: {e}')
        all_ok = False
exit(0 if all_ok else 1)
"
check "前端构建" bash -c "cd frontend && npm run build 2>/dev/null | tail -1 | grep -q 'built in'"

# ──────────────────────────────────────────────
# 阶段2：服务检查
# ──────────────────────────────────────────────
section "阶段2：服务可用性"

check "后端服务可达" curl -sf http://localhost:8100/api/system/health > /dev/null
check "LLaVA 模型在线" bash -c "curl -sf http://localhost:8100/api/system/health | python3 -c \"import sys,json; d=json.load(sys.stdin); exit(0 if d.get('data',{}).get('llava') else 1)\""
check "数据库连接正常" bash -c "curl -sf http://localhost:8100/api/system/health | python3 -c \"import sys,json; d=json.load(sys.stdin); exit(0 if d.get('data',{}).get('db') else 1)\""

# ──────────────────────────────────────────────
# 阶段3：门禁状态检查
# ──────────────────────────────────────────────
section "阶段3：系统状态门禁"

check "系统处于空闲状态" bash -c "curl -sf http://localhost:8100/api/system/status | python3 -c \"import sys,json; d=json.load(sys.stdin); s=d.get('data',{}).get('task_state',''); exit(0 if s=='idle' else 1)\""

# ──────────────────────────────────────────────
# 阶段4：回归测试
# ──────────────────────────────────────────────
section "阶段4：回归测试"

check "回归测试集 (62项)" python3 scripts/regression_test.py

# ──────────────────────────────────────────────
# 阶段5：接口契约检查
# ──────────────────────────────────────────────
section "阶段5：接口契约完整性"

check "API_CONTRACT.md 存在" test -f scripts/API_CONTRACT.md
check "baseline.json 存在" test -f scripts/baseline.json

# ──────────────────────────────────────────────
# 汇总
# ──────────────────────────────────────────────
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}  ✅ 全部 ${PASS} 项检查通过，可以提交！${NC}"
    exit 0
else
    echo -e "${RED}  ❌ ${FAIL} 项检查失败，请修复后重试：${NC}"
    for e in "${ERRORS[@]}"; do
        echo -e "${RED}     - $e${NC}"
    done
    echo -e "${YELLOW}  提示：查看 /tmp/gate_*.log 获取详细错误信息${NC}"
    exit 1
fi

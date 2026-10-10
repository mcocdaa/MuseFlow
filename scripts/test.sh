#!/usr/bin/env bash
# MuseFlow 自动化测试与质量巡检脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "  🧪 MuseFlow (灵眸流) — 自动化测试与质量巡检"
echo "=================================================="

# 1. 后端单元测试
echo "[1/2] 正在运行后端单元测试 (pytest)..."
cd "$PROJECT_ROOT/backend"
if command -v uv >/dev/null 2>&1; then
    uv run pytest tests/ -v
else
    pytest tests/ -v
fi

# 2. 前端构建校验
echo "[2/2] 正在校验前端构建完整性 (pnpm build)..."
cd "$PROJECT_ROOT/frontend"
pnpm build

echo "=================================================="
echo "✓ 全部测试与构建校验通过！"
echo "=================================================="

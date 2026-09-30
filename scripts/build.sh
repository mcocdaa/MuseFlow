#!/usr/bin/env bash
# MuseFlow 生产环境构建脚本
# 编译前端静态产物并验证后端环境
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "  📦 MuseFlow (灵眸流) — 生产环境构建中..."
echo "=================================================="

# 1. 构建前端
echo "[1/2] 正在编译前端 Vue 3 + Tailwind CSS v4 产物..."
cd "$PROJECT_ROOT/frontend"
pnpm install --frozen-lockfile || pnpm install
pnpm build

if [[ -f "$PROJECT_ROOT/frontend/dist/index.html" ]]; then
    echo "✓ 前端产物编译成功 -> frontend/dist/"
else
    echo "✗ 前端编译失败，未找到 dist/index.html"
    exit 1
fi

# 2. 检查后端
echo "[2/2] 正在自检后端环境与依赖..."
cd "$PROJECT_ROOT/backend"
if command -v uv >/dev/null 2>&1; then
    uv sync
fi

echo "=================================================="
echo "✓ 构建完成！运行 ./scripts/start.sh 即可直接以单端口运行完整服务。"
echo "=================================================="

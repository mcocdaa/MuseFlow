#!/usr/bin/env bash
# MuseFlow (灵眸流) 本地联动开发启动脚本
# 同时启动后端 FastAPI (:8765) 与前端 Vite 热重载 (:5173)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "  🌊 MuseFlow (灵眸流) — 开发环境启动中..."
echo "=================================================="

# 检查 .env 配置文件
if [[ ! -f "$PROJECT_ROOT/.env" ]] && [[ -f "$PROJECT_ROOT/.env.example" ]]; then
    echo "[info] 未检测到 .env，自动从 .env.example 复制默认配置..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

# 检查后端虚拟环境与依赖
cd "$PROJECT_ROOT/backend"
if command -v uv >/dev/null 2>&1; then
    echo "[backend] 同步 Python 依赖 (uv)..."
    uv sync
else
    echo "[warning] 未找到 uv，建议安装 uv: curl -LsSf https://astral.sh/uv/install.sh"
fi

# 检查前端依赖
cd "$PROJECT_ROOT/frontend"
if [[ ! -d "node_modules" ]]; then
    echo "[frontend] 安装前端依赖 (pnpm)..."
    pnpm install
fi

echo "--------------------------------------------------"
echo "后端地址: http://127.0.0.1:8765"
echo "前端地址: http://127.0.0.1:5173"
echo "API 文档: http://127.0.0.1:8765/docs"
echo "按下 Ctrl+C 可同时停止前后端服务"
echo "--------------------------------------------------"

# 捕获退出信号以同时终止子进程
cleanup() {
    echo ""
    echo "[shutdown] 正在停止开发服务..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 启动后端
cd "$PROJECT_ROOT/backend"
if command -v uv >/dev/null 2>&1; then
    uv run python run.py &
else
    python3 run.py &
fi
BACKEND_PID=$!

# 启动前端
cd "$PROJECT_ROOT/frontend"
pnpm dev &
FRONTEND_PID=$!

wait

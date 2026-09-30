#!/usr/bin/env bash
# MuseFlow 生产环境一键启动脚本
# 用法:
#   ./scripts/start.sh          # 本地生产模式（单端口 8765 托管 API + 前端 Dist）
#   ./scripts/start.sh docker   # Docker Compose 容器编排启动
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

MODE="${1:-local}"

if [[ "$MODE" == "docker" ]]; then
    echo "=================================================="
    echo "  🐳 MuseFlow (灵眸流) — Docker 容器启动"
    echo "=================================================="
    docker compose -f "$PROJECT_ROOT/compose.yaml" up -d --build
    echo "✓ MuseFlow 容器已在后台运行！"
    echo "访问入口: http://localhost:8765"
    exit 0
fi

echo "=================================================="
echo "  🚀 MuseFlow (灵眸流) — 本地生产服务启动"
echo "=================================================="

# 确保前端 dist 已构建
if [[ ! -d "$PROJECT_ROOT/frontend/dist" ]]; then
    echo "[info] 未检测到前端产物，正在执行生产构建..."
    "$SCRIPT_DIR/build.sh"
fi

cd "$PROJECT_ROOT/backend"
echo "正在启动单端口全功能服务: http://0.0.0.0:8765"
if command -v uv >/dev/null 2>&1; then
    exec uv run python run.py
else
    exec python3 run.py
fi

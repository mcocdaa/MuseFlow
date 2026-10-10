#!/usr/bin/env bash
# ==============================================================================
# MuseFlow (灵眸流) — WSL 网络存储/驱动器一键永久自动挂载通用脚本
# 用法:
#   ./scripts/setup_nas_automount.sh <盘符 (如 X, Y, Z)> [挂载点]
# 示例:
#   ./scripts/setup_nas_automount.sh Y /mnt/nas
#   ./scripts/setup_nas_automount.sh X /mnt/media
# ==============================================================================
set -e

if [ -z "${1:-}" ] && [ -z "${MUSEFLOW_DRIVE_LETTER:-}" ]; then
    echo "❌ 错误: 未指定 Windows 驱动器盘符！"
    echo "用法: $0 <盘符 (如 X, Y, Z)> [挂载点 (默认: /mnt/<盘符小写>)]"
    echo "示例: $0 Y /mnt/nas"
    exit 1
fi

DRIVE_INPUT="${1:-$MUSEFLOW_DRIVE_LETTER}"
# 移除末尾冒号（如 Y: -> Y）
DRIVE_LETTER="${DRIVE_INPUT%:}"
DRIVE_LOWER="$(echo "$DRIVE_LETTER" | tr '[:upper:]' '[:lower:]')"
MOUNT_POINT="${2:-${MUSEFLOW_NAS_MOUNT:-/mnt/${DRIVE_LOWER}}}"

echo "🌊 [MuseFlow] 配置 WSL 永久自动挂载 Windows ${DRIVE_LETTER}: 盘 -> ${MOUNT_POINT} ..."

# 1. 确保挂载点目录存在
sudo mkdir -p "${MOUNT_POINT}"
sudo chown "$(id -u):$(id -g)" "${MOUNT_POINT}"

# 2. 写入 /etc/fstab（若已存在同挂载点配置则更新）
FSTAB_LINE="${DRIVE_LETTER}: ${MOUNT_POINT} drvfs defaults,uid=$(id -u),gid=$(id -g),users 0 0"

if grep -q " ${MOUNT_POINT} " /etc/fstab 2>/dev/null; then
    echo "ℹ️  /etc/fstab 已存在 ${MOUNT_POINT} 挂载规则，正在更新参数..."
    sudo sed -i "\| ${MOUNT_POINT} |d" /etc/fstab
fi

echo "$FSTAB_LINE" | sudo tee -a /etc/fstab > /dev/null
echo "✅ /etc/fstab 自动挂载规则配置完成！"

# 3. 立即执行挂载
echo "🚀 正在挂载 ${MOUNT_POINT} ..."
sudo mount "${MOUNT_POINT}" 2>/dev/null || sudo mount -t drvfs "${DRIVE_LETTER}:" "${MOUNT_POINT}" -o "uid=$(id -u),gid=$(id -g)"

# 4. 验证挂载结果
if [ -d "${MOUNT_POINT}" ] && [ "$(ls -A "${MOUNT_POINT}" 2>/dev/null)" ]; then
    echo "🎉 挂载成功！${MOUNT_POINT} 内容预览："
    ls -la "${MOUNT_POINT}" | head -n 10
    echo ""
    echo "✨ 以后每次 WSL 启动时都将自动挂载，无需重复执行。"
else
    echo "⚠️  挂载命令已执行，但 ${MOUNT_POINT} 目录为空。"
    echo "💡 请确认 Windows 宿主机中已成功连接 ${DRIVE_LETTER}: 盘。"
fi

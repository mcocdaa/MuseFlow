"""
MuseFlow (灵眸流) — 全库数据清空与重新全量采集脚本
运行方式：
    cd backend && uv run python reindex_library.py [--sync-only]
"""

import sys
import time
import argparse
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.db import engine, init_db
from sqlmodel import Session, select
from app.models.entities import AssetUnit, AssetFile, Collection
from app.services.sync_engine import check_mount_status, wipe_and_rebuild_all, sync_library_changes

def main():
    parser = argparse.ArgumentParser(description="MuseFlow 全库数据清空重扫与增量同步工具")
    parser.add_argument("--sync-only", action="store_true", help="仅增量同步变更，不清空旧数据")
    parser.add_argument("--path", type=str, default=None, help="自定义扫描根目录，默认检测环境变量 MUSEFLOW_MEDIA_ROOTS 或挂载点")
    args = parser.parse_args()

    print("=" * 65)
    print("  MuseFlow (灵眸流) — 媒体库数据重构与同步引擎")
    print("=" * 65)

    mount_info = check_mount_status()
    mp = mount_info.get("mount_point", "/mnt/media")
    print(f"[*] 挂载点检测: {mp}")
    print(f"[*] 挂载状态: {'已就绪 (Mounted)' if mount_info['is_mounted'] else '未挂载 (Unmounted)'}")
    print(f"[*] 有效扫描根目录: {mount_info['valid_roots']}")

    if not mount_info["is_mounted"] and not args.path:
        print(f"\n❌ 错误: 挂载点 {mp} 当前未就绪或未找到有效扫描目录！")
        print("💡 请先在终端执行挂载（或在 .env 中设置 MUSEFLOW_MEDIA_ROOTS / MUSEFLOW_NAS_MOUNT）：")
        print(f"    sudo mount -t drvfs <Windows盘符>: {mp} -o uid=$(id -u),gid=$(id -g)")
        print("💡 若使用 WSL 自动挂载脚本，可运行：")
        print("    ./scripts/setup_nas_automount.sh <Windows盘符> <挂载点路径>\n")
        sys.exit(1)

    init_db()
    with Session(engine) as session:
        roots = [args.path] if args.path else mount_info["valid_roots"]

        if args.sync_only:
            print(f"\n🔄 正在执行增量同步变更 (Pruning + Adding)...")
            res = sync_library_changes(session, root_paths=roots, prune_missing=True)
        else:
            print(f"\n🧹 正在清空旧数据并重新全量扫描与反向打标构建...")
            res = wipe_and_rebuild_all(session, root_paths=roots)

        print("\n" + "=" * 65)
        if res.get("status") == "success":
            print("🎉 任务执行成功！")
            if "wiped" in res:
                print(f"  • 清空旧数据: {res['wiped']}")
            print(f"  • 新增单元: +{res.get('added_units', 0)}")
            print(f"  • 新增文件: +{res.get('added_files', 0)}")
            print(f"  • 清理孤儿文件: -{res.get('pruned_files', 0)}")
            print(f"  • 清理孤儿单元: -{res.get('pruned_units', 0)}")
            print(f"  • 清理空合集: -{res.get('pruned_collections', 0)}")
            print(f"  • 系列合并归纳: {res.get('merged_collections', 0)} 个")
            print(f"  • 自动打标统计: {res.get('tag_counts', {})}")
            print(f"  • 总耗时: {res.get('elapsed_seconds', 0)} 秒")

            u_cnt = len(session.exec(select(AssetUnit)).all())
            f_cnt = len(session.exec(select(AssetFile)).all())
            c_cnt = len(session.exec(select(Collection)).all())
            print(f"\n📊 数据库当前全量状态: {u_cnt} 单元, {f_cnt} 文件, {c_cnt} 系列集合")
        else:
            print(f"❌ 任务失败: {res.get('message')}")
        print("=" * 65)

if __name__ == "__main__":
    main()

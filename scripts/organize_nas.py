#!/usr/bin/env python3
"""
MuseFlow (灵眸流) — 独立物理 NAS 整理与投影流水线 CLI 终端工具 (Headless NAS Projection CLI)

用途：
- 无需打开浏览器前端，直接在终端中通过命令行参数或外部规则对 NAS 目录进行投影重组与清洗。
- 支持 Dry-run 三色风险体检（安全/超长警告/重名碰撞）。
- 支持外部 rules.json 规则驱动与多级 Pipeline 编排。

用法示例：
  # 1. 干跑预览（默认安全模式，不移动任何物理文件）
  python scripts/organize_nas.py --folder /mnt/media/Audio --preset category_standard --dry-run

  # 2. 指定自定义用户规则并执行实际物理重组
  python scripts/organize_nas.py --folder /mnt/media/Audio --preset category_standard --rules backend/rules.example.json --execute
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlmodel import Session, select
from app.core.db import engine, init_db
from app.models.entities import AssetUnit, Collection
from app.services.projection_dsl import (
    PipelineConfig,
    LevelOperator,
    generate_pipeline_projection_plan,
)
from app.services.physical_organizer import PhysicalTriagePlan, execute_triage_plan
from app.core.user_rules import load_user_rules, UserRules
from app.api.organize import get_pipeline_presets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("museflow.cli.organize")


def parse_args():
    parser = argparse.ArgumentParser(description="MuseFlow Headless NAS Projection & Organization Tool")
    parser.add_argument("--folder", type=str, help="目标物理文件夹路径 (Target physical folder)")
    parser.add_argument("--collection-id", type=int, help="目标合集 ID (Target collection ID in database)")
    parser.add_argument("--preset", type=str, default="category_standard",
                        choices=["category_standard", "creator_first", "media_kind_clean"],
                        help="预设整理流水线模板 (Default: category_standard)")
    parser.add_argument("--pipeline-file", type=str, help="自定义流水线 JSON 文件路径")
    parser.add_argument("--rules", type=str, help="用户专属规则 JSON 配置文件路径 (如 user_rules.json)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="仅模拟推演与风险诊断，不修改物理文件 (默认开启)")
    parser.add_argument("--execute", action="store_true", help="确认执行物理文件移动与数据库路径自愈 (Dangerous!)")
    return parser.parse_args()


def main():
    args = parse_args()
    init_db()

    if args.execute:
        args.dry_run = False

    # 1. 加载用户专属规则
    if args.rules:
        os.environ["MUSEFLOW_USER_RULES"] = str(Path(args.rules).resolve())
        rules = load_user_rules(force_reload=True)
        print(f"[Rules] 已载入外部规则配置: {args.rules} (别名: {len(rules.creator_aliases)}, 剥离后缀: {len(rules.strip_suffixes)})")

    # 2. 确定流水线配置
    pipeline_config = None
    if args.pipeline_file:
        with open(args.pipeline_file, "r", encoding="utf-8") as f:
            pipeline_config = PipelineConfig(**json.load(f))
    else:
        presets = get_pipeline_presets()
        target_preset = next((p for p in presets if p["id"] == args.preset), presets[0])
        print(f"[Pipeline] 使用预设模板: {target_preset['name']} - {target_preset['description']}")
        pipeline_config = PipelineConfig(
            name=target_preset["name"],
            target_root=args.folder or "/media/organized",
            levels=[LevelOperator(**lvl) for lvl in target_preset["levels"]]
        )

    # 3. 查询目标资产单元
    with Session(engine) as session:
        units_query = select(AssetUnit)
        if args.collection_id:
            units_query = units_query.where(AssetUnit.collection_id == args.collection_id)
        elif args.folder:
            col = session.exec(select(Collection).where(Collection.folder_path == args.folder)).first()
            if col:
                units_query = units_query.where(AssetUnit.collection_id == col.id)

        units = session.exec(units_query).all()
        total_units = len(units)
        print(f"[Dataset] 检索到目标资产单元: {total_units} 个")
        if total_units == 0:
            print("[Info] 没有检索到符合条件的资产单元，退出。")
            return

        # 4. 执行 AST 试运行求值 (Dry-run Plan Generation)
        print("[AST Evaluation] 正在内存中推演投影路径与三色风险体检...")
        plan_dict = generate_pipeline_projection_plan(session, units, pipeline_config)
        actions = plan_dict.get("actions", [])

        # 统计风险指标
        safe_count = sum(1 for a in actions if a["risk_level"] == "safe")
        warning_count = sum(1 for a in actions if a["risk_level"] == "warning")
        danger_count = sum(1 for a in actions if a["risk_level"] == "danger")

        print("\n" + "=" * 80)
        print(f"📊 投影体检报告 (Evaluation Report):")
        print(f"   - 总计划操作数: {plan_dict['total_actions']}")
        print(f"   - 🟢 安全操作 (Safe): {safe_count}")
        print(f"   - 🟡 告警提示 (Warning, 超长/跨盘): {warning_count}")
        print(f"   - 🔴 冲突阻断 (Danger, 目标碰撞): {danger_count}")
        print("=" * 80 + "\n")

        # 打印前 10 条样本预览
        print("📋 样例移动预览 (Sample Actions):")
        for i, act in enumerate(actions[:8], 1):
            src_name = Path(act["src_path"]).name
            dst_rel = act["dst_path"].replace(pipeline_config.target_root, "").lstrip("/\\")
            tag_icon = "🟢" if act["risk_level"] == "safe" else ("🟡" if act["risk_level"] == "warning" else "🔴")
            print(f"  {tag_icon} [{i}] {src_name}")
            print(f"      ➔ {dst_rel}")
            if act.get("risk_messages"):
                print(f"      ⚠️  {'; '.join(act['risk_messages'])}")

        if len(actions) > 8:
            print(f"  ... 以及其他 {len(actions) - 8} 项操作\n")

        # 5. 执行物理移动
        if args.dry_run:
            print("💡 当前为【Dry-run 模拟模式】，物理磁盘未做任何修改。")
            print("👉 若确认无误并执行整理，请在命令末尾添加 --execute 参数重新运行。")
            return

        if danger_count > 0:
            print(f"❌ 检测到 {danger_count} 项命名碰撞或目标冲突！为确保物理文件安全，拒绝执行。请先调整命名模板。")
            return

        print(f"🚀 开始执行物理文件移动与数据库路径自愈 (共 {len(actions)} 项)...")
        plan_obj = PhysicalTriagePlan.from_dict(plan_dict)
        exec_res = execute_triage_plan(session, plan_obj, dry_run=False)
        print("\n" + "=" * 80)
        print("🎉 物理整理执行完成 (Execution Succeeded)!")
        print(f"   - 成功执行操作数: {exec_res.get('actions_executed', 0)}")
        print(f"   - 物理失败: {exec_res.get('actions_failed', 0)}")
        print("=" * 80)


if __name__ == "__main__":
    main()

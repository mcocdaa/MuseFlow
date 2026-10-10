import json
import pytest
from pathlib import Path
from sqlmodel import Session, select

from app.core.db import engine, init_db
from app.core.user_rules import UserRules, apply_creator_cleaning, load_user_rules
from app.models.entities import AssetUnit, Tag, TagClass, AssetUnitTagLink
from app.services.reverse_tagger import infer_and_assign_tags_from_path, cleanup_dirty_tags, get_or_create_tag_fast

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

def test_user_rules_cleaning_logic():
    rules = UserRules(
        creator_aliases={"张导工作室": "张导", "李老师频道": "李老师"},
        strip_suffixes=["老师", "工作室", "Official"],
        slang_filter=["测试过滤A", "测试过滤B"],
        domain_mapping={"特殊音频": "有声剧"},
        ignore_segments=["暂存区"]
    )

    # 1. 验证别名精确匹配
    assert apply_creator_cleaning("张导工作室", rules) == "张导"
    assert apply_creator_cleaning("李老师频道", rules) == "李老师"

    # 2. 验证动态后缀剥离
    assert apply_creator_cleaning("新讲师老师", rules) == "新讲师"
    assert apply_creator_cleaning("制作组Official", rules) == "制作组"

    # 3. 验证无后缀者不被篡改
    assert apply_creator_cleaning("正常创作者", rules) == "正常创作者"

def test_user_rules_tagger_integration(tmp_path):
    # 模拟用户自定义配置文件
    rule_file = tmp_path / "user_rules.json"
    rule_content = {
        "creator_aliases": {"特例作者酱": "特例作者"},
        "strip_suffixes": ["老师", "工作室"],
        "slang_filter": ["临时标签"],
        "domain_mapping": {"科幻漫步": "宇宙天文"},
        "ignore_segments": ["忽略目录"]
    }
    with open(rule_file, "w", encoding="utf-8") as f:
        json.dump(rule_content, f)

    user_rules = UserRules(**rule_content)

    with Session(engine) as session:
        classes = session.exec(select(TagClass)).all()
        class_map = {c.code: c.id for c in classes}
        tag_by_norm = {t.normalized_name: t for t in session.exec(select(Tag)).all()}

        unit = AssetUnit(title="[特例作者酱] 宇宙起源 01", unit_type="audio")
        session.add(unit)
        session.commit()
        session.refresh(unit)

        sample_path = "/media/忽略目录/科幻漫步/[特例作者酱] 宇宙起源 01/track.mp3"
        assigned = infer_and_assign_tags_from_path(
            session=session,
            unit=unit,
            file_path_str=sample_path,
            user_rules=user_rules,
            tag_by_norm=tag_by_norm,
            class_map=class_map,
        )

        names = {a["name"] for a in assigned}
        # 验证别名生效：特例作者酱 -> 特例作者
        assert "特例作者" in names
        assert "特例作者酱" not in names

        # 验证题材映射生效：科幻漫步 -> 宇宙天文
        assert "宇宙天文" in names

        # 验证忽略目录未被打标
        assert "忽略目录" not in names

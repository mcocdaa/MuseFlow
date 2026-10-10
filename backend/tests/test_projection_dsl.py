import pytest
from pathlib import Path
from sqlmodel import Session, select

from app.core.db import engine, init_db
from app.models.entities import AssetFile, AssetUnit, TagClass, Tag
from app.services.path_sanitizer import (
    sanitize_path_segment,
    check_path_length_budget,
    WINDOWS_RESERVED_NAMES,
)
from app.services.projection_dsl import (
    PipelineConfig,
    LevelOperator,
    build_adaptive_disambiguation_map,
    calculate_unit_landing_path,
    generate_pipeline_projection_plan,
)
from app.services.tag_service import assign_tag_to_unit, create_tag

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

def test_path_sanitizer_special_characters():
    # 1. 常见 Windows 非法字符转换
    raw = '作品: "测试" <超清> | 独家? *精品*'
    clean = sanitize_path_segment(raw)
    assert ':' not in clean
    assert '?' not in clean
    assert '*' not in clean
    assert '"' not in clean
    assert '<' not in clean
    assert '>' not in clean
    assert '|' not in clean
    assert "作品：" in clean
    assert "''测试''" in clean

def test_path_sanitizer_dos_reserved_names():
    # 2. DOS 保留设备名规避
    for r_name in ["CON", "con", "AUX", "aux.mp4", "NUL", "prn"]:
        clean = sanitize_path_segment(r_name)
        assert clean.startswith("_")

def test_path_sanitizer_trailing_dots_and_spaces():
    # 3. 剥除末尾非法空格与点
    raw = "我的文件夹...   "
    clean = sanitize_path_segment(raw)
    assert not clean.endswith(" ")
    assert not clean.endswith(".")
    assert clean == "我的文件夹"

def test_path_sanitizer_budget_truncation_with_hash():
    # 4. 超长名称预算截断并追加哈希
    long_name = "超长二次元音乐作品标题" * 15 # > 150 字符
    clean = sanitize_path_segment(long_name, max_length=50)
    assert len(clean) <= 50
    assert "_" in clean
    # 相同名称生成相同哈希
    clean2 = sanitize_path_segment(long_name, max_length=50)
    assert clean == clean2

def test_adaptive_disambiguation_unique_vs_collision():
    with Session(engine) as session:
        # 1. 唯一作品
        u_solo = AssetUnit(title="独一无二的作品", unit_type="audio")
        # 2. 两个重名作品
        u_dup1 = AssetUnit(title="重名同人音声", unit_type="audio", dynamic_attributes={"rj_code": "RJ111111"})
        u_dup2 = AssetUnit(title="重名同人音声", unit_type="audio", dynamic_attributes={"rj_code": "RJ222222"})
        
        session.add(u_solo)
        session.add(u_dup1)
        session.add(u_dup2)
        session.commit()
        session.refresh(u_solo)
        session.refresh(u_dup1)
        session.refresh(u_dup2)

        disambig_map = build_adaptive_disambiguation_map(session, [u_solo, u_dup1, u_dup2])

        # 唯一作品后缀必须为空（保持纯净自然目录名）
        assert disambig_map[u_solo.id] == ""

        # 重名作品必须自适应展开消歧标识
        assert disambig_map[u_dup1.id] == " [RJ111111]"
        assert disambig_map[u_dup2.id] == " [RJ222222]"

def test_customizable_pipeline_dsl_evaluation():
    with Session(engine) as session:
        domain_cls = session.exec(select(TagClass).where(TagClass.code == "domain")).first()
        creator_cls = session.exec(select(TagClass).where(TagClass.code == "creator")).first()

        tag_genre = create_tag(session, "催眠", domain_cls.id)
        tag_circle = create_tag(session, "示例工作室", creator_cls.id)

        unit = AssetUnit(
            title="星空下的奇幻冒险",
            unit_type="bundle",
            primary_class="VoiceDrama",
            dynamic_attributes={"rj_code": "RJ999999", "has_translation": False}
        )
        session.add(unit)
        session.commit()
        session.refresh(unit)

        assign_tag_to_unit(session, unit.id, tag_genre.id, is_primary_landing=True)
        assign_tag_to_unit(session, unit.id, tag_circle.id, is_primary_landing=True)

        # 构建完全自定义排序的管线:
        # 用户自定义: 先按创作者 (Level 0) -> 再按题材 (Level 1) -> 汉化分流 (Level 2) -> 叶子规范名
        pipeline = PipelineConfig(
            name="创作者优先管线",
            target_root="/media/test_root",
            levels=[
                LevelOperator(level_index=0, facet="tag.creator", fallback="未知社团"),
                LevelOperator(level_index=1, facet="tag.domain", fallback="未分类题材"),
                LevelOperator(
                    level_index=2,
                    condition="not unit['has_translation']",
                    folder_name="待翻译",
                    fallback=None
                ),
                LevelOperator(
                    level_index=3,
                    naming="[{meta.rj_code}] {unit.title}%unique{}"
                )
            ]
        )

        segments, leaf = calculate_unit_landing_path(session, unit, pipeline, "")
        
        # 验证层级顺序与生成结果
        assert segments == ["示例工作室", "催眠", "待翻译"]
        assert leaf == "[RJ999999] 星空下的奇幻冒险"

def test_generate_projection_plan_with_risk_diagnostics(tmp_path):
    with Session(engine) as session:
        domain_cls = session.exec(select(TagClass).where(TagClass.code == "domain")).first()
        tag_sleep = create_tag(session, "助眠", domain_cls.id)

        unit = AssetUnit(title="安眠之夜", unit_type="bundle")
        session.add(unit)
        session.commit()
        session.refresh(unit)

        # 为该单元创建虚拟文件
        f1 = AssetFile(
            file_path=str(tmp_path / "old_dir" / "track.wav"),
            file_name="track.wav",
            extension=".wav",
            mime_type="audio/wav",
            file_size=1024,
            modified_at=unit.created_at,
            asset_unit_id=unit.id,
            role="primary"
        )
        session.add(f1)
        session.commit()

        assign_tag_to_unit(session, unit.id, tag_sleep.id, is_primary_landing=True)

        pipeline = PipelineConfig(
            name="助眠管线",
            target_root=str(tmp_path / "organized"),
            levels=[
                LevelOperator(level_index=0, facet="tag.domain", fallback="其他"),
                LevelOperator(level_index=1, naming="{unit.title}")
            ]
        )

        plan = generate_pipeline_projection_plan(session, [unit], pipeline)
        
        assert plan["total_actions"] == 1
        action = plan["actions"][0]
        assert action["risk_level"] == "safe"
        assert "organized/助眠/安眠之夜/track.wav" in action["dst_path"].replace("\\", "/")

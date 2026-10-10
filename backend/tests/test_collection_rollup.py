import pytest
from sqlmodel import Session, select
from app.core.db import engine, init_db
from app.models.entities import Collection, AssetUnit
from app.services.collection_rollup import (
    is_accessory_collection_name,
    find_canonical_work_collection,
    rollup_all_split_works,
    WORK_CODE_REGEX,
    DISC_REGEX,
)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

def test_accessory_and_disc_regex():
    assert is_accessory_collection_name("img") is True
    assert is_accessory_collection_name("イラスト") is True
    assert is_accessory_collection_name("特典") is True
    assert is_accessory_collection_name("01通常版") is True
    assert is_accessory_collection_name("音频数据") is True
    assert is_accessory_collection_name("正篇") is True
    assert bool(DISC_REGEX.search("Disc 1")) is True
    assert bool(DISC_REGEX.search("CD 2")) is True
    assert is_accessory_collection_name("独立交响乐专辑") is False

def test_rollup_split_work_collections():
    with Session(engine) as session:
        # Create canonical parent coded collection
        work_col = Collection(
            name="[AB999999] 测试作品全集",
            folder_path="/mnt/media/library/[AB999999] 测试作品全集"
        )
        session.add(work_col)
        session.commit()
        session.refresh(work_col)

        # Create split sub-collections
        sub_audio = Collection(
            name="01 本篇音频",
            folder_path=f"{work_col.folder_path}/01 本篇音频",
            parent_id=work_col.id
        )
        sub_img = Collection(
            name="img",
            folder_path=f"{work_col.folder_path}/img",
            parent_id=work_col.id
        )
        sub_bonus = Collection(
            name="特典/手机壁纸",
            folder_path=f"{work_col.folder_path}/特典/手机壁纸",
            parent_id=work_col.id
        )
        session.add_all([sub_audio, sub_img, sub_bonus])
        session.commit()
        session.refresh(sub_audio)
        session.refresh(sub_img)
        session.refresh(sub_bonus)

        # Create asset units under sub-collections
        u1 = AssetUnit(title="Track 1", unit_type="audio", collection_id=sub_audio.id)
        u2 = AssetUnit(title="Cover Art", unit_type="image", collection_id=sub_img.id)
        u3 = AssetUnit(title="Bonus Wallpaper", unit_type="image", collection_id=sub_bonus.id)
        session.add_all([u1, u2, u3])
        session.commit()

        # Run rollup
        res = rollup_all_split_works(session)
        assert res["rolled_up_collections"] >= 3
        assert res["consolidated_units"] >= 3

        # Verify units now belong to the canonical parent
        for uid in [u1.id, u2.id, u3.id]:
            refreshed_u = session.get(AssetUnit, uid)
            assert refreshed_u.collection_id == work_col.id
            assert refreshed_u.dynamic_attributes.get("is_subfolder_item") is True
            assert "sub_folder" in refreshed_u.dynamic_attributes

        # Verify child collections were pruned
        assert session.get(Collection, sub_audio.id) is None
        assert session.get(Collection, sub_img.id) is None
        assert session.get(Collection, sub_bonus.id) is None


def test_multipart_series_extraction_and_grouping():
    from app.services.collection_rollup import (
        extract_group_key_and_title,
        group_multipart_works_in_buckets,
    )

    # 1. 验证标题分集提取正则
    g1, s1 = extract_group_key_and_title("A-06.1 宇宙探索系列 太阳系漫游·第1日")
    assert g1 == "A-06"
    assert "太阳系漫游" in s1

    g2, s2 = extract_group_key_and_title("科学漫步专栏（2）黑洞奥秘")
    assert g2 == "科学漫步专栏"
    assert s2 == "科学漫步专栏"

    g3, s3 = extract_group_key_and_title("现代建筑史演进上篇")
    assert g3 == "现代建筑史演进"

    g4, s4 = extract_group_key_and_title("纪录片天地（3）")
    assert g4 == "纪录片天地"

    g5, s5 = extract_group_key_and_title("技术前沿-2")
    assert g5 == "技术前沿"

    # 2. 验证多篇目自动建系列并重锚封面
    with Session(engine) as session:
        bucket_col = Collection(
            name="测试创作者大合集",
            folder_path="/mnt/media/library/测试创作者大合集"
        )
        session.add(bucket_col)
        session.commit()
        session.refresh(bucket_col)

        # 初始放入两个分集单元和一个独立单元
        ep1 = AssetUnit(title="多情女秘书（上）", unit_type="audio", collection_id=bucket_col.id)
        ep2 = AssetUnit(title="多情女秘书（下）", unit_type="audio", collection_id=bucket_col.id)
        standalone = AssetUnit(title="纯独家单曲", unit_type="audio", collection_id=bucket_col.id)
        session.add_all([ep1, ep2, standalone])
        session.commit()
        session.refresh(ep1)
        session.refresh(ep2)
        session.refresh(standalone)

        # 初始将父大桶封面设在 ep1 上
        bucket_col.cover_asset_id = ep1.id
        session.add(bucket_col)
        session.commit()

        # 执行智能聚类与重拢
        res = group_multipart_works_in_buckets(session)
        assert res["created_series_count"] >= 1
        assert res["grouped_units_count"] >= 2

        # 验证新建的系列集合
        sub_series = session.exec(
            select(Collection).where(Collection.parent_id == bucket_col.id, Collection.name == "多情女秘书")
        ).first()
        assert sub_series is not None
        assert sub_series.cover_asset_id in [ep1.id, ep2.id]

        # 验证分集单元归属已迁移至子系列
        session.refresh(ep1)
        session.refresh(ep2)
        session.refresh(standalone)
        assert ep1.collection_id == sub_series.id
        assert ep2.collection_id == sub_series.id
        assert ep1.dynamic_attributes.get("is_series_episode") is True
        assert standalone.collection_id == bucket_col.id

        # 验证父级集合封面已被重新自愈锚定到剩余的 direct unit
        session.refresh(bucket_col)
        assert bucket_col.cover_asset_id == standalone.id


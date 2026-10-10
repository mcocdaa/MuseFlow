import pytest
from app.mcp.server import (
    get_library_stats,
    check_database_health,
    search_assets,
    get_asset_details,
    list_collections,
    get_taxonomy_tree,
    organize_tag_column,
    analyze_collection_topology,
    batch_assign_tags,
)


def test_mcp_get_library_stats():
    stats = get_library_stats()
    assert "total_asset_units" in stats
    assert "total_asset_files" in stats
    assert "status" in stats
    assert stats["primary_invariant_violations"] == 0


def test_mcp_check_database_health():
    health = check_database_health()
    assert health["status"] == "healthy"
    assert health["foreign_key_violations_count"] == 0


def test_mcp_search_and_details():
    results = search_assets(query="", limit=5)
    assert isinstance(results, list)
    if results:
        first_id = results[0]["id"]
        details = get_asset_details(first_id)
        assert details["id"] == first_id
        assert "files" in details
        assert "tags" in details


def test_mcp_list_collections_and_topology():
    cols = list_collections(limit=5)
    assert isinstance(cols, list)
    if cols:
        topo = analyze_collection_topology(collection_id=cols[0]["id"])
        assert "collection" in topo
        assert "indexed_units" in topo
        assert "physical_file_tree" in topo


def test_mcp_taxonomy_and_organize_column():
    tree = get_taxonomy_tree(class_code="domain")
    assert isinstance(tree, list)
    assert len(tree) == 1
    assert tree[0]["code"] == "domain"

    # Test creating, adding alias, and deleting a temporary tag via organize_tag_column
    res_create = organize_tag_column(
        "domain",
        [
            {"op": "create", "name": "MCP_Temp_Parent"},
            {"op": "create", "name": "MCP_Temp_Child", "parent_name": "MCP_Temp_Parent"},
        ],
    )
    assert res_create["status"] == "ok"
    assert res_create["applied_operations"] == 2

    updated_tree = get_taxonomy_tree(class_code="domain")[0]["tree"]
    parent_node = next((n for n in updated_tree if n["name"] == "MCP_Temp_Parent"), None)
    assert parent_node is not None
    child_node = next((c for c in parent_node.get("children", []) if c["name"] == "MCP_Temp_Child"), None)
    assert child_node is not None

    # Clean up temporary tags
    res_del = organize_tag_column(
        "domain",
        [
            {"op": "delete", "tag_id": child_node["id"]},
            {"op": "delete", "tag_id": parent_node["id"]},
        ],
    )
    assert res_del["status"] == "ok"
    assert res_del["applied_operations"] == 2

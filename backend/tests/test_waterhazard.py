"""水害防治筛选与日报的接口测试。

运行：.venv/bin/pip install pytest httpx && .venv/bin/python -m pytest tests -q
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app import regions
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def keep_divisions():
    """区域改名用例会动命名沿革，跑完恢复，避免用例之间互相影响。"""
    snapshot = copy.deepcopy(regions.DIVISIONS)
    yield
    regions.DIVISIONS[:] = snapshot


def fetch_all(params: dict, size: int = 200) -> list[dict]:
    """按给定条件翻完全部页，返回拼起来的命中结果。"""
    items: list[dict] = []
    page = 1
    while True:
        payload = client.get("/api/waterhazard", params={**params, "page": page, "size": size}).json()
        items.extend(payload["items"])
        if len(items) >= payload["total"]:
            return items
        page += 1


def test_combined_filter_matches_every_condition():
    params = {"region": "东翼", "date_from": "2026-09-01", "date_to": "2026-09-30", "inflow_min": "50"}
    payload = client.get("/api/waterhazard", params=params).json()
    assert payload["total"] > 0
    for row in payload["items"]:
        assert "东翼" in row["所在区域"]
        assert "2026-09-01" <= row["监测日期"] <= "2026-09-30"
        assert float(row["涌水量"]) >= 50


def test_results_sorted_by_inflow_desc():
    payload = client.get("/api/waterhazard", params={"size": 100}).json()
    inflows = [float(row["涌水量"]) for row in payload["items"]]
    assert inflows == sorted(inflows, reverse=True)


def test_region_filter_is_fuzzy_and_covers_old_and_new_names():
    payload = client.get("/api/waterhazard", params={"region": "东翼", "size": 100}).json()
    names = {row["所在区域"] for row in payload["items"]}
    # 改名前后的名称都能被“东翼”模糊命中
    assert "东翼采区" in names
    assert "东翼一采区" in names


def test_old_region_name_still_finds_legacy_records():
    payload = client.get("/api/waterhazard", params={"region": "东翼采区", "size": 100}).json()
    assert payload["total"] > 0
    assert all(row["所在区域"] == "东翼采区" for row in payload["items"])
    assert all(row["监测日期"] <= "2026-08-31" for row in payload["items"])


def test_reversed_inflow_range_returns_400_not_full_table():
    response = client.get("/api/waterhazard", params={"inflow_min": "200", "inflow_max": "50"})
    assert response.status_code == 400
    assert "写反" in response.json()["detail"]


def test_reversed_date_range_returns_400():
    response = client.get("/api/waterhazard", params={"date_from": "2026-10-01", "date_to": "2026-09-01"})
    assert response.status_code == 400
    assert "写反" in response.json()["detail"]


def test_invalid_inflow_value_returns_400():
    response = client.get("/api/waterhazard", params={"inflow_min": "abc"})
    assert response.status_code == 400
    assert "不是数字" in response.json()["detail"]


def test_pagination_total_matches_actual_count_and_pages_join_cleanly():
    params = {"region": "采区"}
    for size in (10, 20, 50):
        first = client.get("/api/waterhazard", params={**params, "page": 1, "size": size}).json()
        assert first["total"] > 0
        assert len(first["items"]) == min(size, first["total"])
        items = fetch_all(params, size=size)
        assert len(items) == first["total"]
        ids = [row["id"] for row in items]
        assert len(ids) == len(set(ids))


def test_page_size_is_selectable():
    for size in (10, 20, 50, 100):
        payload = client.get("/api/waterhazard", params={"page": 1, "size": size}).json()
        assert payload["size"] == size
        assert len(payload["items"]) == min(size, payload["total"])


def test_daily_report_matches_list_under_same_filters():
    params = {"region": "西翼", "date_from": "2026-08-01", "inflow_min": "30"}
    listed = fetch_all(params, size=20)
    report = client.get("/api/waterhazard/daily-report", params=params).json()
    assert report["total"] == len(listed)
    assert [row["id"] for row in report["items"]] == [row["id"] for row in listed]
    assert report["filters"]["所在区域"] == "西翼"


def test_daily_report_rejects_reversed_range_too():
    response = client.get("/api/waterhazard/daily-report", params={"inflow_min": "90", "inflow_max": "10"})
    assert response.status_code == 400


def test_legacy_rows_backfilled_by_division_at_the_time():
    payload = client.get("/api/waterhazard", params={"size": 100}).json()
    by_id = {row["id"]: row for row in payload["items"]}
    # 三条存量记录登记时没填区域名，已按监测日期当时的区域划分回填
    assert by_id[49]["所在区域"] == "东翼采区"      # 2026-08-10，改名前
    assert by_id[50]["所在区域"] == "东翼一采区"    # 2026-09-15，改名后
    assert by_id[51]["所在区域"] == "西翼采区"


def test_rename_keeps_old_records_searchable_by_old_name():
    before = client.get("/api/waterhazard", params={"region": "西翼采区", "size": 100}).json()
    assert before["total"] > 0

    result = client.post(
        "/api/waterhazard/regions/rename",
        json={"values": {"片区": "西翼", "新名称": "西翼一采区", "生效日期": "2026-10-04"}},
    ).json()
    assert result["ok"], result["message"]

    # 改名不改写存量记录：旧名仍筛得出老记录，且条数不变
    after = client.get("/api/waterhazard", params={"region": "西翼采区", "size": 100}).json()
    assert after["total"] == before["total"]
    assert [row["id"] for row in after["items"]] == [row["id"] for row in before["items"]]

    names = client.get("/api/waterhazard/regions").json()
    assert "西翼一采区" in names["current"]
    assert "西翼采区" in names["names"]  # 旧名保留在名录里，供筛选联想


def test_rename_rejects_unknown_area():
    result = client.post(
        "/api/waterhazard/regions/rename",
        json={"values": {"片区": "不存在的片区", "新名称": "某某采区", "生效日期": "2026-10-04"}},
    ).json()
    assert not result["ok"]
    assert "不存在" in result["message"]


def test_export_honors_filters():
    params = {"region": "南翼", "inflow_min": "100"}
    exported = client.get("/api/waterhazard/export", params=params).json()
    listed = fetch_all(params)
    assert exported["total"] == len(listed)
    assert [row["id"] for row in exported["items"]] == [row["id"] for row in listed]


def test_size_over_limit_returns_400():
    response = client.get("/api/waterhazard", params={"size": 201})
    assert response.status_code == 400

"""区域命名沿革：区域改名只影响生效日之后的记录，老记录沿用当时的名字。

水害防治的筛选、日报都按记录上保存的「所在区域」匹配；这里维护片区划分的历史，
负责回答"某片区在某一天叫什么名字"，并把缺区域名的存量记录按当时划分回填。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

# 区域划分沿革：同一片区在不同时间段使用不同名称；停用日期为 None 表示沿用至今。
DIVISIONS: list[dict[str, Any]] = [
    {"片区": "东翼", "名称": "东翼采区", "生效日期": "2026-01-01", "停用日期": "2026-08-31"},
    {"片区": "东翼", "名称": "东翼一采区", "生效日期": "2026-09-01", "停用日期": None},
    {"片区": "西翼", "名称": "西翼采区", "生效日期": "2026-01-01", "停用日期": None},
    {"片区": "南翼", "名称": "南翼采区", "生效日期": "2026-01-01", "停用日期": None},
    {"片区": "北翼", "名称": "北翼采区", "生效日期": "2026-01-01", "停用日期": None},
]


def parse_date(text: Any) -> date | None:
    """把 '2026-09-01' 这类文本解析成日期；空值返回 None，非法格式抛 ValueError。"""
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"日期「{raw}」格式不对，请按 YYYY-MM-DD 填写") from None


def region_name_on(area: str, day: date) -> str | None:
    """查某片区在某一天使用的区域名；没有覆盖该日期的划分时返回 None。"""
    for item in DIVISIONS:
        if item["片区"] != area:
            continue
        start = parse_date(item["生效日期"])
        end = parse_date(item["停用日期"])
        if (start is None or day >= start) and (end is None or day <= end):
            return str(item["名称"])
    return None


def current_regions() -> list[str]:
    """当前仍在沿用的区域名。"""
    today = date.today()
    names: list[str] = []
    for item in DIVISIONS:
        start = parse_date(item["生效日期"])
        end = parse_date(item["停用日期"])
        if (start is None or start <= today) and (end is None or end >= today):
            names.append(str(item["名称"]))
    return names


def all_region_names() -> list[str]:
    """全部历史区域名（含旧名），供筛选联想；老记录按旧名也能筛出来。"""
    seen: list[str] = []
    for item in DIVISIONS:
        name = str(item["名称"])
        if name not in seen:
            seen.append(name)
    return seen


def rename_region(area: str, new_name: str, effective: date) -> str | None:
    """区域改名：停用该片区当前名称，自生效日起使用新名称。

    只追加划分沿革，不改写存量记录——老记录仍按旧名筛出来。
    返回被替换的旧名称；片区不存在时返回 None。
    """
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("新区域名不能为空")
    old_name: str | None = None
    for item in DIVISIONS:
        if item["片区"] != area:
            continue
        if parse_date(item["停用日期"]) is None:
            old_name = str(item["名称"])
            item["停用日期"] = (effective - timedelta(days=1)).isoformat()
    if old_name is None:
        return None
    DIVISIONS.append({"片区": area, "名称": new_name, "生效日期": effective.isoformat(), "停用日期": None})
    return old_name


def backfill_region_names(
    rows: Iterable[dict[str, Any]],
    *,
    area_field: str = "所属片区",
    name_field: str = "所在区域",
    date_field: str = "监测日期",
) -> int:
    """存量回填：缺区域名的记录按监测日期当时的区域划分补上；已有名字的保持不动。

    返回回填的记录条数。
    """
    filled = 0
    for row in rows:
        if str(row.get(name_field) or "").strip():
            continue
        area = str(row.get(area_field) or "").strip()
        try:
            day = parse_date(row.get(date_field))
        except ValueError:
            day = None
        if not area or day is None:
            continue
        name = region_name_on(area, day)
        if name:
            row[name_field] = name
            filled += 1
    return filled

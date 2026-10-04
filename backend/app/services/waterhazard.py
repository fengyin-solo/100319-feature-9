"""水害防治业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app import regions
from app.store import store

MODULE = "waterhazard"
REQUIRED_FIELDS = ["监测编号", "所在区域", "涌水量"]
OPTIONAL_FIELDS = ["监测日期", "水压", "水温", "水质类型", "排水能力", "所属片区"]
STATUS_ORDER = ["正常", "涌水增加", "突水危险", "已控制"]
ACTION_RULES = {"增加监测": "涌水增加", "突水预警": "突水危险", "控制确认": "已控制"}
NEGATIVE_ACTIONS = []
REPORT_SIZE = 10000

FILTER_LABELS = {
    "keyword": "监测编号",
    "status": "水害状态",
    "region": "所在区域",
    "date_from": "监测日期起",
    "date_to": "监测日期止",
    "inflow_min": "涌水量下限",
    "inflow_max": "涌水量上限",
}


class FilterError(ValueError):
    """过滤条件不合法：消息要能让值班人员当场看懂并改正。"""


def _parse_inflow(raw: Any, label: str) -> float | None:
    """解析涌水量边界；空值视为未填写，非数字当场说明。"""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        raise FilterError(f"涌水量{label}「{text}」不是数字，请填写数值") from None


def _inflow_of(row: dict[str, Any]) -> float | None:
    try:
        return float(str(row.get("涌水量")).strip())
    except (TypeError, ValueError):
        return None


def _row_date(row: dict[str, Any]) -> date | None:
    try:
        return regions.parse_date(row.get("监测日期"))
    except ValueError:
        return None


class WaterhazardService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        region: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        inflow_min: str | None = None,
        inflow_max: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """组合过滤：区域模糊、监测日期区间、涌水量区间；命中按涌水量从大到小排序。"""
        rows = list(store.rows(MODULE))
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("监测编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if region and region.strip():
            needle = region.strip().casefold()
            rows = [row for row in rows if needle in str(row.get("所在区域", "")).casefold()]
        try:
            start = regions.parse_date(date_from)
            end = regions.parse_date(date_to)
        except ValueError as exc:
            raise FilterError(str(exc)) from None
        if start and end and start > end:
            raise FilterError(f"监测日期区间写反了：起始 {start} 晚于截止 {end}，请对调后再查")
        if start:
            rows = [row for row in rows if (day := _row_date(row)) is not None and day >= start]
        if end:
            rows = [row for row in rows if (day := _row_date(row)) is not None and day <= end]
        low = _parse_inflow(inflow_min, "下限")
        high = _parse_inflow(inflow_max, "上限")
        if low is not None and high is not None and low > high:
            raise FilterError(f"涌水量区间写反了：下限 {low} 大于上限 {high}，请对调后再查")
        if low is not None:
            rows = [row for row in rows if (value := _inflow_of(row)) is not None and value >= low]
        if high is not None:
            rows = [row for row in rows if (value := _inflow_of(row)) is not None and value <= high]

        def sort_key(row: dict[str, Any]) -> tuple[int, float, int]:
            value = _inflow_of(row)
            if value is None:
                return (1, 0.0, int(row.get("id", 0)))
            return (0, -value, int(row.get("id", 0)))

        rows.sort(key=sort_key)
        total = len(rows)
        page = max(page, 1)
        start_at = (page - 1) * size
        return rows[start_at:start_at + size], total

    def daily_report(self, **filters: Any) -> dict[str, Any]:
        """水害防治日报：与列表共用同一套过滤口径，另一个入口读到的结果一致。"""
        items, total = self.list_entries(page=1, size=REPORT_SIZE, **filters)
        inflows = [value for value in (_inflow_of(row) for row in items) if value is not None]
        applied = {FILTER_LABELS[key]: value for key, value in filters.items() if str(value or "").strip()}
        return {
            "module": MODULE,
            "title": "水害防治日报",
            "generated_on": date.today().isoformat(),
            "filters": applied,
            "total": total,
            "max_inflow": max(inflows) if inflows else None,
            "items": items,
        }

    def rename_region(self, area: str, new_name: str, effective: str) -> tuple[str | None, str]:
        """区域改名：只追加命名沿革，存量记录沿用当时的区域名。"""
        if not area:
            raise FilterError("片区不能为空")
        if not new_name.strip():
            raise FilterError("新区域名不能为空")
        try:
            day = regions.parse_date(effective)
        except ValueError as exc:
            raise FilterError(str(exc)) from None
        if day is None:
            raise FilterError("生效日期不能为空，请按 YYYY-MM-DD 填写")
        old_name = regions.rename_region(area, new_name, day)
        if old_name is None:
            return None, f"片区「{area}」不存在，无法改名"
        return old_name, f"区域「{old_name}」自 {day} 起改名为「{new_name.strip()}」，老记录仍按旧名检索"

    def backfill_regions(self) -> int:
        """存量数据按当时的区域划分回填，返回回填条数。"""
        return regions.backfill_region_names(store.rows(MODULE))

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in OPTIONAL_FIELDS:
            if str(values.get(field) or "").strip():
                entry[field] = values.get(field)
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"水文监测 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于水害防治可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"水文监测已{action}"

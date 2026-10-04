"""水害防治业务规则：状态流转、字段校验与筛选口径都收在这里。

筛选口径（列表与「水害防治日报」共用，保证另一个入口读到的结果一致）：
- 所在区域：模糊匹配，且区域改名后旧名仍能筛出存量记录（见 REGION_GROUPS）；
- 监测日期：闭区间，按「监测日期」YYYY-MM-DD 比较；
- 涌水量：按下限（或上下限）数值过滤，命中结果固定按涌水量从大到小排序；
- 区间写反（下限大于上限 / 开始日期晚于结束日期）：当场给出说明并返回空结果，
  绝不退化成不带条件的全表查询。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "waterhazard"
REQUIRED_FIELDS = ["监测编号", "所在区域", "涌水量"]
OPTIONAL_FIELDS = ["水压", "水温", "水质类型", "排水能力", "监测日期", "水害状态"]
STATUS_ORDER = ["正常", "涌水增加", "突水危险", "已控制"]
ACTION_RULES = {"增加监测": "涌水增加", "突水预警": "突水危险", "控制确认": "已控制"}
NEGATIVE_ACTIONS = []

# 区域改名台账：current 为沿用的既有（现行）区域命名，aliases 为历史命名。
# 命中任一新旧名称都视为同一区域；存量记录保留旧名仍可被筛出。
REGION_GROUPS: list[dict[str, Any]] = [
    {"current": "北翼综采工作面", "aliases": ["北翼采区"]},
]


def _flow_value(row: dict[str, Any]) -> float | None:
    """把涌水量解析成数值；无法解析时返回 None（排序时排到最后）。"""
    raw = row.get("涌水量")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _normalize_region(name: str) -> str:
    """新登记记录沿用既有区域命名：直接使用历史旧名时归并为现行名称。"""
    stripped = name.strip()
    for group in REGION_GROUPS:
        if stripped in group["aliases"] or stripped == group["current"]:
            return str(group["current"])
    return stripped


class WaterhazardService:
    def query_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        region: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        flow_min: float | None = None,
        flow_max: float | None = None,
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        """按区域、监测日期区间、涌水量区间做组合过滤并分页。

        返回 items / total / warning / summary。区间反转时 warning 说明原因，
        items 与 total 一律为空（调用方无需再追加任何兜底条件）。
        """
        warning = ""
        if flow_min is not None and flow_max is not None and flow_min > flow_max:
            warning = f"涌水量区间写反了：下限 {flow_min:g} 大于上限 {flow_max:g}，请调换后再查"
        if date_start and date_end and date_start > date_end:
            text = f"监测日期区间写反了：开始日期 {date_start} 晚于结束日期 {date_end}，请调换后再查"
            warning = f"{warning}；{text}" if warning else text
        if warning:
            return {"items": [], "total": 0, "warning": warning, "summary": self._summary([])}

        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("监测编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if region and region.strip():
            # 直接按记录上的区域名做模糊包含：
            # - 输入「北翼采区」（旧名）只命中保留旧名的存量记录；
            # - 输入「北翼综采工作面」（新名）只命中改名后的记录；
            # - 输入「北翼」新旧名都能命中。
            token = region.strip()
            rows = [row for row in rows if token in str(row.get("所在区域", ""))]
        if date_start:
            rows = [row for row in rows if str(row.get("监测日期", "")) >= date_start]
        if date_end:
            rows = [row for row in rows if str(row.get("监测日期", "")) <= date_end]
        if flow_min is not None:
            rows = [row for row in rows if (value := _flow_value(row)) is not None and value >= flow_min]
        if flow_max is not None:
            rows = [row for row in rows if (value := _flow_value(row)) is not None and value <= flow_max]

        # 命中结果固定按涌水量从大到小；同值时按记录编号稳定排序。
        rows.sort(key=lambda row: (_flow_value(row) is None, -(_flow_value(row) or 0.0), int(row.get("id", 0))))

        total = len(rows)
        start = max(page - 1, 0) * size
        return {
            "items": rows[start:start + size],
            "total": total,
            "warning": "",
            "summary": self._summary(rows),
        }

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        region: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        flow_min: float | None = None,
        flow_max: float | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """兼容旧调用方的精简返回：只取当前条件下的分页条目与总数。"""
        result = self.query_entries(
            keyword=keyword,
            status=status,
            region=region,
            date_start=date_start,
            date_end=date_end,
            flow_min=flow_min,
            flow_max=flow_max,
            page=page,
            size=size,
        )
        return result["items"], result["total"]

    def _summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """对筛选后的全量命中行（分页前）做状态汇总，供日报与统计卡片使用。"""
        counts = {name: 0 for name in STATUS_ORDER}
        max_flow: float | None = None
        for row in rows:
            status = str(row.get("status", ""))
            if status in counts:
                counts[status] += 1
            value = _flow_value(row)
            if value is not None and (max_flow is None or value > max_flow):
                max_flow = value
        return {"total": len(rows), "status_counts": counts, "max_flow": max_flow}

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
            if values.get(field) is not None and str(values.get(field)).strip():
                entry[field] = values.get(field)
        # 区域沿用既有命名：旧名登记自动归并到现行名称。
        entry["所在区域"] = _normalize_region(str(entry["所在区域"]))
        flow = str(entry.get("涌水量", "")).strip()
        try:
            entry["涌水量"] = float(flow) if "." in flow else int(flow)
        except ValueError:
            pass
        entry["status"] = STATUS_ORDER[0]
        entry["水害状态"] = STATUS_ORDER[0]
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
        # 「水害状态」展示列与状态机保持同步，避免筛出来的记录前后矛盾。
        entry["水害状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"水文监测已{action}"

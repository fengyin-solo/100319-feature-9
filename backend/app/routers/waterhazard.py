"""水害防治接口：维护水文监测，覆盖增加监测、突水预警、控制确认等动作。

列表与「水害防治日报」走同一套筛选口径（service.query_entries），
保证日报入口读到的命中结果与列表页完全一致。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.waterhazard import WaterhazardService

router = APIRouter(prefix="/api/waterhazard", tags=["水害防治"])

service = WaterhazardService()

LIST_FIELDS = ["监测编号", "所在区域", "涌水量", "水压", "水温", "水质类型", "排水能力", "监测日期", "水害状态"]
STATUSES = ["正常", "涌水增加", "突水危险", "已控制"]


def _parse_number(raw: str | None, label: str) -> float | None:
    """涌水量区间按数字解析；填了非数字要当场说明，而不是静默忽略条件。"""
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label}必须是数字，当前填写：{raw}") from None


def _parse_day(raw: str | None, label: str) -> str | None:
    if raw is None or not raw.strip():
        return None
    text = raw.strip()
    try:
        date.fromisoformat(text)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label}格式应为 YYYY-MM-DD，当前填写：{raw}") from None
    return text


def _run_query(
    *,
    keyword: str | None,
    status: str | None,
    region: str | None,
    date_start: str | None,
    date_end: str | None,
    flow_min_raw: str | None,
    flow_max_raw: str | None,
    page: int,
    size: int,
) -> dict[str, Any]:
    """两个入口（列表 / 日报 / 导出）共用的参数解析与查询。"""
    flow_min = _parse_number(flow_min_raw, "涌水量下限")
    flow_max = _parse_number(flow_max_raw, "涌水量上限")
    start = _parse_day(date_start, "监测开始日期")
    end = _parse_day(date_end, "监测结束日期")
    return service.query_entries(
        keyword=keyword,
        status=status,
        region=region,
        date_start=start,
        date_end=end,
        flow_min=flow_min,
        flow_max=flow_max,
        page=page,
        size=size,
    )


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按监测编号检索"),
    status: str | None = Query(default=None, description="正常、涌水增加、突水危险、已控制"),
    region: str | None = Query(default=None, description="所在区域，支持模糊匹配与历史区域名"),
    date_start: str | None = Query(default=None, description="监测日期起，YYYY-MM-DD"),
    date_end: str | None = Query(default=None, description="监测日期止，YYYY-MM-DD"),
    flow_min: str | None = Query(default=None, description="涌水量下限（m³/h）"),
    flow_max: str | None = Query(default=None, description="涌水量上限（m³/h）；下限大于上限时返回空页并提示"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1),
) -> PageResult[dict]:
    """按区域、监测日期区间、涌水量区间组合过滤；结果按涌水量降序分页返回。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    result = _run_query(
        keyword=keyword,
        status=status,
        region=region,
        date_start=date_start,
        date_end=date_end,
        flow_min_raw=flow_min,
        flow_max_raw=flow_max,
        page=page,
        size=size,
    )
    return PageResult(
        items=result["items"],
        total=result["total"],
        page=page,
        size=size,
        warning=result["warning"] or None,
        summary=result["summary"],
    )


@router.get("/daily-report")
def daily_report(
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    region: str | None = Query(default=None),
    date_start: str | None = Query(default=None),
    date_end: str | None = Query(default=None),
    flow_min: str | None = Query(default=None),
    flow_max: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1),
) -> dict[str, Any]:
    """水害防治日报：与列表完全相同的筛选口径，读到的命中结果保持一致。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    filters = {
        "keyword": keyword,
        "status": status,
        "region": region,
        "date_start": date_start,
        "date_end": date_end,
        "flow_min": flow_min,
        "flow_max": flow_max,
    }
    result = _run_query(
        keyword=keyword,
        status=status,
        region=region,
        date_start=date_start,
        date_end=date_end,
        flow_min_raw=flow_min,
        flow_max_raw=flow_max,
        page=page,
        size=size,
    )
    return {
        "module": "waterhazard",
        "title": "水害防治日报",
        "filters": filters,
        "items": result["items"],
        "total": result["total"],
        "page": page,
        "size": size,
        "warning": result["warning"] or None,
        "summary": result["summary"],
    }


@router.get("/export")
def export_entries(
    keyword: str | None = None,
    status: str | None = None,
    region: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    flow_min: str | None = None,
    flow_max: str | None = None,
) -> dict[str, Any]:
    """导出水害防治清单：沿用当前筛选条件导出全量命中数据；区间写反时导出空清单。"""
    result = _run_query(
        keyword=keyword,
        status=status,
        region=region,
        date_start=date_start,
        date_end=date_end,
        flow_min_raw=flow_min,
        flow_max_raw=flow_max,
        page=1,
        size=10000,
    )
    return {
        "module": "waterhazard",
        "total": result["total"],
        "warning": result["warning"] or None,
        "items": result["items"],
    }


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条水文监测明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"水文监测 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条水文监测，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="水文监测已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条水文监测执行增加监测、突水预警、控制确认；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

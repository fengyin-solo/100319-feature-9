"""水害防治接口：维护水文监测，覆盖增加监测、突水预警、控制确认等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app import regions
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.waterhazard import FilterError, WaterhazardService

router = APIRouter(prefix="/api/waterhazard", tags=["水害防治"])

service = WaterhazardService()

LIST_FIELDS = ["监测编号", "所在区域", "监测日期", "涌水量", "水压", "水温", "水质类型", "排水能力", "水害状态"]
STATUSES = ["正常", "涌水增加", "突水危险", "已控制"]
PAGE_SIZE_LIMIT = 200


def _filters(
    keyword: str | None,
    status: str | None,
    region: str | None,
    date_from: str | None,
    date_to: str | None,
    inflow_min: str | None,
    inflow_max: str | None,
) -> dict[str, Any]:
    return {
        "keyword": keyword,
        "status": status,
        "region": region,
        "date_from": date_from,
        "date_to": date_to,
        "inflow_min": inflow_min,
        "inflow_max": inflow_max,
    }


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按监测编号检索"),
    status: str | None = Query(default=None, description="正常、涌水增加、突水危险、已控制"),
    region: str | None = Query(default=None, description="所在区域，支持模糊匹配"),
    date_from: str | None = Query(default=None, description="监测日期起，YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="监测日期止，YYYY-MM-DD"),
    inflow_min: str | None = Query(default=None, description="涌水量下限"),
    inflow_max: str | None = Query(default=None, description="涌水量上限"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按区域、监测日期区间、涌水量区间组合过滤；命中按涌水量从大到小排序。

    区间写反或格式不对时返回 400 说明，按空结果处理，绝不退回整表。
    """
    if size > PAGE_SIZE_LIMIT:
        raise HTTPException(status_code=400, detail=f"每页最多 {PAGE_SIZE_LIMIT} 条，请缩小分页范围")
    try:
        items, total = service.list_entries(
            **_filters(keyword, status, region, date_from, date_to, inflow_min, inflow_max),
            page=page,
            size=size,
        )
    except FilterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/daily-report")
def daily_report(
    keyword: str | None = Query(default=None, description="按监测编号检索"),
    status: str | None = Query(default=None, description="正常、涌水增加、突水危险、已控制"),
    region: str | None = Query(default=None, description="所在区域，支持模糊匹配"),
    date_from: str | None = Query(default=None, description="监测日期起，YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="监测日期止，YYYY-MM-DD"),
    inflow_min: str | None = Query(default=None, description="涌水量下限"),
    inflow_max: str | None = Query(default=None, description="涌水量上限"),
) -> dict[str, Any]:
    """水害防治日报：与列表共用同一套过滤口径，另一个入口读到的结果一致。"""
    try:
        return service.daily_report(
            **_filters(keyword, status, region, date_from, date_to, inflow_min, inflow_max)
        )
    except FilterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/regions")
def list_regions() -> dict[str, Any]:
    """区域名录：当前沿用的名称与命名沿革，供筛选联想；旧名仍能筛出老记录。"""
    return {
        "current": regions.current_regions(),
        "names": regions.all_region_names(),
        "history": regions.DIVISIONS,
    }


@router.post("/regions/rename", response_model=ActionResult)
def rename_region(payload: EntryPayload) -> ActionResult:
    """区域改名：自生效日起用新名称，存量记录沿用当时的区域名，老记录仍按旧名筛出来。"""
    try:
        old_name, message = service.rename_region(
            area=str(payload.values.get("片区") or "").strip(),
            new_name=str(payload.values.get("新名称") or ""),
            effective=str(payload.values.get("生效日期") or ""),
        )
    except FilterError as exc:
        return ActionResult(ok=False, message=str(exc))
    if old_name is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message)


@router.post("/regions/backfill", response_model=ActionResult)
def backfill_regions() -> ActionResult:
    """存量数据按当时的区域划分回填：只补缺区域名的记录，已有命名保持不动。"""
    filled = service.backfill_regions()
    return ActionResult(ok=True, message=f"已按当时的区域划分回填 {filled} 条存量记录")


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按监测编号检索"),
    status: str | None = Query(default=None, description="正常、涌水增加、突水危险、已控制"),
    region: str | None = Query(default=None, description="所在区域，支持模糊匹配"),
    date_from: str | None = Query(default=None, description="监测日期起，YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="监测日期止，YYYY-MM-DD"),
    inflow_min: str | None = Query(default=None, description="涌水量下限"),
    inflow_max: str | None = Query(default=None, description="涌水量上限"),
) -> dict[str, Any]:
    """导出水害防治清单：返回当前过滤条件下的全量数据。"""
    try:
        items, total = service.list_entries(
            **_filters(keyword, status, region, date_from, date_to, inflow_min, inflow_max),
            page=1,
            size=10000,
        )
    except FilterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"module": "waterhazard", "total": total, "items": items}


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

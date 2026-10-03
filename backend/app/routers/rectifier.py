"""开关电源接口：维护开关电源，覆盖记录缺失、记录异常、安排更换与处理单填报。

注意路由顺序：/summary、/workorder、/export 这些固定路径要写在 /{entry_id} 前面，
否则会被当成 entry_id 匹配，直接 422。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.rectifier import RectifierService

router = APIRouter(prefix="/api/rectifier", tags=["开关电源"])

service = RectifierService()

LIST_FIELDS = ["电源编号", "额定功率", "所属站点", "整流模块数", "负载率", "输出电压", "模块故障", "电源状态"]
STATUSES = ["正常", "模块缺失", "输出异常", "已更换"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按电源编号检索"),
    status: str | None = Query(default=None, description="正常、模块缺失、输出异常、已更换"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按电源编号与状态过滤开关电源列表；total 是过滤后的全量条数，翻页不会丢记录。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/summary")
def summary() -> dict[str, int]:
    """各状态台数汇总，给页头统计卡用。"""
    return service.summary()


@router.get("/workorder")
def workorder() -> dict[str, Any]:
    """处理单：待处理电源清单 + 每台草稿 + 第一台没填完的 id，断了能接着做。"""
    items, next_id = service.workorder()
    return {"items": items, "total": len(items), "next_id": next_id}


@router.put("/workorder/{entry_id}", response_model=ActionResult)
def save_workorder_unit(entry_id: int, payload: EntryPayload) -> ActionResult:
    """按台保存处理单草稿：只合并提交的字段，其他台、其他字段都不动。"""
    entry, message = service.save_draft(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出开关电源清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "rectifier", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单台开关电源明细；与列表同一个出数口，负载率不会对不上。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"开关电源 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一台开关电源，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="开关电源已登记", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """保存输出电压等参数；负载率随统一推导同步到列表和详情。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行记录缺失、记录异常、安排更换；状态和业务字段一起落盘。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

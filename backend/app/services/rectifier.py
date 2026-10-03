"""开关电源业务规则：状态流转、负载率推导与处理单草稿都收在这里。

负载率不在任何一处单独存数，统一由 present() 用同一份存储字段推导：
负载电流 = 负载功率 / 输出电压，负载率 = 负载电流 / (整流模块数 × 单模块额定电流)。
列表、详情、动作回包、处理单都走 present()，改完任何一处，各处看到的值自然一致。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "rectifier"
REQUIRED_FIELDS = ["电源编号", "额定功率", "所属站点"]
STATUS_ORDER = ["正常", "模块缺失", "输出异常", "已更换"]
ACTION_RULES = {"记录缺失": "模块缺失", "记录异常": "输出异常", "安排更换": "已更换"}
NEGATIVE_ACTIONS = ["记录缺失", "记录异常"]

MODULE_RATED_CURRENT = 50.0  # 单块整流模块额定电流（A）
VOLTAGE_MIN, VOLTAGE_MAX = 40.0, 60.0  # 输出电压允许范围（V）
EDITABLE_FIELDS = ["输出电压", "负载功率", "所属站点"]
DRAFT_FIELDS = ["处理措施", "处理人", "计划完成时间", "备注"]
DRAFT_REQUIRED = ["处理措施"]
TODO_STATUSES = ("模块缺失", "输出异常")


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def present(entry: dict[str, Any]) -> dict[str, Any]:
    """统一出数口：任何接口要往外给开关电源，都从这里过一遍。"""
    modules = _as_int(entry.get("整流模块数"))
    voltage = _as_float(entry.get("输出电压"))
    power = _as_float(entry.get("负载功率"))
    current = power / voltage if voltage > 0 else None
    rate = current / (modules * MODULE_RATED_CURRENT) * 100 if current is not None and modules > 0 else None
    draft = entry.get("处理单") or {}
    filled = all(str(draft.get(field) or "").strip() for field in DRAFT_REQUIRED)
    return {
        "id": entry.get("id"),
        "status": entry.get("status"),
        "pending": bool(entry.get("pending")),
        "abnormal": bool(entry.get("abnormal")),
        "电源编号": entry.get("电源编号"),
        "额定功率": entry.get("额定功率"),
        "所属站点": entry.get("所属站点"),
        "整流模块数": modules,
        "负载功率": power,
        "负载电流": f"{current:.1f}A" if current is not None else "—",
        "负载率": f"{rate:.1f}%" if rate is not None else "—",
        "输出电压": voltage,
        "模块故障": _as_int(entry.get("模块故障")),
        "电源状态": entry.get("status"),
        "处理单": {field: str(draft.get(field, "")) for field in DRAFT_FIELDS},
        "已填报": filled,
    }


class RectifierService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("电源编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        rows = sorted(rows, key=lambda row: _as_int(row.get("id")))
        total = len(rows)
        start = max(page - 1, 0) * size
        return [present(row) for row in rows[start:start + size]], total

    def summary(self) -> dict[str, int]:
        counts = {status: 0 for status in STATUS_ORDER}
        for row in store.rows(MODULE):
            status = str(row.get("status"))
            counts[status] = counts.get(status, 0) + 1
        return counts

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return present(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["整流模块数"] = _as_int(values.get("整流模块数"), 6)
        entry["负载功率"] = _as_float(values.get("负载功率"))
        entry["输出电压"] = _as_float(values.get("输出电压"), 53.5)
        entry["模块故障"] = 0
        rows.append(entry)
        return present(entry), []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"开关电源 {entry_id} 不存在或已归档"
        if "输出电压" in values:
            voltage = _as_float(values.get("输出电压"), -1)
            if not VOLTAGE_MIN <= voltage <= VOLTAGE_MAX:
                return None, f"输出电压要在 {VOLTAGE_MIN:.0f}V 到 {VOLTAGE_MAX:.0f}V 之间"
            entry["输出电压"] = voltage
        if "负载功率" in values:
            power = _as_float(values.get("负载功率"), -1)
            if power < 0:
                return None, "负载功率不能为负"
            entry["负载功率"] = power
        if "所属站点" in values and str(values.get("所属站点") or "").strip():
            entry["所属站点"] = str(values["所属站点"]).strip()
        return present(entry), "开关电源参数已保存"

    def run_action(self, entry_id: int, action: str, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"开关电源 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于开关电源可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        if action == "记录缺失":
            # 模块缺失和整流模块数一起落盘：减在架数、记故障数，负载率随推导自动更新
            missing = _as_int(values.get("缺失模块数"), 1)
            installed = _as_int(entry.get("整流模块数"))
            if missing <= 0:
                return None, "缺失模块数要大于 0"
            if missing > installed:
                return None, f"缺失 {missing} 块超过在架 {installed} 块，请核对整流模块数"
            entry["整流模块数"] = installed - missing
            entry["模块故障"] = _as_int(entry.get("模块故障")) + missing
        elif action == "记录异常":
            # 输出异常和实测电压一起落盘
            if values.get("输出电压") is None:
                return None, "记录输出异常要带上实测输出电压"
            voltage = _as_float(values.get("输出电压"), -1)
            if not VOLTAGE_MIN <= voltage <= VOLTAGE_MAX:
                return None, f"输出电压要在 {VOLTAGE_MIN:.0f}V 到 {VOLTAGE_MAX:.0f}V 之间"
            entry["输出电压"] = voltage
        elif action == "安排更换":
            entry["模块故障"] = 0
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return present(entry), f"开关电源已{action}"

    def workorder(self) -> tuple[list[dict[str, Any]], int | None]:
        """处理单：取出待处理的电源和各自的草稿，并给出第一台没填完的 id。"""
        rows = [row for row in store.rows(MODULE) if row.get("status") in TODO_STATUSES]
        rows = sorted(rows, key=lambda row: _as_int(row.get("id")))
        items = [present(row) for row in rows]
        next_id = next((item["id"] for item in items if not item["已填报"]), None)
        return items, next_id

    def save_draft(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """按台保存草稿：只合并本次提交的字段，已填过的内容不被覆盖。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"开关电源 {entry_id} 不存在或已归档"
        if entry.get("status") not in TODO_STATUSES:
            return None, f"开关电源 {entry.get('电源编号')} 当前不在待处理范围"
        draft = entry.setdefault("处理单", {})
        for field in DRAFT_FIELDS:
            if field in values and values[field] is not None:
                draft[field] = str(values[field]).strip()
        return present(entry), "处理单已保存"

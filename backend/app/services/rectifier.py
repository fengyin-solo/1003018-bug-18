"""开关电源业务规则：状态流转、字段校验与筛选口径都收在这里。

列表、详情、处理单都从这同一份数据里取数；写操作也只走
update_entry / run_action 两个入口，保证状态与运行参数一起落盘。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "rectifier"
REQUIRED_FIELDS = ["电源编号", "额定功率", "所属站点"]
METRIC_FIELDS = ["整流模块数", "负载率", "输出电压", "模块故障"]
STATUS_ORDER = ["正常", "模块缺失", "输出异常", "已更换"]
ACTION_RULES = {"记录缺失": "模块缺失", "记录异常": "输出异常", "安排更换": "已更换"}
ABNORMAL_STATUSES = {"模块缺失", "输出异常"}


class RectifierService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """先过滤再翻页：total 是过滤后的全量条数，翻页不会丢记录。"""
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("电源编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def status_summary(self) -> dict[str, int]:
        """各状态条数：统计卡片与列表同源，避免两处口径不一致。"""
        summary = {status: 0 for status in STATUS_ORDER}
        for row in store.rows(MODULE):
            status = str(row.get("status", ""))
            if status in summary:
                summary[status] += 1
        return summary

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in METRIC_FIELDS:
            entry[field] = values.get(field, "")
        entry["status"] = STATUS_ORDER[0]
        entry["电源状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """保存运行参数：只接收白名单字段，保存后返回落盘后的整条记录。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"开关电源 {entry_id} 不存在或已归档"
        changed = [field for field in METRIC_FIELDS if field in values]
        if not changed:
            return None, f"没有可保存的字段，仅支持：{'、'.join(METRIC_FIELDS)}"
        for field in changed:
            entry[field] = values[field]
        return entry, f"开关电源运行参数已保存：{'、'.join(changed)}"

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """状态流转与运行参数一次落盘：记录缺失、记录异常时整流模块数等随单提交。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"开关电源 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于开关电源可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        saved_fields: list[str] = []
        for field in METRIC_FIELDS:
            if values is not None and field in values and str(values[field]).strip() != "":
                entry[field] = values[field]
                saved_fields.append(field)
        entry["status"] = target
        entry["电源状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = target in ABNORMAL_STATUSES
        message = f"开关电源已{action}"
        if saved_fields:
            message += f"，{'、'.join(saved_fields)}已一并落盘"
        return entry, message

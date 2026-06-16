"""Mock 内部 API：员工 / 考勤 / 订单（数据来自 data/mock/*.json）。

与主后端同处一个 FastAPI 项目，通过 /mock-api 前缀暴露，
用于模拟企业内部系统，供 Tool Calling 调用。
"""

import json
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/mock-api", tags=["mock-api"])

_MOCK_DIR = Path("data/mock")


def _load(name: str) -> list:
    return json.loads((_MOCK_DIR / name).read_text(encoding="utf-8"))


@router.get("/employees/{employee_id}")
async def get_employee(employee_id: str) -> JSONResponse:
    """根据员工 ID 查询基础信息。"""
    for e in _load("employees.json"):
        if e["id"] == employee_id:
            return JSONResponse(e)
    return JSONResponse({"error": "not found", "employee_id": employee_id}, status_code=404)


@router.get("/attendance")
async def get_attendance(
    employee_id: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
) -> JSONResponse:
    """根据员工 ID 与日期范围查询考勤。"""
    items = [
        a
        for a in _load("attendance.json")
        if a["emp_id"] == employee_id and start_date <= a["date"] <= end_date
    ]
    work_days = sum(1 for a in items if a["status"] in ("normal", "late"))
    late_days = sum(1 for a in items if a["status"] == "late")
    return JSONResponse(
        {
            "employee_id": employee_id,
            "items": items,
            "summary": {"work_days": work_days, "late_days": late_days, "absent_days": 0},
        }
    )


@router.get("/orders")
async def get_orders(
    start_date: str = Query(...), end_date: str = Query(...), customer: str | None = Query(None)
) -> JSONResponse:
    """根据日期范围（可选客户）查询订单。"""
    items = [
        o
        for o in _load("orders.json")
        if start_date <= o["date"] <= end_date and (customer is None or o["customer"] == customer)
    ]
    gross = sum(o["amount"] for o in items)
    refund = sum(o["amount"] for o in items if o["status"] == "refund")
    return JSONResponse(
        {
            "items": items,
            "summary": {
                "count": len(items),
                "gross_amount": gross,
                "refund_amount": refund,
                "net_amount": gross - refund,
            },
        }
    )

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pyodbc
from agents import function_tool

from ..config import settings

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "dept_supplier_actuals.sql"
DEPT_SUPPLIER_SQL = SQL_PATH.read_text(encoding="utf-8")


@function_tool
def get_department_supplier_actuals(
    department: str,
    fiscal_year: int | None = None,
) -> str:
    """Fetch actual expenditure data for a department and fiscal year from PeopleSoft."""

    if not department:
        return "Please provide a department ID."

    fy = fiscal_year or 2026
    conn_str = settings.fin_connection_string
    if not conn_str:
        return "FIN_STR connection string is not configured on the server."

    try:
        with pyodbc.connect(conn_str, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute(DEPT_SUPPLIER_SQL, department, fy)
            rows = cursor.fetchmany(20)
    except Exception as exc:  # pragma: no cover - safety net
        return f"Failed to query PeopleSoft: {exc}"

    if not rows:
        return f"No actuals were found for department {department} in fiscal year {fy}."

    headers = [
        "vendor_id",
        "vendor_name",
        "description",
        "fiscal_year",
        "fund_code",
        "program_code",
        "account",
        "operating_unit",
        "deptid",
        "project_id",
        "business_unit_pc",
        "amount",
    ]
    lines: list[str] = []
    for row in rows:
        data = dict(zip(headers, row, strict=False))
        line = textwrap.dedent(
            f"""
            Vendor {data['vendor_id']} ({data['vendor_name']}), account {data['account']}:
            amount ${data['amount']:,.2f} in FY{data['fiscal_year']} for department {data['deptid']}.
            """
        ).strip()
        lines.append(line)

    return "\n\n".join(lines)

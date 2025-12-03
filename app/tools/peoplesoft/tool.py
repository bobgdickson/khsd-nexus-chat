from typing import List, Union, Literal, Optional
from pydantic import BaseModel

from .sql_builder import build_sql
from .db import run_query
from agents import function_tool


class FinanceFilter(BaseModel):
    field: str
    op: Literal["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "BETWEEN"]
    value: Union[str, int, float, List[Union[str, int, float]]]

class FinanceOrderBy(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"

class FinanceGroupBy(BaseModel):
    field: str

@function_tool
def query_ps_finance(
    entity: str,
    select: List[str],
    filters: Optional[List[FinanceFilter]] = None,
    limit: int = 1000,
    order_by: Optional[List[FinanceOrderBy]] = None,
    group_by: Optional[List[FinanceGroupBy]] = None,
) -> dict:
    """
    KHSD PeopleSoft Finance querying (via query_ps_finance):

    You have access to a tool named query_ps_finance that lets you query logical finance entities from KHSD's PeopleSoft Finance system.

    Currently supported entity:
    - "gl_summary": general ledger balances by business unit, ledger, fiscal year, accounting period, and chartfields.

    Logical fields for gl_summary:
    - "business_unit"      (GL business unit, assume KERNH if not specified)
    - "fiscal_year"        (accounting year, assume current fiscal year which runs from July to June)
    - "period"             (accounting period)
    - "object"             (GL account)
    - "department"
    - "fund"
    - "resource"           (program code)
    - "class"
    - "project"
    - "amount"             (posted balance for that combination)

    Usage guidelines:
    - Use "gl_summary" when the user asks about balances, totals, or summary by year/period, account, dept, fund, program, etc.
    - Always include a fiscal_year filter when the user mentions a specific year.
    - When user says "this year" or "current fiscal year", interpret as the current accounting year (you may approximate if not given).
    - If the user asks for “by account and department”, include "object", "department" in select.
    - Keep select fields minimal but sufficient to answer the question.
    - Provide group_by fields when requesting aggregations (e.g., totals by department).
    - Use reasonable limits (e.g. <= 5000 rows). Let the backend enforce a hard max.

    Examples:

    1) User: "Show me actuals by account and department for fiscal year 2024."

    Call query_ps_finance with:
    - entity: "gl_summary"
    - select: ["business_unit", "fiscal_year", "period", "account", "department", "amount"]
    - filters:
    - fiscal_year = 2024
    - business_unit = "KERNH"
    - order_by: object asc, department asc

    2) User: "Total for account 4301 in FY 2023 by department."

    Call query_ps_finance with:
    - entity: "gl_summary"
    - select: ["fiscal_year", "account", "department", "amount"]
    - filters:
    - fiscal_year = 2023
    - business_unit = "KERNH"
    - account = "4300"
    - order_by: ["department" asc]

    3) User: "Summarize FY 2024 amounts grouped by department."

    Call query_ps_finance with:
    - entity: "gl_summary"
    - select: ["fiscal_year", "department", "amount_sum"] (define amount_sum as an aggregate in entities.py)
    - filters:
    - fiscal_year = 2024
    - group_by: [{"field": "fiscal_year"}, {"field": "department"}]
"""

    # Agents may pass validated BaseModel instances while tests often pass dicts.
    # Normalize to dict form (filters/order_by) or string list (group_by) so build_sql
    # can treat both the same way.
    normalized_filters = [
        f.model_dump() if isinstance(f, BaseModel) else f  # type: ignore[arg-type]
        for f in (filters or [])
    ]
    normalized_order_by = [
        o.model_dump() if isinstance(o, BaseModel) else o  # type: ignore[arg-type]
        for o in (order_by or [])
    ]
    normalized_group_by: List[str] = []
    for g in group_by or []:
        if isinstance(g, FinanceGroupBy):
            normalized_group_by.append(g.field)
        elif isinstance(g, str):
            normalized_group_by.append(g)
        else:
            field_name = g.get("field")
            if not field_name:
                raise ValueError("Group-by entries must include a 'field'")
            normalized_group_by.append(field_name)

    try:
        sql, params = build_sql(
            entity,
            select,
            normalized_filters,
            limit,
            normalized_order_by,
            normalized_group_by,
        )
    except ValueError as e:
        return {"error": str(e)}

    rows = run_query(sql, params)

    return {
        "entity": entity,
        "row_count": len(rows),
        "rows": rows,
    }

if __name__ == "__main__":
    # Simple test
    args = {
        "entity": "GL_SUMMARY",
        "select": ["fiscal_year", "department", "amount_sum"],
        "filters": [
            {"field": "fiscal_year", "op": "=", "value": 2024},
            {"field": "department", "op": "=", "value": "5500"},
        ],
        "limit": 10,
        "order_by": [{"field": "amount_sum", "direction": "desc"}],
        "group_by": ["fiscal_year", "department"],
    }
    result = query_ps_finance(args)
    print(result)

from __future__ import annotations

from typing import Dict, List

from agents import function_tool

from .db import run_query

MAX_RESULTS = 50

CHARTFIELD_SPECS: Dict[str, Dict[str, object]] = {
    "account": {
        "label": "GL account",
        "table": "PS_GL_ACCOUNT_TBL",
        "alias": "acct",
        "code": "ACCOUNT",
        "description": "DESCR",
        "filters": [
            "acct.SETID = 'SHARE'",
            "acct.EFF_STATUS = 'A'",
            "acct.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_GL_ACCOUNT_TBL A_ED "
            "WHERE A_ED.SETID = acct.SETID "
            "AND A_ED.ACCOUNT = acct.ACCOUNT "
            "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
        ],
    },
    "department": {
        "label": "Department",
        "table": "PS_DEPT_TBL",
        "alias": "dpt",
        "code": "DEPTID",
        "description": "DESCR",
        "filters": [
            "dpt.SETID = 'SHARE'",
            "dpt.EFF_STATUS = 'A'",
            "dpt.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_DEPT_TBL A_ED "
            "WHERE A_ED.SETID = dpt.SETID "
            "AND A_ED.DEPTID = dpt.DEPTID "
            "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
        ],
    },
    "fund": {
        "label": "Fund",
        "table": "PS_FUND_TBL",
        "alias": "fnd",
        "code": "FUND_CODE",
        "description": "DESCR",
        "filters": [
            "fnd.SETID = 'SHARE'",
            "fnd.EFF_STATUS = 'A'",
            "fnd.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_FUND_TBL A_ED "
            "WHERE A_ED.SETID = fnd.SETID "
            "AND A_ED.FUND_CODE = fnd.FUND_CODE "
            "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
        ],
    },
    "resource": {
        "label": "Program/resource",
        "table": "PS_PROGRAM_TBL",
        "alias": "prg",
        "code": "PROGRAM_CODE",
        "description": "DESCR",
        "filters": [
            "prg.SETID = 'SHARE'",
            "prg.EFF_STATUS = 'A'",
            "prg.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_PROGRAM_TBL A_ED "
            "WHERE A_ED.SETID = prg.SETID "
            "AND A_ED.PROGRAM_CODE = prg.PROGRAM_CODE "
            "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
        ],
    },
    "site": {
        "label": "Operating unit / site",
        "table": "PS_OPER_UNIT_TBL",
        "alias": "ou",
        "code": "OPERATING_UNIT",
        "description": "DESCR",
        "filters": [
            "ou.SETID = 'SHARE'",
            "ou.EFF_STATUS = 'A'",
            "ou.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_OPER_UNIT_TBL A_ED "
            "WHERE A_ED.SETID = ou.SETID "
            "AND A_ED.OPERATING_UNIT = ou.OPERATING_UNIT "
            "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
        ],
    },
    "class": {
        "label": "Class field",
        "table": "PS_CLASS_CF_TBL",
        "alias": "cls",
        "code": "CLASS_FLD",
        "description": "DESCR",
        "filters": [
            "cls.SETID = 'SHARE'",
            "cls.EFF_STATUS = 'A'",
            "cls.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_CLASS_CF_TBL A_ED "
            "WHERE A_ED.SETID = cls.SETID "
            "AND A_ED.CLASS_FLD = cls.CLASS_FLD "
            "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
        ],
    },
    "project": {
        "label": "Project",
        "table": "PS_PROJECT",
        "alias": "prj",
        "code": "PROJECT_ID",
        "description": "DESCR",
        "filters": [],
    },
}

CHARTFIELD_ALIASES: Dict[str, str] = {
    "acct": "account",
    "account": "account",
    "gl_account": "account",
    "dept": "department",
    "department": "department",
    "fund": "fund",
    "fund_code": "fund",
    "resource": "resource",
    "program": "resource",
    "program_code": "resource",
    "site": "site",
    "operating_unit": "site",
    "opp_unit": "site",
    "class": "class",
    "class_field": "class",
    "project": "project",
    "project_id": "project",
}


def _normalize_chartfield(value: str) -> str | None:
    key = (value or "").strip().lower()
    if key in CHARTFIELD_SPECS:
        return key
    return CHARTFIELD_ALIASES.get(key)


@function_tool
def search_chartfield_codes(chartfield: str, query: str, max_results: int = 20) -> dict:
    """
    Search chartfield master tables (accounts, departments, funds, programs/resources, operating units, classes, or projects)
    by code or description.

    Parameters:
        - chartfield: Which chartfield to search. Accepted values include account/acct, department/dept, fund, resource/program,
          site/operating_unit, class, or project.
        - query: Plain language text or partial code to match (case-insensitive).
        - max_results: Optional cap (1-50) on number of rows returned.

    Returns a JSON object with the matched codes and descriptions (e.g., [{"code": "4300", "description": "Postage"}]).
    Use this tool when the user needs to translate human terms ("postage", "nursing supplies", "campus maintenance") into the
    correct PeopleSoft chartfield codes.
    """

    if not query or not query.strip():
        return {"error": "Please provide a non-empty query string to search."}

    normalized = _normalize_chartfield(chartfield)
    if not normalized or normalized not in CHARTFIELD_SPECS:
        valid = ", ".join(sorted(CHARTFIELD_SPECS))
        return {"error": f"Unknown chartfield '{chartfield}'. Valid options: {valid}"}

    spec = CHARTFIELD_SPECS[normalized]
    alias = spec["alias"]
    code_col = f"{alias}.{spec['code']}"
    descr_col = f"{alias}.{spec['description']}"

    filters: List[str] = list(spec.get("filters", []))  # type: ignore[arg-type]

    search_value = f"%{query.strip()}%"
    search_clause = f"(UPPER({code_col}) LIKE UPPER(%s) OR UPPER({descr_col}) LIKE UPPER(%s))"
    filters.append(search_clause)

    where_sql = f" WHERE {' AND '.join(filters)}" if filters else ""

    limit = max(1, min(max_results, MAX_RESULTS))
    select_cols = f"{code_col} AS code, {descr_col} AS description"
    sql = f"SELECT TOP {limit} {select_cols} FROM {spec['table']} {alias}{where_sql} ORDER BY {code_col}"

    try:
        rows = run_query(sql, [search_value, search_value])
    except Exception as exc:  # pragma: no cover - safety net
        return {"error": f"Failed to search chartfields: {exc}"}

    return {
        "chartfield": normalized,
        "query": query,
        "row_count": len(rows),
        "rows": rows,
    }

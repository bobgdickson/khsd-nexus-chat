from typing import Any, Dict, List, Sequence
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result
from sqlalchemy.pool import QueuePool
import sqlalchemy

from app.config import settings

def engine_fin():
    """Return SQLAlchemy URL for the PeopleSoft finance database."""
    if not settings.fin_connection_string:
        raise ValueError("FIN_STR environment variable is not set.")
    return sqlalchemy.engine.URL.create(
        "mssql+pyodbc",
        query={"odbc_connect": quote_plus(settings.fin_connection_string)},
    )

engine: Engine = create_engine(
    engine_fin(),
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=600,
)

def run_query(sql: str, params: Sequence[Any] | None = None) -> List[Dict[str, Any]]:
    """
    Execute a read-only SQL query against the FIN database and return rows as list[dict].

    This helper expects:
    - SQL text with *positional* parameters, written using '%s' placeholders or already
      using :p0, :p1, ... SQLAlchemy-style binds.
    - 'params' is a flat sequence of positional values.

    It normalizes '%s' placeholders to :p0/:p1/... so SQLAlchemy can bind them correctly.
    """
    params = list(params or [])

    bind_params: Dict[str, Any] = {}

    # If upstream SQL uses '%s', convert to :p0, :p1, ...
    if "%s" in sql:
        parts = sql.split("%s")
        new_sql_parts: List[str] = []
        for i, part in enumerate(parts):
            new_sql_parts.append(part)
            if i < len(parts) - 1:
                placeholder = f":p{i}"
                new_sql_parts.append(placeholder)
                # bind key is p{i} (without colon)
                bind_params[f"p{i}"] = params[i] if i < len(params) else None
        sql = "".join(new_sql_parts)
    else:
        # If no '%s', assume caller already used :p0-style placeholders.
        for idx, value in enumerate(params):
            bind_params[f"p{idx}"] = value

    stmt = text(sql)

    rows: List[Dict[str, Any]] = []
    with engine.connect() as conn:
        result: Result = conn.execute(stmt, bind_params)
        for row in result.mappings():
            rows.append(dict(row))

    return rows

if __name__ == "__main__":
    # Simple test
    test_sql = "SELECT TOP 10 gl.FISCAL_YEAR AS fiscal_year, gl.DEPTID AS department, dpt.DESCR AS dept_descr, SUM(gl.POSTED_TOTAL_AMT) AS amount_sum " \
    "FROM PS_LEDGER gl LEFT JOIN PS_GL_ACCOUNT_TBL acct ON acct.SETID = 'SHARE' AND acct.ACCOUNT = gl.ACCOUNT AND acct.EFF_STATUS = 'A' " \
    "AND acct.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_GL_ACCOUNT_TBL A_ED WHERE A_ED.SETID = acct.SETID " \
    "AND A_ED.ACCOUNT = acct.ACCOUNT AND A_ED.EFFDT <= CAST(GETDATE() AS DATE)) LEFT JOIN PS_DEPT_TBL dpt ON dpt.SETID = 'SHARE' AND dpt.DEPTID = gl.DEPTID " \
    "AND dpt.EFF_STATUS = 'A' AND dpt.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_DEPT_TBL A_ED WHERE A_ED.SETID = dpt.SETID " \
    "AND A_ED.DEPTID = dpt.DEPTID AND A_ED.EFFDT <= CAST(GETDATE() AS DATE)) LEFT JOIN PS_FUND_TBL fnd ON fnd.SETID = 'SHARE' " \
    "AND fnd.FUND_CODE = gl.FUND_CODE AND fnd.EFF_STATUS = 'A' AND fnd.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_FUND_TBL A_ED WHERE A_ED.SETID = fnd.SETID " \
    "AND A_ED.FUND_CODE = fnd.FUND_CODE AND A_ED.EFFDT <= CAST(GETDATE() AS DATE)) LEFT JOIN PS_PROGRAM_TBL prg ON prg.SETID = 'SHARE' " \
    "AND prg.PROGRAM_CODE = gl.PROGRAM_CODE AND prg.EFF_STATUS = 'A' AND prg.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_PROGRAM_TBL A_ED WHERE A_ED.SETID = prg.SETID " \
    "AND A_ED.PROGRAM_CODE = prg.PROGRAM_CODE AND A_ED.EFFDT <= CAST(GETDATE() AS DATE)) LEFT JOIN PS_OPER_UNIT_TBL ou ON ou.SETID = 'SHARE' " \
    "AND ou.OPERATING_UNIT = gl.OPERATING_UNIT AND ou.EFF_STATUS = 'A' AND ou.EFFDT = (SELECT MAX(A_ED.EFFDT) " \
    "FROM PS_OPER_UNIT_TBL A_ED WHERE A_ED.SETID = ou.SETID AND A_ED.OPERATING_UNIT = ou.OPERATING_UNIT AND A_ED.EFFDT <= CAST(GETDATE() AS DATE)) " \
    "LEFT JOIN PS_CLASS_CF_TBL cls ON cls.SETID = 'SHARE' AND cls.CLASS_FLD = gl.CLASS_FLD AND cls.EFF_STATUS = 'A' AND cls.EFFDT = (SELECT MAX(A_ED.EFFDT) " \
    "FROM PS_CLASS_CF_TBL A_ED WHERE A_ED.SETID = cls.SETID AND A_ED.CLASS_FLD = cls.CLASS_FLD AND A_ED.EFFDT <= CAST(GETDATE() AS DATE)) " \
    "LEFT JOIN PS_PROJECT prj ON prj.BUSINESS_UNIT = gl.BUSINESS_UNIT AND prj.PROJECT_ID = gl.PROJECT_ID WHERE gl.ACCOUNTING_PERIOD NOT IN ('999') " \
    "AND gl.FISCAL_YEAR = %s AND gl.DEPTID = %s GROUP BY gl.FISCAL_YEAR, gl.DEPTID, dpt.DESCR ORDER BY SUM(gl.POSTED_TOTAL_AMT) DESC"
    test_params = [2024, "5500"]
    result_rows = run_query(test_sql, test_params)
    for r in result_rows:
        print(r)
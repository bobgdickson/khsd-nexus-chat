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
    test_sql = "SELECT TOP 5 FISCAL_YEAR, DEPTID, ACCOUNT, POSTED_TOTAL_AMT FROM PS_LEDGER WHERE FISCAL_YEAR = %s AND DEPTID = %s ORDER BY POSTED_TOTAL_AMT DESC"
    test_params = [2024, "5500"]
    result_rows = run_query(test_sql, test_params)
    for r in result_rows:
        print(r)
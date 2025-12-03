from typing import Dict, Any, List, Tuple, Union
from .entities import ENTITIES

OP_MAP = {
    "=": "=",
    "!=": "!=",
    ">": ">",
    "<": "<",
    ">=": ">=",
    "<=": "<=",
    "LIKE": "LIKE",
    "IN": "IN",
    "BETWEEN": "BETWEEN",
}

MAX_LIMIT = 5000  # hard cap, adjust as you like

def build_sql(
    entity: str,
    select: List[str],
    filters: List[Dict[str, Any]] | None,
    limit: int | None,
    order_by: List[Dict[str, str]] | None,
    group_by: List[str] | None = None,
) -> Tuple[str, List[Any]]:
    entity = entity.lower()
    if entity not in ENTITIES:
        raise ValueError(f"Unknown entity '{entity}'")

    cfg = ENTITIES[entity]
    table = cfg["table"]
    alias = cfg.get("alias", "t")
    field_map: Dict[str, Union[str, Dict[str, Any], None]] = cfg["field_map"]

    def _get_mapping(field: str) -> Union[str, Dict[str, Any]]:
        mapping = field_map.get(field)
        if not mapping:
            raise ValueError(f"Field '{field}' is not available for entity '{entity}'")
        return mapping

    def _select_expression(field: str) -> str:
        mapping = _get_mapping(field)
        if isinstance(mapping, str):
            return f"{alias}.{mapping} AS {field}"
        expression = mapping.get("expression")
        if expression:
            expr_sql = expression.format(alias=alias)
            return f"{expr_sql} AS {field}"
        column = mapping.get("column")
        if column:
            return f"{alias}.{column} AS {field}"
        raise ValueError(f"Field '{field}' is not selectable for entity '{entity}'")

    def _column_reference(field: str, purpose: str) -> str:
        mapping = _get_mapping(field)
        if isinstance(mapping, str):
            return f"{alias}.{mapping}"
        column = mapping.get("column")
        if column:
            return f"{alias}.{column}"
        raise ValueError(f"Field '{field}' cannot be used in {purpose} for entity '{entity}'")

    eff_limit = min(limit or 1000, MAX_LIMIT)

    # Map logical select fields to physical columns
    columns: List[str] = []
    for f in select:
        columns.append(_select_expression(f))

    if not columns:
        raise ValueError("No select columns specified")

    # For SQL Server, apply TOP at the select level for limit.
    top_clause = f"TOP {eff_limit} " if eff_limit is not None else ""
    sql = f"SELECT {top_clause}{', '.join(columns)} FROM {table} {alias}"

    where_clauses: List[str] = []
    params: List[Any] = []

    # default filters
    for df in cfg.get("default_filters", []):
        where_clauses.append(df["sql"])
        params.extend(df.get("params", []))

    # user filters
    filters = filters or []
    for flt in filters:
        field = flt["field"]
        op = flt["op"]
        value = flt["value"]

        col = _column_reference(field, "filters")

        if op not in OP_MAP:
            raise ValueError(f"Unsupported operator '{op}'")

        if op == "IN":
            if not isinstance(value, (list, tuple)):
                raise ValueError("IN operator requires a list value")
            if not value:
                where_clauses.append("1=0")
            else:
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"{col} IN ({placeholders})")
                params.extend(value)
        elif op == "BETWEEN":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValueError("BETWEEN operator requires [low, high]")
            where_clauses.append(f"{col} BETWEEN %s AND %s")
            params.extend(value)
        else:
            where_clauses.append(f"{col} {OP_MAP[op]} %s")
            params.append(value)

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    # GROUP BY
    group_clauses: List[str] = []
    for grp_field in group_by or []:
        group_clauses.append(_column_reference(grp_field, "group by"))
    if group_clauses:
        sql += " GROUP BY " + ", ".join(group_clauses)

    # ORDER BY
    if order_by:
        order_clauses: List[str] = []
        for ob in order_by:
            field = ob["field"]
            direction = ob.get("direction", "asc").lower()
            try:
                col = _column_reference(field, "order by")
            except ValueError:
                mapping = field_map.get(field)
                if isinstance(mapping, dict) and mapping.get("expression"):
                    col = field  # fall back to alias for computed fields
                else:
                    raise
            dir_sql = "DESC" if direction == "desc" else "ASC"
            order_clauses.append(f"{col} {dir_sql}")
        if order_clauses:
            sql += " ORDER BY " + ", ".join(order_clauses)

    return sql, params

if __name__ == "__main__":
    # Simple test
    test_entity = "gl_summary"
    test_select = ["fiscal_year", "department", "amount_sum"]
    test_filters = [
        {"field": "fiscal_year", "op": "=", "value": 2024},
        {"field": "department", "op": "=", "value": "5500"},
    ]
    test_limit = 10
    test_order_by = [{"field": "amount_sum", "direction": "desc"}]
    test_group_by = ["fiscal_year", "department"]

    sql, params = build_sql(
        test_entity,
        test_select,
        test_filters,
        test_limit,
        test_order_by,
        test_group_by,
    )
    print("Generated SQL:")
    print(sql)
    print("Parameters:")
    print(params)

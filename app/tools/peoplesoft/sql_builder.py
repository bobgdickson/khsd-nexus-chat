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
    field_map: Dict[str, Union[str, Dict[str, Any]]] = cfg["field_map"]
    joins_cfg: List[Dict[str, Any]] = cfg.get("joins", [])

    # Map logical join fields (descrs) to their full expressions (e.g. "acct.DESCR")
    join_field_map: Dict[str, str] = {}
    for j in joins_cfg:
        for logical, expr in j.get("fields", {}).items():
            join_field_map[logical] = expr

    def _get_mapping(field: str) -> Union[str, Dict[str, Any]]:
        if field in field_map:
            return field_map[field]
        if field in join_field_map:
            return {"join_expression": join_field_map[field]}
        raise ValueError(f"Field '{field}' is not available for entity '{entity}'")

    def _select_expression(field: str) -> str:
        mapping = _get_mapping(field)

        if isinstance(mapping, str):
            return f"{alias}.{mapping} AS {field}"

        # Expression on base table (e.g., amount_sum)
        expression = mapping.get("expression")
        if expression:
            expr_sql = expression.format(alias=alias)
            return f"{expr_sql} AS {field}"

        # Join-based field
        join_expr = mapping.get("join_expression")
        if join_expr:
            return f"{join_expr} AS {field}"

        # Column on base table
        column = mapping.get("column")
        if column:
            return f"{alias}.{column} AS {field}"

        raise ValueError(f"Field '{field}' is not selectable for entity '{entity}'")

    def _column_reference(field: str, purpose: str) -> str:
        mapping = _get_mapping(field)

        if isinstance(mapping, str):
            return f"{alias}.{mapping}"

        expression = mapping.get("expression")
        if expression:
            return expression.format(alias=alias)

        join_expr = mapping.get("join_expression")
        if join_expr:
            return join_expr

        column = mapping.get("column")
        if column:
            return f"{alias}.{column}"

        raise ValueError(f"Field '{field}' cannot be used in {purpose} for entity '{entity}'")

    eff_limit = min(limit or 1000, MAX_LIMIT)

    # SELECT clause
    if not select:
        raise ValueError("No select columns specified")
    columns = [_select_expression(f) for f in select]

    top_clause = f"TOP {eff_limit} " if eff_limit is not None else ""
    sql = f"SELECT {top_clause}{', '.join(columns)} FROM {table} {alias}"

    # Always add all joins defined for the entity
    for j in joins_cfg:
        join_type = j.get("type", "LEFT").upper()
        join_table = j["table"]
        join_alias = j["alias"]
        on_conditions = j.get("on", [])
        on_sql = " AND ".join(on_conditions)
        sql += f" {join_type} JOIN {join_table} {join_alias} ON {on_sql}"

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
            col = _column_reference(field, "order by")
            dir_sql = "DESC" if direction == "desc" else "ASC"
            order_clauses.append(f"{col} {dir_sql}")
        if order_clauses:
            sql += " ORDER BY " + ", ".join(order_clauses)

    return sql, params

if __name__ == "__main__":
    test_entity = "gl_summary"
    test_select = ["fiscal_year", "department", "dept_descr", "amount_sum"]
    test_filters = [
        {"field": "fiscal_year", "op": "=", "value": 2024},
        {"field": "department", "op": "=", "value": "5500"},
    ]
    test_limit = 10
    test_order_by = [{"field": "amount_sum", "direction": "desc"}]
    test_group_by = ["fiscal_year", "department", "dept_descr"]

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
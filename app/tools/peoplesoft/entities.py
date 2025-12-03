GL_SUMMARY = {
    # Today this can be PS_LEDGER; later swap to KHSD_DW_GL_SUMMARY or a saved query.
    "table": "PS_LEDGER",
    "alias": "gl",
    # Logical -> physical column mapping
    "field_map": {
        "business_unit": "BUSINESS_UNIT",
        "ledger": "LEDGER",
        "fiscal_year": "FISCAL_YEAR",
        "period": "ACCOUNTING_PERIOD",
        "object": "ACCOUNT",
        "department": "DEPTID",
        "fund": "FUND_CODE",
        "resource": "PROGRAM_CODE",
        "class": "CLASS_FLD",
        "project": "PROJECT_ID",
        "amount": "POSTED_TOTAL_AMT",
        # Aggregates use SQL expressions; {alias} will be replaced with the entity alias.
        "amount_sum": {"expression": "SUM({alias}.POSTED_TOTAL_AMT)"},

        # Fake DW fields for later; for now you can either:
        # - leave them unmapped (and disallow their use), or
        # - map them to placeholder expressions or join them manually in SQL file.
        # When you have a DW view/table that already includes these, just update mappings.
        "account_descr": None,
        "dept_descr": None,
        "fund_descr": None,
        "program_descr": None,
    },
    # Optional default filters you always want (e.g. exclude weird ledgers)
    "default_filters": [
        # Example: {"sql": "gl.LEDGER != 'CLOSING'", "params": []},
    ],
}

ENTITIES = {
    "gl_summary": GL_SUMMARY,
}

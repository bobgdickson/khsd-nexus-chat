GL_SUMMARY = {
    "table": "PS_LEDGER",
    "alias": "gl",
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
        "amount_sum": {"expression": "SUM({alias}.POSTED_TOTAL_AMT)"},
        # IMPORTANT: do NOT put descr fields here with None
        # They will be provided via joins["fields"] only.
    },

    "joins": [
        {
            "name": "account",
            "type": "LEFT",
            "table": "PS_GL_ACCOUNT_TBL",
            "alias": "acct",
            "on": [
                "acct.SETID = 'SHARE'",
                "acct.ACCOUNT = gl.ACCOUNT",
                "acct.EFF_STATUS = 'A'",
                "acct.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_GL_ACCOUNT_TBL A_ED "
                "WHERE A_ED.SETID = acct.SETID "
                "AND A_ED.ACCOUNT = acct.ACCOUNT "
                "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
            ],
            "fields": {
                "account_descr": "acct.DESCR",
            },
        },
        {
            "name": "department",
            "type": "LEFT",
            "table": "PS_DEPT_TBL",
            "alias": "dpt",
            "on": [
                "dpt.SETID = 'SHARE'",
                "dpt.DEPTID = gl.DEPTID",
                "dpt.EFF_STATUS = 'A'",
                "dpt.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_DEPT_TBL A_ED "
                "WHERE A_ED.SETID = dpt.SETID "
                "AND A_ED.DEPTID = dpt.DEPTID "
                "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
            ],
            "fields": {
                "dept_descr": "dpt.DESCR",
            },
        },
        {
            "name": "fund",
            "type": "LEFT",
            "table": "PS_FUND_TBL",
            "alias": "fnd",
            "on": [
                "fnd.SETID = 'SHARE'",
                "fnd.FUND_CODE = gl.FUND_CODE",
                "fnd.EFF_STATUS = 'A'",
                "fnd.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_FUND_TBL A_ED "
                "WHERE A_ED.SETID = fnd.SETID "
                "AND A_ED.FUND_CODE = fnd.FUND_CODE "
                "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
            ],
            "fields": {
                "fund_descr": "fnd.DESCR",
            },
        },
        {
            "name": "program",
            "type": "LEFT",
            "table": "PS_PROGRAM_TBL",
            "alias": "prg",
            "on": [
                "prg.SETID = 'SHARE'",
                "prg.PROGRAM_CODE = gl.PROGRAM_CODE",
                "prg.EFF_STATUS = 'A'",
                "prg.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_PROGRAM_TBL A_ED "
                "WHERE A_ED.SETID = prg.SETID "
                "AND A_ED.PROGRAM_CODE = prg.PROGRAM_CODE "
                "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
            ],
            "fields": {
                "resource_descr": "prg.DESCR",
            },
        },
        {
            "name": "operating_unit",
            "type": "LEFT",
            "table": "PS_OPER_UNIT_TBL",
            "alias": "ou",
            "on": [
                "ou.SETID = 'SHARE'",
                "ou.OPERATING_UNIT = gl.OPERATING_UNIT",
                "ou.EFF_STATUS = 'A'",
                "ou.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_OPER_UNIT_TBL A_ED "
                "WHERE A_ED.SETID = ou.SETID "
                "AND A_ED.OPERATING_UNIT = ou.OPERATING_UNIT "
                "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
            ],
            "fields": {
                "site_descr": "ou.DESCR",
            },
        },
        {
            "name": "class",
            "type": "LEFT",
            "table": "PS_CLASS_CF_TBL",
            "alias": "cls",
            "on": [
                "cls.SETID = 'SHARE'",
                "cls.CLASS_FLD = gl.CLASS_FLD",
                "cls.EFF_STATUS = 'A'",
                "cls.EFFDT = (SELECT MAX(A_ED.EFFDT) FROM PS_CLASS_CF_TBL A_ED "
                "WHERE A_ED.SETID = cls.SETID "
                "AND A_ED.CLASS_FLD = cls.CLASS_FLD "
                "AND A_ED.EFFDT <= CAST(GETDATE() AS DATE))",
            ],
            "fields": {
                "class_descr": "cls.DESCR",
            },
        },
        {
            "name": "project",
            "type": "LEFT",
            "table": "PS_PROJECT",
            "alias": "prj",
            "on": [
                "prj.BUSINESS_UNIT = gl.BUSINESS_UNIT",
                "prj.PROJECT_ID = gl.PROJECT_ID",
            ],
            "fields": {
                "project_descr": "prj.DESCR",
            },
        },
    ],

    "default_filters": [
        {"sql": "gl.ACCOUNTING_PERIOD NOT IN ('999')", "params": []},
    ],
}

ENTITIES = {
    "gl_summary": GL_SUMMARY,
}
import random

def detect_types(df):
    """Detect column types: numeric, date, text"""
    types = {}
    for col in df.columns:
        if df[col].dtype in ["int64", "float64"]:
            types[col] = "numeric"
        else:
            try:
                import pandas as pd
                pd.to_datetime(df[col].dropna().head(10))
                types[col] = "date"
            except:
                types[col] = "text"
    return types


def pick_val(df, col):
    """Get a sample non-null value from a column"""
    vals = df[col].dropna().unique()
    return str(vals[0]) if len(vals) > 0 else "SampleValue"


def generate_level1(tables: dict) -> list:
    """Generate Level 1 questions: SELECT, WHERE, GROUP BY, aggregations"""
    questions = []

    for t, df in tables.items():
        cols = list(df.columns)
        types = detect_types(df)
        nums  = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        dates = [c for c in cols if types[c] == "date"]
        c0 = cols[0]
        c1 = cols[1] if len(cols) > 1 else cols[0]
        n   = nums[0]  if nums  else None
        tx  = texts[0] if texts else None
        tx2 = texts[1] if len(texts) > 1 else None
        sv  = pick_val(df, tx or c0)
        threshold = float(df[n].dropna().mean()) if n else 100
        threshold = round(threshold, 2)

        def add(concept, question, answer, hint):
            questions.append({"concept": concept, "question": question,
                              "sample_answer": answer, "hint": hint})

        add("SELECT *", f'Retrieve all records from the "{t}" table.',
            f"SELECT * FROM {t};",
            "SELECT * fetches every column and every row.")

        add("SELECT columns", f'Fetch only "{c0}" and "{c1}" from "{t}".',
            f"SELECT {c0}, {c1}\nFROM {t};",
            "List specific column names after SELECT, comma-separated.")

        add("DISTINCT", f'Find all unique values of "{c0}" in "{t}".',
            f"SELECT DISTINCT {c0}\nFROM {t};",
            "DISTINCT removes duplicate values from results.")

        add("LIMIT", f'Get the first 10 records from "{t}".',
            f"SELECT *\nFROM {t}\nLIMIT 10;",
            "LIMIT restricts how many rows are returned.")

        add("ORDER BY ASC", f'List all records from "{t}" ordered by "{c0}" ascending.',
            f"SELECT *\nFROM {t}\nORDER BY {c0} ASC;",
            "ASC sorts from lowest to highest (default).")

        if tx:
            add("WHERE (text)", f'Get all records from "{t}" where "{tx}" equals \'{sv}\'.',
                f"SELECT *\nFROM {t}\nWHERE {tx} = '{sv}';",
                "Use single quotes around text values in WHERE.")

            add("LIKE", f'Find records in "{t}" where "{tx}" starts with the letter \'A\'.',
                f"SELECT *\nFROM {t}\nWHERE {tx} LIKE 'A%';",
                "% is a wildcard in LIKE. 'A%' means starts with A.")

            add("IS NULL", f'Find all records in "{t}" where "{tx}" has no value (NULL).',
                f"SELECT *\nFROM {t}\nWHERE {tx} IS NULL;",
                "Use IS NULL not = NULL. They behave differently.")

        if n:
            add("WHERE numeric", f'Get records from "{t}" where "{n}" is greater than {threshold}.',
                f"SELECT *\nFROM {t}\nWHERE {n} > {threshold};",
                "Use >, <, >=, <= for numeric comparisons.")

            add("ORDER BY DESC", f'List all records ordered by "{n}" from highest to lowest.',
                f"SELECT *\nFROM {t}\nORDER BY {n} DESC;",
                "DESC sorts from highest to lowest.")

            add("TOP N", f'Get the top 5 records with the highest "{n}" from "{t}".',
                f"SELECT *\nFROM {t}\nORDER BY {n} DESC\nLIMIT 5;",
                "Combine ORDER BY DESC with LIMIT to get top N records.")

            add("COUNT", f'Count the total number of records in "{t}".',
                f"SELECT COUNT(*) AS total_records\nFROM {t};",
                "COUNT(*) counts all rows including NULLs.")

            add("SUM", f'Calculate the total of "{n}" across all records in "{t}".',
                f"SELECT SUM({n}) AS total_{n}\nFROM {t};",
                "SUM() adds up all values in a numeric column.")

            add("AVG", f'Find the average value of "{n}" in "{t}".',
                f"SELECT ROUND(AVG({n})::numeric, 2) AS avg_{n}\nFROM {t};",
                "AVG() calculates the mean, ignoring NULLs.")

            add("MIN MAX", f'Find the smallest and largest "{n}" in "{t}".',
                f"SELECT MIN({n}) AS min_val, MAX({n}) AS max_val\nFROM {t};",
                "MIN() and MAX() can be used together in one SELECT.")

            add("BETWEEN", f'Get records from "{t}" where "{n}" is between 50 and 200.',
                f"SELECT *\nFROM {t}\nWHERE {n} BETWEEN 50 AND 200;",
                "BETWEEN is inclusive — both boundary values are included.")

            if tx:
                add("GROUP BY SUM", f'Find the total "{n}" for each "{tx}" in "{t}".',
                    f"SELECT {tx}, SUM({n}) AS total\nFROM {t}\nGROUP BY {tx};",
                    "GROUP BY groups rows; use with aggregate functions.")

                add("GROUP BY COUNT", f'Count how many records exist for each "{tx}" in "{t}".',
                    f"SELECT {tx}, COUNT(*) AS cnt\nFROM {t}\nGROUP BY {tx};",
                    "COUNT(*) with GROUP BY counts rows in each group.")

                add("GROUP BY AVG", f'Find average "{n}" per "{tx}", sorted highest first.',
                    f"SELECT {tx}, AVG({n}) AS avg_val\nFROM {t}\nGROUP BY {tx}\nORDER BY avg_val DESC;",
                    "You can ORDER BY an alias from an aggregate function.")

                add("HAVING", f'Find all "{tx}" groups where total "{n}" exceeds {threshold}.',
                    f"SELECT {tx}, SUM({n}) AS total\nFROM {t}\nGROUP BY {tx}\nHAVING SUM({n}) > {threshold};",
                    "HAVING filters AFTER GROUP BY. WHERE filters BEFORE.")

                if tx2:
                    add("GROUP BY multiple", f'Count records grouped by "{tx}" and "{tx2}" in "{t}".',
                        f"SELECT {tx}, {tx2}, COUNT(*) AS cnt\nFROM {t}\nGROUP BY {tx}, {tx2};",
                        "All non-aggregated columns must appear in GROUP BY.")

        if dates:
            d = dates[0]
            add("EXTRACT year", f'Get records from "{t}" where "{d}" falls in the year 2023.',
                f"SELECT *\nFROM {t}\nWHERE EXTRACT(YEAR FROM {d}) = 2023;",
                "EXTRACT(YEAR FROM col) pulls just the year from a date.")

    random.shuffle(questions)
    return questions[:20]


def generate_level2(tables: dict) -> list:
    """Generate Level 2: JOINs, subqueries, CASE WHEN, COALESCE"""
    questions = []
    table_list = list(tables.items())

    for i, (t, df) in enumerate(table_list):
        cols  = list(df.columns)
        types = detect_types(df)
        nums  = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        n     = nums[0]  if nums  else None
        tx    = texts[0] if texts else None
        tx2   = texts[1] if len(texts) > 1 else None
        c0    = cols[0]
        sv    = pick_val(df, tx or c0)

        def add(concept, question, answer, hint):
            questions.append({"concept": concept, "question": question,
                              "sample_answer": answer, "hint": hint})

        # Cross-table JOINs
        others = [(tn, tdf) for j, (tn, tdf) in enumerate(table_list) if j != i]
        if others:
            t2, df2 = others[0]
            shared = next((c for c in cols if c in df2.columns), c0)

            add("INNER JOIN",
                f'Join "{t}" and "{t2}" on their common column "{shared}" and return all matching records.',
                f"SELECT a.*, b.*\nFROM {t} a\nINNER JOIN {t2} b ON a.{shared} = b.{shared};",
                "INNER JOIN returns only rows that match in both tables.")

            add("LEFT JOIN",
                f'Get all records from "{t}" with matching data from "{t2}". Keep "{t}" rows even with no match.',
                f"SELECT a.*, b.{df2.columns[0]}\nFROM {t} a\nLEFT JOIN {t2} b ON a.{shared} = b.{shared};",
                "LEFT JOIN keeps all left table rows. NULL where no match in right table.")

            add("LEFT JOIN anti-match",
                f'Find all records in "{t}" that have NO matching record in "{t2}".',
                f"SELECT a.*\nFROM {t} a\nLEFT JOIN {t2} b ON a.{shared} = b.{shared}\nWHERE b.{shared} IS NULL;",
                "After LEFT JOIN, filter WHERE right-side key IS NULL to find unmatched rows.")

            if n:
                add("JOIN + GROUP BY",
                    f'Join "{t}" and "{t2}", then find total "{n}" grouped by "{c0}".',
                    f"SELECT a.{c0}, SUM(a.{n}) AS total\nFROM {t} a\nINNER JOIN {t2} b ON a.{shared} = b.{shared}\nGROUP BY a.{c0};",
                    "After a JOIN, GROUP BY and aggregate normally.")

        if n and tx:
            add("Subquery WHERE",
                f'Find all records in "{t}" where "{n}" is above the table average.',
                f"SELECT *\nFROM {t}\nWHERE {n} > (SELECT AVG({n}) FROM {t});",
                "The subquery runs first and returns a single value for comparison.")

            add("Subquery SELECT",
                f'For every record in "{t}", show "{tx}", "{n}", and the overall average "{n}" as a column.',
                f"SELECT {tx}, {n},\n  (SELECT AVG({n}) FROM {t}) AS overall_avg\nFROM {t};",
                "A scalar subquery in SELECT runs once and returns one value per row.")

            add("CASE WHEN",
                f'Add a label: \'High\' if "{n}" > 100, \'Medium\' if > 50, else \'Low\'.',
                f"SELECT *,\n  CASE\n    WHEN {n} > 100 THEN 'High'\n    WHEN {n} > 50 THEN 'Medium'\n    ELSE 'Low'\n  END AS category\nFROM {t};",
                "CASE WHEN checks conditions in order, returns the first match.")

            add("IN",
                f'Get all records from "{t}" where "{tx}" is one of three specific values.',
                f"SELECT *\nFROM {t}\nWHERE {tx} IN ('Value1', 'Value2', 'Value3');",
                "IN is cleaner than writing multiple OR conditions.")

            add("NOT IN",
                f'Find records where "{tx}" is NOT one of those values.',
                f"SELECT *\nFROM {t}\nWHERE {tx} NOT IN ('Value1', 'Value2', 'Value3');",
                "NOT IN excludes any row matching a value in the list.")

            add("COALESCE",
                f'Replace NULL values in "{n}" with 0 for every row in "{t}".',
                f"SELECT *, COALESCE({n}, 0) AS {n}_filled\nFROM {t};",
                "COALESCE returns the first non-NULL argument.")

            add("EXISTS",
                f'Find records in "{t}" where a matching row with "{n}" > 100 exists.',
                f"SELECT *\nFROM {t} a\nWHERE EXISTS (\n  SELECT 1 FROM {t} b\n  WHERE b.{tx} = a.{tx}\n  AND b.{n} > 100\n);",
                "EXISTS checks if the subquery returns any row. Faster than IN on large data.")

            add("HAVING COUNT duplicates",
                f'Find all "{tx}" values that appear more than once in "{t}".',
                f"SELECT {tx}, COUNT(*) AS occurrences\nFROM {t}\nGROUP BY {tx}\nHAVING COUNT(*) > 1;",
                "HAVING COUNT(*) > 1 finds groups with duplicates.")

            add("CONCAT",
                f'Combine "{tx}" and "{n}" into one text column separated by \' - \'.',
                f"SELECT {tx} || ' - ' || CAST({n} AS TEXT) AS combined\nFROM {t};",
                "In PostgreSQL, || concatenates strings. Cast numbers to TEXT first.")

            if tx2:
                add("Multiple aggregates",
                    f'For each "{tx}" show count, total and average "{n}" in one query.',
                    f"SELECT {tx},\n  COUNT(*) AS cnt,\n  SUM({n}) AS total,\n  ROUND(AVG({n})::numeric, 2) AS avg_val\nFROM {t}\nGROUP BY {tx};",
                    "Multiple aggregate functions can appear in one SELECT with GROUP BY.")

    random.shuffle(questions)
    return questions[:20]


def generate_level3(tables: dict) -> list:
    """Generate Level 3: CTEs, window functions, CAST, date functions"""
    questions = []

    for t, df in tables.items():
        cols  = list(df.columns)
        types = detect_types(df)
        nums  = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        dates = [c for c in cols if types[c] == "date"]
        n     = nums[0]  if nums  else None
        n2    = nums[1]  if len(nums) > 1 else n
        tx    = texts[0] if texts else None
        c0    = cols[0]

        def add(concept, question, answer, hint):
            questions.append({"concept": concept, "question": question,
                              "sample_answer": answer, "hint": hint})

        if n and tx:
            add("CTE basic",
                f'Using a CTE, get average "{n}" per "{tx}", then select groups with average > 100.',
                f"WITH avg_by_group AS (\n  SELECT {tx}, AVG({n}) AS avg_val\n  FROM {t}\n  GROUP BY {tx}\n)\nSELECT * FROM avg_by_group\nWHERE avg_val > 100;",
                "Define CTE with WITH name AS (...), then query it like a regular table.")

            add("ROW_NUMBER()",
                f'Add a row number restarting per "{tx}" group, ordered by "{n}" descending.',
                f"SELECT *,\n  ROW_NUMBER() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS rn\nFROM {t};",
                "ROW_NUMBER() assigns sequential integers within each partition.")

            add("RANK()",
                f'Rank each record by "{n}" within each "{tx}" group. Ties get the same rank.',
                f"SELECT *,\n  RANK() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS rnk\nFROM {t};",
                "RANK() gives ties the same rank, then skips the next number.")

            add("DENSE_RANK()",
                f'Apply DENSE_RANK() by "{n}" within "{tx}" groups. Ranks must be consecutive.',
                f"SELECT *,\n  DENSE_RANK() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS dense_rnk\nFROM {t};",
                "DENSE_RANK() doesn't skip numbers after ties. Produces 1,2,2,3 not 1,2,2,4.")

            add("Top N per group",
                f'Using CTE + ROW_NUMBER(), return top 3 records per "{tx}" by highest "{n}".',
                f"WITH ranked AS (\n  SELECT *,\n    ROW_NUMBER() OVER (\n      PARTITION BY {tx}\n      ORDER BY {n} DESC\n    ) AS rn\n  FROM {t}\n)\nSELECT * FROM ranked WHERE rn <= 3;",
                "Classic interview pattern: CTE + ROW_NUMBER() + WHERE rn <= N.")

            add("Running total",
                f'Show running total of "{n}" within each "{tx}" group, ordered by "{c0}".',
                f"SELECT *,\n  SUM({n}) OVER (\n    PARTITION BY {tx}\n    ORDER BY {c0}\n  ) AS running_total\nFROM {t};",
                "SUM() OVER with ORDER BY creates a cumulative sum within each partition.")

            add("LAG()",
                f'For each record (ordered by "{c0}"), show the previous row\'s "{n}" value.',
                f"SELECT *,\n  LAG({n}, 1) OVER (ORDER BY {c0}) AS prev_{n}\nFROM {t};",
                "LAG(col, n) looks back n rows. Great for period-over-period comparisons.")

            add("LEAD()",
                f'For each record, show the next row\'s "{n}" value (ordered by "{c0}").',
                f"SELECT *,\n  LEAD({n}, 1) OVER (ORDER BY {c0}) AS next_{n}\nFROM {t};",
                "LEAD(col, n) looks forward n rows. Opposite of LAG.")

            add("NTILE()",
                f'Divide all records in "{t}" into 4 quartile buckets based on "{n}".',
                f"SELECT *,\n  NTILE(4) OVER (ORDER BY {n}) AS quartile\nFROM {t};",
                "NTILE(n) divides rows into n roughly equal groups numbered 1 to n.")

            add("PERCENT_RANK()",
                f'Calculate the percentile rank (0 to 1) of each "{n}" value in "{t}".',
                f"SELECT *,\n  ROUND(PERCENT_RANK() OVER (ORDER BY {n})::numeric, 4) AS pct_rank\nFROM {t};",
                "PERCENT_RANK() = (rank - 1) / (total - 1). Bottom row = 0, top = 1.")

            add("SUM() OVER ()",
                f'Show each record\'s "{n}" with the overall table average as a window column.',
                f"SELECT *,\n  AVG({n}) OVER () AS overall_avg\nFROM {t};",
                "OVER () with no PARTITION BY applies the function to the entire table.")

            add("Chained CTEs",
                f'Two CTEs: first get average "{n}" per "{tx}", then rank those groups.',
                f"WITH group_avg AS (\n  SELECT {tx}, AVG({n}) AS avg_val\n  FROM {t}\n  GROUP BY {tx}\n),\nranked AS (\n  SELECT *,\n    RANK() OVER (ORDER BY avg_val DESC) AS rnk\n  FROM group_avg\n)\nSELECT * FROM ranked;",
                "Separate CTEs with a comma. Each CTE can reference the ones before it.")

            add("CASE inside window",
                f'Label each record \'Above Avg\' or \'Below Avg\' based on "{n}" vs group average of "{tx}".',
                f"SELECT *,\n  CASE\n    WHEN {n} > AVG({n}) OVER (PARTITION BY {tx})\n    THEN 'Above Avg'\n    ELSE 'Below Avg'\n  END AS position\nFROM {t};",
                "A window function can go directly inside a CASE WHEN expression.")

            add("CAST + CONCAT",
                f'Cast "{n}" to TEXT and concatenate with "{tx}" separated by \' | \'.',
                f"SELECT {tx} || ' | ' || CAST({n} AS TEXT) AS label\nFROM {t};",
                "CAST(col AS TEXT) converts numbers to string. Use || for concat in PostgreSQL.")

            add("FILTER aggregate",
                f'In one query: total count of "{t}" and count only where "{n}" > 100.',
                f"SELECT\n  COUNT(*) AS total,\n  COUNT(*) FILTER (WHERE {n} > 100) AS above_100\nFROM {t};",
                "FILTER (WHERE ...) is a clean PostgreSQL way to do conditional aggregation.")

            if n2 and n2 != n:
                add("Multiple window functions",
                    f'Show ROW_NUMBER by "{n}" and running SUM of "{n2}", both partitioned by "{tx}".',
                    f"SELECT *,\n  ROW_NUMBER() OVER (PARTITION BY {tx} ORDER BY {n} DESC) AS rn,\n  SUM({n2}) OVER (PARTITION BY {tx} ORDER BY {c0}) AS running_total\nFROM {t};",
                    "You can have multiple OVER() clauses in one SELECT — each defines its own window.")

        if dates and n:
            d = dates[0]
            add("DATE_TRUNC",
                f'Truncate "{d}" to month level and count records + total "{n}" per month.',
                f"SELECT\n  DATE_TRUNC('month', {d}) AS month_start,\n  COUNT(*) AS cnt,\n  SUM({n}) AS total\nFROM {t}\nGROUP BY month_start\nORDER BY month_start;",
                "DATE_TRUNC('month', col) rounds down to the first day of the month.")

            add("EXTRACT + window",
                f'Show each record with year from "{d}" and total "{n}" for that year as a window column.',
                f"SELECT *,\n  EXTRACT(YEAR FROM {d}) AS yr,\n  SUM({n}) OVER (PARTITION BY EXTRACT(YEAR FROM {d})) AS yearly_total\nFROM {t};",
                "You can PARTITION BY a computed expression like EXTRACT(YEAR FROM date_col).")

    random.shuffle(questions)
    return questions[:20]


def get_questions(tables: dict, level: int) -> list:
    if level == 1:
        return generate_level1(tables)
    elif level == 2:
        return generate_level2(tables)
    else:
        return generate_level3(tables)

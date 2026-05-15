import random
import duckdb


def compute_expected(sql: str, df_dict: dict) -> dict:
    try:
        conn = duckdb.connect()
        for name, df in df_dict.items():
            conn.register(name, df)
        result = conn.execute(sql).fetchdf()
        conn.close()
        return {"expected_columns": list(result.columns), "expected_rows": len(result)}
    except Exception:
        return {"expected_columns": [], "expected_rows": None}


def detect_types(df):
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


def pick_val(df, col, n=1):
    vals = list(df[col].dropna().unique()[:5])
    return random.choice(vals) if vals else "SampleValue"


def pick_vals(df, col, n=3):
    vals = list(df[col].dropna().unique()[:10])
    random.shuffle(vals)
    return [str(v) for v in vals[:n]]


def r(templates):
    """Pick a random template from list"""
    return random.choice(templates)


DIFFICULTY_ORDER = {"Easy": 0, "Medium": 1, "Hard": 2, "MAANG": 3}


def generate_level1(tables):
    questions = []

    for t, df in tables.items():
        cols = list(df.columns)
        types = detect_types(df)
        nums = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        dates = [c for c in cols if types[c] == "date"]
        c0 = cols[0]
        c1 = cols[1] if len(cols) > 1 else cols[0]
        n = nums[0] if nums else None
        n2 = nums[1] if len(nums) > 1 else None
        tx = texts[0] if texts else None
        tx2 = texts[1] if len(texts) > 1 else None
        threshold = round(float(df[n].dropna().mean()), 2) if n else 100
        threshold2 = round(threshold * 1.5, 2)

        def add(concept, difficulty, question, answer, hint):
            questions.append({"concept": concept, "difficulty": difficulty,
                              "question": question, "sample_answer": answer, "hint": hint})

        # SELECT * — 3 variations
        add("SELECT *", "Easy",
            r([f'Retrieve all records from the `{t}` table.',
               f'Your manager wants a full snapshot of `{t}`. Pull every row and column.',
               f'Fetch the complete dataset from `{t}` — all rows, all columns.']),
            f'SELECT * FROM {t};',
            'SELECT * fetches all columns and rows from a table.')

        # SELECT columns — uses real column names
        add("SELECT columns", "Easy",
            r([f'From `{t}`, fetch only the `{c0}` and `{c1}` columns.',
               f'Extract just `{c0}` and `{c1}` from the `{t}` table.',
               f'The report only needs `{c0}` and `{c1}` from `{t}`. Write the query.']),
            f'SELECT {c0}, {c1}\nFROM {t};',
            f'List only the needed columns after SELECT: {c0}, {c1}')

        # DISTINCT — uses real column name
        add("DISTINCT", "Easy",
            r([f'Find all unique values in the `{c0}` column of `{t}`.',
               f'How many distinct `{c0}` values exist in `{t}`? List them all.',
               f'Remove duplicates and show every unique `{c0}` from `{t}`.']),
            f'SELECT DISTINCT {c0}\nFROM {t};',
            'DISTINCT removes duplicate rows from the result.')

        # COUNT
        add("COUNT", "Easy",
            r([f'Count the total number of records in `{t}`.',
               f'How many rows does the `{t}` table have?',
               f'The operations team needs the total record count in `{t}`.']),
            f'SELECT COUNT(*) AS total_records\nFROM {t};',
            'COUNT(*) counts all rows including NULLs.')

        # LIMIT
        add("LIMIT", "Easy",
            r([f'Preview the first 10 rows of `{t}` before running a full report.',
               f'Show a quick sample of 10 records from `{t}`.',
               f'Get the first 10 entries from `{t}`.']),
            f'SELECT *\nFROM {t}\nLIMIT 10;',
            'LIMIT restricts the number of rows returned.')

        if tx:
            sv = str(pick_val(df, tx))
            sv2 = str(pick_val(df, tx))
            vals = pick_vals(df, tx, 3)

            # WHERE text — uses real column name, real value
            add("WHERE (text)", "Easy",
                r([f'Get all records from `{t}` where `{tx}` equals `{sv}`.',
                   f'Filter `{t}` to show only rows where `{tx}` is `{sv}`.',
                   f'Find every entry in `{t}` where the `{tx}` column matches `{sv}`.']),
                f"SELECT *\nFROM {t}\nWHERE {tx} = '{sv}';",
                f'Use WHERE {tx} = value. Wrap text in single quotes.')

            # LIKE — uses real column name
            add("LIKE", "Easy",
                r([f'Find all records in `{t}` where `{tx}` starts with the letter `A`.',
                   f'Search `{t}` for rows where `{tx}` contains the word `{sv[:3]}`.',
                   f'Get all entries from `{t}` where `{tx}` ends with `e`.']),
                r([f"SELECT *\nFROM {t}\nWHERE {tx} LIKE 'A%';",
                   f"SELECT *\nFROM {t}\nWHERE {tx} ILIKE '%{sv[:3]}%';",
                   f"SELECT *\nFROM {t}\nWHERE {tx} LIKE '%e';"]),
                f'LIKE with % wildcard. A% = starts with A, %e = ends with e, %word% = contains.')

            # IS NULL — uses real column name
            add("IS NULL", "Easy",
                r([f'Find all records in `{t}` where `{tx}` has no value (NULL).',
                   f'Data quality check: which rows in `{t}` have a missing `{tx}`?',
                   f'Identify entries in `{t}` where `{tx}` is empty or not filled.']),
                f'SELECT *\nFROM {t}\nWHERE {tx} IS NULL;',
                f'Use IS NULL not = NULL. They behave differently in SQL.')

            # IN — uses real values from data
            add("IN", "Easy",
                r([f'From `{t}`, get all rows where `{tx}` is one of: `{vals[0]}`, `{vals[1] if len(vals)>1 else vals[0]}`, `{vals[2] if len(vals)>2 else vals[0]}`.',
                   f'Filter `{t}` to show only records where `{tx}` matches any of these values: {", ".join(vals[:3])}.']),
                f"SELECT *\nFROM {t}\nWHERE {tx} IN ({', '.join([chr(39)+v+chr(39) for v in vals[:3]])});",
                'IN is cleaner than multiple OR conditions.')

        if n:
            sv_n = pick_val(df, n)
            try:
                num_val = round(float(sv_n), 2)
            except:
                num_val = threshold

            # WHERE numeric — uses real column name
            add("WHERE (numeric)", "Easy",
                r([f'Get all records from `{t}` where `{n}` is greater than `{threshold}`.',
                   f'Filter `{t}` to show only rows where `{n}` exceeds `{threshold}`.',
                   f'Find entries in `{t}` where `{n}` is less than `{round(threshold*0.5, 2)}`.']),
                r([f'SELECT *\nFROM {t}\nWHERE {n} > {threshold};',
                   f'SELECT *\nFROM {t}\nWHERE {n} > {threshold};',
                   f'SELECT *\nFROM {t}\nWHERE {n} < {round(threshold*0.5, 2)};']),
                f'Use >, <, >=, <= for numeric comparisons in WHERE.')

            # ORDER BY
            add("ORDER BY DESC", "Easy",
                r([f'Sort all records in `{t}` by `{n}` from highest to lowest.',
                   f'List `{t}` ranked by `{n}` in descending order.',
                   f'Who has the highest `{n}` in `{t}`? Sort to find out.']),
                f'SELECT *\nFROM {t}\nORDER BY {n} DESC;',
                'ORDER BY column DESC sorts from highest to lowest.')

            # TOP N
            add("TOP N", "Easy",
                r([f'Get the top 5 records from `{t}` with the highest `{n}`.',
                   f'Find the 5 best performing rows in `{t}` based on `{n}`.',
                   f'Return only the top 5 entries from `{t}` ordered by `{n}` descending.']),
                f'SELECT *\nFROM {t}\nORDER BY {n} DESC\nLIMIT 5;',
                'Combine ORDER BY DESC with LIMIT to get top N.')

            # SUM
            add("SUM", "Easy",
                r([f'Calculate the total sum of `{n}` across all records in `{t}`.',
                   f'What is the grand total of `{n}` in `{t}`?',
                   f'Finance needs the overall `{n}` total from `{t}`.']),
                f'SELECT SUM({n}) AS total_{n}\nFROM {t};',
                'SUM() adds all non-NULL values in a numeric column.')

            # AVG
            add("AVG", "Easy",
                r([f'Find the average value of `{n}` in `{t}`.',
                   f'What is the mean `{n}` across all rows in `{t}`?',
                   f'Calculate the typical `{n}` value in `{t}`.']),
                f'SELECT ROUND(AVG({n})::numeric, 2) AS avg_{n}\nFROM {t};',
                'AVG() calculates the mean ignoring NULLs. Cast to numeric for ROUND.')

            # MIN MAX
            add("MIN MAX", "Medium",
                r([f'Find the smallest and largest `{n}` in `{t}`.',
                   f'What is the range of `{n}` values in `{t}`? Show min and max.',
                   f'Report the minimum and maximum `{n}` from `{t}` in one query.']),
                f'SELECT MIN({n}) AS min_{n}, MAX({n}) AS max_{n}\nFROM {t};',
                'Use MIN() and MAX() together in one SELECT.')

            # BETWEEN
            add("BETWEEN", "Medium",
                r([f'Get records from `{t}` where `{n}` is between `{round(threshold*0.5,2)}` and `{threshold2}`.',
                   f'Filter `{t}` to rows where `{n}` falls in the range `{round(threshold*0.5,2)}` to `{threshold2}`.',
                   f'Find entries in `{t}` where `{n}` is within `{round(threshold*0.5,2)}` and `{threshold2}` inclusive.']),
                f'SELECT *\nFROM {t}\nWHERE {n} BETWEEN {round(threshold*0.5,2)} AND {threshold2};',
                'BETWEEN is inclusive — includes both boundary values.')

            if tx:
                # GROUP BY COUNT
                add("GROUP BY + COUNT", "Medium",
                    r([f'Count how many records exist for each `{tx}` in `{t}`.',
                       f'How is `{t}` distributed across different `{tx}` values?',
                       f'Show the record count per `{tx}` category in `{t}`.']),
                    f'SELECT {tx}, COUNT(*) AS count\nFROM {t}\nGROUP BY {tx}\nORDER BY count DESC;',
                    f'GROUP BY {tx} groups rows by category. COUNT(*) counts each group.')

                # GROUP BY SUM
                add("GROUP BY + SUM", "Medium",
                    r([f'Find the total `{n}` for each `{tx}` in `{t}`.',
                       f'Which `{tx}` has the highest total `{n}` in `{t}`?',
                       f'Calculate sum of `{n}` grouped by `{tx}` in `{t}`.']),
                    f'SELECT {tx}, SUM({n}) AS total_{n}\nFROM {t}\nGROUP BY {tx}\nORDER BY total_{n} DESC;',
                    f'GROUP BY {tx} then SUM({n}) gives total per group.')

                # GROUP BY AVG
                add("GROUP BY + AVG", "Medium",
                    r([f'Find the average `{n}` per `{tx}` in `{t}`.',
                       f'Which `{tx}` category has the best average `{n}` in `{t}`?',
                       f'Calculate mean `{n}` for each `{tx}` group in `{t}`.']),
                    f'SELECT {tx}, ROUND(AVG({n})::numeric, 2) AS avg_{n}\nFROM {t}\nGROUP BY {tx}\nORDER BY avg_{n} DESC;',
                    f'AVG({n}) with GROUP BY {tx} gives mean per category.')

                # HAVING
                add("HAVING", "Medium",
                    r([f'Find `{tx}` groups in `{t}` where the total `{n}` exceeds `{threshold}`.',
                       f'Which `{tx}` categories in `{t}` have total `{n}` above `{threshold}`?',
                       f'Filter `{tx}` groups in `{t}` to only those with sum of `{n}` greater than `{threshold}`.']),
                    f'SELECT {tx}, SUM({n}) AS total\nFROM {t}\nGROUP BY {tx}\nHAVING SUM({n}) > {threshold}\nORDER BY total DESC;',
                    'HAVING filters AFTER GROUP BY. WHERE filters before aggregation.')

                # PERCENTILE
                add("PERCENTILE", "Medium",
                    r([f'Find the median value of `{n}` in `{t}` — not the average, the true middle value.',
                       f'Calculate the 50th percentile of `{n}` in `{t}`.',
                       f'What value does 50% of `{n}` fall below in `{t}`?']),
                    f'SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {n}) AS median_{n}\nFROM {t};',
                    'PERCENTILE_CONT(0.5) gives the exact median in PostgreSQL.')

                if tx2:
                    add("GROUP BY multiple", "Medium",
                        r([f'Count records in `{t}` grouped by both `{tx}` and `{tx2}`.',
                           f'Break down `{t}` record counts by `{tx}` and `{tx2}` combined.',
                           f'Show how many rows exist for each combination of `{tx}` and `{tx2}` in `{t}`.']),
                        f'SELECT {tx}, {tx2}, COUNT(*) AS count\nFROM {t}\nGROUP BY {tx}, {tx2}\nORDER BY count DESC;',
                        f'All non-aggregated columns ({tx}, {tx2}) must appear in GROUP BY.')

        if dates:
            d = dates[0]
            yr = random.choice([2022, 2023, 2024])
            add("EXTRACT year", "Medium",
                r([f'Get all records from `{t}` where `{d}` falls in the year {yr}.',
                   f'Filter `{t}` to show only {yr} data based on the `{d}` column.',
                   f'From `{t}`, extract all rows from the year {yr} using `{d}`.']),
                f'SELECT *\nFROM {t}\nWHERE EXTRACT(YEAR FROM {d}) = {yr};',
                f'EXTRACT(YEAR FROM {d}) pulls the year from a date column.')

    qs = sorted(questions, key=lambda q: DIFFICULTY_ORDER.get(q.get("difficulty","Easy"), 0))
    # Shuffle within same difficulty
    from itertools import groupby
    result = []
    for _, group in groupby(qs, key=lambda q: q.get("difficulty","Easy")):
        g = list(group)
        random.shuffle(g)
        result.extend(g)
    return result[:20]


def generate_level2(tables):
    questions = []
    table_list = list(tables.items())

    for i, (t, df) in enumerate(table_list):
        cols = list(df.columns)
        types = detect_types(df)
        nums = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        dates = [c for c in cols if types[c] == "date"]
        n = nums[0] if nums else None
        tx = texts[0] if texts else None
        c0 = cols[0]
        threshold = round(float(df[n].dropna().mean()), 2) if n else 100
        others = [(tn, tdf) for j, (tn, tdf) in enumerate(table_list) if j != i]

        def add(concept, difficulty, question, answer, hint):
            questions.append({"concept": concept, "difficulty": difficulty,
                              "question": question, "sample_answer": answer, "hint": hint})

        if others:
            t2, df2 = others[0]
            shared = next((c for c in cols if c in df2.columns), c0)

            add("INNER JOIN", "Medium",
                r([f'Join `{t}` and `{t2}` on `{shared}` and return only matching records.',
                   f'Combine `{t}` and `{t2}` using `{shared}` as the key — keep only rows that exist in both.',
                   f'Find records in `{t}` that have a matching entry in `{t2}` based on `{shared}`.']),
                f'SELECT a.*, b.*\nFROM {t} a\nINNER JOIN {t2} b ON a.{shared} = b.{shared};',
                'INNER JOIN returns only rows where the join key matches in both tables.')

            add("LEFT JOIN", "Medium",
                r([f'Get all records from `{t}` with matching data from `{t2}`. Keep `{t}` rows even with no match.',
                   f'Left join `{t}` and `{t2}` on `{shared}`. Show NULL where no match in `{t2}`.',
                   f'Combine `{t}` and `{t2}` but preserve all rows from `{t}` regardless of match.']),
                f'SELECT a.*, b.*\nFROM {t} a\nLEFT JOIN {t2} b ON a.{shared} = b.{shared};',
                'LEFT JOIN keeps all rows from the left table. NULLs appear where no match in right table.')

            add("LEFT JOIN anti-match", "Hard",
                r([f'Find all records in `{t}` that have NO matching entry in `{t2}` based on `{shared}`.',
                   f'Which `{t}` rows are orphaned — no corresponding record in `{t2}`?',
                   f'Identify `{t}` records not present in `{t2}` using an anti-join pattern.']),
                f'SELECT a.*\nFROM {t} a\nLEFT JOIN {t2} b ON a.{shared} = b.{shared}\nWHERE b.{shared} IS NULL;',
                'After LEFT JOIN, filter WHERE right-side key IS NULL to find unmatched rows.')

            if n:
                add("JOIN + GROUP BY", "Hard",
                    r([f'Join `{t}` and `{t2}`, then calculate total `{n}` per `{c0}`.',
                       f'After joining `{t}` and `{t2}` on `{shared}`, find the sum of `{n}` for each `{c0}`.',
                       f'Combine `{t}` and `{t2}`, then group by `{c0}` to get total `{n}`.']),
                    f'SELECT a.{c0}, SUM(a.{n}) AS total_{n}\nFROM {t} a\nINNER JOIN {t2} b ON a.{shared} = b.{shared}\nGROUP BY a.{c0}\nORDER BY total_{n} DESC;',
                    'JOIN first, then GROUP BY and aggregate on the combined result.')

        if n and tx:
            add("Subquery WHERE", "Hard",
                r([f'Find all records in `{t}` where `{n}` is above the overall average `{n}`.',
                   f'From `{t}`, return rows where `{n}` exceeds the table-wide mean.',
                   f'Filter `{t}` to show only above-average performers based on `{n}`.']),
                f'SELECT *\nFROM {t}\nWHERE {n} > (SELECT AVG({n}) FROM {t});',
                'The subquery (SELECT AVG...) runs first and returns a single value.')

            add("CASE WHEN", "Hard",
                r([f'Label each row in `{t}` as High (>{round(threshold*1.2,0):.0f}), Medium (>{round(threshold*0.8,0):.0f}), or Low based on `{n}`.',
                   f'Add a `tier` column to `{t}`: High if `{n}` > {round(threshold*1.2,0):.0f}, Medium if > {round(threshold*0.8,0):.0f}, else Low.',
                   f'Segment `{t}` records by `{n}` into performance tiers: High, Medium, Low.']),
                f"SELECT *,\n  CASE\n    WHEN {n} > {round(threshold*1.2,0):.0f} THEN 'High'\n    WHEN {n} > {round(threshold*0.8,0):.0f} THEN 'Medium'\n    ELSE 'Low'\n  END AS tier\nFROM {t};",
                'CASE WHEN checks conditions in order and returns the first match.')

            add("COALESCE", "Medium",
                r([f'Replace any NULL values in `{n}` with 0 in `{t}`.',
                   f'Clean up `{t}` by filling missing `{n}` values with 0.',
                   f'Ensure no NULLs exist in `{n}` by defaulting them to 0 in `{t}`.']),
                f'SELECT *, COALESCE({n}, 0) AS {n}_clean\nFROM {t};',
                'COALESCE returns the first non-NULL value. COALESCE(col, 0) replaces NULL with 0.')

            add("Duplicate detection", "Hard",
                r([f'Find all `{tx}` values that appear more than once in `{t}`.',
                   f'Which `{tx}` entries are duplicated in `{t}`?',
                   f'Quality check: identify repeated `{tx}` values in `{t}`.']),
                f'SELECT {tx}, COUNT(*) AS occurrences\nFROM {t}\nGROUP BY {tx}\nHAVING COUNT(*) > 1\nORDER BY occurrences DESC;',
                'HAVING COUNT(*) > 1 finds groups with more than one record.')

            add("Conditional aggregation", "Hard",
                r([f'In one query on `{t}`: count all rows AND count only rows where `{n}` > {threshold}.',
                   f'Show total record count and count of high performers (where `{n}` > {threshold}) from `{t}`.',
                   f'From `{t}`, calculate two counts: total rows and rows where `{n}` exceeds {threshold}.']),
                f'SELECT\n  COUNT(*) AS total,\n  COUNT(*) FILTER (WHERE {n} > {threshold}) AS above_{round(threshold,0):.0f}\nFROM {t};',
                'FILTER (WHERE ...) after COUNT is a PostgreSQL conditional aggregation pattern.')

            add("EXISTS", "Hard",
                r([f'Find records in `{t}` where another row with the same `{tx}` but higher `{n}` exists.',
                   f'From `{t}`, get rows that are NOT the maximum `{n}` within their `{tx}` group.',
                   f'Identify non-top performers in `{t}` — rows where a higher `{n}` exists in the same `{tx}`.']),
                f'SELECT *\nFROM {t} a\nWHERE EXISTS (\n  SELECT 1 FROM {t} b\n  WHERE b.{tx} = a.{tx}\n  AND b.{n} > a.{n}\n);',
                'EXISTS checks if the subquery returns any rows. Use table aliases a and b.')

            add("CONCAT", "Medium",
                r([f'Combine `{tx}` and `{n}` into one label column in `{t}` separated by ` - `.',
                   f'Create a descriptive tag for each row in `{t}` by joining `{tx}` and `{n}`.',
                   f'Build a single text field from `{tx}` and `{n}` in `{t}` using concatenation.']),
                f"SELECT {tx} || ' - ' || CAST({n} AS TEXT) AS label\nFROM {t};",
                "Use || to concatenate in PostgreSQL. Cast numbers to TEXT first.")

        if dates and n:
            d = dates[0]
            add("Month over month", "Hard",
                r([f'Calculate total `{n}` per month from `{d}` in `{t}` and show month-over-month change.',
                   f'Show monthly `{n}` trend in `{t}` using `{d}`, including change from previous month.',
                   f'Break `{t}` into monthly `{n}` totals and compute the difference between consecutive months.']),
                f"WITH monthly AS (\n  SELECT DATE_TRUNC('month', {d}) AS month, SUM({n}) AS total\n  FROM {t} GROUP BY month\n)\nSELECT month, total,\n  LAG(total) OVER (ORDER BY month) AS prev_month,\n  total - LAG(total) OVER (ORDER BY month) AS change\nFROM monthly ORDER BY month;",
                "DATE_TRUNC groups by month. LAG() accesses the previous row's value.")

    qs = sorted(questions, key=lambda q: DIFFICULTY_ORDER.get(q.get("difficulty","Easy"), 0))
    from itertools import groupby
    result = []
    for _, group in groupby(qs, key=lambda q: q.get("difficulty","Easy")):
        g = list(group)
        random.shuffle(g)
        result.extend(g)
    return result[:20]


def generate_level3(tables):
    questions = []

    for t, df in tables.items():
        cols = list(df.columns)
        types = detect_types(df)
        nums = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        dates = [c for c in cols if types[c] == "date"]
        n = nums[0] if nums else None
        n2 = nums[1] if len(nums) > 1 else n
        tx = texts[0] if texts else None
        c0 = cols[0]
        threshold = round(float(df[n].dropna().mean()), 2) if n else 100

        def add(concept, difficulty, question, answer, hint):
            questions.append({"concept": concept, "difficulty": difficulty,
                              "question": question, "sample_answer": answer, "hint": hint})

        if n and tx:
            add("CTE", "Hard",
                r([f'[Google] Using a CTE, find `{tx}` groups in `{t}` where average `{n}` exceeds the overall average.',
                   f'[Google] Write a two-step CTE: first calculate avg `{n}` per `{tx}`, then filter above-average groups.',
                   f'[Google] CTE challenge: compute total `{n}` per `{tx}` in `{t}`, then return only top half by total.']),
                r([f'WITH avg_by_group AS (\n  SELECT {tx}, AVG({n}) AS avg_val\n  FROM {t} GROUP BY {tx}\n)\nSELECT * FROM avg_by_group\nWHERE avg_val > (SELECT AVG({n}) FROM {t});',
                   f'WITH avg_by_group AS (\n  SELECT {tx}, AVG({n}) AS avg_val\n  FROM {t} GROUP BY {tx}\n)\nSELECT * FROM avg_by_group\nWHERE avg_val > (SELECT AVG(avg_val) FROM avg_by_group);',
                   f'WITH totals AS (\n  SELECT {tx}, SUM({n}) AS total FROM {t} GROUP BY {tx}\n)\nSELECT * FROM totals\nWHERE total > (SELECT AVG(total) FROM totals)\nORDER BY total DESC;']),
                'Define CTE with WITH name AS (...), then query it like a regular table.')

            add("ROW_NUMBER()", "Hard",
                r([f'[Amazon] Assign a row number to each record in `{t}`, restarting at 1 for each `{tx}`, ordered by `{n}` descending.',
                   f'[Amazon] Number each row within its `{tx}` group in `{t}` from highest to lowest `{n}`.',
                   f'[Amazon] Add a sequential rank within each `{tx}` category in `{t}` based on `{n}`.']),
                f'SELECT *,\n  ROW_NUMBER() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS row_num\nFROM {t};',
                'ROW_NUMBER() OVER (PARTITION BY group ORDER BY col) restarts numbering per group.')

            add("RANK()", "Hard",
                r([f'[Meta] Rank records in `{t}` by `{n}` within each `{tx}` group. Ties share the same rank.',
                   f'[Meta] Add a rank column to `{t}` per `{tx}` group using `{n}`. Tied values get identical rank.',
                   f'[Meta] Within each `{tx}` in `{t}`, rank rows by `{n}` desc. Duplicates should tie.']),
                f'SELECT *,\n  RANK() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS rnk\nFROM {t};',
                'RANK() gives tied rows the same rank then skips next rank (1,2,2,4).')

            add("DENSE_RANK()", "Hard",
                r([f'[Netflix] Rank `{t}` by `{n}` within `{tx}` groups. Ranks must be consecutive — no gaps after ties.',
                   f'[Netflix] Apply DENSE_RANK on `{n}` per `{tx}` in `{t}`. Unlike RANK, no numbers are skipped.',
                   f'[Netflix] Rank rows in `{t}` by `{n}` per `{tx}` group with consecutive ranking even with ties.']),
                f'SELECT *,\n  DENSE_RANK() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS dense_rnk\nFROM {t};',
                'DENSE_RANK() never skips numbers after ties. Produces 1,2,2,3 not 1,2,2,4.')

            add("Top N per group", "MAANG",
                r([f'[Amazon] Classic interview question: find the top 3 records per `{tx}` in `{t}` by highest `{n}`.',
                   f'[Amazon] Return the best 3 rows per `{tx}` group in `{t}` based on `{n}`. Use CTE + ROW_NUMBER.',
                   f'[Amazon] For each `{tx}` in `{t}`, get the top 3 entries by `{n}`. Each group has at most 3 rows.']),
                f'WITH ranked AS (\n  SELECT *,\n    ROW_NUMBER() OVER (\n      PARTITION BY {tx} ORDER BY {n} DESC\n    ) AS rn\n  FROM {t}\n)\nSELECT * FROM ranked WHERE rn <= 3;',
                'Classic pattern: CTE + ROW_NUMBER() + WHERE rn <= N. Most common window function interview question.')

            add("Running total", "MAANG",
                r([f'[Uber] Show a running cumulative total of `{n}` within each `{tx}` group in `{t}`.',
                   f'[Uber] Add a column showing how `{n}` accumulates row by row within each `{tx}` in `{t}`.',
                   f'[Uber] Calculate cumulative `{n}` per `{tx}` group in `{t}`, ordered by `{c0}`.']),
                f'SELECT *,\n  SUM({n}) OVER (\n    PARTITION BY {tx}\n    ORDER BY {c0}\n    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW\n  ) AS running_total\nFROM {t};',
                'SUM() OVER with ORDER BY creates cumulative sum. ROWS BETWEEN defines the window frame.')

            add("LAG()", "MAANG",
                r([f'[Google] For each row in `{t}`, show the previous row\'s `{n}` and the change from it.',
                   f'[Google] Add columns to `{t}` showing previous `{n}` (LAG) and difference from current row.',
                   f'[Google] Period-over-period analysis: show `{n}` change vs previous record in `{t}`.']),
                f'SELECT *,\n  LAG({n}) OVER (ORDER BY {c0}) AS prev_{n},\n  {n} - LAG({n}) OVER (ORDER BY {c0}) AS change\nFROM {t};',
                'LAG(col) gets the previous row value. Subtract to get the change between rows.')

            add("NTILE()", "MAANG",
                r([f'[McKinsey] Divide `{t}` into 4 equal quartiles based on `{n}`. Label each row 1-4.',
                   f'[McKinsey] Segment all records in `{t}` into 4 performance buckets by `{n}`.',
                   f'[McKinsey] Assign a quartile (1=lowest, 4=highest) to each row in `{t}` based on `{n}`.']),
                f'SELECT *,\n  NTILE(4) OVER (ORDER BY {n}) AS quartile\nFROM {t};',
                'NTILE(4) divides all rows into 4 roughly equal groups numbered 1 to 4.')

            add("Above/Below group average", "MAANG",
                r([f'[Google] Label each row in `{t}` as Above Average or Below Average vs its `{tx}` group mean.',
                   f'[Google] Compare each `{n}` to its `{tx}` group average in `{t}`. Tag Above or Below.',
                   f'[Google] For each record in `{t}`, show whether `{n}` beats the average for its `{tx}` group.']),
                f"SELECT *,\n  CASE\n    WHEN {n} > AVG({n}) OVER (PARTITION BY {tx}) THEN 'Above Average'\n    ELSE 'Below Average'\n  END AS vs_group_avg\nFROM {t};",
                'AVG() OVER (PARTITION BY group) computes group mean per row. Use inside CASE WHEN.')

            add("Chained CTEs", "MAANG",
                r([f'[Amazon] Three-step CTE: total `{n}` per `{tx}`, rank groups, return only top half.',
                   f'[Amazon] Chain two CTEs in `{t}`: first aggregate `{n}` by `{tx}`, then rank the results.',
                   f'[Amazon] Multi-step analysis on `{t}`: compute totals, rank them, filter top performers.']),
                f'WITH totals AS (\n  SELECT {tx}, SUM({n}) AS total FROM {t} GROUP BY {tx}\n),\nranked AS (\n  SELECT *, RANK() OVER (ORDER BY total DESC) AS rnk,\n    COUNT(*) OVER () AS total_groups\n  FROM totals\n)\nSELECT {tx}, total, rnk FROM ranked\nWHERE rnk <= total_groups / 2\nORDER BY rnk;',
                'Chain CTEs with commas. Each CTE can reference all previously defined CTEs.')

            add("Pareto 80/20", "MAANG",
                r([f'[Meta] Find which `{tx}` categories make up 80% of total `{n}` in `{t}` (Pareto rule).',
                   f'[Meta] Pareto analysis on `{t}`: which `{tx}` groups drive 80% of `{n}`?',
                   f'[Meta] Apply 80/20 principle to `{t}`: identify top `{tx}` categories by cumulative `{n}`.']),
                f'WITH totals AS (\n  SELECT {tx}, SUM({n}) AS cat_total FROM {t} GROUP BY {tx}\n),\ncumulative AS (\n  SELECT *,\n    SUM(cat_total) OVER (ORDER BY cat_total DESC) AS running_sum,\n    SUM(cat_total) OVER () AS grand_total\n  FROM totals\n)\nSELECT {tx}, cat_total,\n  ROUND(100.0*running_sum/grand_total::numeric,2) AS cumulative_pct\nFROM cumulative\nWHERE running_sum - cat_total < grand_total * 0.8\nORDER BY cat_total DESC;',
                'Calculate cumulative sum as % of total. Filter where cumulative < 80%.')

        if dates and n:
            d = dates[0]
            add("YoY Growth", "MAANG",
                r([f'[Amazon] Calculate year-over-year growth rate of `{n}` in `{t}` using `{d}`.',
                   f'[Amazon] Show annual `{n}` totals from `{t}` with YoY % change based on `{d}`.',
                   f'[Amazon] YoY analysis: compare `{n}` each year in `{t}` to the previous year.']),
                f"WITH yearly AS (\n  SELECT EXTRACT(YEAR FROM {d}) AS yr, SUM({n}) AS total\n  FROM {t} GROUP BY yr\n)\nSELECT yr, total,\n  LAG(total) OVER (ORDER BY yr) AS prev_year,\n  ROUND(100.0*(total-LAG(total) OVER (ORDER BY yr))/NULLIF(LAG(total) OVER (ORDER BY yr),0)::numeric,2) AS yoy_pct\nFROM yearly ORDER BY yr;",
                'YoY = (current - previous) / previous * 100. NULLIF avoids division by zero.')

            add("Cohort analysis", "MAANG",
                r([f'[Airbnb] Group `{t}` by month of `{d}` and analyze `{n}` per cohort.',
                   f'[Airbnb] Cohort analysis on `{t}`: aggregate `{n}` by the month records were created (`{d}`).',
                   f'[Airbnb] Monthly cohort report on `{t}`: count records and total `{n}` per `{d}` month.']),
                f"WITH cohorts AS (\n  SELECT DATE_TRUNC('month', {d}) AS cohort_month,\n    COUNT(*) AS cohort_size, SUM({n}) AS total\n  FROM {t} GROUP BY cohort_month\n)\nSELECT cohort_month, cohort_size, total,\n  ROUND(total::numeric/cohort_size, 2) AS avg_per_record\nFROM cohorts ORDER BY cohort_month;",
                "DATE_TRUNC('month', date) groups to first day of each month.")

    qs = sorted(questions, key=lambda q: DIFFICULTY_ORDER.get(q.get("difficulty","Easy"), 0))
    from itertools import groupby
    result = []
    for _, group in groupby(qs, key=lambda q: q.get("difficulty","Easy")):
        g = list(group)
        random.shuffle(g)
        result.extend(g)
    return result[:20]


def get_questions(tables: dict, level: int) -> list:
    if level == 1:
        qs = generate_level1(tables)
    elif level == 2:
        qs = generate_level2(tables)
    else:
        qs = generate_level3(tables)

    for i, q in enumerate(qs):
        expected = compute_expected(q["sample_answer"], tables)
        q.update(expected)
        q["id"] = i + 1

    return qs

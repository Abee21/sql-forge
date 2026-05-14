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


def pick_val(df, col):
    vals = df[col].dropna().unique()
    return str(vals[0]) if len(vals) > 0 else "SampleValue"


def shuffle(arr):
    a = list(arr)
    random.shuffle(a)
    return a


def generate_level1(tables):
    questions = []

    for t, df in tables.items():
        cols = list(df.columns)
        types = detect_types(df)
        nums = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        dates = [c for c in cols if types[c] == "date"]
        n = nums[0] if nums else None
        n2 = nums[1] if len(nums) > 1 else None
        tx = texts[0] if texts else None
        tx2 = texts[1] if len(texts) > 1 else None
        c0 = cols[0]
        sv = pick_val(df, tx or c0)
        threshold = round(float(df[n].dropna().mean()), 2) if n else 100

        def add(concept, difficulty, question, answer, hint):
            questions.append({
                "concept": concept, "difficulty": difficulty,
                "question": question, "sample_answer": answer, "hint": hint
            })

        # Situation-based questions — no column names given directly
        add("SELECT *", "Easy",
            f'Your manager wants a complete snapshot of everything stored in the {t} database. Pull all records.',
            f'SELECT * FROM {t};',
            f'Use SELECT * to retrieve every column and row from {t}.')

        add("DISTINCT", "Easy",
            f'The business team wants to know how many unique categories or types exist in the {t} table. Find all distinct values in the first categorical column.',
            f'SELECT DISTINCT {tx or c0} FROM {t};',
            f'Use DISTINCT to eliminate duplicate values.')

        add("LIMIT", "Easy",
            f'You need to quickly preview the {t} data before running a full report. Show only the first 10 records.',
            f'SELECT * FROM {t} LIMIT 10;',
            f'Use LIMIT to restrict the number of rows returned.')

        add("COUNT", "Easy",
            f'The operations team needs to know the total volume of records in {t}. How many records exist?',
            f'SELECT COUNT(*) AS total_records FROM {t};',
            f'COUNT(*) counts all rows including those with NULL values.')

        if tx and sv:
            add("WHERE (text)", "Easy",
                f'Filter the {t} records to show only entries where the primary category equals "{sv}". Return all columns.',
                f"SELECT * FROM {t} WHERE {tx} = '{sv}';",
                f'Use WHERE with = for exact text matching. Wrap text values in single quotes.')

            add("LIKE", "Easy",
                f'The search team wants to find all {t} records where the main descriptor starts with the letter A. Write a pattern search query.',
                f"SELECT * FROM {t} WHERE {tx} LIKE 'A%';",
                f'LIKE with % as wildcard. A% means starts with A.')

            add("IS NULL", "Easy",
                f'Data quality check: identify all records in {t} where the primary text field has no value at all.',
                f'SELECT * FROM {t} WHERE {tx} IS NULL;',
                f'Use IS NULL to find missing values. Never use = NULL.')

        if n:
            add("ORDER BY DESC", "Easy",
                f'The sales team wants to see the {t} records ranked from highest to lowest by the main numeric measure. Return all columns.',
                f'SELECT * FROM {t} ORDER BY {n} DESC;',
                f'Use ORDER BY column DESC to sort highest first.')

            add("TOP N", "Easy",
                f'Your analyst needs the top 5 performing records from {t} based on the primary numeric metric.',
                f'SELECT * FROM {t} ORDER BY {n} DESC LIMIT 5;',
                f'Combine ORDER BY DESC with LIMIT 5 to get top performers.')

            add("SUM", "Easy",
                f'Finance needs the grand total of the main numeric measure across all records in {t}.',
                f'SELECT SUM({n}) AS total FROM {t};',
                f'SUM() adds all non-NULL values in a numeric column.')

            add("AVG", "Easy",
                f'What is the typical performance level? Calculate the average of the primary numeric metric in {t}.',
                f'SELECT ROUND(AVG({n})::numeric, 2) AS average FROM {t};',
                f'AVG() calculates the mean. Use ROUND to limit decimal places.')

            add("MIN MAX", "Easy",
                f'What is the range of values? Find the lowest and highest values of the main numeric metric in {t}.',
                f'SELECT MIN({n}) AS minimum, MAX({n}) AS maximum FROM {t};',
                f'Use MIN() and MAX() together in one SELECT statement.')

            add("BETWEEN", "Medium",
                f'The team only wants to analyze mid-range records from {t}. Filter to records where the numeric measure falls between 50 and 200.',
                f'SELECT * FROM {t} WHERE {n} BETWEEN 50 AND 200;',
                f'BETWEEN is inclusive — it includes both boundary values.')

            if tx:
                add("GROUP BY + COUNT", "Medium",
                    f'How is the data distributed across different categories in {t}? Count the number of records in each group.',
                    f'SELECT {tx}, COUNT(*) AS record_count FROM {t} GROUP BY {tx} ORDER BY record_count DESC;',
                    f'GROUP BY groups rows by a column. Use COUNT(*) to count rows in each group.')

                add("GROUP BY + SUM", "Medium",
                    f'Calculate the total value of the numeric metric for each category in {t}. Which category contributes the most?',
                    f'SELECT {tx}, SUM({n}) AS total FROM {t} GROUP BY {tx} ORDER BY total DESC;',
                    f'Combine GROUP BY with SUM() to aggregate by category.')

                add("GROUP BY + AVG", "Medium",
                    f'Which category in {t} has the best average performance? Find the average numeric metric per group.',
                    f'SELECT {tx}, ROUND(AVG({n})::numeric, 2) AS avg_value FROM {t} GROUP BY {tx} ORDER BY avg_value DESC;',
                    f'GROUP BY with AVG() gives the mean per category.')

                add("HAVING", "Medium",
                    f'Focus only on the high-performing categories. Find groups in {t} where the total numeric value exceeds {threshold}.',
                    f'SELECT {tx}, SUM({n}) AS total FROM {t} GROUP BY {tx} HAVING SUM({n}) > {threshold} ORDER BY total DESC;',
                    f'HAVING filters groups after aggregation. WHERE filters rows before.')

                add("PERCENTILE", "Medium",
                    f'The data science team wants the median value of the numeric metric in {t} — not the average, but the true middle value.',
                    f'SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {n}) AS median_value FROM {t};',
                    f'PERCENTILE_CONT(0.5) gives the exact median in PostgreSQL.')

                if tx2:
                    add("GROUP BY multiple", "Medium",
                        f'Break down the count of records in {t} by two different categorical dimensions simultaneously.',
                        f'SELECT {tx}, {tx2}, COUNT(*) AS count FROM {t} GROUP BY {tx}, {tx2} ORDER BY count DESC;',
                        f'Include all non-aggregated columns in GROUP BY.')

        if dates:
            d = dates[0]
            add("EXTRACT year", "Medium",
                f'The annual report team needs records from {t} for the year 2023 only. Filter by year.',
                f'SELECT * FROM {t} WHERE EXTRACT(YEAR FROM {d}) = 2023;',
                f'EXTRACT(YEAR FROM date_column) pulls just the year portion.')

    return shuffle(questions)[:20]


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
        tx2 = texts[1] if len(texts) > 1 else None
        c0 = cols[0]
        threshold = round(float(df[n].dropna().mean()), 2) if n else 100
        others = [(tn, tdf) for j, (tn, tdf) in enumerate(table_list) if j != i]

        def add(concept, difficulty, question, answer, hint):
            questions.append({
                "concept": concept, "difficulty": difficulty,
                "question": question, "sample_answer": answer, "hint": hint
            })

        if others:
            t2, df2 = others[0]
            shared = next((c for c in cols if c in df2.columns), c0)
            t2c = df2.columns[0]

            add("INNER JOIN", "Medium",
                f'Combine the {t} and {t2} datasets to show only records that exist in both tables. Return all matched columns.',
                f'SELECT a.*, b.*\nFROM {t} a\nINNER JOIN {t2} b ON a.{shared} = b.{shared};',
                f'INNER JOIN returns only rows where the join key exists in both tables.')

            add("LEFT JOIN", "Medium",
                f'The business wants all records from {t} regardless of whether a match exists in {t2}. Include the matched data from {t2} where available.',
                f'SELECT a.*, b.{t2c}\nFROM {t} a\nLEFT JOIN {t2} b ON a.{shared} = b.{shared};',
                f'LEFT JOIN keeps all rows from the left table. NULLs appear where no match exists in right table.')

            add("LEFT JOIN anti-match", "Hard",
                f'Which records in {t} have no corresponding entry in {t2}? These are the orphaned records.',
                f'SELECT a.*\nFROM {t} a\nLEFT JOIN {t2} b ON a.{shared} = b.{shared}\nWHERE b.{shared} IS NULL;',
                f'After LEFT JOIN, filter WHERE right table key IS NULL to find unmatched rows.')

            if n:
                add("JOIN + GROUP BY", "Hard",
                    f'After joining {t} and {t2}, find the total numeric value grouped by the primary category. Which category performs best across both datasets?',
                    f'SELECT a.{c0}, SUM(a.{n}) AS total\nFROM {t} a\nINNER JOIN {t2} b ON a.{shared} = b.{shared}\nGROUP BY a.{c0}\nORDER BY total DESC;',
                    f'JOIN first, then GROUP BY and aggregate on the result.')

        if n and tx:
            add("Subquery WHERE", "Hard",
                f'Find all records in {t} that are performing above average. Only return entries where the numeric metric exceeds the overall mean.',
                f'SELECT *\nFROM {t}\nWHERE {n} > (SELECT AVG({n}) FROM {t});',
                f'The subquery (SELECT AVG...) runs first and returns a single value to compare against.')

            add("CASE WHEN", "Hard",
                f'Segment the {t} records into performance tiers: label records as High if above 100, Medium if between 50 and 100, otherwise Low.',
                f"SELECT *,\n  CASE\n    WHEN {n} > 100 THEN 'High'\n    WHEN {n} BETWEEN 50 AND 100 THEN 'Medium'\n    ELSE 'Low'\n  END AS performance_tier\nFROM {t};",
                f'CASE WHEN checks conditions in order and returns the first match.')

            add("COALESCE", "Medium",
                f'Data cleanup task: replace any missing numeric values in {t} with 0 so downstream calculations are not affected by NULLs.',
                f'SELECT *, COALESCE({n}, 0) AS clean_value\nFROM {t};',
                f'COALESCE returns the first non-NULL value. COALESCE(col, 0) replaces NULL with 0.')

            add("EXISTS", "Hard",
                f'Find all records in {t} that have at least one other record in the same table sharing the same category but with a higher numeric value.',
                f'SELECT *\nFROM {t} a\nWHERE EXISTS (\n  SELECT 1 FROM {t} b\n  WHERE b.{tx} = a.{tx}\n  AND b.{n} > a.{n}\n);',
                f'EXISTS checks if the subquery returns any rows. Use table aliases a and b for self-reference.')

            add("Duplicate detection", "Hard",
                f'Quality check: identify all category values in {t} that appear more than once. These could be duplicates.',
                f'SELECT {tx}, COUNT(*) AS occurrences\nFROM {t}\nGROUP BY {tx}\nHAVING COUNT(*) > 1\nORDER BY occurrences DESC;',
                f'HAVING COUNT(*) > 1 finds groups with more than one record.')

            add("Top performer per group", "Hard",
                f'From {t}, find the single record with the highest numeric value within each category. Show only the best performer per group.',
                f'SELECT {tx}, MAX({n}) AS best_value\nFROM {t}\nGROUP BY {tx}\nORDER BY best_value DESC;',
                f'MAX() with GROUP BY gives the top value in each category.')

            add("Month over month", "Hard",
                f'Compare performance across months in {t}. Calculate total numeric value per month and show the change from the previous month.',
                f"WITH monthly AS (\n  SELECT DATE_TRUNC('month', {dates[0] if dates else c0}::date) AS month, SUM({n}) AS total\n  FROM {t}\n  GROUP BY month\n)\nSELECT month, total,\n  LAG(total) OVER (ORDER BY month) AS prev_month,\n  total - LAG(total) OVER (ORDER BY month) AS change\nFROM monthly ORDER BY month;" if dates else
                f'SELECT {tx}, SUM({n}) AS total, AVG({n}) AS average\nFROM {t}\nGROUP BY {tx}\nORDER BY total DESC;',
                f'DATE_TRUNC groups by month. LAG() accesses the previous row value.')

            add("CONCAT", "Medium",
                f'Create a descriptive label for each record in {t} by combining the category name and numeric value into a single text field.',
                f"SELECT {tx} || ' - ' || CAST({n} AS TEXT) AS label\nFROM {t};",
                f'Use || to concatenate in PostgreSQL. Cast numbers to TEXT first.')

            add("Conditional count", "Hard",
                f'In a single query on {t}, show the total record count AND separately count only records where the numeric metric is above {threshold}.',
                f'SELECT\n  COUNT(*) AS total,\n  COUNT(*) FILTER (WHERE {n} > {threshold}) AS above_threshold\nFROM {t};',
                f'FILTER (WHERE ...) after COUNT is a PostgreSQL way to do conditional aggregation.')

    return shuffle(questions)[:20]


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
        tx2 = texts[1] if len(texts) > 1 else None
        c0 = cols[0]
        threshold = round(float(df[n].dropna().mean()), 2) if n else 100

        def add(concept, difficulty, question, answer, hint):
            questions.append({
                "concept": concept, "difficulty": difficulty,
                "question": question, "sample_answer": answer, "hint": hint
            })

        if n and tx:
            add("CTE", "Hard",
                f'[Google] Write a multi-step query on {t}: first calculate the total numeric value per category, then return only categories that perform above average across all groups.',
                f'WITH category_totals AS (\n  SELECT {tx}, SUM({n}) AS total\n  FROM {t}\n  GROUP BY {tx}\n)\nSELECT *\nFROM category_totals\nWHERE total > (SELECT AVG(total) FROM category_totals);',
                f'CTEs (WITH clause) let you build the query step by step. Query the CTE like a regular table.')

            add("ROW_NUMBER()", "Hard",
                f'[Amazon] Assign a ranking number to each record within its category group in {t}, ordered from highest to lowest numeric value. Each category starts ranking from 1.',
                f'SELECT *,\n  ROW_NUMBER() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS rank_in_group\nFROM {t};',
                f'ROW_NUMBER() OVER (PARTITION BY group ORDER BY value) assigns sequential numbers within each group.')

            add("RANK()", "Hard",
                f'[Meta] Rank all records in {t} by their numeric value within each category. Records with the same value should receive the same rank, with the next rank skipped.',
                f'SELECT *,\n  RANK() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS rank_position\nFROM {t};',
                f'RANK() gives tied records the same rank. Unlike ROW_NUMBER(), it skips the next rank after a tie (1,2,2,4).')

            add("DENSE_RANK()", "Hard",
                f'[Netflix] Rank records in {t} by numeric value per category, but ensure ranks are always consecutive even when ties occur. No gaps in ranking numbers.',
                f'SELECT *,\n  DENSE_RANK() OVER (\n    PARTITION BY {tx}\n    ORDER BY {n} DESC\n  ) AS dense_rank\nFROM {t};',
                f'DENSE_RANK() never skips numbers after ties. Produces 1,2,2,3 instead of 1,2,2,4.')

            add("Top N per group", "MAANG",
                f'[Amazon Interview] Classic interview question: find the top 3 records per category in {t} based on the highest numeric value. Each category should have at most 3 entries.',
                f'WITH ranked AS (\n  SELECT *,\n    ROW_NUMBER() OVER (\n      PARTITION BY {tx}\n      ORDER BY {n} DESC\n    ) AS rn\n  FROM {t}\n)\nSELECT * FROM ranked WHERE rn <= 3;',
                f'This is one of the most asked SQL interview questions. CTE + ROW_NUMBER() + WHERE rn <= N.')

            add("Running total", "MAANG",
                f'[Uber] Calculate a running cumulative total of the numeric metric within each category in {t}. Show how the total builds up record by record.',
                f'SELECT *,\n  SUM({n}) OVER (\n    PARTITION BY {tx}\n    ORDER BY {c0}\n    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW\n  ) AS running_total\nFROM {t};',
                f'SUM() OVER with ORDER BY creates a cumulative sum. ROWS BETWEEN defines the window frame.')

            add("LAG() - period comparison", "MAANG",
                f'[Google] For each record in {t}, show how the numeric value compares to the previous record. Calculate the difference from the prior entry.',
                f'SELECT *,\n  LAG({n}) OVER (ORDER BY {c0}) AS previous_value,\n  {n} - LAG({n}) OVER (ORDER BY {c0}) AS change_from_prev\nFROM {t};',
                f'LAG(col) gets the value from the previous row. Subtract to get the change.')

            add("LEAD()", "Hard",
                f'[Facebook] For each record in {t}, show the upcoming numeric value from the next row. This is useful for forecasting and lookahead analysis.',
                f'SELECT *,\n  LEAD({n}) OVER (ORDER BY {c0}) AS next_value\nFROM {t};',
                f'LEAD(col) accesses the next row value. Opposite of LAG().')

            add("NTILE() quartiles", "MAANG",
                f'[McKinsey Data] Segment all records in {t} into 4 equal performance quartiles based on the numeric metric. Label each record with its quartile (1=bottom, 4=top).',
                f'SELECT *,\n  NTILE(4) OVER (ORDER BY {n}) AS quartile\nFROM {t};',
                f'NTILE(4) divides all rows into 4 equal groups. Great for percentile segmentation.')

            add("Above/Below average per group", "MAANG",
                f'[Google] Label each record in {t} as either Above Average or Below Average compared to its own category group average.',
                f"SELECT *,\n  CASE\n    WHEN {n} > AVG({n}) OVER (PARTITION BY {tx})\n    THEN 'Above Average'\n    ELSE 'Below Average'\n  END AS performance_vs_group\nFROM {t};",
                f'AVG() OVER (PARTITION BY group) calculates the group mean for each row. Use it inside CASE WHEN.')

            add("Chained CTEs", "MAANG",
                f'[Amazon] Three-step analysis: (1) calculate total numeric value per category, (2) rank the categories, (3) return only the top half of categories by performance.',
                f'WITH category_totals AS (\n  SELECT {tx}, SUM({n}) AS total\n  FROM {t}\n  GROUP BY {tx}\n),\nranked_categories AS (\n  SELECT *,\n    RANK() OVER (ORDER BY total DESC) AS rnk,\n    COUNT(*) OVER () AS total_groups\n  FROM category_totals\n)\nSELECT {tx}, total, rnk\nFROM ranked_categories\nWHERE rnk <= total_groups / 2\nORDER BY rnk;',
                f'Chain multiple CTEs with commas. Each CTE can reference the ones defined before it.')

            add("Pareto 80/20", "MAANG",
                f'[Meta Interview] Apply the 80/20 rule to {t}: find which categories contribute to the top 80% of the total numeric value. Classic business analysis question.',
                f'WITH totals AS (\n  SELECT {tx}, SUM({n}) AS cat_total\n  FROM {t}\n  GROUP BY {tx}\n),\ncumulative AS (\n  SELECT *,\n    SUM(cat_total) OVER (ORDER BY cat_total DESC) AS running_sum,\n    SUM(cat_total) OVER () AS grand_total\n  FROM totals\n)\nSELECT {tx}, cat_total,\n  ROUND(100.0 * running_sum / grand_total, 2) AS cumulative_pct\nFROM cumulative\nWHERE running_sum - cat_total < grand_total * 0.8\nORDER BY cat_total DESC;',
                f'Calculate cumulative sum as percentage of total. Filter where cumulative % < 80%.')

            if n2 and n2 != n:
                add("Correlation analysis", "MAANG",
                    f'[Data Science Interview] Is there a relationship between the two numeric metrics in {t}? Calculate the Pearson correlation coefficient between them.',
                    f'SELECT\n  CORR({n}, {n2}) AS correlation_coefficient\nFROM {t};',
                    f'CORR() in PostgreSQL calculates Pearson correlation. Returns -1 to 1.')

        if dates and n:
            d = dates[0]
            add("YoY Growth", "MAANG",
                f'[Amazon] Calculate year-over-year growth rate of the numeric metric in {t}. Show each year, its total, the previous year total, and the % growth.',
                f"WITH yearly AS (\n  SELECT\n    EXTRACT(YEAR FROM {d}) AS yr,\n    SUM({n}) AS total\n  FROM {t}\n  GROUP BY yr\n)\nSELECT yr, total,\n  LAG(total) OVER (ORDER BY yr) AS prev_year,\n  ROUND(\n    100.0 * (total - LAG(total) OVER (ORDER BY yr))\n    / NULLIF(LAG(total) OVER (ORDER BY yr), 0)\n  ::numeric, 2) AS yoy_growth_pct\nFROM yearly\nORDER BY yr;",
                f'YoY = (current - previous) / previous * 100. Use NULLIF to avoid division by zero.')

            add("Cohort analysis", "MAANG",
                f'[Airbnb] Group {t} records by the month they were created and analyze the total numeric metric and average per record for each cohort.',
                f"WITH cohorts AS (\n  SELECT\n    DATE_TRUNC('month', {d}) AS cohort_month,\n    COUNT(*) AS cohort_size,\n    SUM({n}) AS total\n  FROM {t}\n  GROUP BY cohort_month\n)\nSELECT cohort_month, cohort_size, total,\n  ROUND(total::numeric / cohort_size, 2) AS avg_per_record\nFROM cohorts\nORDER BY cohort_month;",
                f'DATE_TRUNC groups dates to month start. This is the foundation of cohort retention analysis.')

    return shuffle(questions)[:20]


DIFFICULTY_ORDER = {"Easy": 0, "Medium": 1, "Hard": 2, "MAANG": 3}

def get_questions(tables: dict, level: int) -> list:
    if level == 1:
        qs = generate_level1(tables)
    elif level == 2:
        qs = generate_level2(tables)
    else:
        qs = generate_level3(tables)

    # Sort by difficulty — Easy first, MAANG last
    qs = sorted(qs, key=lambda q: DIFFICULTY_ORDER.get(q.get("difficulty", "Easy"), 0))

    # Within same difficulty, shuffle for variety
    from itertools import groupby
    sorted_qs = []
    for _, group in groupby(qs, key=lambda q: q.get("difficulty", "Easy")):
        group_list = list(group)
        random.shuffle(group_list)
        sorted_qs.extend(group_list)

    # Attach expected output to each question by running the reference answer
    for i, q in enumerate(sorted_qs):
        expected = compute_expected(q["sample_answer"], tables)
        q.update(expected)
        q["id"] = i + 1

    return sorted_qs

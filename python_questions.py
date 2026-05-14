import random
import pandas as pd
import numpy as np
import io
import contextlib


def detect_types(df):
    types = {}
    for col in df.columns:
        if df[col].dtype in ["int64", "float64"]:
            types[col] = "numeric"
        else:
            try:
                pd.to_datetime(df[col].dropna().head(10))
                types[col] = "date"
            except:
                types[col] = "text"
    return types


def compute_expected(code: str, tables: dict) -> dict:
    try:
        result = run_python(code, tables)
        if isinstance(result, pd.DataFrame):
            return {"expected_columns": list(result.columns), "expected_rows": len(result)}
        return {"expected_columns": [], "expected_rows": None}
    except:
        return {"expected_columns": [], "expected_rows": None}


def run_python(code: str, tables: dict) -> object:
    """Safely execute Python code with pandas/numpy access"""
    # Build namespace with dataframes
    namespace = {"pd": pd, "np": np}
    for name, df in tables.items():
        namespace[name] = df.copy()
        namespace["df"] = df.copy()  # always have 'df' as alias for first table

    # Block dangerous imports
    blocked = ["os", "sys", "subprocess", "shutil", "open", "exec", "eval",
               "import", "__import__", "compile", "globals", "locals"]
    for b in blocked:
        if b in code and b not in ["import pandas", "import numpy"]:
            if f"import {b}" in code or f"__import__('{b}')" in code:
                raise ValueError(f"Import of '{b}' is not allowed.")

    # Execute and capture result
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(code, "<string>", "exec"), namespace)

    # Return 'result' variable if defined, else last assigned variable
    if "result" in namespace:
        return namespace["result"]
    return None


DIFFICULTY_ORDER = {"Easy": 0, "Medium": 1, "Hard": 2, "MAANG": 3}


def generate_python_level1(tables):
    questions = []

    for t, df in tables.items():
        cols = list(df.columns)
        types = detect_types(df)
        nums = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        n = nums[0] if nums else None
        tx = texts[0] if texts else None
        threshold = round(float(df[n].dropna().mean()), 2) if n else 100
        sv = str(df[tx].dropna().iloc[0]) if tx and len(df[tx].dropna()) > 0 else "Value"

        def add(concept, difficulty, question, answer, hint):
            questions.append({
                "concept": concept, "difficulty": difficulty,
                "question": question, "sample_answer": answer, "hint": hint,
                "mode": "python"
            })

        add("df.head()", "Easy",
            f'Preview the first 5 rows of the {t} dataset to understand its structure.',
            f'result = {t}.head()',
            f'Use df.head() or df.head(5) to see the first 5 rows.')

        add("df.shape", "Easy",
            f'How many rows and columns does the {t} dataset have? Store the result.',
            f'result = pd.DataFrame([{{\"rows\": {t}.shape[0], \"columns\": {t}.shape[1]}}])',
            f'df.shape returns a tuple (rows, columns).')

        add("df.describe()", "Easy",
            f'Generate a statistical summary of all numeric columns in {t}.',
            f'result = {t}.describe()',
            f'df.describe() gives count, mean, std, min, max for numeric columns.')

        add("df.dtypes", "Easy",
            f'Check the data type of each column in {t}.',
            f'result = pd.DataFrame({t}.dtypes, columns=["dtype"]).reset_index().rename(columns={{"index":"column"}})',
            f'df.dtypes returns the data type of each column.')

        add("df.isnull()", "Easy",
            f'Count the number of missing values in each column of {t}.',
            f'result = pd.DataFrame({t}.isnull().sum(), columns=["missing"]).reset_index().rename(columns={{"index":"column"}})',
            f'df.isnull().sum() counts NULL values per column.')

        if tx:
            add("value_counts()", "Easy",
                f'How is the data distributed across different categories in {t}? Count occurrences of each unique value in the main text column.',
                f'result = {t}["{tx}"].value_counts().reset_index()\nresult.columns = ["{tx}", "count"]',
                f'df["col"].value_counts() counts each unique value.')

            add("nunique()", "Easy",
                f'How many unique categories exist in the {t} dataset for the main categorical column?',
                f'result = pd.DataFrame([{{"{tx}_unique": {t}["{tx}"].nunique()}}])',
                f'df["col"].nunique() returns the count of unique values.')

            add("Filtering rows", "Easy",
                f'Filter the {t} dataset to show only records where the main category equals "{sv}".',
                f'result = {t}[{t}["{tx}"] == "{sv}"]',
                f'Use boolean indexing: df[df["col"] == value]')

        if n:
            add("Filtering numeric", "Easy",
                f'From {t}, select only the records where the main numeric column is greater than {threshold}.',
                f'result = {t}[{t}["{n}"] > {threshold}]',
                f'Boolean filter: df[df["col"] > value]')

            add("sort_values()", "Easy",
                f'Sort the {t} dataset by the main numeric column from highest to lowest.',
                f'result = {t}.sort_values("{n}", ascending=False).reset_index(drop=True)',
                f'df.sort_values("col", ascending=False) sorts descending.')

            add("Top N rows", "Easy",
                f'Get the top 5 records from {t} with the highest values in the main numeric column.',
                f'result = {t}.nlargest(5, "{n}").reset_index(drop=True)',
                f'df.nlargest(n, "col") returns the n largest rows.')

            add("Column stats", "Medium",
                f'Calculate the mean, median and standard deviation of the main numeric column in {t}.',
                f'result = pd.DataFrame([{{"mean": round({t}["{n}"].mean(),2), "median": round({t}["{n}"].median(),2), "std": round({t}["{n}"].std(),2)}}])',
                f'Use .mean(), .median(), .std() on a Series.')

            add("Percentile", "Medium",
                f'Find the 25th, 50th and 75th percentile of the main numeric column in {t}.',
                f'result = pd.DataFrame([{{"p25": np.percentile({t}["{n}"].dropna(), 25), "p50": np.percentile({t}["{n}"].dropna(), 50), "p75": np.percentile({t}["{n}"].dropna(), 75)}}])',
                f'Use np.percentile(series, q) where q is 0-100.')

            if tx:
                add("groupby + count", "Medium",
                    f'Count how many records fall into each category in {t}.',
                    f'result = {t}.groupby("{tx}").size().reset_index(name="count").sort_values("count", ascending=False)',
                    f'df.groupby("col").size() counts rows per group.')

                add("groupby + sum", "Medium",
                    f'Calculate the total of the numeric column for each category in {t}.',
                    f'result = {t}.groupby("{tx}")["{n}"].sum().reset_index().rename(columns={{"{n}":"total"}}).sort_values("total", ascending=False)',
                    f'df.groupby("col")["num"].sum() aggregates by group.')

                add("groupby + mean", "Medium",
                    f'Find the average numeric value per category in {t}. Round to 2 decimal places.',
                    f'result = {t}.groupby("{tx}")["{n}"].mean().round(2).reset_index().rename(columns={{"{n}":"average"}}).sort_values("average", ascending=False)',
                    f'df.groupby("col")["num"].mean() gives mean per group.')

    questions = sorted(questions, key=lambda q: DIFFICULTY_ORDER.get(q.get("difficulty","Easy"), 0))
    random.shuffle(questions)
    return questions[:20]


def generate_python_level2(tables):
    questions = []
    table_list = list(tables.items())

    for i, (t, df) in enumerate(table_list):
        cols = list(df.columns)
        types = detect_types(df)
        nums = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        n = nums[0] if nums else None
        n2 = nums[1] if len(nums) > 1 else None
        tx = texts[0] if texts else None
        threshold = round(float(df[n].dropna().mean()), 2) if n else 100
        others = [(tn, tdf) for j, (tn, tdf) in enumerate(table_list) if j != i]

        def add(concept, difficulty, question, answer, hint):
            questions.append({
                "concept": concept, "difficulty": difficulty,
                "question": question, "sample_answer": answer, "hint": hint,
                "mode": "python"
            })

        if n and tx:
            add("groupby + agg", "Medium",
                f'For each category in {t}, calculate count, sum, mean and max of the numeric column in one operation.',
                f'result = {t}.groupby("{tx}")["{n}"].agg(["count","sum","mean","max"]).round(2).reset_index()',
                f'df.groupby("col")["num"].agg(["count","sum","mean","max"]) computes multiple aggregations.')

            add("apply()", "Medium",
                f'Add a new column to {t} that categorizes each row as High, Medium or Low based on the numeric column.',
                f'def categorize(x):\n    if x > 100: return "High"\n    elif x > 50: return "Medium"\n    else: return "Low"\nresult = {t}.copy()\nresult["category"] = result["{n}"].apply(categorize)',
                f'df["col"].apply(func) applies a function to each value.')

            add("Above average filter", "Hard",
                f'Find all records in {t} where the numeric value is above the group average for their category.',
                f'group_avg = {t}.groupby("{tx}")["{n}"].transform("mean")\nresult = {t}[{t}["{n}"] > group_avg].reset_index(drop=True)',
                f'Use transform("mean") to broadcast group mean to each row, then filter.')

            add("pivot_table", "Hard",
                f'Create a pivot table from {t} showing the average numeric value for each category.',
                f'result = pd.pivot_table({t}, values="{n}", index="{tx}", aggfunc="mean").round(2).reset_index()',
                f'pd.pivot_table(df, values="num", index="cat", aggfunc="mean")')

            add("rank()", "Hard",
                f'Rank all records in {t} by the numeric column from highest to lowest. Add a rank column.',
                f'result = {t}.copy()\nresult["rank"] = result["{n}"].rank(ascending=False, method="dense").astype(int)\nresult = result.sort_values("rank")',
                f'df["col"].rank(ascending=False, method="dense") ranks values.')

            add("cumsum()", "Hard",
                f'Add a running cumulative total of the numeric column to {t}, sorted by the current order.',
                f'result = {t}.copy()\nresult["cumulative"] = result["{n}"].cumsum()',
                f'df["col"].cumsum() creates a running total.')

            add("Top N per group", "Hard",
                f'Find the top 2 records per category in {t} based on the highest numeric value.',
                f'result = {t}.sort_values("{n}", ascending=False).groupby("{tx}").head(2).reset_index(drop=True)',
                f'Sort first, then groupby().head(n) gets top n per group.')

            add("pct_change()", "Hard",
                f'Calculate the percentage change in the numeric column between consecutive rows in {t}.',
                f'result = {t}.copy()\nresult["pct_change"] = result["{n}"].pct_change().round(4)\nresult = result.dropna()',
                f'df["col"].pct_change() gives row-over-row % change.')

        if others:
            t2, df2 = others[0]
            shared = next((c for c in cols if c in df2.columns), cols[0])

            add("pd.merge() inner", "Medium",
                f'Merge {t} and {t2} datasets keeping only records that exist in both.',
                f'result = pd.merge({t}, {t2}, on="{shared}", how="inner")',
                f'pd.merge(df1, df2, on="key", how="inner") keeps matching rows only.')

            add("pd.merge() left", "Medium",
                f'Merge {t} and {t2} keeping all records from {t} even if no match exists in {t2}.',
                f'result = pd.merge({t}, {t2}, on="{shared}", how="left")',
                f'how="left" keeps all rows from the left dataframe.')

            add("Anti-join", "Hard",
                f'Find all records in {t} that have NO match in {t2}.',
                f'merged = pd.merge({t}, {t2}[["{shared}"]], on="{shared}", how="left", indicator=True)\nresult = merged[merged["_merge"] == "left_only"].drop("_merge", axis=1).reset_index(drop=True)',
                f'Merge with indicator=True, then filter where _merge == "left_only".')

        questions.append({
            "concept": "NumPy operations", "difficulty": "Medium",
            "question": f'Using NumPy on {t}, calculate the mean, variance and standard deviation of all numeric columns.',
            "sample_answer": f'num_cols = {t}.select_dtypes(include="number").columns\nresult = pd.DataFrame({{\n    "column": num_cols,\n    "mean": [round(np.mean({t}[c].dropna()),2) for c in num_cols],\n    "variance": [round(np.var({t}[c].dropna()),2) for c in num_cols],\n    "std": [round(np.std({t}[c].dropna()),2) for c in num_cols]\n}})',
            "hint": "np.mean(), np.var(), np.std() work on arrays/series.",
            "mode": "python"
        })

    questions = sorted(questions, key=lambda q: DIFFICULTY_ORDER.get(q.get("difficulty","Easy"), 0))
    random.shuffle(questions)
    return questions[:20]


def generate_python_level3(tables):
    questions = []

    for t, df in tables.items():
        cols = list(df.columns)
        types = detect_types(df)
        nums = [c for c in cols if types[c] == "numeric"]
        texts = [c for c in cols if types[c] == "text"]
        n = nums[0] if nums else None
        n2 = nums[1] if len(nums) > 1 else None
        tx = texts[0] if texts else None

        def add(concept, difficulty, question, answer, hint):
            questions.append({
                "concept": concept, "difficulty": difficulty,
                "question": question, "sample_answer": answer, "hint": hint,
                "mode": "python"
            })

        if n and tx:
            add("rolling window", "Hard",
                f'[Google] Calculate a 3-row rolling average of the numeric column in {t}.',
                f'result = {t}.copy()\nresult["rolling_avg"] = result["{n}"].rolling(window=3).mean().round(2)',
                f'df["col"].rolling(window=3).mean() computes moving average.')

            add("transform + rank", "MAANG",
                f'[Amazon] For each record in {t}, add a column showing its rank within its category group based on the numeric column.',
                f'result = {t}.copy()\nresult["group_rank"] = result.groupby("{tx}")["{n}"].rank(ascending=False, method="dense").astype(int)',
                f'groupby().rank() ranks within each group.')

            add("Pareto 80/20", "MAANG",
                f'[Meta] Identify which categories in {t} account for 80% of the total numeric value (Pareto principle).',
                f'totals = {t}.groupby("{tx}")["{n}"].sum().sort_values(ascending=False).reset_index()\ntotals["cumulative_pct"] = totals["{n}"].cumsum() / totals["{n}"].sum() * 100\nresult = totals[totals["cumulative_pct"].shift(1, fill_value=0) < 80]',
                f'Sort descending, calculate cumsum as % of total, filter where cumulative < 80%.')

            add("Correlation matrix", "MAANG",
                f'[Data Science] Calculate the Pearson correlation between all numeric columns in {t}.',
                f'result = {t}.select_dtypes(include="number").corr().round(3).reset_index()\nresult.rename(columns={{"index":"column"}}, inplace=True)',
                f'df.corr() computes pairwise correlation of all numeric columns.')

            add("Z-score normalization", "MAANG",
                f'[Netflix] Normalize the numeric column in {t} using Z-score standardization.',
                f'result = {t}.copy()\nmean = result["{n}"].mean()\nstd = result["{n}"].std()\nresult["z_score"] = ((result["{n}"] - mean) / std).round(4)',
                f'Z-score = (value - mean) / std. Values within ±2 are typical.')

            add("Outlier detection", "MAANG",
                f'[Uber] Find outliers in the numeric column of {t} using the IQR method (values below Q1-1.5*IQR or above Q3+1.5*IQR).',
                f'Q1 = {t}["{n}"].quantile(0.25)\nQ3 = {t}["{n}"].quantile(0.75)\nIQR = Q3 - Q1\nresult = {t}[({t}["{n}"] < Q1 - 1.5*IQR) | ({t}["{n}"] > Q3 + 1.5*IQR)].reset_index(drop=True)',
                f'IQR = Q3 - Q1. Outliers are below Q1-1.5*IQR or above Q3+1.5*IQR.')

            add("crosstab", "Hard",
                f'[Airbnb] Create a cross-tabulation showing the count of records for each combination of categorical values in {t}.',
                f'result = pd.crosstab({t}["{tx}"], {t}["{texts[1] if len(texts)>1 else tx}"]).reset_index()' if len(texts) > 1 else
                f'result = {t}.groupby("{tx}").size().reset_index(name="count")',
                f'pd.crosstab(df["col1"], df["col2"]) creates a frequency table.')

            add("window + pct of total", "MAANG",
                f'[Google] For each record in {t}, calculate what percentage of the group total the numeric value represents.',
                f'result = {t}.copy()\ngroup_total = result.groupby("{tx}")["{n}"].transform("sum")\nresult["pct_of_group"] = (result["{n}"] / group_total * 100).round(2)',
                f'transform("sum") broadcasts the group total to each row. Divide individual by group total.')

            add("YoY with shift", "MAANG",
                f'[Amazon] Calculate year-over-year growth of the numeric metric in {t} grouped by category.',
                f'result = {t}.groupby("{tx}")["{n}"].sum().reset_index()\nresult["prev"] = result["{n}"].shift(1)\nresult["yoy_growth_pct"] = ((result["{n}"] - result["prev"]) / result["prev"] * 100).round(2)',
                f'shift(1) gets the previous row value. Useful for period-over-period comparisons.')

            if n2:
                add("np.where()", "Hard",
                    f'[Meta] Use numpy to add a flag column to {t} — 1 if the numeric value is above average, 0 otherwise.',
                    f'result = {t}.copy()\nresult["above_avg"] = np.where(result["{n}"] > result["{n}"].mean(), 1, 0)',
                    f'np.where(condition, value_if_true, value_if_false) is vectorized if-else.')

    questions = sorted(questions, key=lambda q: DIFFICULTY_ORDER.get(q.get("difficulty","Easy"), 0))
    random.shuffle(questions)
    return questions[:20]


def get_python_questions(tables: dict, level: int) -> list:
    if level == 1:
        qs = generate_python_level1(tables)
    elif level == 2:
        qs = generate_python_level2(tables)
    else:
        qs = generate_python_level3(tables)

    for i, q in enumerate(qs):
        expected = compute_expected(q["sample_answer"], tables)
        q.update(expected)
        q["id"] = i + 1

    return qs

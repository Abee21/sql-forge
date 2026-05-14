import duckdb
import pandas as pd
import numpy as np


def run_sql(sql: str, tables: dict) -> pd.DataFrame:
    conn = duckdb.connect()
    for name, df in tables.items():
        conn.register(name, df)
    result = conn.execute(sql).fetchdf()
    conn.close()
    return result


def normalize_df(df: pd.DataFrame, strict: bool = True) -> pd.DataFrame:
    """
    Normalize dataframe for comparison.
    - Always: sort columns alphabetically, reset index
    - Strict (Hero): exact numeric values
    - Lenient (Beginner): round numbers to 1 decimal place
    """
    if df.empty:
        return df

    df = df.copy()

    # Round floats
    for col in df.select_dtypes(include="float").columns:
        if strict:
            df[col] = df[col].round(4)
        else:
            df[col] = df[col].round(1)  # More tolerance in beginner

    # Sort columns alphabetically — fixes column order differences
    df = df.reindex(sorted(df.columns, key=lambda x: str(x).lower()), axis=1)

    # Rename all columns to generic names — fixes alias differences
    df.columns = [f"col_{i}" for i in range(len(df.columns))]

    # Sort rows — fixes row order differences
    try:
        df = df.sort_values(by=list(df.columns)).reset_index(drop=True)
    except Exception:
        df = df.reset_index(drop=True)

    return df


def values_close_enough(ref: pd.DataFrame, stu: pd.DataFrame, tolerance: float = 0.05) -> bool:
    """Check if numeric values are within tolerance percentage (for Beginner mode)"""
    try:
        for col in ref.columns:
            ref_col = ref[col]
            stu_col = stu[col]
            if ref_col.dtype in [np.float64, np.int64]:
                # Allow 5% tolerance
                diff = (ref_col - stu_col).abs()
                allowed = ref_col.abs() * tolerance + 0.01
                if not (diff <= allowed).all():
                    return False
            else:
                if not ref_col.equals(stu_col):
                    return False
        return True
    except Exception:
        return False


def evaluate_answer(schema_info: str, question: str, concept: str,
                    sample_answer: str, user_sql: str, api_key: str,
                    tables: dict = None, mode: str = "Hero") -> dict:

    if not tables:
        return {"correct": False, "score": 0,
                "explanation": "No table data available.",
                "tip": "Make sure your file is uploaded."}

    strict = (mode == "Hero")

    # Run reference answer
    try:
        ref_result = run_sql(sample_answer, tables)
    except Exception as e:
        return {"correct": False, "score": 0,
                "explanation": f"Reference query error: {str(e)}",
                "tip": "System error — try next question."}

    # Run student query
    try:
        student_result = run_sql(user_sql, tables)
    except Exception as e:
        return {"correct": False, "score": 0,
                "explanation": f"Syntax error in your query: {str(e)}",
                "tip": "Check table name, column names and SQL syntax carefully."}

    # Normalize both
    ref_norm = normalize_df(ref_result, strict=strict)
    stu_norm = normalize_df(student_result, strict=strict)

    ref_rows, ref_cols = ref_norm.shape
    stu_rows, stu_cols = stu_norm.shape

    # Check row count
    if ref_rows != stu_rows:
        return {
            "correct": False, "score": 20,
            "explanation": f"Expected {ref_rows} rows but your query returned {stu_rows} rows. "
                          f"{'Check your WHERE or HAVING condition.' if stu_rows < ref_rows else 'You may have duplicate rows or a missing filter.'}",
            "tip": "Run your query first to see the output and compare with what the question expects."
        }

    # Check column count
    if ref_cols != stu_cols:
        if strict:
            return {
                "correct": False, "score": 30,
                "explanation": f"Expected {ref_cols} column(s) but your query returned {stu_cols} column(s).",
                "tip": "Check which columns the question is asking you to select."
            }
        # Beginner mode: if row count matches and at least one column matches, be lenient
        # Check if student result contains all reference columns by value
        if stu_cols < ref_cols:
            return {
                "correct": False, "score": 50,
                "explanation": f"You selected {stu_cols} column(s) but the answer needs {ref_cols} column(s). Your logic seems right but you're missing some columns.",
                "tip": "Add the missing columns to your SELECT statement."
            }

    # Exact match check
    if ref_norm.equals(stu_norm):
        return {
            "correct": True, "score": 100,
            "explanation": f"✓ Perfect! Your query returned exactly the correct result — {stu_rows} row(s) with matching values.",
            "tip": "Great work! Try the next question."
        }

    # Beginner mode: check with value tolerance
    if not strict:
        if values_close_enough(ref_norm, stu_norm, tolerance=0.05):
            return {
                "correct": True, "score": 85,
                "explanation": f"✓ Correct! Your values are within the acceptable range. (Beginner mode: 5% tolerance applied)",
                "tip": "Switch to Hero mode for exact value checking."
            }

        # Beginner: also check if they got the right concept even if values differ slightly
        # If row count matches and column count matches, give partial credit
        return {
            "correct": False, "score": 55,
            "explanation": f"Your query returned {stu_rows} rows and {stu_cols} columns (correct shape!) but the values don't match the expected output.",
            "tip": "Check your aggregation function, GROUP BY columns, or WHERE condition."
        }

    # Hero mode: strict exact match failed
    # Check if it's a ranking issue (RANK vs ROW_NUMBER with ties)
    if "rank" in question.lower() or "row_number" in concept.lower():
        return {
            "correct": False, "score": 45,
            "explanation": "Your query structure looks right but the ranking values differ. If there are tied values, RANK() and ROW_NUMBER() produce different results.",
            "tip": "Check if your data has ties — if yes, use RANK() not ROW_NUMBER() for ranking questions."
        }

    return {
        "correct": False, "score": 35,
        "explanation": f"Your query returned the right shape ({stu_rows} rows, {stu_cols} cols) but the values don't exactly match. (Hero mode: exact match required)",
        "tip": "Check your aggregation, ORDER BY, or filter condition."
    }

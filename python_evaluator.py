import pandas as pd
import numpy as np
import io
import contextlib
import traceback


def run_python(code: str, tables: dict) -> object:
    """Safely execute Python code"""
    namespace = {"pd": pd, "np": np}
    for name, df in tables.items():
        namespace[name] = df.copy()
    namespace["df"] = list(tables.values())[0].copy() if tables else pd.DataFrame()

    # Block dangerous operations
    dangerous = ["import os", "import sys", "import subprocess", "import shutil",
                 "__import__", "open(", "exec(", "eval(", "compile("]
    for d in dangerous:
        if d in code:
            raise ValueError(f"Operation '{d}' is not allowed for security reasons.")

    exec(compile(code, "<string>", "exec"), namespace)

    if "result" in namespace:
        return namespace["result"]
    return None


def normalize_output(output) -> pd.DataFrame:
    """Convert any output to comparable DataFrame"""
    if isinstance(output, pd.DataFrame):
        df = output.copy().reset_index(drop=True)
    elif isinstance(output, pd.Series):
        df = output.reset_index()
        df.columns = [str(c) for c in df.columns]
    elif isinstance(output, (int, float, np.integer, np.floating)):
        df = pd.DataFrame([{"value": round(float(output), 4)}])
    elif isinstance(output, dict):
        df = pd.DataFrame([output])
    else:
        df = pd.DataFrame([{"value": str(output)}])

    # Round floats
    for col in df.select_dtypes(include="float").columns:
        df[col] = df[col].round(2)

    # Sort columns and rows
    df = df.reindex(sorted(df.columns, key=str), axis=1)
    df.columns = [f"col_{i}" for i in range(len(df.columns))]
    try:
        df = df.sort_values(by=list(df.columns)).reset_index(drop=True)
    except:
        df = df.reset_index(drop=True)

    return df


def evaluate_python(question: str, concept: str, sample_answer: str,
                    user_code: str, tables: dict, mode: str = "Hero") -> dict:
    strict = (mode == "Hero")

    # Run reference
    try:
        ref_output = run_python(sample_answer, tables)
        ref_df = normalize_output(ref_output)
    except Exception as e:
        return {"correct": False, "score": 0,
                "explanation": f"Reference code error: {str(e)}",
                "tip": "System error — try next question."}

    # Run student code
    try:
        stu_output = run_python(user_code, tables)
        if stu_output is None:
            return {"correct": False, "score": 0,
                    "explanation": "Your code ran but produced no output. Make sure you assign your final result to a variable called 'result'.",
                    "tip": "Add 'result = your_dataframe' at the end of your code."}
        stu_df = normalize_output(stu_output)
    except Exception as e:
        return {"correct": False, "score": 0,
                "explanation": f"Your code has an error: {str(e)}",
                "tip": "Check your syntax, column names and method names carefully."}

    ref_rows, ref_cols = ref_df.shape
    stu_rows, stu_cols = stu_df.shape

    # Check shape
    if ref_rows != stu_rows:
        return {
            "correct": False, "score": 20,
            "explanation": f"Expected {ref_rows} rows but got {stu_rows} rows.",
            "tip": "Check your filter conditions or groupby logic."
        }

    if ref_cols != stu_cols:
        if strict:
            return {
                "correct": False, "score": 30,
                "explanation": f"Expected {ref_cols} column(s) but got {stu_cols} column(s).",
                "tip": "Check which columns or aggregations the question asks for."
            }

    # Exact match
    if ref_df.equals(stu_df):
        return {
            "correct": True, "score": 100,
            "explanation": f"✓ Perfect! Your code produced exactly the correct output — {stu_rows} row(s) with matching values.",
            "tip": "Excellent work!"
        }

    # Beginner tolerance
    if not strict:
        try:
            for col in ref_df.columns:
                if col in stu_df.columns:
                    r = pd.to_numeric(ref_df[col], errors="coerce")
                    s = pd.to_numeric(stu_df[col], errors="coerce")
                    if r.notna().all() and s.notna().all():
                        if not ((r - s).abs() <= r.abs() * 0.05 + 0.01).all():
                            break
            else:
                return {
                    "correct": True, "score": 85,
                    "explanation": "✓ Correct! Values are within acceptable range. (Beginner mode: 5% tolerance)",
                    "tip": "Switch to Hero mode for exact matching."
                }
        except:
            pass

    return {
        "correct": False, "score": 40,
        "explanation": f"Your code returned the right shape ({stu_rows} rows) but values don't match the expected output.",
        "tip": "Run your code and check the output carefully. Compare with the expected columns shown above."
    }

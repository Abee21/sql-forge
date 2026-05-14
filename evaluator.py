import google.generativeai as genai
import json


def evaluate_answer(schema_info: str, question: str, concept: str,
                    sample_answer: str, user_sql: str, api_key: str) -> dict:
    """
    Use Google Gemini to evaluate if the user's SQL is logically correct.
    Returns: {"correct": bool, "score": int, "explanation": str, "tip": str}
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""You are a strict PostgreSQL SQL evaluator.

Schema:
{schema_info}

Question: {question}
Concept being tested: {concept}
Reference answer:
{sample_answer}

Student's SQL:
{user_sql}

Evaluate: does the student's SQL logically solve the question correctly?
- Minor alias/formatting differences are fine
- Wrong table, missing JOIN, wrong aggregation = incorrect
- Partially correct = give partial score

Return ONLY raw JSON, no markdown, no explanation:
{{"correct": true, "score": 85, "explanation": "Your feedback here.", "tip": "One improvement tip."}}"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        return {
            "correct": False,
            "score": 0,
            "explanation": f"Evaluation error: {str(e)}",
            "tip": "Check your syntax and try again."
        }

import google.generativeai as genai
import json


def evaluate_answer(schema_info: str, question: str, concept: str,
                    sample_answer: str, user_sql: str, api_key: str) -> dict:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash-8b")

    prompt = f"""You are a PostgreSQL SQL evaluator. Be LENIENT — focus on logic not formatting.

Schema:
{schema_info}

Question: {question}
Concept: {concept}
Reference answer:
{sample_answer}

Student SQL:
{user_sql}

EVALUATION RULES:
- If the student query produces the SAME logical result as the reference = CORRECT
- Case differences (SELECT vs select) = OK
- Different aliases = OK
- Extra spaces, different formatting = OK
- Missing semicolon = OK
- Wrong table, missing JOIN, wrong aggregation = INCORRECT
- Be generous — if the logic is right, mark it correct

Return ONLY raw JSON, no markdown, no explanation:
{{"correct": true, "score": 90, "explanation": "Short feedback.", "tip": "One tip."}}"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        return {"correct": False, "score": 0,
                "explanation": f"Evaluation error: {str(e)}",
                "tip": "Check your syntax and try again."}

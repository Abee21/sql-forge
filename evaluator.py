import google.generativeai as genai
import json


def evaluate_answer(schema_info: str, question: str, concept: str,
                    sample_answer: str, user_sql: str, api_key: str) -> dict:
    genai.configure(api_key=api_key)
    
    # Try models in order until one works
    models_to_try = [
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-pro",
        "gemini-1.0-pro"
    ]
    
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
- Same logical result as reference = CORRECT
- Case differences, aliases, formatting = OK
- Missing semicolon = OK
- Wrong table, missing JOIN, wrong aggregation = INCORRECT

Return ONLY raw JSON:
{{"correct": true, "score": 90, "explanation": "Short feedback.", "tip": "One tip."}}"""

    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            raw = response.text.strip().replace("```json","").replace("```","").strip()
            return json.loads(raw)
        except Exception as e:
            last_error = str(e)
            continue
    
    return {"correct": False, "score": 0,
            "explanation": f"Evaluation error: {last_error}",
            "tip": "Check your syntax and try again."}

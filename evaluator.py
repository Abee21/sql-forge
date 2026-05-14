import json
import urllib.request


def evaluate_answer(schema_info: str, question: str, concept: str,
                    sample_answer: str, user_sql: str, api_key: str) -> dict:

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
- Be generous — if logic is right, mark correct

Return ONLY raw JSON, no markdown:
{{"correct": true, "score": 90, "explanation": "Short feedback.", "tip": "One tip."}}"""

    payload = json.dumps({
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.1
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            raw = data["choices"][0]["message"]["content"]
            raw = raw.strip().replace("```json","").replace("```","").strip()
            return json.loads(raw)
    except Exception as e:
        return {"correct": False, "score": 0,
                "explanation": f"Evaluation error: {str(e)}",
                "tip": "Check your syntax and try again."}

import json
import urllib.request
import urllib.error


def evaluate_answer(schema_info: str, question: str, concept: str,
                    sample_answer: str, user_sql: str, api_key: str) -> dict:

    prompt = f"""You are a PostgreSQL SQL evaluator. Be LENIENT.

Schema: {schema_info}
Question: {question}
Concept: {concept}
Reference: {sample_answer}
Student SQL: {user_sql}

Rules: Same logic = CORRECT. Case/formatting/aliases/semicolon = OK. Wrong table or aggregation = INCORRECT.

Respond with ONLY this JSON (no markdown):
{{"correct": true, "score": 85, "explanation": "feedback here", "tip": "tip here"}}"""

    payload = json.dumps({
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.1
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            method="POST"
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw = data["choices"][0]["message"]["content"]
            raw = raw.strip().replace("```json","").replace("```","").strip()
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return {"correct": False, "score": 0,
                "explanation": f"API Error {e.code}: {body[:200]}",
                "tip": "Check your API key in settings."}
    except Exception as e:
        return {"correct": False, "score": 0,
                "explanation": f"Evaluation error: {str(e)}",
                "tip": "Check your syntax and try again."}

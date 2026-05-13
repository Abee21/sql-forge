# ⬡ SQL.FORGE — PostgreSQL Practice Engine

A standalone SQL practice platform that generates questions from your own CSV/Excel data.

## How it works
- **Question generation** → Pure Python logic (free, instant, zero AI)
- **Answer evaluation** → Claude AI checks your SQL logic
- **3 levels** → Foundations → Joins → Advanced (CTEs, window functions)
- **15 streak** → Advance to next level

---

## Run Locally

### 1. Clone / download this project

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your API key
Create `.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```
Get your key free at: https://console.anthropic.com

### 4. Run
```bash
streamlit run app.py
```
Opens at http://localhost:8501

---

## Deploy Free on Streamlit Cloud

1. Push this project to a **GitHub repo**
2. Go to https://share.streamlit.io
3. Click **New app** → connect your repo
4. Set main file: `app.py`
5. Go to **Settings → Secrets** and add:
   ```
   ANTHROPIC_API_KEY = "sk-ant-your-key-here"
   ```
6. Click **Deploy** — your app is live!

---

## Project Structure

```
sql-forge/
├── app.py                  ← Main Streamlit app (UI)
├── question_generator.py   ← Pure Python question generation
├── evaluator.py            ← AI answer evaluation
├── requirements.txt
└── .streamlit/
    └── secrets.toml        ← Your API key (never commit this)
```

---

## Cost
- Question generation: **₹0** (pure Python)
- Answer evaluation: ~₹0.003 per submission (Claude Haiku)
- Full session (20 answers): ~₹0.06 total

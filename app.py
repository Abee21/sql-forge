import streamlit as st
import pandas as pd
import duckdb
import io
import os
from question_generator import get_questions
from evaluator import evaluate_answer

st.set_page_config(page_title="SQL Forge", page_icon="⬡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif !important; }
.stApp { background: #080c14; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #0c1220 !important; border-right: 1px solid #1a2535; }
section[data-testid="stSidebar"] * { color: #8899aa !important; }

/* Hide streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem !important; }

/* Text areas */
.stTextArea textarea {
    background: #060a10 !important;
    color: #e2f0ff !important;
    border: 1px solid #1a2535 !important;
    border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    line-height: 1.8 !important;
    caret-color: #00ff9d;
}
.stTextArea textarea:focus { border-color: #00ff9d55 !important; box-shadow: 0 0 0 2px #00ff9d11 !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #00ff9d, #00cc7a) !important;
    color: #080c14 !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.3px !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.2s !important;
}
.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0 4px 20px #00ff9d33 !important; }
.stButton > button:disabled { opacity: 0.4 !important; transform: none !important; }

/* Run button specific */
.run-btn .stButton > button {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    color: white !important;
}

/* Metrics */
[data-testid="metric-container"] {
    background: #0c1220 !important;
    border: 1px solid #1a2535 !important;
    border-radius: 10px !important;
    padding: 14px !important;
}
[data-testid="metric-container"] label { color: #4a6080 !important; font-size: 10px !important; letter-spacing: 1px !important; text-transform: uppercase !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #00ff9d !important; font-size: 24px !important; font-weight: 700 !important; }

/* Progress */
.stProgress > div > div { background: linear-gradient(90deg, #00ff9d, #00cc7a) !important; border-radius: 99px !important; }
.stProgress { background: #1a2535 !important; border-radius: 99px !important; }

/* Dataframe */
.stDataFrame { border: 1px solid #1a2535 !important; border-radius: 8px !important; }

/* File uploader */
[data-testid="stFileUploader"] { background: #0c1220 !important; border: 2px dashed #1a2535 !important; border-radius: 12px !important; }

/* Code */
code { background: #0c1220 !important; color: #00ff9d !important; border-radius: 4px !important; font-family: 'JetBrains Mono', monospace !important; }
pre { background: #060a10 !important; border: 1px solid #1a2535 !important; border-radius: 8px !important; }

/* Expander */
details { border: 1px solid #1a2535 !important; border-radius: 8px !important; background: #0c1220 !important; }
details summary { color: #8899aa !important; }

/* Selectbox */
.stSelectbox > div > div { background: #0c1220 !important; border-color: #1a2535 !important; color: #e2f0ff !important; }

/* Text input */
.stTextInput > div > div > input { background: #0c1220 !important; border-color: #1a2535 !important; color: #e2f0ff !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ── State ────────────────────────────────────────────────────
def init():
    defaults = {
        "stage": "upload", "tables": {}, "questions": [], "qi": 0,
        "level": 1, "streak": 0, "stats": {"total": 0, "correct": 0, "times": []},
        "feedback": None, "user_sql": "", "file_name": "", "query_result": None,
        "query_error": None, "query_ran": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
init()

LEVELS = {
    1: {"label": "Level 1", "title": "Foundations", "color": "#00ff9d", "tag": "L1", "desc": "Aggregations · Filtering · Grouping"},
    2: {"label": "Level 2", "title": "Joins & Subqueries", "color": "#f59e0b", "tag": "L2", "desc": "JOINs · Subqueries · CASE · CTEs"},
    3: {"label": "Level 3", "title": "MAANG Level", "color": "#f87171", "tag": "L3", "desc": "Window Functions · Cohorts · YoY · Gaps"},
}

DIFFICULTY_COLOR = {"Easy": "#00ff9d", "Medium": "#f59e0b", "Hard": "#f87171", "MAANG": "#c084fc"}

def get_api_key():
    try: return st.secrets["GEMINI_API_KEY"]
    except: return os.environ.get("GEMINI_API_KEY", st.session_state.get("api_key", ""))

def get_schema_text():
    return "\n".join([f'Table "{n}" ({len(d)} rows), columns: {", ".join(d.columns)}' for n, d in st.session_state.tables.items()])

def parse_file(f):
    ext = f.name.rsplit(".", 1)[-1].lower()
    tables = {}
    if ext == "csv":
        df = pd.read_csv(f)
        name = f.name.rsplit(".", 1)[0].replace(" ", "_").replace("-", "_").lower()
        tables[name] = df
    elif ext in ["xlsx", "xls"]:
        xf = pd.ExcelFile(f)
        for sh in xf.sheet_names[:3]:
            df = pd.read_excel(f, sheet_name=sh)
            if len(df): tables[sh.replace(" ", "_").lower()] = df
    return tables

def run_query(sql):
    try:
        conn = duckdb.connect()
        for name, df in st.session_state.tables.items():
            conn.register(name, df)
        result = conn.execute(sql).fetchdf()
        conn.close()
        return result, None
    except Exception as e:
        return None, str(e)

def start_level(lvl):
    qs = get_questions(st.session_state.tables, lvl)
    st.session_state.update({
        "questions": qs, "qi": 0, "streak": 0, "feedback": None,
        "user_sql": "", "level": lvl, "stage": "practice",
        "query_result": None, "query_error": None, "query_ran": False
    })
    st.rerun()

def next_q():
    st.session_state.update({
        "qi": (st.session_state.qi + 1) % len(st.session_state.questions),
        "feedback": None, "user_sql": "", "query_result": None,
        "query_error": None, "query_ran": False
    })
    st.rerun()

# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:16px 0 8px'>
        <div style='color:#00ff9d;font-size:22px;font-weight:800;letter-spacing:2px'>⬡ SQL.FORGE</div>
        <div style='color:#4a6080;font-size:11px;margin-top:2px;letter-spacing:1px'>POSTGRESQL PRACTICE ENGINE</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<hr style='border-color:#1a2535;margin:8px 0 16px'>", unsafe_allow_html=True)

    if st.session_state.stage == "practice":
        cfg = LEVELS[st.session_state.level]
        q = st.session_state.questions[st.session_state.qi] if st.session_state.questions else {}
        diff = q.get("difficulty", "")

        st.markdown(f"""
        <div style='background:#0c1220;border:1px solid {cfg["color"]}33;border-radius:10px;padding:14px;margin-bottom:16px'>
            <div style='color:{cfg["color"]};font-size:10px;font-weight:700;letter-spacing:1.5px'>{cfg["label"].upper()}</div>
            <div style='color:#e2f0ff;font-size:15px;font-weight:700;margin:4px 0'>{cfg["title"]}</div>
            <div style='color:#4a6080;font-size:11px'>{cfg["desc"]}</div>
        </div>
        """, unsafe_allow_html=True)

        # Streak
        st.markdown(f"<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>STREAK — {st.session_state.streak}/15</div>", unsafe_allow_html=True)
        dots = "".join([f"<span style='display:inline-block;width:13px;height:13px;background:{'#00ff9d' if i < st.session_state.streak else '#1a2535'};border-radius:3px;margin:2px'></span>" for i in range(15)])
        st.markdown(f"<div>{dots}</div>", unsafe_allow_html=True)
        st.progress(st.session_state.streak / 15)
        st.markdown("<hr style='border-color:#1a2535;margin:12px 0'>", unsafe_allow_html=True)

        # Stats
        s = st.session_state.stats
        acc = round((s["correct"] / s["total"]) * 100) if s["total"] > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric("Solved", s["total"])
        c2.metric("Accuracy", f"{acc}%")
        st.markdown("<hr style='border-color:#1a2535;margin:12px 0'>", unsafe_allow_html=True)

        # Schema Browser
        st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:10px'>DATABASE SCHEMA</div>", unsafe_allow_html=True)
        for tname, df in st.session_state.tables.items():
            with st.expander(f"⬡ {tname}  ({len(df)} rows)"):
                types_map = {}
                for col in df.columns:
                    if df[col].dtype in ["int64", "float64"]: types_map[col] = ("123", "#f59e0b")
                    else: types_map[col] = ("abc", "#8899aa")
                for col, (icon, color) in types_map.items():
                    st.markdown(f"<div style='color:{color};font-size:11px;font-family:monospace;padding:2px 0'><span style='opacity:.5'>{icon}</span> {col}</div>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#1a2535;margin:12px 0'>", unsafe_allow_html=True)

        # Level Progress
        st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:10px'>PROGRESS</div>", unsafe_allow_html=True)
        for l in [1,2,3]:
            lc = LEVELS[l]
            cur = st.session_state.level
            if l < cur: st.markdown(f"<div style='color:#4a6080;font-size:11px;margin-bottom:6px'>✓ {lc['label']}: {lc['title']}</div>", unsafe_allow_html=True)
            elif l == cur: st.markdown(f"<div style='color:{lc['color']};font-size:11px;font-weight:700;margin-bottom:6px'>▶ {lc['label']}: {lc['title']}</div>", unsafe_allow_html=True)
            else: st.markdown(f"<div style='color:#1a2535;font-size:11px;margin-bottom:6px'>○ {lc['label']}: {lc['title']}</div>", unsafe_allow_html=True)

        st.markdown("")
        if st.button("↩ New File"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            init(); st.rerun()

# ── UPLOAD ───────────────────────────────────────────────────
if st.session_state.stage == "upload":
    st.markdown("""
    <div style='text-align:center;padding:40px 0 30px'>
        <div style='font-size:56px;margin-bottom:16px'>⬡</div>
        <div style='color:#00ff9d;font-size:42px;font-weight:800;letter-spacing:3px;margin-bottom:8px'>SQL.FORGE</div>
        <div style='color:#4a6080;font-size:15px;max-width:500px;margin:0 auto;line-height:1.6'>
            Upload your data. Practice real PostgreSQL from foundations to MAANG-level interview questions.
        </div>
    </div>
    """, unsafe_allow_html=True)

    api_key = get_api_key()
    if not api_key:
        st.markdown("""<div style='background:#0c1220;border:1px solid #f59e0b44;border-radius:10px;padding:16px;margin-bottom:20px'>
            <div style='color:#f59e0b;font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>🔑 GEMINI API KEY REQUIRED</div>
            <div style='color:#4a6080;font-size:12px;margin-bottom:10px'>Free at aistudio.google.com — needed only for answer evaluation</div>
        </div>""", unsafe_allow_html=True)
        key_input = st.text_input("Paste your Gemini API key", type="password", placeholder="AIza...")
        if key_input: st.session_state["api_key"] = key_input
        st.markdown("---")

    col1, col2, col3 = st.columns(3)
    for l, col in zip([1,2,3], [col1, col2, col3]):
        lc = LEVELS[l]
        col.markdown(f"""
        <div style='background:#0c1220;border:1px solid {lc["color"]}33;border-radius:12px;padding:18px;height:120px'>
            <div style='color:{lc["color"]};font-size:10px;font-weight:700;letter-spacing:1.5px;margin-bottom:8px'>{lc["label"].upper()}</div>
            <div style='color:#e2f0ff;font-size:14px;font-weight:700;margin-bottom:6px'>{lc["title"]}</div>
            <div style='color:#4a6080;font-size:11px;line-height:1.5'>{lc["desc"]}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style='margin:24px 0 8px;color:#4a6080;font-size:11px;font-weight:700;letter-spacing:1px;text-align:center'>
        UPLOAD YOUR DATASET
    </div>
    <div style='color:#4a6080;font-size:11px;text-align:center;margin-bottom:12px'>
        Upload up to 3 CSV files <b style='color:#8899aa'>or</b> one Excel file with up to 3 sheets
    </div>
    """, unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "", type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if uploaded_files:
        # Limit to 3 files
        if len(uploaded_files) > 3:
            st.warning("Maximum 3 files allowed. Only the first 3 will be used.")
            uploaded_files = uploaded_files[:3]

        with st.spinner("Parsing schema and generating questions..."):
            tables = {}
            for f in uploaded_files:
                parsed = parse_file(f)
                tables.update(parsed)
                # Stop at 3 tables
                if len(tables) >= 3:
                    tables = dict(list(tables.items())[:3])
                    break

            if tables:
                st.session_state.tables = tables
                st.session_state.file_name = ", ".join([f.name for f in uploaded_files])

                # Show loaded tables
                st.markdown(f"""<div style='background:#0c1220;border:1px solid #00ff9d33;border-radius:10px;padding:14px;margin:16px 0'>
                    <span style='color:#00ff9d;font-weight:700'>✓ Loaded {len(tables)} table(s):</span>
                    <span style='color:#e2f0ff'> {", ".join(tables.keys())}</span>
                    <span style='color:#4a6080'> · {sum(len(d) for d in tables.values())} total rows</span>
                </div>""", unsafe_allow_html=True)

                # Table badges
                cols = st.columns(len(tables))
                for col, (name, df) in zip(cols, tables.items()):
                    col.markdown(f"""
                    <div style='background:#0c1220;border:1px solid #1a2535;border-radius:8px;padding:12px;text-align:center'>
                        <div style='color:#00ff9d;font-size:13px;font-weight:700'>⬡ {name}</div>
                        <div style='color:#4a6080;font-size:11px;margin-top:4px'>{len(df)} rows · {len(df.columns)} cols</div>
                        <div style='color:#1a2535;font-size:10px;margin-top:4px'>{" · ".join(list(df.columns)[:4])}{"..." if len(df.columns)>4 else ""}</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("")

                # Preview each table
                for name, df in tables.items():
                    with st.expander(f"Preview: {name}"):
                        st.dataframe(df.head(5), use_container_width=True)

                if len(tables) > 1:
                    st.markdown(f"""<div style='background:#f59e0b08;border:1px solid #f59e0b33;border-radius:8px;padding:12px;margin-bottom:12px'>
                        <span style='color:#f59e0b;font-size:11px;font-weight:700'>🔗 MULTI-TABLE MODE</span>
                        <span style='color:#8899aa;font-size:12px'> — Level 2 & 3 will generate JOIN questions across your {len(tables)} tables</span>
                    </div>""", unsafe_allow_html=True)

                if st.button("🚀 Start Practising"):
                    start_level(1)

# ── PRACTICE ─────────────────────────────────────────────────
elif st.session_state.stage == "practice":
    questions = st.session_state.questions
    qi = st.session_state.qi
    q = questions[qi]
    cfg = LEVELS[st.session_state.level]
    diff_color = DIFFICULTY_COLOR.get(q.get("difficulty",""), "#8899aa")

    # Top bar
    col_a, col_b, col_c, col_d = st.columns([4, 1, 1, 1])
    col_a.markdown(f"""
    <div style='display:flex;align-items:center;gap:12px;padding:4px 0'>
        <span style='color:#00ff9d;font-size:20px;font-weight:800'>⬡ SQL.FORGE</span>
        <span style='color:#1a2535'>|</span>
        <span style='color:#4a6080;font-size:12px'>{st.session_state.file_name}</span>
    </div>
    """, unsafe_allow_html=True)
    col_b.markdown(f"<div style='color:{cfg['color']};font-weight:700;text-align:center;padding-top:6px'>{cfg['label']}</div>", unsafe_allow_html=True)
    col_c.markdown(f"<div style='color:#4a6080;text-align:center;padding-top:6px'>Q{qi+1}/{len(questions)}</div>", unsafe_allow_html=True)
    col_d.markdown(f"<div style='color:{diff_color};font-weight:700;text-align:center;padding-top:6px'>{q.get('difficulty','')}</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1a2535;margin:8px 0 16px'>", unsafe_allow_html=True)

    # Question card
    st.markdown(f"""
    <div style='background:#0c1220;border:1px solid #1a2535;border-left:3px solid {cfg["color"]};border-radius:10px;padding:20px;margin-bottom:16px'>
        <div style='display:flex;align-items:center;gap:10px;margin-bottom:12px'>
            <span style='background:{cfg["color"]}22;border:1px solid {cfg["color"]}44;color:{cfg["color"]};border-radius:6px;padding:3px 12px;font-size:10px;font-weight:700;letter-spacing:1px'>{q.get("concept","").upper()}</span>
            <span style='background:{diff_color}22;border:1px solid {diff_color}44;color:{diff_color};border-radius:6px;padding:3px 10px;font-size:10px;font-weight:700'>{q.get("difficulty","")}</span>
        </div>
        <div style='color:#e2f0ff;font-size:15px;font-weight:500;line-height:1.7'>{q["question"]}</div>
    </div>
    """, unsafe_allow_html=True)

    # SQL Editor
    st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>SQL EDITOR</div>", unsafe_allow_html=True)
    user_sql = st.text_area("", value=st.session_state.user_sql, height=180,
        placeholder="-- Write your PostgreSQL query here\nSELECT ...",
        key=f"sql_{qi}", label_visibility="collapsed")
    st.session_state.user_sql = user_sql

    # Buttons row
    cb1, cb2, cb3, cb4, cb5 = st.columns([2, 2, 1, 1, 2])

    run_clicked = cb1.button("▶ Run Query", help="Execute your SQL and see the output")
    submit_clicked = cb2.button("✓ Submit Answer",
        disabled=not st.session_state.query_ran or bool(st.session_state.feedback),
        help="Run your query first, then submit")
    skip_clicked = cb3.button("Skip")
    hint_clicked = cb4.button("Hint")
    show_ans = cb5.checkbox("Show reference answer")

    # Run query
    if run_clicked and user_sql.strip():
        result, error = run_query(user_sql)
        st.session_state.query_result = result
        st.session_state.query_error = error
        st.session_state.query_ran = True

    # Show query results
    if st.session_state.query_ran:
        st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin:12px 0 8px'>QUERY OUTPUT</div>", unsafe_allow_html=True)
        if st.session_state.query_error:
            st.markdown(f"""<div style='background:#f8717110;border:1px solid #f8717144;border-radius:8px;padding:14px'>
                <div style='color:#f87171;font-size:11px;font-weight:700;margin-bottom:6px'>⚠ SYNTAX ERROR</div>
                <code style='color:#f87171;font-size:12px'>{st.session_state.query_error}</code>
            </div>""", unsafe_allow_html=True)
        elif st.session_state.query_result is not None:
            result_df = st.session_state.query_result
            st.markdown(f"<div style='color:#4a6080;font-size:11px;margin-bottom:6px'>Returned {len(result_df)} rows · {len(result_df.columns)} columns</div>", unsafe_allow_html=True)
            st.dataframe(result_df.head(20), use_container_width=True)
            if not st.session_state.feedback:
                st.markdown("<div style='color:#00ff9d;font-size:12px;margin-top:8px'>✓ Query ran successfully — click Submit Answer to evaluate your logic</div>", unsafe_allow_html=True)

    # Hint
    if hint_clicked:
        st.markdown(f"""<div style='background:#00ff9d08;border:1px solid #00ff9d33;border-radius:8px;padding:14px;margin-top:12px'>
            <span style='color:#00ff9d;font-size:10px;font-weight:700'>HINT  </span>
            <span style='color:#8899aa;font-size:13px'>{q["hint"]}</span>
        </div>""", unsafe_allow_html=True)

    # Reference answer
    if show_ans:
        st.markdown("<div style='color:#f59e0b;font-size:10px;font-weight:700;letter-spacing:1px;margin:12px 0 6px'>REFERENCE ANSWER</div>", unsafe_allow_html=True)
        st.code(q["sample_answer"], language="sql")

    # Evaluate
    if submit_clicked:
        api_key = get_api_key()
        if not api_key:
            st.error("Please add your Gemini API key.")
        else:
            with st.spinner("AI is evaluating your query logic..."):
                result = evaluate_answer(get_schema_text(), q["question"], q["concept"],
                                         q["sample_answer"], user_sql, api_key)
                st.session_state.feedback = result
                new_streak = st.session_state.streak + 1 if result["correct"] else 0
                st.session_state.streak = new_streak
                s = st.session_state.stats
                s["total"] += 1
                if result["correct"]: s["correct"] += 1
                if new_streak >= 15:
                    if st.session_state.level < 3:
                        st.balloons()
                        st.success(f"🎉 15 streak! Advancing to Level {st.session_state.level + 1}!")
                        import time; time.sleep(2)
                        start_level(st.session_state.level + 1)
                    else:
                        st.session_state.stage = "complete"; st.rerun()

    # Feedback
    if st.session_state.feedback:
        fb = st.session_state.feedback
        border_color = "#00ff9d" if fb["correct"] else "#f87171"
        bg_color = "#00ff9d08" if fb["correct"] else "#f8717108"
        icon = "✓" if fb["correct"] else "✗"
        label = "Correct!" if fb["correct"] else "Incorrect"

        st.markdown(f"""
        <div style='background:{bg_color};border:1px solid {border_color}44;border-radius:10px;padding:18px;margin-top:12px'>
            <div style='display:flex;align-items:center;gap:12px;margin-bottom:10px'>
                <span style='color:{border_color};font-size:20px;font-weight:700'>{icon}</span>
                <span style='color:{border_color};font-weight:700;font-size:16px'>{label}</span>
                <span style='color:#4a6080;font-size:12px;margin-left:auto'>Score: {fb.get("score",0)}/100</span>
            </div>
            <div style='color:#c0d0e0;font-size:14px;line-height:1.7;margin-bottom:10px'>{fb.get("explanation","")}</div>
            <div style='color:#4a6080;font-size:12px'><span style='color:#00ff9d'>tip: </span>{fb.get("tip","")}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Next Question →"):
            next_q()

    if skip_clicked:
        next_q()

# ── COMPLETE ─────────────────────────────────────────────────
elif st.session_state.stage == "complete":
    s = st.session_state.stats
    acc = round((s["correct"] / s["total"]) * 100) if s["total"] > 0 else 0
    st.markdown(f"""
    <div style='text-align:center;padding:60px 0'>
        <div style='font-size:64px;margin-bottom:20px'>🏆</div>
        <div style='color:#00ff9d;font-size:36px;font-weight:800;margin-bottom:10px'>All Levels Complete!</div>
        <div style='color:#4a6080;font-size:15px;max-width:400px;margin:0 auto'>
            Foundations → Joins → MAANG Level. You're interview ready.
        </div>
    </div>
    """, unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    c1.metric("Questions Solved", s["total"])
    c2.metric("Accuracy", f"{acc}%")
    c3.metric("Correct", s["correct"])
    st.markdown("")
    if st.button("🔄 Start New Session"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        init(); st.rerun()

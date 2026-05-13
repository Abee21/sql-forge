import streamlit as st
import pandas as pd
import io
import os
from question_generator import get_questions
from evaluator import evaluate_answer

# ─── Page Config ────────────────────────────────────────────
st.set_page_config(
    page_title="SQL Forge",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'JetBrains Mono', monospace !important;
}
.stApp { background-color: #0a0e14; color: #bfc7d5; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0d1117 !important;
    border-right: 1px solid #1e2530;
}

/* Inputs */
.stTextArea textarea {
    background-color: #060a0f !important;
    color: #e6f0ff !important;
    border: 1px solid #1e2530 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    border-radius: 6px !important;
}
.stTextArea textarea:focus { border-color: #4ade8066 !important; }

/* Buttons */
.stButton > button {
    background-color: #4ade80;
    color: #0a0e14;
    border: none;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    border-radius: 6px;
    padding: 0.4rem 1.2rem;
}
.stButton > button:hover { background-color: #22c55e; }

/* Metrics */
[data-testid="metric-container"] {
    background: #060a0f;
    border: 1px solid #1e2530;
    border-radius: 8px;
    padding: 12px;
}
[data-testid="metric-container"] label { color: #4a5568 !important; font-size: 11px !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #4ade80 !important; font-size: 22px !important; }

/* Progress */
.stProgress > div > div { background-color: #4ade80 !important; }

/* Code blocks */
code { background: #060a0f !important; color: #4ade80 !important; border-radius: 4px !important; }
pre { background: #060a0f !important; border: 1px solid #1e2530 !important; border-radius: 6px !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    border: 2px dashed #1e2530 !important;
    border-radius: 10px !important;
    padding: 20px !important;
    background: #0d1117 !important;
}

/* Expanders */
details { border: 1px solid #1e2530 !important; border-radius: 6px !important; background: #0d1117 !important; }

/* Dividers */
hr { border-color: #1e2530 !important; }

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ─── Session State Init ──────────────────────────────────────
def init_state():
    defaults = {
        "stage": "upload",
        "tables": {},
        "questions": [],
        "q_index": 0,
        "level": 1,
        "streak": 0,
        "stats": {"total": 0, "correct": 0, "times": []},
        "feedback": None,
        "user_sql": "",
        "file_name": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ─── Helpers ─────────────────────────────────────────────────
LEVEL_CONFIG = {
    1: {"label": "Level 1", "title": "Foundations", "color": "#4ade80",
        "desc": "SELECT · WHERE · GROUP BY · Aggregations"},
    2: {"label": "Level 2", "title": "Joins & Subqueries", "color": "#facc15",
        "desc": "JOINs · CASE · Subqueries · COALESCE"},
    3: {"label": "Level 3", "title": "Advanced", "color": "#f87171",
        "desc": "CTEs · Window functions · CAST · Dates"},
}

def start_level(level):
    qs = get_questions(st.session_state.tables, level)
    st.session_state.questions = qs
    st.session_state.q_index = 0
    st.session_state.streak = 0
    st.session_state.feedback = None
    st.session_state.user_sql = ""
    st.session_state.level = level
    st.session_state.stage = "practice"
    st.rerun()

def next_question():
    st.session_state.q_index = (st.session_state.q_index + 1) % len(st.session_state.questions)
    st.session_state.feedback = None
    st.session_state.user_sql = ""
    st.rerun()

def get_schema_text():
    lines = []
    for name, df in st.session_state.tables.items():
        lines.append(f'Table "{name}" ({len(df)} rows), columns: {", ".join(df.columns)}')
    return "\n".join(lines)

def get_api_key():
    # Try Streamlit secrets first (for cloud deployment), then env var, then session input
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except:
        return os.environ.get("ANTHROPIC_API_KEY", st.session_state.get("api_key", ""))

def parse_file(uploaded):
    name = uploaded.name
    ext = name.rsplit(".", 1)[-1].lower()
    tables = {}
    if ext == "csv":
        df = pd.read_csv(uploaded)
        table_name = name.rsplit(".", 1)[0].replace(" ", "_").replace("-", "_").lower()
        tables[table_name] = df
    elif ext in ["xlsx", "xls"]:
        xf = pd.ExcelFile(uploaded)
        for sheet in xf.sheet_names[:3]:
            df = pd.read_excel(uploaded, sheet_name=sheet)
            if len(df) > 0:
                sname = sheet.replace(" ", "_").replace("-", "_").lower()
                tables[sname] = df
    return tables


# ─── SIDEBAR ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⬡ SQL.FORGE")
    st.markdown("*PostgreSQL Practice Engine*")
    st.markdown("---")

    if st.session_state.stage == "practice":
        cfg = LEVEL_CONFIG[st.session_state.level]
        st.markdown(f"**Current Level**")
        st.markdown(f"<span style='color:{cfg['color']};font-weight:700'>{cfg['label']}: {cfg['title']}</span>", unsafe_allow_html=True)
        st.markdown(f"<small style='color:#4a5568'>{cfg['desc']}</small>", unsafe_allow_html=True)
        st.markdown("---")

        # Streak tracker
        st.markdown("**Streak** (15 to advance)")
        streak = st.session_state.streak
        dots = ""
        for i in range(15):
            color = cfg["color"] if i < streak else "#1e2530"
            dots += f"<span style='display:inline-block;width:12px;height:12px;background:{color};border-radius:3px;margin:2px'></span>"
        st.markdown(dots, unsafe_allow_html=True)
        st.progress(streak / 15)
        st.markdown(f"<small style='color:#4a5568'>{streak}/15</small>", unsafe_allow_html=True)
        st.markdown("---")

        # Stats
        s = st.session_state.stats
        acc = round((s["correct"] / s["total"]) * 100) if s["total"] > 0 else 0
        avg_time = round(sum(s["times"]) / len(s["times"])) if s["times"] else 0
        col1, col2 = st.columns(2)
        col1.metric("Solved", s["total"])
        col2.metric("Accuracy", f"{acc}%")
        col1.metric("Correct", s["correct"])
        col2.metric("Avg Time", f"{avg_time}s")
        st.markdown("---")

        # Schema
        st.markdown("**Schema**")
        for tname, df in st.session_state.tables.items():
            with st.expander(f"▶ {tname} ({len(df)} rows)"):
                for col in df.columns:
                    st.markdown(f"<small style='color:#6b7a8f'>— {col}</small>", unsafe_allow_html=True)
        st.markdown("---")

        if st.button("🔄 Upload New File"):
            st.session_state.stage = "upload"
            st.session_state.tables = {}
            st.session_state.stats = {"total": 0, "correct": 0, "times": []}
            st.rerun()

    # Level progress (always show)
    if st.session_state.stage == "practice":
        st.markdown("**Level Progress**")
        for l in [1, 2, 3]:
            lcfg = LEVEL_CONFIG[l]
            cur = st.session_state.level
            if l < cur:
                st.markdown(f"<small style='color:#4a5568'>✓ L{l}: {lcfg['title']}</small>", unsafe_allow_html=True)
            elif l == cur:
                st.markdown(f"<small style='color:{lcfg['color']};font-weight:700'>▶ L{l}: {lcfg['title']}</small>", unsafe_allow_html=True)
            else:
                st.markdown(f"<small style='color:#1e2530'>○ L{l}: {lcfg['title']}</small>", unsafe_allow_html=True)


# ─── UPLOAD STAGE ────────────────────────────────────────────
if st.session_state.stage == "upload":
    st.markdown("# ⬡ SQL.FORGE")
    st.markdown("#### PostgreSQL Practice Engine")
    st.markdown("Upload your dataset → questions generated instantly from your schema using pure Python logic — free, no AI for question generation.")
    st.markdown("---")

    # API key input if not set
    api_key = get_api_key()
    if not api_key:
        st.markdown("#### 🔑 Gemini API Key")
        st.markdown("<small style='color:#4a5568'>Needed only for answer evaluation. Question generation is free.</small>", unsafe_allow_html=True)
        key_input = st.text_input("Enter your Gemini API key", type="password", placeholder="sk-ant-...")
        if key_input:
            st.session_state["api_key"] = key_input
        st.markdown("---")

    col1, col2, col3 = st.columns(3)
    for l, col in zip([1, 2, 3], [col1, col2, col3]):
        lcfg = LEVEL_CONFIG[l]
        col.markdown(f"""
        <div style='background:#0d1117;border:1px solid #1e2530;border-radius:8px;padding:14px'>
            <div style='color:{lcfg["color"]};font-size:10px;font-weight:700;letter-spacing:1px'>LEVEL {l}</div>
            <div style='color:#e6f0ff;font-size:13px;font-weight:600;margin:4px 0'>{lcfg["title"]}</div>
            <div style='color:#4a5568;font-size:11px'>{lcfg["desc"]}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    uploaded = st.file_uploader(
        "Drop your CSV or Excel file here",
        type=["csv", "xlsx", "xls"],
        label_visibility="visible"
    )

    if uploaded:
        with st.spinner("Parsing file and generating questions..."):
            tables = parse_file(uploaded)
            if tables:
                st.session_state.tables = tables
                st.session_state.file_name = uploaded.name
                st.success(f"✓ Loaded: {', '.join(tables.keys())}")

                # Preview
                for tname, df in tables.items():
                    st.markdown(f"**Preview: {tname}** ({len(df)} rows, {len(df.columns)} columns)")
                    st.dataframe(df.head(3), use_container_width=True)

                if st.button("🚀 Start Practising — Level 1"):
                    start_level(1)
            else:
                st.error("Could not parse file. Try a valid CSV or Excel file.")

    st.markdown("---")
    st.markdown("""
    <div style='background:#060a0f;border:1px solid #1e2530;border-radius:8px;padding:16px'>
        <div style='color:#4a5568;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>HOW IT WORKS</div>
        <div style='color:#6b7a8f;font-size:12px;line-height:1.9'>
            <span style='color:#4ade80'>▶</span> Questions generated from your schema — <b>free, instant, zero AI</b><br>
            <span style='color:#4ade80'>▶</span> AI used only for answer evaluation — checks SQL logic not just syntax<br>
            <span style='color:#4ade80'>▶</span> 15 consecutive correct answers → advance to next level<br>
            <span style='color:#4ade80'>▶</span> Hints + reference answers available for every question
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── PRACTICE STAGE ──────────────────────────────────────────
elif st.session_state.stage == "practice":
    questions = st.session_state.questions
    qi = st.session_state.q_index
    q  = questions[qi]
    cfg = LEVEL_CONFIG[st.session_state.level]

    # Header
    col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
    col_h1.markdown(f"""
    <div style='display:flex;align-items:center;gap:12px'>
        <span style='color:#4ade80;font-size:22px'>⬡</span>
        <span style='color:#4ade80;font-weight:700;font-size:18px;letter-spacing:1px'>SQL.FORGE</span>
        <span style='color:#4a5568;font-size:13px'>·  {st.session_state.file_name}</span>
    </div>
    """, unsafe_allow_html=True)

    col_h2.markdown(f"<div style='color:{cfg['color']};font-weight:700;text-align:center;padding-top:6px'>{cfg['label']}</div>", unsafe_allow_html=True)
    col_h3.markdown(f"<div style='color:#4a5568;text-align:center;padding-top:6px'>Q{qi+1}/{len(questions)}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Question card
    st.markdown(f"""
    <div style='background:#0d1117;border:1px solid #1e2530;border-radius:8px;padding:18px;margin-bottom:16px'>
        <div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>
            <span style='background:{cfg["color"]}22;border:1px solid {cfg["color"]}44;color:{cfg["color"]};
                border-radius:4px;padding:2px 10px;font-size:11px;font-weight:700;letter-spacing:0.5px'>
                {q["concept"]}
            </span>
        </div>
        <div style='color:#e6f0ff;font-size:15px;font-weight:600;line-height:1.7'>{q["question"]}</div>
    </div>
    """, unsafe_allow_html=True)

    # SQL editor
    user_sql = st.text_area(
        "Your PostgreSQL query",
        value=st.session_state.user_sql,
        height=200,
        placeholder="-- Write your SQL here\nSELECT ...",
        key=f"sql_input_{qi}"
    )
    st.session_state.user_sql = user_sql

    # Action buttons
    col_b1, col_b2, col_b3, col_b4 = st.columns([2, 1, 1, 3])

    submit_clicked = col_b1.button("✓ Submit Answer", disabled=bool(st.session_state.feedback))
    skip_clicked   = col_b2.button("Skip →")
    hint_clicked   = col_b3.button("Hint")
    show_ans       = col_b4.checkbox("Show reference answer")

    # Hint
    if hint_clicked:
        st.info(f"💡 **Hint:** {q['hint']}")

    # Reference answer
    if show_ans:
        st.markdown("""
        <div style='background:#facc1508;border:1px solid #facc1533;border-radius:6px;padding:14px'>
            <div style='color:#facc15;font-size:10px;font-weight:700;margin-bottom:8px'>REFERENCE ANSWER</div>
        </div>
        """, unsafe_allow_html=True)
        st.code(q["sample_answer"], language="sql")

    # Evaluate
    if submit_clicked and user_sql.strip():
        api_key = get_api_key()
        if not api_key:
            st.error("Please enter your Anthropic API key in the upload screen.")
        else:
            with st.spinner("Evaluating your SQL..."):
                result = evaluate_answer(
                    schema_info=get_schema_text(),
                    question=q["question"],
                    concept=q["concept"],
                    sample_answer=q["sample_answer"],
                    user_sql=user_sql,
                    api_key=api_key
                )
                st.session_state.feedback = result

                # Update streak
                new_streak = st.session_state.streak + 1 if result["correct"] else 0
                st.session_state.streak = new_streak

                # Update stats
                s = st.session_state.stats
                s["total"] += 1
                if result["correct"]:
                    s["correct"] += 1

                # Level up check
                if new_streak >= 15:
                    if st.session_state.level < 3:
                        st.balloons()
                        st.success(f"🎉 15 streak! Advancing to Level {st.session_state.level + 1}...")
                        import time; time.sleep(2)
                        start_level(st.session_state.level + 1)
                    else:
                        st.session_state.stage = "complete"
                        st.rerun()

    # Show feedback
    if st.session_state.feedback:
        fb = st.session_state.feedback
        if fb["correct"]:
            st.markdown(f"""
            <div style='background:#4ade8010;border:1px solid #4ade8044;border-radius:8px;padding:16px;margin-top:12px'>
                <div style='color:#4ade80;font-weight:700;font-size:15px;margin-bottom:8px'>✓ Correct!  <span style='color:#4a5568;font-size:12px;font-weight:400'>Score: {fb["score"]}/100</span></div>
                <div style='color:#bfc7d5;font-size:13px;line-height:1.6'>{fb["explanation"]}</div>
                <div style='color:#6b7a8f;font-size:12px;margin-top:8px'><span style='color:#4ade80'>tip: </span>{fb.get("tip","")}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style='background:#f8717110;border:1px solid #f8717144;border-radius:8px;padding:16px;margin-top:12px'>
                <div style='color:#f87171;font-weight:700;font-size:15px;margin-bottom:8px'>✗ Not quite  <span style='color:#4a5568;font-size:12px;font-weight:400'>Score: {fb["score"]}/100</span></div>
                <div style='color:#bfc7d5;font-size:13px;line-height:1.6'>{fb["explanation"]}</div>
                <div style='color:#6b7a8f;font-size:12px;margin-top:8px'><span style='color:#4ade80'>tip: </span>{fb.get("tip","")}</div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("Next Question →"):
            next_question()

    # Skip
    if skip_clicked:
        next_question()


# ─── COMPLETE STAGE ──────────────────────────────────────────
elif st.session_state.stage == "complete":
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("# 🏆 All Levels Complete!")
        st.markdown("You've mastered Foundations → Joins → Advanced SQL. You're interview ready.")
        st.markdown("---")
        s = st.session_state.stats
        acc = round((s["correct"] / s["total"]) * 100) if s["total"] > 0 else 0
        avg_time = round(sum(s["times"]) / len(s["times"])) if s["times"] else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Questions", s["total"])
        c2.metric("Accuracy", f"{acc}%")
        c3.metric("Avg Time", f"{avg_time}s")
        st.markdown("")
        if st.button("🔄 Practice with New Dataset"):
            for key in ["stage", "tables", "questions", "q_index", "level",
                        "streak", "stats", "feedback", "user_sql", "file_name"]:
                del st.session_state[key]
            init_state()
            st.rerun()

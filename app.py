import streamlit as st
import pandas as pd
import duckdb
import os
import json
from datetime import datetime, date
from question_generator import get_questions
from evaluator import evaluate_answer

st.set_page_config(page_title="SQL Forge", page_icon="⬡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif !important; }
.stApp { background: #080c14; }
section[data-testid="stSidebar"] { background: #0c1220 !important; border-right: 1px solid #1a2535; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem !important; }
.stTextArea textarea {
    background: #060a10 !important; color: #e2f0ff !important;
    border: 1px solid #1a2535 !important; border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important; line-height: 1.8 !important;
}
.stTextArea textarea:focus { border-color: #00ff9d55 !important; }
.stButton > button {
    background: linear-gradient(135deg, #00ff9d, #00cc7a) !important;
    color: #080c14 !important; border: none !important; border-radius: 8px !important;
    font-family: 'Space Grotesk', sans-serif !important; font-weight: 700 !important;
    padding: 0.5rem 1.5rem !important; transition: all 0.2s !important;
}
.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0 4px 20px #00ff9d33 !important; }
.stButton > button:disabled { opacity: 0.4 !important; transform: none !important; }
[data-testid="metric-container"] {
    background: #0c1220 !important; border: 1px solid #1a2535 !important;
    border-radius: 10px !important; padding: 14px !important;
}
[data-testid="metric-container"] label { color: #4a6080 !important; font-size: 10px !important; letter-spacing: 1px !important; text-transform: uppercase !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #00ff9d !important; font-size: 22px !important; font-weight: 700 !important; }
.stProgress > div > div { background: linear-gradient(90deg, #00ff9d, #00cc7a) !important; border-radius: 99px !important; }
.stTabs [data-baseweb="tab-list"] { background: #0c1220 !important; border-radius: 8px !important; padding: 4px !important; }
.stTabs [data-baseweb="tab"] { color: #4a6080 !important; border-radius: 6px !important; }
.stTabs [aria-selected="true"] { background: #1a2535 !important; color: #00ff9d !important; }
[data-testid="stFileUploader"] { background: #0c1220 !important; border: 2px dashed #1a2535 !important; border-radius: 12px !important; }
details { border: 1px solid #1a2535 !important; border-radius: 8px !important; background: #0c1220 !important; }
code { background: #0c1220 !important; color: #00ff9d !important; border-radius: 4px !important; font-family: 'JetBrains Mono', monospace !important; }
pre { background: #060a10 !important; border: 1px solid #1a2535 !important; border-radius: 8px !important; }
.stDataFrame { border: 1px solid #1a2535 !important; border-radius: 8px !important; }
.stTextInput > div > div > input { background: #0c1220 !important; border-color: #1a2535 !important; color: #e2f0ff !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ── XP CONFIG ────────────────────────────────────────────────
XP = {
    "correct": 10, "streak_5": 25, "streak_10": 50,
    "level_complete": 100, "speed_bonus": 5, "daily_login": 20,
    "hint_cost": 20, "answer_cost": 50, "skip_cost": 15
}

LEVELS_XP = [(0,"Beginner"),(100,"Apprentice"),(300,"Practitioner"),
             (600,"Analyst"),(1000,"Senior Analyst"),(1500,"SQL Expert"),
             (2500,"MAANG Ready"),(4000,"SQL Master")]

def xp_level(xp):
    title = LEVELS_XP[0][1]
    for threshold, name in LEVELS_XP:
        if xp >= threshold: title = name
        else: break
    return title

def next_xp_threshold(xp):
    for threshold, _ in LEVELS_XP:
        if xp < threshold: return threshold
    return LEVELS_XP[-1][0]

# ── STATE ────────────────────────────────────────────────────
def init():
    defaults = {
        "stage": "upload", "tables": {}, "questions": [], "qi": 0,
        "level": 1, "streak": 0,
        "stats": {"total": 0, "correct": 0, "times": [], "concepts": {}},
        "feedback": None, "user_sql": "", "file_name": "",
        "query_result": None, "query_error": None, "query_ran": False,
        "xp": 0, "hint_used": False, "answer_used": False,
        "q_start_time": None,
        "streak_days": [], "practiced_today": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Daily login XP
    today = str(date.today())
    if today not in st.session_state.streak_days:
        st.session_state.streak_days.append(today)
        st.session_state.xp += XP["daily_login"]
        st.session_state.practiced_today = True
init()

LEVELS = {
    1: {"label": "Level 1", "title": "Foundations", "color": "#00ff9d", "desc": "Aggregations · Filtering · Grouping"},
    2: {"label": "Level 2", "title": "Joins & Subqueries", "color": "#f59e0b", "desc": "JOINs · Subqueries · CASE · CTEs"},
    3: {"label": "Level 3", "title": "MAANG Level", "color": "#f87171", "desc": "Window Functions · Cohorts · YoY · Gaps"},
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
        "query_result": None, "query_error": None, "query_ran": False,
        "hint_used": False, "answer_used": False, "q_start_time": datetime.now()
    })
    st.rerun()

def next_q():
    st.session_state.update({
        "qi": (st.session_state.qi + 1) % len(st.session_state.questions),
        "feedback": None, "user_sql": "", "query_result": None,
        "query_error": None, "query_ran": False,
        "hint_used": False, "answer_used": False,
        "q_start_time": datetime.now()
    })
    st.rerun()

def award_xp(amount, reason=""):
    st.session_state.xp += amount

def spend_xp(amount):
    if st.session_state.xp >= amount:
        st.session_state.xp -= amount
        return True
    return False

def dataset_brief(tables):
    """Generate a brief summary of uploaded tables"""
    for tname, df in tables.items():
        st.markdown(f"""
        <div style='background:#0c1220;border:1px solid #1a2535;border-radius:10px;padding:16px;margin-bottom:16px'>
            <div style='color:#00ff9d;font-size:13px;font-weight:700;margin-bottom:12px'>⬡ {tname}</div>
            <div style='display:flex;gap:20px;margin-bottom:12px'>
                <span style='color:#8899aa;font-size:12px'>📊 <b style='color:#e2f0ff'>{len(df)}</b> rows</span>
                <span style='color:#8899aa;font-size:12px'>📋 <b style='color:#e2f0ff'>{len(df.columns)}</b> columns</span>
                <span style='color:#8899aa;font-size:12px'>❌ <b style='color:#f87171'>{df.isnull().sum().sum()}</b> missing values</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        num_cols = df.select_dtypes(include="number").columns.tolist()
        txt_cols = df.select_dtypes(exclude="number").columns.tolist()

        if num_cols:
            st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>NUMERIC COLUMNS</div>", unsafe_allow_html=True)
            stats_df = df[num_cols].agg(["min","max","mean","std"]).round(2)
            st.dataframe(stats_df, use_container_width=True)

        if txt_cols:
            st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin:12px 0 8px'>TEXT COLUMNS — TOP VALUES</div>", unsafe_allow_html=True)
            for col in txt_cols[:4]:
                top = df[col].value_counts().head(3)
                vals = " · ".join([f"{v} ({c})" for v, c in top.items()])
                st.markdown(f"<div style='color:#8899aa;font-size:12px;margin-bottom:4px'><span style='color:#e2f0ff'>{col}:</span> {vals}</div>", unsafe_allow_html=True)

def weak_areas(concepts_dict):
    """Show weak concept areas based on performance"""
    if not concepts_dict:
        st.markdown("<div style='color:#4a6080;font-size:13px'>Practice more questions to see your weak areas.</div>", unsafe_allow_html=True)
        return

    st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:12px'>CONCEPT PERFORMANCE</div>", unsafe_allow_html=True)

    sorted_concepts = sorted(concepts_dict.items(), key=lambda x: x[1]["acc"])
    for concept, data in sorted_concepts:
        acc = data["acc"]
        attempts = data["attempts"]
        color = "#f87171" if acc < 50 else "#f59e0b" if acc < 75 else "#00ff9d"
        bar_width = int(acc)
        st.markdown(f"""
        <div style='margin-bottom:12px'>
            <div style='display:flex;justify-content:space-between;margin-bottom:4px'>
                <span style='color:#e2f0ff;font-size:12px'>{concept}</span>
                <span style='color:{color};font-size:12px;font-weight:700'>{acc}% <span style='color:#4a6080;font-weight:400'>({attempts} attempts)</span></span>
            </div>
            <div style='background:#1a2535;border-radius:99px;height:6px'>
                <div style='background:{color};width:{bar_width}%;height:100%;border-radius:99px;transition:width .3s'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Weak area recommendation
    weak = [c for c, d in concepts_dict.items() if d["acc"] < 60]
    if weak:
        st.markdown(f"""
        <div style='background:#f8717108;border:1px solid #f8717133;border-radius:8px;padding:12px;margin-top:12px'>
            <div style='color:#f87171;font-size:11px;font-weight:700;margin-bottom:4px'>⚠ FOCUS AREAS</div>
            <div style='color:#8899aa;font-size:12px'>You need more practice on: <b style='color:#f87171'>{", ".join(weak)}</b></div>
        </div>
        """, unsafe_allow_html=True)

def streak_calendar(streak_days):
    """Show last 30 days practice calendar"""
    st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:10px'>PRACTICE CALENDAR — LAST 30 DAYS</div>", unsafe_allow_html=True)
    from datetime import timedelta
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    practiced = set(streak_days)

    # Count consecutive streak from today
    streak_count = 0
    for i in range(30):
        d = (today - timedelta(days=i)).isoformat()
        if d in practiced: streak_count += 1
        else: break

    html = "<div style='display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px'>"
    for d in days:
        color = "#00ff9d" if d in practiced else "#1a2535"
        title = d
        html += f"<div title='{title}' style='width:14px;height:14px;background:{color};border-radius:3px;cursor:default'></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(f"<div style='color:#00ff9d;font-size:13px;font-weight:700'>{streak_count} day streak 🔥</div>", unsafe_allow_html=True)

# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:16px 0 8px'>
        <div style='color:#00ff9d;font-size:20px;font-weight:800;letter-spacing:2px'>⬡ SQL.FORGE</div>
        <div style='color:#4a6080;font-size:10px;margin-top:2px;letter-spacing:1px'>POSTGRESQL PRACTICE ENGINE</div>
    </div>
    """, unsafe_allow_html=True)

    # XP Bar
    xp = st.session_state.xp
    xp_title = xp_level(xp)
    next_thresh = next_xp_threshold(xp)
    prev_thresh = max(t for t, _ in LEVELS_XP if t <= xp)
    xp_progress = (xp - prev_thresh) / max(next_thresh - prev_thresh, 1)

    st.markdown(f"""
    <div style='background:#0c1220;border:1px solid #c084fc33;border-radius:10px;padding:14px;margin-bottom:12px'>
        <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'>
            <div>
                <div style='color:#c084fc;font-size:10px;font-weight:700;letter-spacing:1px'>XP RANK</div>
                <div style='color:#e2f0ff;font-size:14px;font-weight:700'>{xp_title}</div>
            </div>
            <div style='text-align:right'>
                <div style='color:#c084fc;font-size:18px;font-weight:800'>{xp}</div>
                <div style='color:#4a6080;font-size:10px'>XP</div>
            </div>
        </div>
        <div style='background:#1a2535;border-radius:99px;height:5px'>
            <div style='background:linear-gradient(90deg,#c084fc,#a855f7);width:{int(xp_progress*100)}%;height:100%;border-radius:99px'></div>
        </div>
        <div style='color:#4a6080;font-size:10px;margin-top:4px'>Next rank at {next_thresh} XP</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1a2535;margin:4px 0 12px'>", unsafe_allow_html=True)

    if st.session_state.stage == "practice":
        cfg = LEVELS[st.session_state.level]

        # Level badge
        st.markdown(f"""
        <div style='background:#0c1220;border:1px solid {cfg["color"]}33;border-radius:10px;padding:12px;margin-bottom:12px'>
            <div style='color:{cfg["color"]};font-size:10px;font-weight:700;letter-spacing:1px'>{cfg["label"].upper()}</div>
            <div style='color:#e2f0ff;font-size:14px;font-weight:700'>{cfg["title"]}</div>
            <div style='color:#4a6080;font-size:11px'>{cfg["desc"]}</div>
        </div>
        """, unsafe_allow_html=True)

        # Streak dots
        streak = st.session_state.streak
        st.markdown(f"<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>STREAK — {streak}/15</div>", unsafe_allow_html=True)
        dots = "".join([f"<span style='display:inline-block;width:12px;height:12px;background:{'#00ff9d' if i < streak else '#1a2535'};border-radius:3px;margin:2px'></span>" for i in range(15)])
        st.markdown(f"<div>{dots}</div>", unsafe_allow_html=True)
        st.progress(streak / 15)

        st.markdown("<hr style='border-color:#1a2535;margin:10px 0'>", unsafe_allow_html=True)

        # Stats
        s = st.session_state.stats
        acc = round((s["correct"] / s["total"]) * 100) if s["total"] > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric("Solved", s["total"])
        c2.metric("Accuracy", f"{acc}%")
        c1.metric("XP Earned", st.session_state.xp)
        c2.metric("Correct", s["correct"])

        st.markdown("<hr style='border-color:#1a2535;margin:10px 0'>", unsafe_allow_html=True)

        # Schema
        st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>SCHEMA</div>", unsafe_allow_html=True)
        for tname, df in st.session_state.tables.items():
            with st.expander(f"⬡ {tname} ({len(df)}r)"):
                for col in df.columns:
                    dtype = df[col].dtype
                    icon = "123" if dtype in ["int64","float64"] else "abc"
                    color = "#f59e0b" if dtype in ["int64","float64"] else "#8899aa"
                    st.markdown(f"<div style='color:{color};font-size:11px;font-family:monospace;padding:2px 0'><span style='opacity:.5'>{icon}</span> {col}</div>", unsafe_allow_html=True)

        st.markdown("<hr style='border-color:#1a2535;margin:10px 0'>", unsafe_allow_html=True)

        # Level progress
        st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>PROGRESS</div>", unsafe_allow_html=True)
        for l in [1,2,3]:
            lc = LEVELS[l]
            cur = st.session_state.level
            if l < cur: label = f"✓ {lc['label']}"
            elif l == cur: label = f"▶ {lc['label']}"
            else: label = f"○ {lc['label']}"
            color = lc["color"] if l == cur else "#4a6080" if l < cur else "#1a2535"
            st.markdown(f"<div style='color:{color};font-size:11px;margin-bottom:4px;font-weight:{'700' if l==cur else '400'}'>{label}: {lc['title']}</div>", unsafe_allow_html=True)

        st.markdown("")
        if st.button("↩ New File"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            init(); st.rerun()

    # Calendar always visible
    st.markdown("<hr style='border-color:#1a2535;margin:10px 0'>", unsafe_allow_html=True)
    streak_calendar(st.session_state.streak_days)

# ── UPLOAD STAGE ─────────────────────────────────────────────
if st.session_state.stage == "upload":
    st.markdown("""
    <div style='text-align:center;padding:30px 0 20px'>
        <div style='font-size:48px;margin-bottom:12px'>⬡</div>
        <div style='color:#00ff9d;font-size:38px;font-weight:800;letter-spacing:3px;margin-bottom:8px'>SQL.FORGE</div>
        <div style='color:#4a6080;font-size:14px;max-width:480px;margin:0 auto;line-height:1.6'>
            Upload your data. Practice real PostgreSQL from foundations to MAANG-level interview questions.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Level cards
    c1, c2, c3 = st.columns(3)
    for l, col in zip([1,2,3],[c1,c2,c3]):
        lc = LEVELS[l]
        col.markdown(f"""
        <div style='background:#0c1220;border:1px solid {lc["color"]}33;border-radius:12px;padding:16px'>
            <div style='color:{lc["color"]};font-size:10px;font-weight:700;letter-spacing:1.5px'>{lc["label"].upper()}</div>
            <div style='color:#e2f0ff;font-size:13px;font-weight:700;margin:4px 0'>{lc["title"]}</div>
            <div style='color:#4a6080;font-size:11px'>{lc["desc"]}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # API Key
    api_key = get_api_key()
    if not api_key:
        st.markdown("""<div style='background:#0c1220;border:1px solid #f59e0b44;border-radius:10px;padding:14px;margin-bottom:16px'>
            <div style='color:#f59e0b;font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>🔑 GEMINI API KEY</div>
            <div style='color:#4a6080;font-size:12px;margin-bottom:10px'>Free at aistudio.google.com — needed only for answer evaluation</div>
        </div>""", unsafe_allow_html=True)
        key_input = st.text_input("Paste your Gemini API key", type="password", placeholder="AIza...")
        if key_input: st.session_state["api_key"] = key_input

    # Column name warning
    st.markdown("""
    <div style='background:#f59e0b08;border:1px solid #f59e0b44;border-radius:10px;padding:16px;margin:16px 0'>
        <div style='color:#f59e0b;font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>⚠ IMPORTANT — FOR JOIN QUESTIONS</div>
        <div style='color:#8899aa;font-size:12px;line-height:1.8'>
            For Level 2 & 3 JOIN questions to work correctly, shared columns must have the <b style='color:#e2f0ff'>exact same name</b> across files.<br>
            ✓ <span style='color:#00ff9d'>customers.customer_id</span> ↔ <span style='color:#00ff9d'>orders.customer_id</span> — will detect join<br>
            ✗ <span style='color:#f87171'>customers.cust_id</span> ↔ <span style='color:#f87171'>orders.customer_id</span> — join NOT detected
        </div>
    </div>
    """, unsafe_allow_html=True)

    # File uploader
    st.markdown("<div style='color:#4a6080;font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>UPLOAD DATASET — up to 3 CSV files or 1 Excel with 3 sheets</div>", unsafe_allow_html=True)
    uploaded_files = st.file_uploader("", type=["csv","xlsx","xls"], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if len(uploaded_files) > 3:
            st.warning("Max 3 files. Using first 3 only.")
            uploaded_files = uploaded_files[:3]

        with st.spinner("Parsing schema..."):
            tables = {}
            for f in uploaded_files:
                parsed = parse_file(f)
                tables.update(parsed)
                if len(tables) >= 3:
                    tables = dict(list(tables.items())[:3])
                    break

        if tables:
            st.session_state.tables = tables
            st.session_state.file_name = ", ".join([f.name for f in uploaded_files])

            # Table loaded badges
            st.markdown(f"""<div style='background:#0c1220;border:1px solid #00ff9d33;border-radius:10px;padding:14px;margin:12px 0'>
                <span style='color:#00ff9d;font-weight:700'>✓ Loaded {len(tables)} table(s):</span>
                <span style='color:#e2f0ff'> {", ".join(tables.keys())}</span>
                <span style='color:#4a6080'> · {sum(len(d) for d in tables.values())} total rows</span>
            </div>""", unsafe_allow_html=True)

            # Relationship detection
            if len(tables) > 1:
                tnames = list(tables.keys())
                dfs = list(tables.values())
                shared_cols = []
                for i in range(len(tnames)):
                    for j in range(i+1, len(tnames)):
                        common = set(dfs[i].columns) & set(dfs[j].columns)
                        for col in common:
                            shared_cols.append((tnames[i], tnames[j], col))

                if shared_cols:
                    rel_html = "".join([f"<div style='color:#8899aa;font-size:12px;margin:3px 0'>🔗 <span style='color:#00ff9d'>{a}</span> ↔ <span style='color:#00ff9d'>{b}</span> via <span style='color:#f59e0b'>{col}</span></div>" for a,b,col in shared_cols])
                    st.markdown(f"""
                    <div style='background:#00ff9d08;border:1px solid #00ff9d33;border-radius:8px;padding:12px;margin-bottom:12px'>
                        <div style='color:#00ff9d;font-size:11px;font-weight:700;margin-bottom:6px'>✓ RELATIONSHIPS DETECTED</div>
                        {rel_html}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='background:#f8717108;border:1px solid #f8717133;border-radius:8px;padding:12px;margin-bottom:12px'>
                        <div style='color:#f87171;font-size:11px;font-weight:700;margin-bottom:4px'>⚠ NO SHARED COLUMNS FOUND</div>
                        <div style='color:#8899aa;font-size:12px'>No common column names detected across your tables. JOIN questions may not generate correctly. Make sure shared columns have identical names.</div>
                    </div>
                    """, unsafe_allow_html=True)

            # Dataset Brief tabs
            st.markdown("<div style='color:#4a6080;font-size:11px;font-weight:700;letter-spacing:1px;margin:16px 0 8px'>DATASET BRIEF</div>", unsafe_allow_html=True)
            if len(tables) == 1:
                dataset_brief(tables)
            else:
                tabs = st.tabs(list(tables.keys()))
                for tab, (tname, df) in zip(tabs, tables.items()):
                    with tab:
                        dataset_brief({tname: df})

            if st.button("🚀 Start Practising — Level 1"):
                start_level(1)

# ── PRACTICE STAGE ───────────────────────────────────────────
elif st.session_state.stage == "practice":
    questions = st.session_state.questions
    qi = st.session_state.qi
    q = questions[qi]
    cfg = LEVELS[st.session_state.level]
    diff_color = DIFFICULTY_COLOR.get(q.get("difficulty",""), "#8899aa")

    # Top bar
    ca, cb, cc, cd = st.columns([4,1,1,1])
    ca.markdown(f"<div style='color:#00ff9d;font-size:18px;font-weight:800;padding-top:4px'>⬡ SQL.FORGE <span style='color:#1a2535'>|</span> <span style='color:#4a6080;font-size:12px;font-weight:400'>{st.session_state.file_name}</span></div>", unsafe_allow_html=True)
    cb.markdown(f"<div style='color:{cfg['color']};font-weight:700;text-align:center;padding-top:6px'>{cfg['label']}</div>", unsafe_allow_html=True)
    cc.markdown(f"<div style='color:#4a6080;text-align:center;padding-top:6px'>Q{qi+1}/{len(questions)}</div>", unsafe_allow_html=True)
    cd.markdown(f"<div style='color:{diff_color};font-weight:700;text-align:center;padding-top:6px'>{q.get('difficulty','')}</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1a2535;margin:8px 0 12px'>", unsafe_allow_html=True)

    # Main tabs
    tab_practice, tab_brief, tab_weak = st.tabs(["📝 Practice", "📊 Dataset Brief", "🎯 Weak Areas"])

    with tab_practice:
        # Question card
        st.markdown(f"""
        <div style='background:#0c1220;border:1px solid #1a2535;border-left:3px solid {cfg["color"]};border-radius:10px;padding:18px;margin-bottom:14px'>
            <div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>
                <span style='background:{cfg["color"]}22;border:1px solid {cfg["color"]}44;color:{cfg["color"]};border-radius:6px;padding:3px 10px;font-size:10px;font-weight:700;letter-spacing:1px'>{q.get("concept","").upper()}</span>
                <span style='background:{diff_color}22;color:{diff_color};border-radius:6px;padding:3px 10px;font-size:10px;font-weight:700'>{q.get("difficulty","")}</span>
                <span style='color:#4a6080;font-size:11px;margin-left:auto'>+{XP["correct"]} XP on correct answer</span>
            </div>
            <div style='color:#e2f0ff;font-size:15px;font-weight:500;line-height:1.7'>{q["question"]}</div>
        </div>
        """, unsafe_allow_html=True)

        # SQL Editor
        st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>SQL EDITOR</div>", unsafe_allow_html=True)
        user_sql = st.text_area("", value=st.session_state.user_sql, height=170,
            placeholder="-- Write your PostgreSQL query here\nSELECT ...",
            key=f"sql_{qi}", label_visibility="collapsed")
        st.session_state.user_sql = user_sql

        # Action buttons
        b1, b2, b3, b4, b5 = st.columns([2,2,1,1,2])
        run_clicked = b1.button("▶ Run Query")
        submit_clicked = b2.button("✓ Submit Answer",
            disabled=not st.session_state.query_ran or bool(st.session_state.feedback))
        skip_clicked = b3.button("Skip")

        # XP-gated hint and answer
        xp_now = st.session_state.xp
        hint_label = f"Hint ({XP['hint_cost']}XP)" if not st.session_state.hint_used else "Hint ✓"
        ans_label = f"Answer ({XP['answer_cost']}XP)" if not st.session_state.answer_used else "Answer ✓"
        hint_clicked = b4.button(hint_label, disabled=st.session_state.hint_used)
        show_ans = b5.checkbox(ans_label, disabled=st.session_state.answer_used)

        # XP spend for hint
        if hint_clicked and not st.session_state.hint_used:
            if spend_xp(XP["hint_cost"]):
                st.session_state.hint_used = True
                st.rerun()
            else:
                st.warning(f"Not enough XP! You need {XP['hint_cost']} XP for a hint. Earn XP by answering questions correctly.")

        # XP spend for answer
        if show_ans and not st.session_state.answer_used:
            if spend_xp(XP["answer_cost"]):
                st.session_state.answer_used = True
            else:
                st.warning(f"Not enough XP! You need {XP['answer_cost']} XP to reveal the answer.")

        # Skip costs XP
        if skip_clicked:
            spend_xp(XP["skip_cost"])
            next_q()

        # Run query
        if run_clicked and user_sql.strip():
            result, error = run_query(user_sql)
            st.session_state.query_result = result
            st.session_state.query_error = error
            st.session_state.query_ran = True

        # Show hint
        if st.session_state.hint_used:
            st.markdown(f"""<div style='background:#00ff9d08;border:1px solid #00ff9d33;border-radius:8px;padding:12px;margin-top:10px'>
                <span style='color:#00ff9d;font-size:10px;font-weight:700'>HINT  </span>
                <span style='color:#8899aa;font-size:13px'>{q["hint"]}</span>
            </div>""", unsafe_allow_html=True)

        # Show reference answer
        if st.session_state.answer_used:
            st.markdown("<div style='color:#f59e0b;font-size:10px;font-weight:700;letter-spacing:1px;margin:10px 0 6px'>REFERENCE ANSWER</div>", unsafe_allow_html=True)
            st.code(q["sample_answer"], language="sql")

        # Query output
        if st.session_state.query_ran:
            st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin:12px 0 6px'>QUERY OUTPUT</div>", unsafe_allow_html=True)
            if st.session_state.query_error:
                st.markdown(f"""<div style='background:#f8717110;border:1px solid #f8717144;border-radius:8px;padding:12px'>
                    <div style='color:#f87171;font-size:11px;font-weight:700;margin-bottom:4px'>⚠ ERROR</div>
                    <code style='color:#f87171;font-size:12px'>{st.session_state.query_error}</code>
                </div>""", unsafe_allow_html=True)
            elif st.session_state.query_result is not None:
                r = st.session_state.query_result
                st.markdown(f"<div style='color:#4a6080;font-size:11px;margin-bottom:6px'>{len(r)} rows · {len(r.columns)} columns returned</div>", unsafe_allow_html=True)
                st.dataframe(r.head(20), use_container_width=True)
                if not st.session_state.feedback:
                    st.markdown("<div style='color:#00ff9d;font-size:12px;margin-top:6px'>✓ Query executed — now click Submit Answer</div>", unsafe_allow_html=True)

        # Evaluate
        if submit_clicked:
            api_key = get_api_key()
            if not api_key:
                st.error("Add your Gemini API key first.")
            else:
                with st.spinner("Evaluating your query..."):
                    result = evaluate_answer(get_schema_text(), q["question"],
                                             q["concept"], q["sample_answer"], user_sql, api_key)
                    st.session_state.feedback = result
                    concept = q.get("concept","Other")

                    # Update concept stats for weak area tracking
                    concepts = st.session_state.stats["concepts"]
                    if concept not in concepts:
                        concepts[concept] = {"attempts": 0, "correct": 0, "acc": 0}
                    concepts[concept]["attempts"] += 1
                    if result["correct"]:
                        concepts[concept]["correct"] += 1
                    concepts[concept]["acc"] = round(100 * concepts[concept]["correct"] / concepts[concept]["attempts"])

                    new_streak = st.session_state.streak + 1 if result["correct"] else 0
                    st.session_state.streak = new_streak
                    s = st.session_state.stats
                    s["total"] += 1

                    if result["correct"]:
                        s["correct"] += 1
                        xp_gained = XP["correct"]
                        # Time bonus
                        if st.session_state.q_start_time:
                            elapsed = (datetime.now() - st.session_state.q_start_time).seconds
                            if elapsed < 60: xp_gained += XP["speed_bonus"]
                        # Streak bonus
                        if new_streak == 5: xp_gained += XP["streak_5"]
                        if new_streak == 10: xp_gained += XP["streak_10"]
                        award_xp(xp_gained)

                    if new_streak >= 15:
                        award_xp(XP["level_complete"])
                        if st.session_state.level < 3:
                            st.balloons()
                            st.success(f"🎉 Level complete! +{XP['level_complete']} XP! Moving to Level {st.session_state.level + 1}...")
                            import time; time.sleep(2)
                            start_level(st.session_state.level + 1)
                        else:
                            st.session_state.stage = "complete"; st.rerun()

        # Feedback card
        if st.session_state.feedback:
            fb = st.session_state.feedback
            bc = "#00ff9d" if fb["correct"] else "#f87171"
            bg = "#00ff9d08" if fb["correct"] else "#f8717108"
            icon = "✓" if fb["correct"] else "✗"

            xp_msg = ""
            if fb["correct"]:
                elapsed = (datetime.now() - st.session_state.q_start_time).seconds if st.session_state.q_start_time else 999
                xp_msg = f"+{XP['correct']} XP"
                if elapsed < 60: xp_msg += f" +{XP['speed_bonus']} speed bonus"
                if st.session_state.streak == 5: xp_msg += f" +{XP['streak_5']} streak bonus!"
                if st.session_state.streak == 10: xp_msg += f" +{XP['streak_10']} streak bonus!"

            st.markdown(f"""
            <div style='background:{bg};border:1px solid {bc}44;border-radius:10px;padding:16px;margin-top:10px'>
                <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>
                    <span style='color:{bc};font-size:18px;font-weight:700'>{icon}</span>
                    <span style='color:{bc};font-weight:700;font-size:15px'>{"Correct!" if fb["correct"] else "Not quite"}</span>
                    <span style='color:#4a6080;font-size:11px;margin-left:auto'>Score: {fb.get("score",0)}/100</span>
                    {"<span style='color:#c084fc;font-size:12px;font-weight:700'>"+xp_msg+"</span>" if xp_msg else ""}
                </div>
                <div style='color:#c0d0e0;font-size:13px;line-height:1.7;margin-bottom:8px'>{fb.get("explanation","")}</div>
                <div style='color:#4a6080;font-size:12px'><span style='color:#00ff9d'>tip: </span>{fb.get("tip","")}</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Next Question →"):
                next_q()

    with tab_brief:
        dataset_brief(st.session_state.tables)

    with tab_weak:
        weak_areas(st.session_state.stats["concepts"])

# ── COMPLETE ─────────────────────────────────────────────────
elif st.session_state.stage == "complete":
    s = st.session_state.stats
    acc = round((s["correct"] / s["total"]) * 100) if s["total"] > 0 else 0
    st.markdown(f"""
    <div style='text-align:center;padding:50px 0'>
        <div style='font-size:56px;margin-bottom:16px'>🏆</div>
        <div style='color:#00ff9d;font-size:32px;font-weight:800;margin-bottom:8px'>All Levels Complete!</div>
        <div style='color:#c084fc;font-size:18px;font-weight:700;margin-bottom:6px'>{xp_level(st.session_state.xp)} · {st.session_state.xp} XP</div>
        <div style='color:#4a6080;font-size:14px'>Foundations → Joins → MAANG Level mastered.</div>
    </div>
    """, unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Questions", s["total"])
    c2.metric("Accuracy", f"{acc}%")
    c3.metric("Total XP", st.session_state.xp)
    c4.metric("XP Rank", xp_level(st.session_state.xp))
    st.markdown("")
    st.markdown("### 🎯 Your Weak Areas")
    weak_areas(s["concepts"])
    st.markdown("")
    if st.button("🔄 New Session"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        init(); st.rerun()

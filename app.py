import streamlit as st
import pandas as pd
import duckdb
import os
from datetime import datetime, date, timedelta
from question_generator import get_questions
from evaluator import evaluate_answer

st.set_page_config(page_title="SQL Forge", page_icon="⬡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif !important; }
.stApp { background: #080c14; }
section[data-testid="stSidebar"] { background: #0c1220 !important; border-right: 1px solid #1a2535; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: visible !important; background: #080c14 !important; }
[data-testid="collapsedControl"] { background: #00ff9d !important; border-radius: 8px !important; }
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
/* XP cost info below buttons */
.xp-info { color: #4a6080; font-size: 10px; text-align: center; margin-top: 4px; }
[data-testid="metric-container"] {
    background: #0c1220 !important; border: 1px solid #1a2535 !important;
    border-radius: 10px !important; padding: 14px !important;
}
[data-testid="metric-container"] label { color: #4a6080 !important; font-size: 10px !important; letter-spacing: 1px !important; text-transform: uppercase !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #00ff9d !important; font-size: 22px !important; font-weight: 700 !important; }
.stProgress > div > div { background: linear-gradient(90deg, #00ff9d, #00cc7a) !important; border-radius: 99px !important; }
.stTabs [data-baseweb="tab-list"] { background: #0c1220 !important; border-radius: 8px !important; padding: 4px !important; gap: 4px !important; }
.stTabs [data-baseweb="tab"] { color: #4a6080 !important; border-radius: 6px !important; font-size: 13px !important; }
.stTabs [aria-selected="true"] { background: #1a2535 !important; color: #00ff9d !important; font-weight: 700 !important; }
[data-testid="stFileUploader"] { background: #0c1220 !important; border: 2px dashed #1a2535 !important; border-radius: 12px !important; }
details { border: 1px solid #1a2535 !important; border-radius: 8px !important; background: #0c1220 !important; }
code { background: #0c1220 !important; color: #00ff9d !important; border-radius: 4px !important; font-family: 'JetBrains Mono', monospace !important; }
pre { background: #060a10 !important; border: 1px solid #1a2535 !important; border-radius: 8px !important; }
.stDataFrame { border: 1px solid #1a2535 !important; border-radius: 8px !important; }
.stTextInput > div > div > input { background: #0c1220 !important; border-color: #1a2535 !important; color: #e2f0ff !important; border-radius: 8px !important; }
.stToggle > label { color: #e2f0ff !important; }
</style>
""", unsafe_allow_html=True)

# ── XP CONFIG ────────────────────────────────────────────────
XP_EARN = {"correct_hero": 10, "correct_starter": 5, "streak_5": 25, "streak_10": 50, "level_complete": 100, "speed_bonus": 5, "daily_login": 20}
XP_COST = {"hint": 20, "answer": 50, "skip": 15}
XP_PENALTY_PER_DAY = 20
XP_RANKS = [(0,"Beginner"),(100,"Apprentice"),(300,"Practitioner"),(600,"Analyst"),(1000,"Senior Analyst"),(1500,"SQL Expert"),(2500,"MAANG Ready"),(4000,"SQL Master")]

def xp_rank(xp):
    title = XP_RANKS[0][1]
    for t, n in XP_RANKS:
        if xp >= t: title = n
        else: break
    return title

def next_rank_xp(xp):
    for t, _ in XP_RANKS:
        if xp < t: return t
    return XP_RANKS[-1][0]

def prev_rank_xp(xp):
    prev = 0
    for t, _ in XP_RANKS:
        if xp >= t: prev = t
        else: break
    return prev

LEVELS = {
    1: {"label": "Level 1", "title": "Foundations", "color": "#00ff9d", "desc": "Aggregations · Filtering · Grouping"},
    2: {"label": "Level 2", "title": "Joins & Subqueries", "color": "#f59e0b", "desc": "JOINs · Subqueries · CASE · CTEs"},
    3: {"label": "Level 3", "title": "MAANG Level", "color": "#f87171", "desc": "Window Functions · Cohorts · YoY · Gaps"},
}
DIFF_COLOR = {"Easy": "#00ff9d", "Medium": "#f59e0b", "Hard": "#f87171", "MAANG": "#c084fc"}

# ── STATE ────────────────────────────────────────────────────
def init():
    today = str(date.today())
    defaults = {
        "stage": "upload", "tables": {}, "questions": [], "qi": 0,
        "level": 1, "streak": 0,
        "stats": {"total": 0, "correct": 0, "concepts": {}, "syntax_scores": [], "times": []},
        "feedback": None, "user_sql": "", "file_name": "",
        "query_result": None, "query_error": None, "query_ran": False,
        "xp": 0, "hint_used": False, "answer_used": False,
        "q_start_time": None, "mode": "Hero",
        "streak_days": [], "last_practice_date": None,
        "penalty_applied_today": False, "demoted": False,
        "total_attempted": 0, "consecutive_correct": 0,
        "max_consecutive": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Daily login XP + penalty check
    if today not in st.session_state.streak_days:
        # Apply penalty for missed days
        last = st.session_state.last_practice_date
        if last and not st.session_state.penalty_applied_today:
            last_date = date.fromisoformat(last)
            missed = (date.today() - last_date).days - 1
            if missed > 0:
                penalty = missed * XP_PENALTY_PER_DAY
                st.session_state.xp = max(0, st.session_state.xp - penalty)
                st.session_state.penalty_applied_today = True
                # Demote if XP hits 0
                if st.session_state.xp == 0 and st.session_state.level > 1:
                    st.session_state.level = 1
                    st.session_state.streak = 0
                    st.session_state.demoted = True
        st.session_state.streak_days.append(today)
        st.session_state.last_practice_date = today
        st.session_state.xp += XP_EARN["daily_login"]

init()

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
        name = f.name.rsplit(".", 1)[0].replace(" ", "_").replace("-","_").lower()
        tables[name] = df
    elif ext in ["xlsx","xls"]:
        xf = pd.ExcelFile(f)
        for sh in xf.sheet_names[:3]:
            df = pd.read_excel(f, sheet_name=sh)
            if len(df): tables[sh.replace(" ","_").lower()] = df
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
        "hint_used": False, "answer_used": False,
        "q_start_time": datetime.now(), "consecutive_correct": 0
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

def spend_xp(amount):
    if st.session_state.xp >= amount:
        st.session_state.xp -= amount
        return True
    return False

def streak_calendar():
    st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>PRACTICE CALENDAR — LAST 30 DAYS</div>", unsafe_allow_html=True)
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(29,-1,-1)]
    practiced = set(st.session_state.streak_days)
    consecutive = 0
    for i in range(30):
        d = (today - timedelta(days=i)).isoformat()
        if d in practiced: consecutive += 1
        else: break
    html = "<div style='display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px'>"
    for d in days:
        color = "#00ff9d" if d in practiced else "#1a2535"
        html += f"<div title='{d}' style='width:13px;height:13px;background:{color};border-radius:2px'></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(f"<div style='color:#00ff9d;font-size:13px;font-weight:700'>{consecutive} day streak 🔥</div>", unsafe_allow_html=True)

def dataset_brief(tables):
    for tname, df in tables.items():
        st.markdown(f"""<div style='background:#0c1220;border:1px solid #1a2535;border-radius:10px;padding:14px;margin-bottom:14px'>
            <div style='color:#00ff9d;font-size:13px;font-weight:700;margin-bottom:10px'>⬡ {tname}</div>
            <div style='display:flex;gap:20px;flex-wrap:wrap;margin-bottom:10px'>
                <span style='color:#8899aa;font-size:12px'>📊 <b style='color:#e2f0ff'>{len(df)}</b> rows</span>
                <span style='color:#8899aa;font-size:12px'>📋 <b style='color:#e2f0ff'>{len(df.columns)}</b> columns</span>
                <span style='color:#8899aa;font-size:12px'>❌ <b style='color:#f87171'>{df.isnull().sum().sum()}</b> nulls</span>
            </div>
        </div>""", unsafe_allow_html=True)
        num_cols = df.select_dtypes(include="number").columns.tolist()
        txt_cols = df.select_dtypes(exclude="number").columns.tolist()
        if num_cols:
            st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>NUMERIC STATS</div>", unsafe_allow_html=True)
            st.dataframe(df[num_cols].agg(["min","max","mean","std"]).round(2), use_container_width=True)
        if txt_cols:
            st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin:10px 0 6px'>TEXT COLUMNS</div>", unsafe_allow_html=True)
            for col in txt_cols[:4]:
                top = df[col].value_counts().head(3)
                vals = " · ".join([f"{v} ({c})" for v,c in top.items()])
                st.markdown(f"<div style='color:#8899aa;font-size:12px;margin-bottom:3px'><span style='color:#e2f0ff'>{col}:</span> {vals}</div>", unsafe_allow_html=True)

def weak_areas():
    concepts = st.session_state.stats["concepts"]
    if not concepts:
        st.markdown("<div style='color:#4a6080;font-size:13px'>Practice more questions to see weak areas.</div>", unsafe_allow_html=True)
        return
    st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:12px'>CONCEPT ACCURACY</div>", unsafe_allow_html=True)
    for concept, data in sorted(concepts.items(), key=lambda x: x[1]["acc"]):
        acc = data["acc"]; attempts = data["attempts"]
        color = "#f87171" if acc < 50 else "#f59e0b" if acc < 75 else "#00ff9d"
        st.markdown(f"""<div style='margin-bottom:10px'>
            <div style='display:flex;justify-content:space-between;margin-bottom:3px'>
                <span style='color:#e2f0ff;font-size:12px'>{concept}</span>
                <span style='color:{color};font-size:12px;font-weight:700'>{acc}% <span style='color:#4a6080;font-weight:400'>({attempts})</span></span>
            </div>
            <div style='background:#1a2535;border-radius:99px;height:5px'>
                <div style='background:{color};width:{acc}%;height:100%;border-radius:99px'></div>
            </div>
        </div>""", unsafe_allow_html=True)
    weak = [c for c,d in concepts.items() if d["acc"] < 60]
    if weak:
        st.markdown(f"""<div style='background:#f8717108;border:1px solid #f8717133;border-radius:8px;padding:12px;margin-top:10px'>
            <div style='color:#f87171;font-size:11px;font-weight:700;margin-bottom:4px'>⚠ FOCUS AREAS</div>
            <div style='color:#8899aa;font-size:12px'>Needs more practice: <b style='color:#f87171'>{", ".join(weak)}</b></div>
        </div>""", unsafe_allow_html=True)

def dashboard_view():
    s = st.session_state.stats
    xp = st.session_state.xp
    lvl = st.session_state.level
    cfg = LEVELS[lvl]
    acc = round((s["correct"] / s["total"]) * 100) if s["total"] > 0 else 0
    avg_time = round(sum(s["times"]) / len(s["times"])) if s["times"] else 0
    avg_syntax = round(sum(s.get("syntax_scores",[])) / len(s.get("syntax_scores",[1]))) if s.get("syntax_scores") else 0
    today = date.today()
    last = st.session_state.last_practice_date
    consecutive = 0
    for i in range(30):
        d = (today - timedelta(days=i)).isoformat()
        if d in st.session_state.streak_days: consecutive += 1
        else: break

    st.markdown(f"""
    <div style='background:#0c1220;border:1px solid {cfg["color"]}33;border-radius:12px;padding:20px;margin-bottom:20px'>
        <div style='display:flex;justify-content:space-between;align-items:center'>
            <div>
                <div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px'>CURRENT LEVEL</div>
                <div style='color:{cfg["color"]};font-size:22px;font-weight:800'>{cfg["label"]}: {cfg["title"]}</div>
                <div style='color:#4a6080;font-size:12px'>{cfg["desc"]}</div>
            </div>
            <div style='text-align:right'>
                <div style='color:#c084fc;font-size:28px;font-weight:800'>{xp} XP</div>
                <div style='color:#4a6080;font-size:11px'>{xp_rank(xp)}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Penalty warning
    if last:
        last_date = date.fromisoformat(last)
        missed = (today - last_date).days - 1
        if missed > 0:
            penalty = missed * XP_PENALTY_PER_DAY
            st.markdown(f"""<div style='background:#f8717108;border:1px solid #f8717155;border-radius:8px;padding:14px;margin-bottom:16px'>
                <div style='color:#f87171;font-size:13px;font-weight:700'>⚠ PENALTY WARNING</div>
                <div style='color:#8899aa;font-size:12px;margin-top:4px'>You missed {missed} day(s). -{penalty} XP penalty applied on next login. Practice now to avoid demotion!</div>
            </div>""", unsafe_allow_html=True)

    # Stats grid
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Attempted", s["total"])
    c2.metric("Correct", s["correct"])
    c3.metric("Accuracy", f"{acc}%")
    c4.metric("Day Streak", f"{consecutive}🔥")

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Avg Solve Time", f"{avg_time}s")
    c2.metric("Syntax Score", f"{avg_syntax}/100")
    c3.metric("Max Streak", st.session_state.max_consecutive)
    c4.metric("Mode", st.session_state.mode)

    st.markdown("<div style='margin-top:20px'>", unsafe_allow_html=True)

    # XP breakdown
    st.markdown("""<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:12px'>XP ECONOMY</div>""", unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("""<div style='background:#0c1220;border:1px solid #00ff9d33;border-radius:8px;padding:14px'>
            <div style='color:#00ff9d;font-size:11px;font-weight:700;margin-bottom:8px'>EARN XP</div>
            <div style='color:#8899aa;font-size:12px;line-height:2'>
                ✓ Correct answer (Hero): +10 XP<br>
                ✓ Correct answer (Starter): +5 XP<br>
                ✓ Speed bonus (&lt;60s): +5 XP<br>
                ✓ 5-streak bonus: +25 XP<br>
                ✓ 10-streak bonus: +50 XP<br>
                ✓ Level complete: +100 XP<br>
                ✓ Daily login: +20 XP
            </div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""<div style='background:#0c1220;border:1px solid #f8717133;border-radius:8px;padding:14px'>
            <div style='color:#f87171;font-size:11px;font-weight:700;margin-bottom:8px'>SPEND / LOSE XP</div>
            <div style='color:#8899aa;font-size:12px;line-height:2'>
                💡 Hint: -20 XP<br>
                📖 See answer: -50 XP<br>
                ⏭ Skip question: -15 XP<br>
                😴 Miss 1 day: -20 XP<br>
                😴 Miss 3 days: -60 XP<br>
                💀 XP hits 0: Demoted to Level 1<br>
                &nbsp;
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:20px'>", unsafe_allow_html=True)
    weak_areas()

# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style='padding:14px 0 6px'>
        <div style='color:#00ff9d;font-size:19px;font-weight:800;letter-spacing:2px'>⬡ SQL.FORGE</div>
        <div style='color:#4a6080;font-size:10px;letter-spacing:1px'>POSTGRESQL PRACTICE ENGINE</div>
    </div>""", unsafe_allow_html=True)

    # Mode toggle
    st.markdown("<hr style='border-color:#1a2535;margin:8px 0'>", unsafe_allow_html=True)
    st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>PRACTICE MODE</div>", unsafe_allow_html=True)
    mode = st.toggle("Hero Mode (Full XP)", value=st.session_state.mode == "Hero")
    st.session_state.mode = "Hero" if mode else "Starter"
    if mode:
        st.markdown("<div style='color:#00ff9d;font-size:11px'>⚡ Strict evaluation · Full XP rewards</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='color:#f59e0b;font-size:11px'>🌱 Lenient evaluation · Half XP rewards</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1a2535;margin:8px 0'>", unsafe_allow_html=True)

    # XP bar
    xp = st.session_state.xp
    nx = next_rank_xp(xp); px = prev_rank_xp(xp)
    prog = (xp - px) / max(nx - px, 1)
    st.markdown(f"""<div style='background:#0c1220;border:1px solid #c084fc33;border-radius:10px;padding:12px;margin-bottom:10px'>
        <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'>
            <div><div style='color:#c084fc;font-size:9px;font-weight:700;letter-spacing:1px'>XP RANK</div>
            <div style='color:#e2f0ff;font-size:13px;font-weight:700'>{xp_rank(xp)}</div></div>
            <div style='text-align:right'><div style='color:#c084fc;font-size:17px;font-weight:800'>{xp}</div>
            <div style='color:#4a6080;font-size:9px'>XP</div></div>
        </div>
        <div style='background:#1a2535;border-radius:99px;height:4px'>
            <div style='background:linear-gradient(90deg,#c084fc,#a855f7);width:{int(prog*100)}%;height:100%;border-radius:99px'></div>
        </div>
        <div style='color:#4a6080;font-size:9px;margin-top:3px'>Next rank at {nx} XP</div>
    </div>""", unsafe_allow_html=True)

    # Demoted alert
    if st.session_state.demoted:
        st.markdown("""<div style='background:#f8717115;border:1px solid #f87171;border-radius:8px;padding:10px;margin-bottom:10px'>
            <div style='color:#f87171;font-size:12px;font-weight:700'>💀 DEMOTED TO LEVEL 1</div>
            <div style='color:#8899aa;font-size:11px;margin-top:3px'>XP hit 0 due to missed days. Practice daily to rebuild!</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Dismiss"):
            st.session_state.demoted = False; st.rerun()

    if st.session_state.stage == "practice":
        cfg = LEVELS[st.session_state.level]
        st.markdown(f"""<div style='background:#0c1220;border:1px solid {cfg["color"]}33;border-radius:8px;padding:10px;margin-bottom:8px'>
            <div style='color:{cfg["color"]};font-size:9px;font-weight:700;letter-spacing:1px'>{cfg["label"].upper()}</div>
            <div style='color:#e2f0ff;font-size:13px;font-weight:700'>{cfg["title"]}</div>
            <div style='color:#4a6080;font-size:10px'>{cfg["desc"]}</div>
        </div>""", unsafe_allow_html=True)

        streak = st.session_state.streak
        st.markdown(f"<div style='color:#4a6080;font-size:9px;font-weight:700;letter-spacing:1px;margin-bottom:4px'>STREAK — {streak}/15</div>", unsafe_allow_html=True)
        dots = "".join([f"<span style='display:inline-block;width:11px;height:11px;background:{'#00ff9d' if i<streak else '#1a2535'};border-radius:2px;margin:2px'></span>" for i in range(15)])
        st.markdown(f"<div>{dots}</div>", unsafe_allow_html=True)
        st.progress(streak/15)

        st.markdown("<hr style='border-color:#1a2535;margin:8px 0'>", unsafe_allow_html=True)
        s = st.session_state.stats
        acc = round((s["correct"]/s["total"])*100) if s["total"] > 0 else 0
        c1,c2 = st.columns(2)
        c1.metric("Solved", s["total"]); c2.metric("Accuracy", f"{acc}%")
        c1.metric("XP", st.session_state.xp); c2.metric("Correct", s["correct"])

        st.markdown("<hr style='border-color:#1a2535;margin:8px 0'>", unsafe_allow_html=True)
        st.markdown("<div style='color:#4a6080;font-size:9px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>SCHEMA</div>", unsafe_allow_html=True)
        for tname, df in st.session_state.tables.items():
            with st.expander(f"⬡ {tname} ({len(df)}r)"):
                for col in df.columns:
                    dtype = df[col].dtype
                    icon = "123" if dtype in ["int64","float64"] else "abc"
                    color = "#f59e0b" if dtype in ["int64","float64"] else "#8899aa"
                    st.markdown(f"<div style='color:{color};font-size:10px;font-family:monospace;padding:1px 0'><span style='opacity:.5'>{icon}</span> {col}</div>", unsafe_allow_html=True)

        st.markdown("<hr style='border-color:#1a2535;margin:8px 0'>", unsafe_allow_html=True)
        for l in [1,2,3]:
            lc = LEVELS[l]; cur = st.session_state.level
            label = f"{'▶' if l==cur else '✓' if l<cur else '○'} {lc['label']}: {lc['title']}"
            color = lc["color"] if l==cur else "#4a6080" if l<cur else "#1a2535"
            st.markdown(f"<div style='color:{color};font-size:10px;margin-bottom:3px;font-weight:{'700' if l==cur else '400'}'>{label}</div>", unsafe_allow_html=True)

        st.markdown("")
        if st.button("↩ New File"):
            for k in list(st.session_state.keys()): del st.session_state[k]
            init(); st.rerun()

    st.markdown("<hr style='border-color:#1a2535;margin:8px 0'>", unsafe_allow_html=True)
    streak_calendar()

# ── UPLOAD ───────────────────────────────────────────────────
if st.session_state.stage == "upload":
    st.markdown("""<div style='text-align:center;padding:28px 0 18px'>
        <div style='font-size:44px;margin-bottom:10px'>⬡</div>
        <div style='color:#00ff9d;font-size:36px;font-weight:800;letter-spacing:3px;margin-bottom:8px'>SQL.FORGE</div>
        <div style='color:#4a6080;font-size:13px;max-width:480px;margin:0 auto;line-height:1.6'>
            Upload your data. Practice real PostgreSQL from foundations to MAANG-level interview questions.
        </div>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    for l,col in zip([1,2,3],[c1,c2,c3]):
        lc = LEVELS[l]
        col.markdown(f"""<div style='background:#0c1220;border:1px solid {lc["color"]}33;border-radius:10px;padding:14px'>
            <div style='color:{lc["color"]};font-size:9px;font-weight:700;letter-spacing:1.5px'>{lc["label"].upper()}</div>
            <div style='color:#e2f0ff;font-size:13px;font-weight:700;margin:3px 0'>{lc["title"]}</div>
            <div style='color:#4a6080;font-size:10px'>{lc["desc"]}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")
    api_key = get_api_key()
    if not api_key:
        st.markdown("""<div style='background:#0c1220;border:1px solid #f59e0b44;border-radius:10px;padding:12px;margin-bottom:14px'>
            <div style='color:#f59e0b;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:4px'>🔑 GEMINI API KEY</div>
            <div style='color:#4a6080;font-size:11px'>Free at aistudio.google.com — needed only for answer evaluation</div>
        </div>""", unsafe_allow_html=True)
        key_input = st.text_input("Paste Gemini API key", type="password", placeholder="AIza...")
        if key_input: st.session_state["api_key"] = key_input

    st.markdown("""<div style='background:#f59e0b08;border:1px solid #f59e0b44;border-radius:10px;padding:14px;margin:12px 0'>
        <div style='color:#f59e0b;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>⚠ IMPORTANT — FOR JOIN QUESTIONS</div>
        <div style='color:#8899aa;font-size:12px;line-height:1.8'>
            Shared columns must have the <b style='color:#e2f0ff'>exact same name</b> across files.<br>
            ✓ <span style='color:#00ff9d'>customers.customer_id ↔ orders.customer_id</span> — join detected<br>
            ✗ <span style='color:#f87171'>customers.cust_id ↔ orders.customer_id</span> — join NOT detected
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>UPLOAD — up to 3 CSV files or 1 Excel with 3 sheets</div>", unsafe_allow_html=True)
    uploaded_files = st.file_uploader("", type=["csv","xlsx","xls"], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        if len(uploaded_files) > 3: uploaded_files = uploaded_files[:3]
        tables = {}
        for f in uploaded_files:
            parsed = parse_file(f)
            tables.update(parsed)
            if len(tables) >= 3: tables = dict(list(tables.items())[:3]); break

        if tables:
            st.session_state.tables = tables
            st.session_state.file_name = ", ".join([f.name for f in uploaded_files])
            st.markdown(f"""<div style='background:#0c1220;border:1px solid #00ff9d33;border-radius:8px;padding:12px;margin:10px 0'>
                <span style='color:#00ff9d;font-weight:700'>✓ {len(tables)} table(s) loaded:</span>
                <span style='color:#e2f0ff'> {", ".join(tables.keys())}</span>
                <span style='color:#4a6080'> · {sum(len(d) for d in tables.values())} rows total</span>
            </div>""", unsafe_allow_html=True)

            if len(tables) > 1:
                tnames = list(tables.keys()); dfs = list(tables.values())
                shared = []
                for i in range(len(tnames)):
                    for j in range(i+1, len(tnames)):
                        common = set(dfs[i].columns) & set(dfs[j].columns)
                        for col in common: shared.append((tnames[i], tnames[j], col))
                if shared:
                    rel = "".join([f"<div style='color:#8899aa;font-size:12px;margin:2px 0'>🔗 <span style='color:#00ff9d'>{a}</span> ↔ <span style='color:#00ff9d'>{b}</span> via <b style='color:#f59e0b'>{col}</b></div>" for a,b,col in shared])
                    st.markdown(f"""<div style='background:#00ff9d08;border:1px solid #00ff9d33;border-radius:8px;padding:12px;margin-bottom:10px'>
                        <div style='color:#00ff9d;font-size:10px;font-weight:700;margin-bottom:6px'>✓ RELATIONSHIPS DETECTED</div>{rel}</div>""", unsafe_allow_html=True)
                else:
                    st.markdown("""<div style='background:#f8717108;border:1px solid #f8717133;border-radius:8px;padding:12px;margin-bottom:10px'>
                        <div style='color:#f87171;font-size:10px;font-weight:700;margin-bottom:4px'>⚠ NO SHARED COLUMNS</div>
                        <div style='color:#8899aa;font-size:12px'>No common column names found. JOIN questions may not generate correctly.</div>
                    </div>""", unsafe_allow_html=True)

            # Dataset brief
            st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin:14px 0 8px'>DATASET BRIEF</div>", unsafe_allow_html=True)
            if len(tables) == 1: dataset_brief(tables)
            else:
                tabs = st.tabs(list(tables.keys()))
                for tab,(tname,df) in zip(tabs, tables.items()):
                    with tab: dataset_brief({tname: df})

            if st.button("🚀 Start Practising — Level 1"): start_level(1)

# ── PRACTICE ─────────────────────────────────────────────────
elif st.session_state.stage == "practice":
    questions = st.session_state.questions
    qi = st.session_state.qi
    q = questions[qi]
    cfg = LEVELS[st.session_state.level]
    dc = DIFF_COLOR.get(q.get("difficulty",""), "#8899aa")

    ca,cb,cc,cd = st.columns([4,1,1,1])
    ca.markdown(f"<div style='color:#00ff9d;font-size:17px;font-weight:800;padding-top:4px'>⬡ SQL.FORGE <span style='color:#1a2535'>|</span> <span style='color:#4a6080;font-size:11px;font-weight:400'>{st.session_state.file_name}</span></div>", unsafe_allow_html=True)
    cb.markdown(f"<div style='color:{cfg['color']};font-weight:700;text-align:center;padding-top:6px'>{cfg['label']}</div>", unsafe_allow_html=True)
    cc.markdown(f"<div style='color:#4a6080;text-align:center;padding-top:6px'>Q{qi+1}/{len(questions)}</div>", unsafe_allow_html=True)
    mode_color = "#00ff9d" if st.session_state.mode == "Hero" else "#f59e0b"
    cd.markdown(f"<div style='color:{mode_color};font-weight:700;text-align:center;padding-top:6px'>{st.session_state.mode}</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1a2535;margin:6px 0 10px'>", unsafe_allow_html=True)

    tab_practice, tab_dash, tab_brief, tab_weak = st.tabs(["📝 Practice", "📊 Dashboard", "📋 Dataset Brief", "🎯 Weak Areas"])

    with tab_practice:
        xp_reward = XP_EARN["correct_hero"] if st.session_state.mode == "Hero" else XP_EARN["correct_starter"]

        st.markdown(f"""<div style='background:#0c1220;border:1px solid #1a2535;border-left:3px solid {cfg["color"]};border-radius:10px;padding:16px;margin-bottom:12px'>
            <div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>
                <span style='background:{cfg["color"]}22;color:{cfg["color"]};border-radius:6px;padding:2px 10px;font-size:10px;font-weight:700;letter-spacing:1px'>{q.get("concept","").upper()}</span>
                <span style='background:{dc}22;color:{dc};border-radius:6px;padding:2px 10px;font-size:10px;font-weight:700'>{q.get("difficulty","")}</span>
                <span style='color:#c084fc;font-size:11px;margin-left:auto'>+{xp_reward} XP on correct</span>
                <span style='color:#4a6080;font-size:11px'>Mode: <b style='color:{mode_color}'>{st.session_state.mode}</b></span>
            </div>
            <div style='color:#e2f0ff;font-size:14px;font-weight:500;line-height:1.7'>{q["question"]}</div>
        </div>""", unsafe_allow_html=True)

        # Inline schema reference
        schema_html = "<div style='background:#060a10;border:1px solid #1a2535;border-radius:8px;padding:10px;margin-bottom:10px'>"
        schema_html += "<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:8px'>📋 SCHEMA REFERENCE — use these exact table & column names</div>"
        schema_html += "<div style='display:flex;flex-wrap:wrap;gap:20px'>"
        for tname, df in st.session_state.tables.items():
            cols_str = "  ".join([f"<span style='color:#f59e0b'>{c}</span>" for c in df.columns])
            schema_html += f"<div><div style='color:#00ff9d;font-size:12px;font-weight:700;margin-bottom:4px'>⬡ {tname} <span style=\'color:#4a6080;font-size:10px\'>{len(df)} rows</span></div><div style=\'font-size:11px;line-height:1.8\'>{cols_str}</div></div>"
        schema_html += "</div></div>"
        st.markdown(schema_html, unsafe_allow_html=True)

        st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin-bottom:6px'>SQL EDITOR</div>", unsafe_allow_html=True)
        user_sql = st.text_area("", value=st.session_state.user_sql, height=165,
            placeholder="-- Write your PostgreSQL query here\nSELECT ...",
            key=f"sql_{qi}", label_visibility="collapsed")
        st.session_state.user_sql = user_sql

        b1,b2,b3,b4,b5 = st.columns([3,3,2,2,2])
        run_clicked = b1.button("▶ Run Query")
        submit_clicked = b2.button("✓ Submit Answer", disabled=not st.session_state.query_ran or bool(st.session_state.feedback))
        skip_clicked = b3.button("⏭ Skip")
        hint_clicked = b4.button("💡 Hint", disabled=st.session_state.hint_used)
        show_ans = b5.checkbox("📖 Show Answer", disabled=st.session_state.answer_used)
        b3.markdown("<div style='color:#4a6080;font-size:10px;text-align:center;margin-top:-8px'>-15 XP</div>", unsafe_allow_html=True)
        b4.markdown("<div style='color:#4a6080;font-size:10px;text-align:center;margin-top:-8px'>-20 XP</div>", unsafe_allow_html=True)
        b5.markdown("<div style='color:#4a6080;font-size:10px;text-align:center;margin-top:-8px'>-50 XP</div>", unsafe_allow_html=True)

        if hint_clicked and not st.session_state.hint_used:
            if spend_xp(XP_COST["hint"]): st.session_state.hint_used = True; st.rerun()
            else: st.warning(f"Need {XP_COST['hint']} XP for hint. Answer questions to earn XP!")

        if show_ans and not st.session_state.answer_used:
            if spend_xp(XP_COST["answer"]): st.session_state.answer_used = True
            else: st.warning(f"Need {XP_COST['answer']} XP to reveal answer!")

        if skip_clicked: spend_xp(XP_COST["skip"]); next_q()

        if run_clicked and user_sql.strip():
            result, error = run_query(user_sql)
            st.session_state.query_result = result
            st.session_state.query_error = error
            st.session_state.query_ran = True

        if st.session_state.hint_used:
            st.markdown(f"""<div style='background:#00ff9d08;border:1px solid #00ff9d33;border-radius:8px;padding:10px;margin-top:8px'>
                <span style='color:#00ff9d;font-size:10px;font-weight:700'>HINT  </span>
                <span style='color:#8899aa;font-size:12px'>{q["hint"]}</span>
            </div>""", unsafe_allow_html=True)

        if st.session_state.answer_used:
            st.markdown("<div style='color:#f59e0b;font-size:10px;font-weight:700;letter-spacing:1px;margin:8px 0 4px'>REFERENCE ANSWER</div>", unsafe_allow_html=True)
            st.code(q["sample_answer"], language="sql")

        if st.session_state.query_ran:
            st.markdown("<div style='color:#4a6080;font-size:10px;font-weight:700;letter-spacing:1px;margin:10px 0 6px'>QUERY OUTPUT</div>", unsafe_allow_html=True)
            if st.session_state.query_error:
                st.markdown(f"""<div style='background:#f8717110;border:1px solid #f8717144;border-radius:8px;padding:10px'>
                    <div style='color:#f87171;font-size:10px;font-weight:700;margin-bottom:3px'>⚠ SYNTAX ERROR</div>
                    <code style='color:#f87171;font-size:12px'>{st.session_state.query_error}</code>
                </div>""", unsafe_allow_html=True)
            elif st.session_state.query_result is not None:
                r = st.session_state.query_result
                st.markdown(f"<div style='color:#4a6080;font-size:11px;margin-bottom:4px'>{len(r)} rows · {len(r.columns)} columns</div>", unsafe_allow_html=True)
                st.dataframe(r.head(20), use_container_width=True)
                if not st.session_state.feedback:
                    st.markdown("<div style='color:#00ff9d;font-size:11px;margin-top:4px'>✓ Query ran — click Submit Answer to evaluate</div>", unsafe_allow_html=True)

        if submit_clicked:
            api_key = get_api_key()
            if not api_key: st.error("Add your Gemini API key first.")
            else:
                strict = st.session_state.mode == "Hero"
                with st.spinner("Evaluating your query..."):
                    result = evaluate_answer(get_schema_text(), q["question"], q["concept"],
                                             q["sample_answer"], user_sql, api_key)
                    elapsed = int((datetime.now() - st.session_state.q_start_time).total_seconds()) if st.session_state.q_start_time else 0
                    st.session_state.feedback = {**result, "elapsed": elapsed}
                    st.session_state.stats["times"].append(elapsed)

                    concept = q.get("concept","Other")
                    concepts = st.session_state.stats["concepts"]
                    if concept not in concepts: concepts[concept] = {"attempts":0,"correct":0,"acc":0}
                    concepts[concept]["attempts"] += 1

                    # Syntax score based on error
                    syntax_score = result.get("score", 0)
                    st.session_state.stats["syntax_scores"].append(syntax_score)

                    st.session_state.total_attempted += 1
                    st.session_state.stats["total"] += 1

                    if result["correct"]:
                        concepts[concept]["correct"] += 1
                        st.session_state.stats["correct"] += 1
                        new_streak = st.session_state.streak + 1
                        st.session_state.consecutive_correct += 1
                        st.session_state.max_consecutive = max(st.session_state.max_consecutive, st.session_state.consecutive_correct)
                        xp_gain = xp_reward
                        if elapsed < 60: xp_gain += XP_EARN["speed_bonus"]
                        if new_streak == 5: xp_gain += XP_EARN["streak_5"]
                        if new_streak == 10: xp_gain += XP_EARN["streak_10"]
                        st.session_state.xp += xp_gain
                        st.session_state.streak = new_streak
                        if new_streak >= 15:
                            st.session_state.xp += XP_EARN["level_complete"]
                            if st.session_state.level < 3:
                                st.balloons()
                                st.success(f"🎉 Level complete! +{XP_EARN['level_complete']} XP!")
                                import time; time.sleep(2)
                                start_level(st.session_state.level + 1)
                            else:
                                st.session_state.stage = "complete"; st.rerun()
                    else:
                        # Wrong answer resets streak to 0
                        st.session_state.streak = 0
                        st.session_state.consecutive_correct = 0

                    concepts[concept]["acc"] = round(100 * concepts[concept]["correct"] / concepts[concept]["attempts"])

        if st.session_state.feedback:
            fb = st.session_state.feedback
            bc = "#00ff9d" if fb["correct"] else "#f87171"
            bg = "#00ff9d08" if fb["correct"] else "#f8717108"
            elapsed = fb.get("elapsed", 0)
            score = fb.get("score", 0)

            xp_msg = ""
            if fb["correct"]:
                xp_gain = xp_reward
                if elapsed < 60: xp_gain += XP_EARN["speed_bonus"]
                xp_msg = f"+{xp_gain} XP"
                if st.session_state.streak == 5: xp_msg += f" +{XP_EARN['streak_5']} streak bonus!"
                if st.session_state.streak == 10: xp_msg += f" +{XP_EARN['streak_10']} streak bonus!"

            # Query quality breakdown
            time_color = "#00ff9d" if elapsed < 60 else "#f59e0b" if elapsed < 120 else "#f87171"
            score_color = "#00ff9d" if score >= 75 else "#f59e0b" if score >= 50 else "#f87171"

            st.markdown(f"""<div style='background:{bg};border:1px solid {bc}44;border-radius:10px;padding:14px;margin-top:10px'>
                <div style='display:flex;align-items:center;gap:10px;margin-bottom:10px'>
                    <span style='color:{bc};font-size:17px;font-weight:700'>{"✓" if fb["correct"] else "✗"}</span>
                    <span style='color:{bc};font-weight:700;font-size:14px'>{"Correct!" if fb["correct"] else "Wrong — streak reset to 0"}</span>
                    <span style='color:#4a6080;font-size:10px;margin-left:auto'>Score: <b style='color:{score_color}'>{score}/100</b></span>
                    {"<span style='color:#c084fc;font-size:12px;font-weight:700'>"+xp_msg+"</span>" if xp_msg else ""}
                </div>
                <div style='color:#c0d0e0;font-size:13px;line-height:1.7;margin-bottom:10px'>{fb.get("explanation","")}</div>
                <div style='color:#4a6080;font-size:12px;margin-bottom:10px'><span style='color:#00ff9d'>tip: </span>{fb.get("tip","")}</div>
                <div style='display:flex;gap:16px;border-top:1px solid #1a2535;padding-top:10px;flex-wrap:wrap'>
                    <span style='color:#4a6080;font-size:11px'>⏱ Time: <b style='color:{time_color}'>{elapsed}s</b></span>
                    <span style='color:#4a6080;font-size:11px'>📊 Score: <b style='color:{score_color}'>{score}/100</b></span>
                    <span style='color:#4a6080;font-size:11px'>🎯 Streak: <b style='color:#00ff9d'>{st.session_state.streak}/15</b></span>
                    <span style='color:#4a6080;font-size:11px'>⚡ Mode: <b style='color:{mode_color}'>{st.session_state.mode}</b></span>
                    {"<span style='color:#00ff9d;font-size:11px'>⚡ Speed bonus!</span>" if elapsed < 60 and fb["correct"] else ""}
                </div>
            </div>""", unsafe_allow_html=True)

            if st.button("Next Question →"): next_q()

    with tab_dash:
        dashboard_view()

    with tab_brief:
        dataset_brief(st.session_state.tables)

    with tab_weak:
        weak_areas()

# ── COMPLETE ─────────────────────────────────────────────────
elif st.session_state.stage == "complete":
    s = st.session_state.stats
    acc = round((s["correct"]/s["total"])*100) if s["total"] > 0 else 0
    st.markdown(f"""<div style='text-align:center;padding:40px 0'>
        <div style='font-size:52px;margin-bottom:14px'>🏆</div>
        <div style='color:#00ff9d;font-size:30px;font-weight:800;margin-bottom:6px'>All Levels Complete!</div>
        <div style='color:#c084fc;font-size:17px;font-weight:700;margin-bottom:4px'>{xp_rank(st.session_state.xp)} · {st.session_state.xp} XP</div>
        <div style='color:#4a6080;font-size:13px'>Foundations → Joins → MAANG Level mastered.</div>
    </div>""", unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Questions", s["total"]); c2.metric("Accuracy", f"{acc}%")
    c3.metric("Total XP", st.session_state.xp); c4.metric("Rank", xp_rank(st.session_state.xp))
    st.markdown("<div style='margin-top:20px'>"); weak_areas()
    st.markdown("")
    if st.button("🔄 New Session"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        init(); st.rerun()

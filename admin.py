import streamlit as st
import pandas as pd
import pickle
import os
import re

st.set_page_config(page_title="SQL Forge — Admin", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif !important; }
.stApp { background: #080c14; color: #bfc7d5; }
section[data-testid="stSidebar"] { background: #0c1220 !important; border-right: 1px solid #1a2535; }
#MainMenu, footer { visibility: hidden; }
header { visibility: visible !important; background: #080c14 !important; }
.stButton > button {
    background: linear-gradient(135deg, #00ff9d, #00cc7a) !important;
    color: #080c14 !important; border: none !important; border-radius: 8px !important;
    font-weight: 700 !important; padding: 0.5rem 1.5rem !important;
}
.stButton > button:hover { transform: translateY(-1px) !important; }
[data-testid="stFileUploader"] { background: #0c1220 !important; border: 2px dashed #1a2535 !important; border-radius: 12px !important; }
.stTextInput > div > div > input { background: #0c1220 !important; border-color: #1a2535 !important; color: #e2f0ff !important; border-radius: 8px !important; }
[data-testid="metric-container"] { background: #0c1220 !important; border: 1px solid #1a2535 !important; border-radius: 10px !important; padding: 14px !important; }
[data-testid="metric-container"] label { color: #4a6080 !important; font-size: 10px !important; text-transform: uppercase !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #00ff9d !important; font-size: 22px !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

CONFIG_FILE = "admin_config.pkl"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", st.secrets.get("ADMIN_PASSWORD", "admin123"))


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "rb") as f:
            return pickle.load(f)
    return {"fixed_dataset": False, "tables": {}, "file_name": "", "message": ""}


def save_config(config):
    with open(CONFIG_FILE, "wb") as f:
        pickle.dump(config, f)


def parse_file(f):
    import openpyxl
    ext = f.name.rsplit(".", 1)[-1].lower()
    tables = {}
    if ext == "csv":
        df = pd.read_csv(f)
        name = re.sub(r"[^a-zA-Z0-9]", "_", f.name.rsplit(".", 1)[0]).lower().strip("_")
        name = re.sub(r"_+", "_", name)
        tables[name] = df
    elif ext in ["xlsx", "xls"]:
        xf = pd.ExcelFile(f)
        for sh in xf.sheet_names[:3]:
            df = pd.read_excel(f, sheet_name=sh)
            if len(df):
                name = re.sub(r"[^a-zA-Z0-9]", "_", sh).lower().strip("_")
                tables[name] = df
    return tables


# ── Auth ─────────────────────────────────────────────────────
if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

if not st.session_state.admin_auth:
    st.markdown("""
    <div style='text-align:center;padding:60px 0 30px'>
        <div style='color:#00ff9d;font-size:36px;font-weight:800;letter-spacing:2px'>⚙️ ADMIN PANEL</div>
        <div style='color:#4a6080;font-size:13px;margin-top:8px'>SQL.FORGE Dataset Control</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("Admin Password", type="password", placeholder="Enter password...")
        if st.button("Login"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# ── Admin Dashboard ───────────────────────────────────────────
config = load_config()

st.markdown("""
<div style='display:flex;align-items:center;gap:12px;margin-bottom:24px'>
    <span style='color:#00ff9d;font-size:22px;font-weight:800'>⚙️ SQL.FORGE ADMIN</span>
    <span style='color:#1a2535'>|</span>
    <span style='color:#4a6080;font-size:13px'>Dataset Control Panel</span>
</div>
""", unsafe_allow_html=True)

# Status
col1, col2, col3 = st.columns(3)
mode = "🔒 Fixed Dataset" if config["fixed_dataset"] else "🔓 Open Upload"
mode_color = "#f87171" if config["fixed_dataset"] else "#00ff9d"
col1.markdown(f"""<div style='background:#0c1220;border:1px solid {mode_color}33;border-radius:10px;padding:16px;text-align:center'>
    <div style='color:{mode_color};font-size:13px;font-weight:700'>{mode}</div>
    <div style='color:#4a6080;font-size:11px;margin-top:4px'>Current mode</div>
</div>""", unsafe_allow_html=True)
col2.metric("Tables Loaded", len(config["tables"]))
col3.metric("File", config["file_name"] or "None")

st.markdown("---")

# ── Toggle ───────────────────────────────────────────────────
st.markdown("### Dataset Mode")
st.markdown("<div style='color:#4a6080;font-size:13px;margin-bottom:12px'>When Fixed Dataset is ON — all users practice on the admin-uploaded file. Upload button is hidden from users.</div>", unsafe_allow_html=True)

col_a, col_b = st.columns([1, 3])
with col_a:
    fixed = st.toggle("Fixed Dataset Mode", value=config["fixed_dataset"])

if fixed != config["fixed_dataset"]:
    config["fixed_dataset"] = fixed
    save_config(config)
    st.rerun()

st.markdown("---")

# ── File Upload ───────────────────────────────────────────────
st.markdown("### Upload Admin Dataset")
st.markdown("<div style='color:#4a6080;font-size:13px;margin-bottom:12px'>Upload the file that all users will practice on when Fixed Dataset mode is ON.</div>", unsafe_allow_html=True)

uploaded = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx","xls"], accept_multiple_files=True)

if uploaded:
    tables = {}
    for f in uploaded[:3]:
        parsed = parse_file(f)
        tables.update(parsed)
        if len(tables) >= 3: break

    if tables:
        st.markdown(f"""<div style='background:#00ff9d08;border:1px solid #00ff9d33;border-radius:8px;padding:12px;margin:12px 0'>
            <span style='color:#00ff9d;font-weight:700'>✓ Ready to save:</span>
            <span style='color:#e2f0ff'> {", ".join(tables.keys())}</span>
            <span style='color:#4a6080'> · {sum(len(d) for d in tables.values())} rows</span>
        </div>""", unsafe_allow_html=True)

        for tname, df in tables.items():
            with st.expander(f"Preview: {tname}"):
                st.dataframe(df.head(5), use_container_width=True)

        col_save, col_clear = st.columns(2)
        with col_save:
            if st.button("💾 Save as Admin Dataset"):
                config["tables"] = tables
                config["file_name"] = ", ".join([f.name for f in uploaded[:3]])
                save_config(config)
                st.success("✓ Admin dataset saved!")
                st.rerun()

st.markdown("---")

# ── Custom Message ────────────────────────────────────────────
st.markdown("### Message to Users (optional)")
msg = st.text_input("Show a message to users on the practice screen", value=config.get("message",""), placeholder="e.g. Today's dataset: E-commerce Sales Q4 2024")
if st.button("Save Message"):
    config["message"] = msg
    save_config(config)
    st.success("Message saved!")

st.markdown("---")

# ── Current Dataset Info ──────────────────────────────────────
if config["tables"]:
    st.markdown("### Current Admin Dataset")
    for tname, df in config["tables"].items():
        st.markdown(f"""<div style='background:#0c1220;border:1px solid #1a2535;border-radius:8px;padding:12px;margin-bottom:8px'>
            <span style='color:#00ff9d;font-weight:700'>⬡ {tname}</span>
            <span style='color:#4a6080;font-size:12px'> — {len(df)} rows · {len(df.columns)} columns</span><br>
            <span style='color:#f59e0b;font-size:11px;font-family:monospace'>{" · ".join(df.columns)}</span>
        </div>""", unsafe_allow_html=True)

    if st.button("🗑️ Clear Admin Dataset"):
        config["tables"] = {}
        config["file_name"] = ""
        save_config(config)
        st.rerun()

# Logout
st.markdown("---")
if st.button("Logout"):
    st.session_state.admin_auth = False
    st.rerun()

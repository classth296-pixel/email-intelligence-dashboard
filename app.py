"""
Streamlit Dashboard for Gmail → Gemini Email Processing Pipeline.
- Start/Stop the polling pipeline
- Manage allowed senders
- View processed email results
"""  
import os
import sys
import json
import threading
import time
import traceback

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Ensure the app's own folder is always on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(override=True)

# Write credential files from Streamlit secrets (for cloud deployment)
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

def secrets_to_dict(obj):
    """Recursively convert Streamlit AttrDict to plain dict."""
    if hasattr(obj, '_asdict'):
        return secrets_to_dict(obj._asdict())
    elif hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif isinstance(obj, dict):
        return {k: secrets_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [secrets_to_dict(i) for i in obj]
    else:
        return obj

# Write credential files from Streamlit secrets (for cloud deployment)
if hasattr(st, 'secrets'):
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

    if "gmail_token" in st.secrets:
        with open("token.json", "w") as f:
            json.dump(secrets_to_dict(dict(st.secrets["gmail_token"])), f)

    if "gmail_credentials" in st.secrets:
        with open("credentials.json", "w") as f:
            json.dump(secrets_to_dict(dict(st.secrets["gmail_credentials"])), f)

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Email Intelligence Dashboard",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Auto refresh using built-in Streamlit fragment
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0

col_refresh = st.sidebar.empty()
if col_refresh.button("⟳ Auto-refreshing...", key="auto"):
    pass

import time
time.sleep(0.1)
st.session_state.refresh_count += 1
if st.session_state.refresh_count % 600 == 0:  # every 60 seconds approx
    st.rerun()

# ── constants ─────────────────────────────────────────────────────────────────
SENDERS_FILE = "senders.json"
OUTPUT_CSV   = "output.csv"

# ── custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Background */
  .stApp { background-color: #0f1117; color: #e0e0e0; }

  /* Sidebar */
  section[data-testid="stSidebar"] { background-color: #1a1d27; }

  /* Cards */
  .card {
    background: #1e2130;
    border: 1px solid #2e3250;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
  }

  /* Status badge */
  .badge-running {
    background: #1a3a2a;
    color: #4ade80;
    border: 1px solid #4ade80;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 600;
    display: inline-block;
  }
  .badge-stopped {
    background: #3a1a1a;
    color: #f87171;
    border: 1px solid #f87171;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 600;
    display: inline-block;
  }

  /* Sender chips */
  .sender-chip {
    background: #252840;
    border: 1px solid #3b3f6b;
    border-radius: 8px;
    padding: 8px 14px;
    margin: 4px 0;
    font-family: monospace;
    font-size: 13px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  /* Metric cards */
  .metric-box {
    background: #1e2130;
    border: 1px solid #2e3250;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
  }
  .metric-value { font-size: 32px; font-weight: 700; color: #818cf8; }
  .metric-label { font-size: 12px; color: #94a3b8; margin-top: 4px; }

  /* Table styling */
  .dataframe { font-size: 13px !important; }

  /* Section headers */
  h2, h3 { color: #c7d2fe !important; }
</style>
""", unsafe_allow_html=True)


# ── helpers: senders.json ────────────────────────────────────────────────────
def load_senders():
    if os.path.exists(SENDERS_FILE):
        with open(SENDERS_FILE) as f:
            return json.load(f).get("allowed_senders", [])
    return []


def save_senders(senders):
    with open(SENDERS_FILE, "w") as f:
        json.dump({"allowed_senders": senders}, f, indent=2)


# ── helpers: CSV ──────────────────────────────────────────────────────────────
def load_csv():
    if os.path.exists(OUTPUT_CSV):
        try:
            df = pd.read_csv(OUTPUT_CSV)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            return df.sort_values("timestamp", ascending=False).reset_index(drop=True)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


# ── pipeline thread ───────────────────────────────────────────────────────────
def run_pipeline(stop_event, log_queue):
    """Runs the poll loop in a background thread."""
    try:
        import config
        import gmail_client
        import gemini_client
        import storage

        log_queue.append("🔐 Authenticating with Gmail...")
        service = gmail_client.get_gmail_service()
        state   = gmail_client.load_state()
        log_queue.append("✅ Authenticated. Pipeline started.")

        while not stop_event.is_set():
            try:
                # Reload allowed senders from file on every cycle
                senders = load_senders()
                allowed = {s.lower() for s in senders}

                new_messages = gmail_client.fetch_new_messages(service, state)

                if not new_messages:
                    log_queue.append("📭 No new messages.")
                else:
                    for msg in new_messages:
                        sender  = msg["sender_email"]
                        subject = msg["subject"]

                        if sender.lower() not in allowed:
                            log_queue.append(f"⏭ Skipped (not in allowlist): {sender}")
                            continue

                        body = msg["body"].strip()
                        if not body:
                            log_queue.append(f"⏭ Skipped (empty body): {sender}")
                            continue

                        log_queue.append(f"⚙️ Processing: {sender} | {subject}")
                        try:
                            output = gemini_client.run_prompt(body)
                            storage.append_result(
                                sender_email=sender,
                                subject=subject,
                                message=body,
                                gemini_output=output,
                            )
                            log_queue.append(f"✅ Saved result for: {subject}")
                        except Exception as e:
                            log_queue.append(f"❌ Gemini error: {e}")

            except Exception:
                log_queue.append(f"❌ Poll error:\n{traceback.format_exc()}")
            finally:
                gmail_client.save_state(state)

            # Sleep in small increments so stop_event is checked quickly
            for _ in range(config.POLL_INTERVAL_SECONDS):
                if stop_event.is_set():
                    break
                time.sleep(1)

        log_queue.append("🛑 Pipeline stopped.")

    except Exception as e:
        log_queue.append(f"❌ Startup error: {e}\n{traceback.format_exc()}")


# ── session state init ────────────────────────────────────────────────────────
if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False
if "stop_event" not in st.session_state:
    st.session_state.stop_event = None
if "thread" not in st.session_state:
    st.session_state.thread = None
if "log" not in st.session_state:
    st.session_state.log = []


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📧 Email Intelligence")
    st.markdown("---")

    # Pipeline status
    if st.session_state.pipeline_running:
        st.markdown('<span class="badge-running">● RUNNING</span>', unsafe_allow_html=True)
        if st.button("⏹ Stop Pipeline", use_container_width=True, type="secondary"):
            if st.session_state.stop_event:
                st.session_state.stop_event.set()
            st.session_state.pipeline_running = False
            st.rerun()
    else:
        st.markdown('<span class="badge-stopped">● STOPPED</span>', unsafe_allow_html=True)
        if st.button("▶ Start Pipeline", use_container_width=True, type="primary"):
            stop_event = threading.Event()
            log_queue  = st.session_state.log
            thread = threading.Thread(
                target=run_pipeline,
                args=(stop_event, log_queue),
                daemon=True
            )
            thread.start()
            st.session_state.stop_event       = stop_event
            st.session_state.thread           = thread
            st.session_state.pipeline_running = True
            st.rerun()

    st.markdown("---")

    # Live log
    st.markdown("### 📋 Live Log")
    log_text = "\n".join(st.session_state.log[-20:]) if st.session_state.log else "No activity yet."
    st.text_area("Log", value=log_text, height=300, label_visibility="collapsed")

    if st.button("🗑 Clear Log", use_container_width=True):
        st.session_state.log = []
        st.rerun()

    st.markdown("---")
    if st.button("🔄 Refresh Dashboard", use_container_width=True):
        st.rerun()




# ── MAIN AREA ─────────────────────────────────────────────────────────────────
st.markdown("# 📧 Email Intelligence Dashboard")
st.markdown("Automated email processing pipeline powered by **Gemini 2.5 Flash**")
st.markdown("---")

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📊 Results", "👥 Manage Senders"])


# ── TAB 1: RESULTS ────────────────────────────────────────────────────────────
with tab1:
    df = load_csv()

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    total     = len(df)
    senders_n = df["sender_email"].nunique() if not df.empty else 0
    today     = df[df["timestamp"].dt.date == pd.Timestamp.now().date()].shape[0] if not df.empty else 0
    subjects  = df["subject"].nunique() if not df.empty else 0

    with col1:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{total}</div><div class="metric-label">Total Processed</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{today}</div><div class="metric-label">Processed Today</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{senders_n}</div><div class="metric-label">Unique Senders</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-box"><div class="metric-value">{subjects}</div><div class="metric-label">Unique Subjects</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if df.empty:
        st.info("No emails processed yet. Start the pipeline and send an email from an allowed sender.")
    else:
        # Filters
        col_f1, col_f2 = st.columns([2, 2])
        with col_f1:
            sender_filter = st.selectbox(
                "Filter by sender",
                ["All"] + sorted(df["sender_email"].unique().tolist())
            )
        with col_f2:
            search = st.text_input("Search subject", placeholder="Type to search...")

        filtered = df.copy()
        if sender_filter != "All":
            filtered = filtered[filtered["sender_email"] == sender_filter]
        if search:
            filtered = filtered[filtered["subject"].str.contains(search, case=False, na=False)]

        st.markdown(f"**Showing {len(filtered)} of {len(df)} results**")
        st.markdown("---")

        # Show each email as expandable card
        for _, row in filtered.iterrows():
            ts = row["timestamp"].strftime("%d %b %Y, %I:%M %p") if pd.notna(row["timestamp"]) else "Unknown"
            with st.expander(f"📩 {row['subject']}  |  {row['sender_email']}  |  {ts}"):
                col_l, col_r = st.columns([1, 1])
                with col_l:
                    st.markdown("**📨 Original Email**")
                    st.text_area("Original Email", value=row.get("message", ""), height=200,
                                 key=f"msg_{_}", label_visibility="collapsed")
                with col_r:
                    st.markdown("**🤖 Gemini Analysis**")
                    st.text_area("Gemini Output", value=row.get("gemini_output", ""), height=200,
                                 key=f"out_{_}", label_visibility="collapsed")

        # Download button
        st.markdown("---")
        csv_data = filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇ Download Results as CSV",
            data=csv_data,
            file_name="email_analysis_results.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ── TAB 2: MANAGE SENDERS ─────────────────────────────────────────────────────
with tab2:
    st.markdown("### 👥 Allowed Senders")
    st.markdown("Only emails from these addresses will be processed by the pipeline.")
    st.markdown("<br>", unsafe_allow_html=True)

    senders = load_senders()

    # Add new sender
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        new_sender = st.text_input("Email Address", placeholder="Enter email address (e.g. boss@company.com)",
                                   label_visibility="collapsed")
    with col_btn:
        if st.button("➕ Add Sender", use_container_width=True, type="primary"):
            new_sender = new_sender.strip().lower()
            if new_sender and "@" in new_sender:
                if new_sender not in [s.lower() for s in senders]:
                    senders.append(new_sender)
                    save_senders(senders)
                    st.success(f"✅ Added: {new_sender}")
                    st.rerun()
                else:
                    st.warning("This email is already in the allowlist.")
            else:
                st.error("Please enter a valid email address.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"**{len(senders)} sender(s) in allowlist:**")

    # Display senders with remove buttons
    if not senders:
        st.info("No senders added yet. Add one above.")
    else:
        for i, sender in enumerate(senders):
            col_s, col_del = st.columns([5, 1])
            with col_s:
                st.markdown(
                    f'<div class="sender-chip">📧 {sender}</div>',
                    unsafe_allow_html=True
                )
            with col_del:
                if st.button("🗑", key=f"del_{i}", help=f"Remove {sender}"):
                    senders.pop(i)
                    save_senders(senders)
                    st.success(f"Removed: {sender}")
                    st.rerun()

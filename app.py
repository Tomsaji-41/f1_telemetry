import os
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
import requests
# pyrefly: ignore[missing-import]
import streamlit as st

st.set_page_config(
    page_title="ApexVision | Premium F1 Telemetry",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
FASTF1_FIRST_YEAR = 2018  # detailed lap and telemetry data starts here

# ---------- Guarded imports: show the real error instead of crashing ----------
try:
    try:
        from backend import config
    except ImportError:
        import config
    from backend.charts import (
        build_position_chart,
        build_grid_vs_finish_chart,
        build_telemetry_comparison_chart,
    )
    from backend.facts import extract_race_facts, get_telemetry_comparison
    from backend import tools
except Exception:
    st.error("Startup import failed. Send this text to get the exact fix:")
    st.code(traceback.format_exc())
    st.stop()

# ---------- Styling ----------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Titillium Web', sans-serif;
        background-color: #0b0e14;
        color: #E2E8F0;
    }
    .glass-card {
        background: rgba(22, 27, 34, 0.75);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        animation: popup 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        transition: transform 0.3s ease, border-color 0.3s ease;
    }
    .glass-card:hover { transform: translateY(-4px); border-color: rgba(230, 0, 43, 0.6); }
    @keyframes popup {
        0% { opacity: 0; transform: scale(0.95) translateY(20px); }
        100% { opacity: 1; transform: scale(1) translateY(0); }
    }
    .badge-f1 {
        background: linear-gradient(135deg, #e6002b 0%, #800018 100%);
        color: white; padding: 4px 12px; border-radius: 12px;
        font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)

# Curated metadata dictionary for constructor power units, bases, and official team colours
KNOWN_TEAM_METADATA = {
    "red_bull": {"power": "Honda RBPT", "base": "Milton Keynes, UK", "color": "#3671C6"},
    "ferrari": {"power": "Ferrari", "base": "Maranello, Italy", "color": "#E8002D"},
    "mercedes": {"power": "Mercedes", "base": "Brackley, UK", "color": "#27F4D2"},
    "mclaren": {"power": "Mercedes", "base": "Woking, UK", "color": "#FF8000"},
    "aston_martin": {"power": "Mercedes", "base": "Silverstone, UK", "color": "#229971"},
    "alpine": {"power": "Renault", "base": "Enstone, UK", "color": "#FF87BC"},
    "williams": {"power": "Mercedes", "base": "Grove, UK", "color": "#64C4FF"},
    "rb": {"power": "Honda RBPT", "base": "Faenza, Italy", "color": "#6692FF"},
    "alphatauri": {"power": "Honda RBPT", "base": "Faenza, Italy", "color": "#5E8FAA"},
    "toro_rosso": {"power": "Honda / Ferrari", "base": "Faenza, Italy", "color": "#469BFF"},
    "sauber": {"power": "Ferrari", "base": "Hinwil, Switzerland", "color": "#52E252"},
    "alfa": {"power": "Ferrari", "base": "Hinwil, Switzerland", "color": "#900000"},
    "haas": {"power": "Ferrari", "base": "Kannapolis, USA", "color": "#B6BABD"},
    "renault": {"power": "Renault", "base": "Enstone, UK", "color": "#FFF500"},
    "racing_point": {"power": "BWT Mercedes", "base": "Silverstone, UK", "color": "#F596C8"},
    "force_india": {"power": "Mercedes", "base": "Silverstone, UK", "color": "#F596C8"},
}

# ---------- Helpers ----------
def season_options():
    rng = getattr(config, "DEFAULT_SEASON_RANGE", None) or getattr(config, "SUPPORTED_SEASONS", None)
    if rng:
        return sorted(rng)
    return list(range(FASTF1_FIRST_YEAR, datetime.now(timezone.utc).year + 1))


@st.cache_data(ttl=600, show_spinner=False)
def completed_rounds(year: int):
    """Rounds whose race has finished, from the FastF1 schedule. Empty list on failure."""
    try:
        import fastf1
        import pandas as pd
        sched = fastf1.get_event_schedule(year, include_testing=False)
        if sched.empty or "Session5DateUtc" not in sched.columns:
            return []
        now = pd.Timestamp.now(tz="UTC")
        sess_utc = pd.to_datetime(sched["Session5DateUtc"], utc=True)
        done = sched[sess_utc < now]
        return [(int(r["RoundNumber"]), str(r["EventName"])) for _, r in done.iterrows()]
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def load_race_data(year: int, round_num: int):
    data_dir = getattr(config, "DATA_DIR", None)
    if data_dir:
        path = Path(data_dir) / str(year) / f"round_{round_num}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return extract_race_facts(year, round_num)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_teams(year: int):
    """Fetch teams from API or fallback gracefully to Jolpica standings and team catalog."""
    try:
        r = requests.get(f"{API_URL}/api/teams", params={"year": year}, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    # High-reliability fallback: query Jolpica constructor standings via tools
    try:
        standings = tools.get_standings(year, kind="constructors")
        if standings.get("status") == "ok":
            teams = []
            for item in standings.get("standings", []):
                cid = item.get("constructor_id", "").lower()
                meta = KNOWN_TEAM_METADATA.get(cid, {})
                teams.append({
                    "name": item.get("team", "Unknown"),
                    "power": meta.get("power", "Formula 1 Hybrid"),
                    "base": meta.get("base", "Europe"),
                    "color": meta.get("color", "#E10600"),
                    "points": item.get("points", 0),
                    "position": item.get("position", "-"),
                })
            if teams:
                return teams
    except Exception:
        pass

    # Static fallback for baseline constructors
    return [
        {"name": "Red Bull Racing", "power": "Honda RBPT", "base": "Milton Keynes, UK", "color": "#3671C6"},
        {"name": "Scuderia Ferrari", "power": "Ferrari", "base": "Maranello, Italy", "color": "#E8002D"},
        {"name": "McLaren F1 Team", "power": "Mercedes", "base": "Woking, UK", "color": "#FF8000"},
        {"name": "Mercedes-AMG PETRONAS", "power": "Mercedes", "base": "Brackley, UK", "color": "#27F4D2"},
        {"name": "Aston Martin Aramco", "power": "Mercedes", "base": "Silverstone, UK", "color": "#229971"},
    ]


def ask(message: str):
    """
    Connects to the backend chat engine. Uses SSE stream endpoint /api/chat/stream,
    capturing 'clarify', 'token', 'answer', and 'done' events seamlessly.
    """
    payload = {
        "message": message,
        "pending_state": st.session_state.get("pending_state"),
        "last_resolved_race": st.session_state.get("last_resolved_race"),
    }
    r = requests.post(f"{API_URL}/api/chat/stream", json=payload, stream=True, timeout=45)
    r.raise_for_status()

    clarify_event = {}
    answer_event = {}
    done_event = {}
    tokens = []
    current_event = None

    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            raw_data = line[len("data:"):].strip()
            try:
                data = json.loads(raw_data) if raw_data else {}
            except Exception:
                data = {}
            if current_event == "clarify":
                clarify_event = data
            elif current_event == "answer":
                answer_event = data
            elif current_event == "token":
                tokens.append(data.get("token", ""))
            elif current_event == "done":
                done_event = data

    if clarify_event:
        st.session_state.pending_state = clarify_event.get("pending_state")
        return {
            "type": "clarify",
            "question": clarify_event.get("question", "Can you provide more details?"),
            "options": clarify_event.get("options", []),
        }

    st.session_state.pending_state = None
    if done_event.get("resolved_context"):
        st.session_state.last_resolved_race = done_event.get("resolved_context")

    markdown_text = answer_event.get("markdown") or "".join(tokens) or "No response returned."
    return {
        "type": "answer",
        "markdown": markdown_text,
        "sources": done_event.get("sources", []),
        "followups": answer_event.get("followups", []),
    }


def handle(message: str):
    st.session_state.messages.append({"role": "user", "content": message})
    try:
        res = ask(message)
    except requests.RequestException as e:
        res = {
            "type": "error",
            "markdown": f"Cannot reach the chat service at {API_URL}. Is the backend running? ({e})",
        }
    st.session_state.messages.append({"role": "assistant", "res": res})


def show(res: dict, key: str, active: bool):
    kind = res.get("type")
    if kind == "clarify":
        st.markdown(res.get("question", "Can you be more specific?"))
        options = res.get("options", [])
        if active and options:
            cols = st.columns(min(len(options), 6))
            for i, opt in enumerate(options):
                lbl = str(opt.get("label", opt.get("value", "")))
                val = str(opt.get("value", lbl))
                if cols[i % len(cols)].button(lbl, key=f"{key}_o{i}"):
                    st.session_state.queued = val
                    st.rerun()
    else:
        st.markdown(res.get("markdown") or res.get("answer") or "No answer returned.")
        if res.get("sources"):
            st.caption(f"Verified from: {', '.join(res['sources'])}")
        if active:
            for i, f in enumerate(res.get("followups", [])):
                lbl = str(f.get("label", ""))
                if lbl and st.button(lbl, key=f"{key}_f{i}"):
                    st.session_state.queued = lbl
                    st.rerun()


# ---------- Sidebar ----------
st.sidebar.title("🏎️ ApexVision F1")
navigation_mode = st.sidebar.radio(
    "Navigation",
    ["Hero Hub & Teams", "Analytics Studio", "Telemetry Teleport", "AI Pit Boss Strategy"],
)

seasons = season_options()
selected_season = st.sidebar.selectbox("Season", seasons, index=len(seasons) - 1)

rounds = completed_rounds(selected_season)
if rounds:
    selected_round = st.sidebar.selectbox(
        "Grand Prix", [r for r, _ in rounds], format_func=lambda r: f"R{r} - {dict(rounds)[r]}",
        index=len(rounds) - 1,
    )
else:
    selected_round = st.sidebar.number_input("Grand Prix Round", min_value=1, max_value=30, value=1)
    st.sidebar.caption("Schedule unavailable, enter a round manually.")

# ---------- Page 1: Hub and teams ----------
if navigation_mode == "Hero Hub & Teams":
    st.markdown("<h1 style='text-align:center;color:#FFFFFF;font-weight:700;'>APEXVISION F1 ANALYTICS</h1>",
                unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#94A3B8;'>Telemetry, history and AI strategy insights.</p>",
                unsafe_allow_html=True)
    st.markdown(f"### Constructors {selected_season}")
    try:
        teams = fetch_teams(selected_season)
        cols = st.columns(3)
        for idx, team in enumerate(teams):
            color = team.get("color", "#334155")
            with cols[idx % 3]:
                st.markdown(f"""
                <div class="glass-card">
                    <span class="badge-f1" style="background:{color};">CONSTRUCTOR</span>
                    <h3 style="margin-top:12px;color:#FFFFFF;">{team.get('name', 'Unknown')}</h3>
                    <p style="color:#94A3B8;margin:4px 0;"><b>Power Unit:</b> {team.get('power', 'n/a')}</p>
                    <p style="color:#94A3B8;margin:4px 0;"><b>Base:</b> {team.get('base', 'n/a')}</p>
                </div>""", unsafe_allow_html=True)
    except Exception:
        st.info("Team data is not available right now.")

# ---------- Page 2: Analytics ----------
elif navigation_mode == "Analytics Studio":
    st.title("📊 Race Analytics Studio")
    if selected_season < FASTF1_FIRST_YEAR:
        st.warning(f"Detailed race analytics are available from {FASTF1_FIRST_YEAR}.")
    else:
        with st.spinner("Loading race data..."):
            try:
                facts = load_race_data(selected_season, int(selected_round))
                st.markdown(f"## {facts.get('event_name', 'Race')} ({facts.get('year', selected_season)})")
                st.markdown(f"**Winner:** `{facts.get('winner', 'n/a')}` | "
                            f"**Location:** `{facts.get('location', 'n/a')}` | "
                            f"**Total Laps:** `{facts.get('total_laps', 'n/a')}`")
                tab1, tab2 = st.tabs(["Position Progression", "Grid vs Finish"])
                with tab1:
                    st.plotly_chart(build_position_chart(facts), use_container_width=True)
                with tab2:
                    st.plotly_chart(build_grid_vs_finish_chart(facts), use_container_width=True)
            except Exception as e:
                st.error(f"Could not load analytics for this race: {e}")

# ---------- Page 3: Telemetry ----------
elif navigation_mode == "Telemetry Teleport":
    st.title("⚡ Telemetry Teleport")
    if selected_season < FASTF1_FIRST_YEAR:
        st.warning(f"Telemetry is available from {FASTF1_FIRST_YEAR}.")
    else:
        codes = []
        try:
            facts = load_race_data(selected_season, int(selected_round))
            codes = [r.get("code") for r in facts.get("results", []) if r.get("code")]
        except Exception as e:
            st.error(f"Could not load the driver list: {e}")

        col1, col2 = st.columns(2)
        if codes:
            d1 = col1.selectbox("Driver 1", codes, index=0)
            d2 = col2.selectbox("Driver 2", codes, index=min(1, len(codes) - 1))
        else:
            d1 = col1.text_input("Driver 1 code").upper()
            d2 = col2.text_input("Driver 2 code").upper()

        if st.button("Generate Telemetry Overlay", disabled=not (d1 and d2 and d1 != d2)):
            with st.spinner("Loading telemetry..."):
                try:
                    tel_data = get_telemetry_comparison(selected_season, int(selected_round), d1, d2)
                    st.plotly_chart(build_telemetry_comparison_chart(tel_data), use_container_width=True)
                except Exception as e:
                    st.error(f"Telemetry extraction error: {e}")

# ---------- Page 4: AI Pit Boss ----------
elif navigation_mode == "AI Pit Boss Strategy":
    st.title("🤖 AI Pit Boss")
    st.caption("Ask about any race, driver or season. The Pit Boss will ask if it needs more detail.")
    st.session_state.setdefault("messages", [])

    typed = st.chat_input("e.g. leclerc race strategy")
    text = st.session_state.pop("queued", None) or typed
    if text:
        with st.spinner("Fetching race data..."):
            handle(text)

    last = len(st.session_state.messages) - 1
    for i, m in enumerate(st.session_state.messages):
        with st.chat_message(m["role"]):
            if m["role"] == "user":
                st.markdown(m.get("content", ""))
            elif "res" in m:
                show(m["res"], f"m{i}", active=(i == last))
            else:
                st.markdown(m.get("content", ""))  # old-format messages

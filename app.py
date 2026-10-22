from pypdf import PdfReader
import streamlit as st 
from datetime import date, timedelta, datetime, timezone
import re
import hashlib
import html
import pandas as pd
from pathlib import Path
import streamlit.components.v1 as components

voice_clues = components.declare_component("syllabussense_voice_clues", path=str(Path(__file__).resolve().parent / "voice_input"))
from ai_analysis import analyze_syllabus, MAX_CHARACTERS
from database import (
    create_database,
    update_assignment_date,
    add_assignment,
    get_assignments,
    update_assignment_status,
    update_study_details,
    create_schedule_tables, get_availability, save_availability,
    get_sessions, replace_unfinished_sessions, set_session_completed, move_session,
    create_focus_table, get_active_focus, get_focus_history,
    start_focus, set_focus_running, finish_focus,
)
from study_schedule import generate_week
from study_calendar import render_calendar
from focus_discard import discard_active_focus, delete_saved_focus
from date_estimates import suggest_missing_dates, record_date_labels, get_date_labels
from course_management import (is_onboarded, mark_onboarded, rename_course, delete_course,
                               delete_assignment, create_management_tables, register_syllabus,
                               list_syllabi, delete_syllabus, list_courses, register_course)

def parse_weight(raw):
    """Convert '10%' or '45% (15% each)' to a numeric total weight.

    Grouped items retain their *total* weight until the student splits them.
    Unknown weights stay NULL rather than pretending to be zero.
    """
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*%", str(raw or ""))
    return float(match.group(1)) if match else None


create_database()
create_schedule_tables()
create_focus_table()
create_management_tables()

st.set_page_config(
    page_title="SyllabusSense",
    page_icon="🎓",
    layout="wide",
)

# ---------- DESIGN ----------
st.markdown("""
<style>
/* SyllabusSense 7.6: consistent light SaaS interface; no external assets. */
:root {color-scheme: light;}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background:#F6F8FC !important; color:#182C44 !important; }
[data-testid="stHeader"] { background:rgba(246,248,252,.96) !important; }
.block-container {max-width:1160px; padding-top:1.6rem; padding-bottom:4rem;}
h1,h2,h3,h4,[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li {color:#182C44;}
h1 {letter-spacing:-.035em !important; font-weight:800 !important;}
h2,h3 {letter-spacing:-.02em !important;}
[data-testid="stCaptionContainer"] p, .stCaption {color:#516780 !important; opacity:1 !important;}
.hero {background:linear-gradient(120deg,#172E54 0%,#315BA5 70%,#487CC8 100%); padding:32px 34px; border-radius:22px; margin:0 0 25px; box-shadow:0 14px 32px rgba(34,65,117,.12);}
.hero h2,.hero p {color:#FFF !important; margin:0;}
.hero h2 {font-size:1.8rem;letter-spacing:-.025em;}
.hero p {margin-top:10px;opacity:.95;}
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"], [data-testid="stForm"] {background-color:#FFFFFF !important; border:1px solid #E0E7F1 !important; border-radius:16px !important; box-shadow:0 3px 12px rgba(24,44,68,.035);}
[data-testid="stMetric"] {background:#FFF; border:1px solid #E0E7F1; border-radius:15px; padding:15px 18px;}
[data-testid="stMetricValue"] {color:#17365D !important;font-weight:800 !important;}
[data-testid="stMetricLabel"] * {color:#516780 !important;}
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,[data-testid="stTextArea"] textarea {
  background:#FFF !important; color:#17365D !important; -webkit-text-fill-color:#17365D !important;
  border-color:#B9C9DF !important;border-radius:10px !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stSelectbox"] [role="combobox"],
[data-testid="stSelectbox"] input {color:#17365D !important;-webkit-text-fill-color:#17365D !important;opacity:1 !important;}
[data-testid="stSelectbox"] svg {fill:#17365D !important;color:#17365D !important;}
[data-baseweb="popover"] [role="option"], [data-baseweb="popover"] [role="option"] *, [data-baseweb="popover"] [role="listbox"] * {color:#17365D !important;-webkit-text-fill-color:#17365D !important;}
[data-testid="stWidgetLabel"] p {color:#314765 !important;}
[data-testid="stTextInput"] input::placeholder,[data-testid="stTextArea"] textarea::placeholder{color:#687B94 !important;opacity:1 !important;}
.stButton button,[data-testid="stFormSubmitButton"] button {color:#17365D !important;background:#FFF !important;border:1px solid #C4D2E5 !important;border-radius:11px !important;font-weight:650 !important;min-height:2.55rem;}
.stButton button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"]{background:#295DA5 !important;border-color:#295DA5 !important;color:#FFF !important;}
.stButton button p,[data-testid="stFormSubmitButton"] button p {color:inherit !important;}
[data-testid="stExpander"] {border:1px solid #DCE5F0 !important;border-radius:13px !important;overflow:hidden;}
[data-testid="stExpander"] summary{background:#EAF0F9 !important;border-radius:10px !important;}
[data-testid="stExpander"] summary *,[data-testid="stExpander"] summary {color:#17365D !important;-webkit-text-fill-color:#17365D !important;}
[data-testid="stSidebar"],[data-testid="stSidebar"] > div {background:#182B49 !important;}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span,[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {color:#EEF4FF !important;-webkit-text-fill-color:#EEF4FF !important;opacity:1 !important;}
[data-testid="stSidebar"] [role="radiogroup"] label {border-radius:10px;padding:7px 8px;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#29456C;}
[data-testid="stSidebar"] [data-testid="stExpander"] summary{background:#29456C !important;}
[data-testid="stSidebar"] [data-testid="stExpander"] summary * {color:#EEF4FF !important;-webkit-text-fill-color:#EEF4FF !important;}
[data-testid="stSidebar"] [data-testid="stExpander"] {border-color:#436087 !important;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] * {color:#EEF4FF !important;}
[data-testid="stFileUploader"] button {color:#17365D !important;background:#FFF !important;}
[data-testid="stDataFrame"],[data-testid="stDataEditor"] {background:#FFF !important;border:1px solid #DCE5F0;border-radius:13px;overflow:hidden;}
hr{border-color:#DFE7F2 !important;}
@media(max-width:720px){.hero{padding:22px 20px;}.hero h2{font-size:1.42rem;}.block-container{padding:1rem .8rem 3rem;}}


/* V7.7 contrast fixes; style across form controls and menus. */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] [role="combobox"],
[data-testid="stSelectbox"] div[data-baseweb="select"] [role="combobox"] * {
  background-color:#FFFFFF !important;color:#162D4C !important;
  -webkit-text-fill-color:#162D4C !important;opacity:1 !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] svg {fill:#315B90 !important;}
[data-baseweb="popover"],[data-baseweb="menu"],[role="listbox"] {
  background:#FFFFFF !important;color:#162D4C !important;
}
[data-baseweb="popover"] [role="option"],[data-baseweb="popover"] [role="option"] *,
[role="listbox"] [role="option"],[role="listbox"] [role="option"] * {
  color:#162D4C !important;-webkit-text-fill-color:#162D4C !important;
}
[data-testid="stDateInput"] input,[data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] button,[data-testid="stFileUploader"] section {
  background:#FFFFFF !important;color:#162D4C !important;
  -webkit-text-fill-color:#162D4C !important;
}
[data-testid="stNumberInput"] button svg,[data-testid="stDateInput"] svg {color:#315B90 !important;fill:#315B90 !important;}
[data-testid="stDataFrame"],[data-testid="stDataEditor"] {background:#FFF !important;color:#162D4C !important;}
[data-testid="stTable"] table {background:#FFF !important;border-collapse:collapse;width:100%;font-size:.92rem;}
[data-testid="stTable"] th {background:#EEF3FA !important;color:#1C3554 !important;text-align:left;}
[data-testid="stTable"] td {background:#FFF !important;color:#1C3554 !important;border-bottom:1px solid #E5EBF4;}
[data-testid="stTable"] tr:hover td {background:#F7F9FD !important;}
[data-testid="stCaptionContainer"] p {color:#526781 !important;}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {color:#F1F5FC !important;}


/* V7.8: consistent light controls. Apply to the component shell, not only the input. */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stDateInput"] div[data-baseweb="input"],
[data-testid="stNumberInput"] div[data-baseweb="input"],
[data-testid="stNumberInput"] [data-testid="stNumberInputContainer"],
[data-testid="stFileUploader"] section {
  background-color:#FFFFFF !important; border-color:#C4D2E5 !important;
  color:#182C44 !important;
}
[data-testid="stNumberInput"] button {background:#F1F5FA !important;color:#1D416A !important;border-color:#DCE5F0 !important;}
[data-testid="stSelectbox"] div[data-baseweb="select"] [role="combobox"] *,
[data-testid="stSelectbox"] div[data-baseweb="select"] span,
[data-testid="stDateInput"] input {color:#182C44 !important;-webkit-text-fill-color:#182C44 !important;}
[data-testid="stTable"] table,[data-testid="stTable"] th,[data-testid="stTable"] td{background-color:#FFFFFF !important;color:#182C44 !important;}


/* V7.9: readable light controls throughout the main app, including nested BaseWeb shells. */
.stApp [data-testid="stSelectbox"], .stApp [data-testid="stDateInput"] { color-scheme:light !important; }
.stApp [data-testid="stSelectbox"] [data-baseweb="select"],
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
.stApp [data-testid="stSelectbox"] [role="combobox"],
.stApp [data-testid="stSelectbox"] [data-baseweb="input"],
.stApp [data-testid="stDateInput"] [data-baseweb="input"],
.stApp [data-testid="stDateInput"] [data-baseweb="input"] > div,
.stApp [data-testid="stDateInput"] input,
.stApp [data-testid="stTextInput"] input {
  background:#FFFFFF !important; background-color:#FFFFFF !important;
  color:#142D4A !important;-webkit-text-fill-color:#142D4A !important;
  border-color:#BFCFE2 !important; opacity:1 !important;
}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] *,
.stApp [data-testid="stSelectbox"] [role="combobox"] *,
.stApp [data-testid="stSelectbox"] [role="combobox"] input,
.stApp [data-testid="stDateInput"] input,
.stApp [data-testid="stDateInput"] button,
.stApp [data-testid="stDateInput"] button * {
  color:#142D4A !important;-webkit-text-fill-color:#142D4A !important;opacity:1 !important;
}
.stApp [data-testid="stSelectbox"] svg,
.stApp [data-testid="stDateInput"] svg {color:#295DA5 !important;fill:#295DA5 !important;}
.stApp [data-testid="stSelectbox"] :focus-within,
.stApp [data-testid="stDateInput"] :focus-within {border-color:#477FCC !important;}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] [role="option"] *,[role="listbox"] [role="option"] {
 background-color:#FFFFFF !important;color:#142D4A !important;
 -webkit-text-fill-color:#142D4A !important;
}
[data-baseweb="popover"] [role="option"]:hover,
[role="listbox"] [role="option"]:hover {background-color:#EAF1FC !important;}


/* Version 7.13.2: calendar and upload/tooltip contrast */
[data-testid="stFileUploaderFile"] *, [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] * {color:#F7FAFF !important;-webkit-text-fill-color:#F7FAFF !important;}
[data-testid="stFileUploaderFile"] {background:#263750 !important;border-radius:9px !important;}
[data-testid="stTooltipContent"],div[role="tooltip"],div[role="tooltip"] * {background:#FFFFFF !important;color:#142D4A !important;-webkit-text-fill-color:#142D4A !important;}
.study-cal-event{background:#E1ECFB;border-left:3px solid #3569AA;border-radius:6px;padding:5px;margin:3px 0; font-size:11px;color:#12365D;overflow-wrap:anywhere;}
.study-cal-event.is-done{background:#DAF3E5;border-left-color:#23825A;color:#20543A;}
.study-cal-empty{min-height:36px;}
/* Version 7.13.2 uploader contrast hotfix: render uploaded file chip in light mode. */
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"],
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] > div,
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] > div > div {
  background-color:#EEF4FB !important;
  color:#172E54 !important;
  color-scheme:light !important;
  border-radius:9px !important;
}
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] span,
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] p,
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] small,
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] [data-testid="stMarkdownContainer"] *,
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] [data-testid="stFileUploaderFileName"],
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] [data-testid="stFileUploaderFileSize"] {
  color:#172E54 !important;
  -webkit-text-fill-color:#172E54 !important;
  opacity:1 !important;
}
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] svg {
  color:#285A98 !important;
  fill:currentColor !important;
}
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] button {
  background-color:#FFFFFF !important;
  border-radius:50% !important;
  color:#172E54 !important;
}

/* Version 7.13.3: force readable file details on the actual dark file chip. */
.stApp [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] :is(span,p,small,div) {
  color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important;
}
/* Explicit selected-PDF label below the widget remains readable even if
   Streamlit changes its internal chip markup. */
/* Version 7.13: dialog controls, premium sidebar, accessible contrast */
[data-testid="stDialog"] [role="dialog"], div[role="dialog"] {
  background:#FFFFFF !important; color:#182C44 !important; color-scheme:light !important;
  border-radius:18px !important;
}
[data-testid="stDialog"] [role="dialog"] *, div[role="dialog"] [data-testid="stMarkdownContainer"] *,
 div[role="dialog"] p,div[role="dialog"] h2,div[role="dialog"] h3 {
  color:#182C44 !important; -webkit-text-fill-color:#182C44 !important;
}
[data-testid="stDialog"] button[kind="primary"],div[role="dialog"] button[kind="primary"] {
  background:#B42318 !important; border-color:#B42318 !important; color:#FFFFFF !important;
}
[data-testid="stDialog"] button[kind="primary"] *,div[role="dialog"] button[kind="primary"] * {
  color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important;
}
[data-testid="stSidebar"] {background:linear-gradient(165deg,#14243F,#1C355B) !important;}
[data-testid="stSidebar"] [role="radiogroup"] label {
  border-radius:12px !important; margin:4px 0; padding:11px 13px !important;
  border:1px solid transparent; transition:background .12s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background:#2B5187 !important; border-color:#5078AE !important;
  box-shadow:inset 3px 0 #9BC6FF;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#294872 !important;}
[data-testid="stSidebar"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p {font-weight:600 !important;}
[data-testid="stSidebar"] .nav-section {font-size:11px;letter-spacing:1.7px;color:#9EBCDF !important;
 padding:15px 2px 7px;font-weight:800;}
[data-testid="stSidebar"] .nav-footer {background:#294872;border-radius:12px;padding:14px;
 color:#D6E8FF;font-size:13px;font-weight:600;}

</style>
""", unsafe_allow_html=True)

# ---------- TASK DATA ----------

def load_tasks():
    rows = get_assignments()

    return [
        {
            "id": row[0],
            "name": row[1],
            "course": row[2],
            "due": date.fromisoformat(row[3]) if row[3] else None,
            "priority": row[4],
            "completed": bool(row[5]),
            "weight": row[6],
            "hours": row[7],
            "confidence": row[8],
        }
        for row in rows
    ]


def study_experiment(records):
    # Compare only comparable planned blocks, not all session lengths pooled.
    long_blocks = [s for s in records if int(s['planned_minutes']) >= 45]
    if len(long_blocks) < 3:
        return None
    recent = long_blocks[:3]  # Returned newest-first by the database.
    mean_fraction = sum(min(max(int(s['elapsed_seconds']), 0) / (60 * int(s['planned_minutes'])), 1.0)
                        for s in recent) / len(recent)
    if mean_fraction >= 0.75:
        return None
    # Recommend one explicit test, not a permanent automatic adjustment.
    typical = round(sum(int(s['planned_minutes']) for s in recent) / 3)
    suggested = 25 if typical >= 45 else 15
    return {'suggested': suggested, 'baseline': recent, 'fraction': mean_fraction,
            'typical': typical}



def evaluate_real_adaptation(records):
    """Evaluate actual focus logs. Never writes data or treats simulations as real.

    Baseline: three most recent long blocks, in session-ID order.
    Follow-up: the first three 25-minute blocks recorded AFTER the latest baseline.
    This is an observational comparison, not proof of causation.
    """
    baseline = study_experiment(records)
    if baseline is None:
        return {'status': 'baseline_pending', 'baseline': None}
    last_long_id = max(int(s['id']) for s in baseline['baseline'])
    after = sorted(
        (s for s in records if int(s['id']) > last_long_id
         and int(s['planned_minutes']) == baseline['suggested']),
        key=lambda s: int(s['id']),
    )
    if len(after) < 3:
        return {'status': 'followup_pending', 'baseline': baseline,
                'followup_count': len(after)}
    followup = after[:3]
    original = baseline['baseline']
    def measures(rows):
        actual = sum(max(0, int(s['elapsed_seconds'])) for s in rows) / 60
        goals = sum(int(s['elapsed_seconds']) >= 60 * int(s['planned_minutes']) for s in rows)
        return actual, goals
    base_minutes, base_goals = measures(original)
    test_minutes, test_goals = measures(followup)
    improvement = (test_goals - base_goals) / 3
    improved = (improvement >= 0.20 and test_minutes >= 0.80 * base_minutes)
    return {'status': 'evaluated', 'baseline': baseline,
            'baseline_minutes': base_minutes, 'test_minutes': test_minutes,
            'baseline_goals': base_goals, 'test_goals': test_goals,
            'keep': improved, 'followup': followup}

tasks = load_tasks()
date_labels = get_date_labels()


# Called by Streamlit BEFORE widgets are reconstructed on the next run.
# This avoids modifying an already-created navigation radio widget.
def open_calendar_focus(assignment_id, duration_hours, study_session_id=None):
    if get_active_focus() is None:
        minutes = max(15, min(120, round(float(duration_hours) * 60)))
        try:
            start_focus(assignment_id, minutes, datetime.now(timezone.utc).isoformat(), study_session_id)
        except ValueError:
            # Another session may already exist; Focus Mode will display it.
            pass
    st.session_state["main_navigation"] = "Focus Mode"


# ---------- NAVIGATION ----------
st.sidebar.markdown("## 🎓 SyllabusSense")
st.sidebar.caption("Plan smarter. Make progress.")
main_pages = ["Syllabus Upload", "Dashboard", "My Courses", "Study Planner", "Focus Mode"]
if not tasks and not is_onboarded():
    main_pages.insert(0, "Welcome")
show_simulation = st.session_state.get("show_dev_simulation", False)
if show_simulation:
    main_pages.append("Simulation Lab")
if st.session_state.get("show_voice_input_test", False):
    main_pages.append("Voice Input Test")
if st.session_state.get("main_navigation") not in main_pages:
    st.session_state["main_navigation"] = "Welcome" if "Welcome" in main_pages else "Dashboard"
sidebar_icons = {"Welcome": "✨", "Dashboard": "▦", "My Courses": "▤", "Syllabus Upload": "↥", "Study Planner": "▦", "Focus Mode": "◷", "Simulation Lab": "⚙", "Voice Input Test": "🎙"}
st.sidebar.markdown("<div class='nav-section'>WORKSPACE</div>", unsafe_allow_html=True)
page = st.sidebar.radio("Navigate", main_pages, key="main_navigation",
                        format_func=lambda name: f"{sidebar_icons.get(name, '•')}   {name}", label_visibility="collapsed")
with st.sidebar.expander("Developer tools", expanded=False):
    st.checkbox("Show Simulation Lab", key="show_dev_simulation", help="Fictional experiments for testing only.")
    st.checkbox("Show Voice Input Test", key="show_voice_input_test", help="Test browser microphone without a syllabus or Gemini API requests.")
st.sidebar.divider()
st.sidebar.markdown("<div class='nav-footer'>✦ &nbsp; One study session at a time.</div>", unsafe_allow_html=True)
st.sidebar.caption("Version 7.13.3 · Local, private study data.")

def enter_from_welcome(destination):
    mark_onboarded()
    st.session_state["main_navigation"] = destination

if page == "Voice Input Test":
    st.markdown('<div class="hero"><h2>Voice Input Test</h2><p>Check microphone input without uploading a syllabus.</p></div>', unsafe_allow_html=True)
    st.info("This test does not call Gemini or use your Gemini API quota. Browser speech recognition may still require your browser's own online service.")
    st.subheader("1. Browser dictation")
    st.caption("Click Speak clues and say a sentence. If it works, the words will appear below. If it does nothing, the browser may be blocking microphone access inside an embedded component.")
    voice_result = voice_clues(key="developer_voice_test", default=None)
    if isinstance(voice_result, dict) and voice_result.get("text"):
        if voice_result.get("nonce") != st.session_state.get("developer_voice_nonce"):
            st.session_state["developer_voice_nonce"] = voice_result.get("nonce")
            st.session_state["developer_voice_text"] = (st.session_state.get("developer_voice_text", "") + " " + voice_result["text"]).strip()[:2000]
    st.text_area("Dictated words (editable)", key="developer_voice_text", height=110,
                 help="You can also type here. This test will not submit your text to AI.")
    st.divider()
    st.subheader("2. Microphone recording (no AI)")
    st.caption("This separate recorder tests microphone access without sending audio to Gemini. It will play back your recording but cannot transcribe it without an additional transcription service.")
    test_recording = st.audio_input("Record a short audio sample", key="developer_voice_audio")
    if test_recording is not None:
        st.success("Microphone recording captured. Play it below to verify audio.")
        st.audio(test_recording)
    st.caption("Recording and playback do not call Gemini. The audio is held temporarily in this Streamlit session, not saved to your assignments database.")
    st.markdown("#### Optional: Transcribe the recording with Gemini")
    st.caption("Only clicking the button below sends this audio to Google Gemini for transcription. Google may enforce API quotas. You can use the recorder and type your clues even when Gemini is unavailable.")
    if st.button("Transcribe my recording with Gemini", key="developer_voice_transcribe", disabled=test_recording is None):
        try:
            from gemini_voice_fallback import transcribe_audio
            with st.spinner("Transcribing your audio..."):
                transcript = transcribe_audio(test_recording.getvalue(), st.secrets["GEMINI_API_KEY"])
            st.session_state["developer_voice_pending"] = transcript
            st.rerun()
        except Exception as exc:
            st.error(f"Transcription unavailable: {str(exc)[:260]}")
    pending_voice = st.session_state.pop("developer_voice_pending", None)
    if pending_voice:
        prior_voice = st.session_state.get("developer_transcribed_text", "")
        st.session_state["developer_transcribed_text"] = (prior_voice + " " + pending_voice).strip()[:2000]
    st.text_area("Gemini transcription (editable)", key="developer_transcribed_text", height=110,
                 help="Review the text before copying it into your actual syllabus clues. Nothing here triggers date suggestions.")
    st.caption("This test never saves the transcript to the database or submits it for date suggestions.")

if page == "Welcome":
    st.markdown('<div class="hero"><h2>Welcome to SyllabusSense</h2><p>Your semester, made simpler.</p></div>', unsafe_allow_html=True)
    st.title("Get started your way")
    st.write("Upload a syllabus to organize assignments automatically, or explore the app without uploading anything.")
    first, second = st.columns(2, gap="medium")
    with first:
        with st.container(border=True):
            st.subheader("Upload a syllabus")
            st.write("Extract deadlines, check AI suggestions, and review before saving.")
            st.button("Upload my syllabus", type="primary", use_container_width=True,
                      on_click=enter_from_welcome, args=("Syllabus Upload",))
    with second:
        with st.container(border=True):
            st.subheader("Explore first")
            st.write("Browse the dashboard and add assignments whenever you're ready.")
            st.button("Explore SyllabusSense", use_container_width=True,
                      on_click=enter_from_welcome, args=("Dashboard",))
    st.caption("No syllabus required. You can upload one later.")

if page == "Dashboard":
    # ---------- DASHBOARD ----------
    st.markdown("""
    <div class="hero">
        <h2>Your semester, under control. 🎓</h2>
        <p>Upload a syllabus, capture the deadlines, and plan with confidence.</p>
    </div>
    """, unsafe_allow_html=True)

    st.title("Overview")
    st.caption(f"Today · {date.today().strftime('%A, %B %d')}")

    # ---------- METRICS ----------
    completed = sum(task["completed"] for task in tasks)
    pending = len(tasks) - completed
    overdue = sum(
        not task["completed"] and task["due"] is not None and task["due"] < date.today()
        for task in tasks
    )

    col1, col2, col3 = st.columns(3)

    def metric_card(label, value, background, border, text_color):
        st.markdown(
            f"""
            <div style="
        background-color: {background};
        border: 1px solid {border};
        border-radius: 16px;
        padding: 22px;
        min-height: 110px;
        box-sizing: border-box;
    ">
                <div style="
                    color: {text_color};
                    font-size: 14px;
                    font-weight: 500;
                ">
                    {label}
                </div>
                <div style="
                    color: {text_color};
                    font-size: 32px;
                    font-weight: 700;
                    margin-top: 8px;
                ">
                    {value}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col1:
        metric_card(
            "Tasks completed",
            completed,
            "#E0ECFF",
            "#B8D0FF",
            "#17365D"
        )

    with col2:
        metric_card(
            "Tasks remaining",
            pending,
            "#DDF7E8",
            "#A9E8C2",
            "#14532D"
        )

    with col3:
        metric_card(
            "Overdue tasks",
            overdue,
            "#FFF0D9",
            "#FFD59A",
            "#7C2D12"
        )

    st.divider()

    # ---------- UPCOMING DEADLINES ----------
    st.subheader("Upcoming deadlines")
    upcoming = sorted(
        (task for task in tasks if not task["completed"] and task["due"] is not None and task["due"] >= date.today()),
        key=lambda t: (t["due"], {"High": 0, "Medium": 1, "Low": 2}.get(t["priority"], 3)),
    )[:5]
    if upcoming:
        for task in upcoming:
            days_left = (task["due"] - date.today()).days
            when = "Due today" if days_left == 0 else "Due tomorrow" if days_left == 1 else f"In {days_left} days"
            left, right = st.columns([4, 1])
            with left:
                st.markdown(f"**{task['name']}**")
                st.caption(f"{task['course']} · {task['due'].strftime('%b %d, %Y') if task['due'] else 'Not announced'} · {task['priority']} priority")
            with right:
                st.markdown(f"**{when}**")
    else:
        st.info("No upcoming unfinished deadlines. Add an assignment or upload a syllabus to get started.")

    st.divider()

    # ---------- ASSIGNMENT CARDS ----------
    st.subheader("Your assignments")
    st.caption("Mark tasks complete, filter courses, and see what needs attention.")

    # Every checkbox uses the assignment ID. Updating one checkbox updates only that record.
    def change_completed(assignment_id, checkbox_key):
        update_assignment_status(assignment_id, st.session_state[checkbox_key])

    if tasks:
        courses = sorted({task["course"] for task in tasks}, key=str.casefold)
        c1, c2 = st.columns([2, 1])
        with c1:
            chosen_course = st.selectbox("Course", ["All courses", *courses], key="assignment_course_filter")
        with c2:
            chosen_status = st.selectbox("Status", ["All", "Remaining", "Completed", "Overdue"], key="assignment_status_filter")

        def shown(task):
            if chosen_course != "All courses" and task["course"] != chosen_course:
                return False
            if chosen_status == "Completed" and not task["completed"]:
                return False
            if chosen_status == "Remaining" and task["completed"]:
                return False
            if chosen_status == "Overdue" and (task["completed"] or task["due"] is None or task["due"] >= date.today()):
                return False
            return True

        visible_tasks = sorted(
            (task for task in tasks if shown(task)),
            key=lambda t: (t["completed"], t["due"] is None, t["due"] or date.max, {"High": 0, "Medium": 1, "Low": 2}.get(t["priority"], 3)),
        )
        if visible_tasks:
            for task in visible_tasks:
                due_days = (task["due"] - date.today()).days if task["due"] else None
                status = "Completed" if task["completed"] else "Date not announced" if due_days is None else "Overdue" if due_days < 0 else "Due today" if due_days == 0 else "Upcoming"
                weight_label = f"{task['weight']:g}% of grade" if task["weight"] is not None else "Weight unknown"
                with st.container(border=True):
                    tick, description, detail = st.columns([0.6, 5, 2.1], vertical_alignment="center")
                    with tick:
                        # State for each task is independent; callbacks avoid bulk edits.
                        key = f"completed_task_{task['id']}"
                        st.checkbox("Done", value=task["completed"], key=key,
                                    on_change=change_completed, args=(task["id"], key),
                                    label_visibility="collapsed")
                    with description:
                        st.markdown(f"**{html.escape(task['name'])}**")
                        status_note = f" · {date_labels[task['id']]} date" if task['id'] in date_labels else ""
                        st.caption(f"{task['course']} · {task['priority']} priority · {weight_label}{status_note}")
                    with detail:
                        st.markdown(f"**{task['due'].strftime('%b %d, %Y') if task['due'] else 'Not announced'}**")
                        st.caption(status)
            st.caption(f"Showing {len(visible_tasks)} of {len(tasks)} saved assignments.")
        else:
            st.info("No assignments match these filters.")
    else:
        st.info("No assignments saved yet.")


# ---------- COURSE & SYLLABUS MANAGEMENT ----------
@st.dialog("Confirm deletion")
def confirm_removal(kind, identity, label):
    st.warning(f"Delete **{label}** and its associated study records? This cannot be undone.")
    st.caption("This only removes the selected item and its linked data.")
    left, right = st.columns(2)
    with left:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with right:
        if st.button("Yes, delete", type="primary", use_container_width=True):
            try:
                if kind == "course":
                    delete_course(identity)
                elif kind == "assignment":
                    delete_assignment(identity)
                elif kind == "syllabus":
                    delete_syllabus(identity)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

if page == "My Courses":
    st.markdown('<div class="hero"><h2>My Courses</h2><p>Organize your classes and clean up your study workspace.</p></div>', unsafe_allow_html=True)
    st.title("Courses & syllabi")
    st.caption("Deleting a course removes its assignments and linked calendar / focus records. Back up your database first.")
    course_names = list_courses()
    if course_names:
        st.subheader("Your courses")
        chosen_course = st.selectbox("Choose a course", course_names, key="manage_course_picker")
        course_tasks = [t for t in tasks if t['course'] == chosen_course]
        with st.container(border=True):
            st.markdown(f"#### {html.escape(chosen_course)}")
            st.caption(f"{len(course_tasks)} saved assignments")
            with st.expander("Rename course"):
                with st.form("course_rename_form"):
                    new_course = st.text_input("Course name", value=chosen_course)
                    rename_it = st.form_submit_button("Save new name", type="primary")
                if rename_it:
                    try:
                        rename_course(chosen_course, new_course)
                        st.success("Course renamed")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            if st.button("Delete this course", key="course_delete", use_container_width=False):
                confirm_removal("course", chosen_course, chosen_course)
        st.subheader("Assignments in this course")
        for t in sorted(course_tasks, key=lambda t: (t['due'] is None, t['due'] or date.max)):
            with st.container(border=True):
                detail, action = st.columns([4,1], vertical_alignment="center")
                with detail:
                    st.markdown(f"**{html.escape(t['name'])}**")
                    st.caption(f"Due {t['due'].strftime('%b %d, %Y') if t['due'] else 'Not announced'} · {t['priority']} priority")
                with action:
                    if st.button("Delete", key=f"delete_task_{t['id']}", use_container_width=True):
                        confirm_removal("assignment", t['id'], t['name'])
                with st.expander("Edit deadline / planning target"):
                    with st.form(f"edit_due_{t['id']}"):
                        new_due = st.text_input("Due date (YYYY-MM-DD; blank if not announced)",
                                                value=t['due'].isoformat() if t['due'] else "")
                        choices = ["Not provided", "Confirmed", "Inferred", "Planning target"]
                        current_label = date_labels.get(t['id'], "Confirmed" if t['due'] else "Not provided")
                        new_label = st.selectbox("Date status", choices,
                                                 index=choices.index(current_label) if current_label in choices else 0)
                        update_due = st.form_submit_button("Save deadline", type="primary")
                    if update_due:
                        try:
                            update_assignment_date(t['id'], new_due, new_label)
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
    else:
        st.info("You have no courses yet. Upload a syllabus or add an assignment to get started.")

    st.divider()
    st.subheader("Imported syllabi")
    st.caption("New syllabus imports are tracked from Version 7.12 onward. Older PDFs weren't linked to assignments; delete their courses above instead.")
    uploads = list_syllabi()
    if uploads:
        for sid, filename, course, imported, count in uploads:
            with st.container(border=True):
                detail, action = st.columns([4,1], vertical_alignment="center")
                with detail:
                    st.markdown(f"**{html.escape(filename)}**")
                    st.caption(f"{course} · {count} linked assignments · Imported {imported[:10]}")
                with action:
                    if st.button("Delete", key=f"delete_pdf_{sid}", use_container_width=True):
                        confirm_removal("syllabus", sid, filename)
    else:
        st.info("No tracked syllabus imports yet. Existing coursework is still manageable under Your courses.")


if page == "Study Planner":
    # ---------- PLANNER ----------
    st.markdown('<div class="hero"><h2>Your study plan</h2><p>Know what matters. Make time for it.</p></div>', unsafe_allow_html=True)
    # Today's plan is first: no scrolling through settings to begin studying.
    st.markdown("### Today's Study Goals")
    todays_sessions = get_sessions(date.today(), date.today())
    task_by_id = {t['id']: t for t in tasks}
    todays_sessions = [s for s in todays_sessions if s['assignment_id'] in task_by_id]
    finished_today = sum(bool(s['completed']) for s in todays_sessions)
    if todays_sessions:
        st.caption(f"{date.today().strftime('%A, %B %d')} · {finished_today} of {len(todays_sessions)} study blocks done")
        st.progress(finished_today / len(todays_sessions))
        for sess in todays_sessions:
            task = task_by_id[sess['assignment_id']]
            with st.container(border=True):
                details, controls = st.columns([3.5, 1.5], vertical_alignment="center")
                with details:
                    st.markdown(f"**{html.escape(task['name'])}**")
                    status_note = f" · {date_labels[task['id']]} date" if task['id'] in date_labels else ""
                    st.caption(f"{task['course']} · {round(float(sess['hours'])*60)} minutes planned · Due {task['due'].strftime('%b %d') if task['due'] else 'Not announced'}{status_note}")
                with controls:
                    completed_key = f"today_goal_done_{sess['id']}"
                    done = st.checkbox("Done", value=bool(sess['completed']), key=completed_key)
                    if done != bool(sess['completed']):
                        set_session_completed(sess['id'], done)
                        st.rerun()
                    if not sess['completed']:
                        st.button(
                            "Open running timer" if get_active_focus() is not None else "Start studying",
                            key=f"today_start_{sess['id']}",
                            type="primary", use_container_width=True,
                            on_click=open_calendar_focus,
                            args=(sess['assignment_id'], sess['hours'], sess['id']),
                        )
        st.caption("Finishing a timer started from this plan marks that study block done, but never automatically completes the assignment.")
    else:
        st.info("Nothing scheduled for today. Generate a study plan below to get started.")
    st.divider()
    st.subheader("Smart Study Planner")
    st.caption("Personalized, rule-based priorities using real deadlines, grading weights and your estimates. This version does not use Gemini to generate study recommendations.")
    active = [task for task in tasks if not task["completed"] and task["due"] is not None]
    undated_active = [task for task in tasks if not task["completed"] and task["due"] is None]
    if undated_active:
        st.info(f"{len(undated_active)} assignment(s) have no announced dates. They are saved, but won't enter deadline-based scheduling until you assign a confirmed date or planning target.")


    def study_priority(task):
        days = (task["due"] - date.today()).days
        urgency = 40 if days < 0 else 38 if days == 0 else 35 if days <= 2 else 28 if days <= 7 else 18 if days <= 14 else 8
        weight_score = min(float(task["weight"]), 40) / 40 * 25 if task["weight"] is not None else 12.5
        confidence_score = (5 - task["confidence"]) / 4 * 20 if task["confidence"] is not None else 10
        hours_score = min(float(task["hours"]), 10) / 10 * 10 if task["hours"] is not None else 5
        priority_score = {"High": 5, "Medium": 3, "Low": 1}.get(task["priority"], 3)
        return round(urgency + weight_score + confidence_score + hours_score + priority_score, 1)


    if not active:
        st.info("No unfinished assignments. Add a task or uncheck a completed task to make a study plan.")
    else:
        with st.expander("Personalize your study priorities", expanded=False):
            st.write("Enter estimated study hours and confidence (1 = not confident, 5 = very confident). Leave them blank if you don't know yet.")
            with st.form("study_details_form"):
                revisions = []
                for task in active:
                    st.markdown(f"**{html.escape(task['name'])}**")
                    a, b = st.columns(2)
                    with a:
                        hrs_str = st.text_input(
                            "Estimated hours (optional)",
                            value="" if task['hours'] is None else str(task['hours']),
                            key=f"hours_{task['id']}", placeholder="e.g. 2.5")
                    with b:
                        conf_label = st.selectbox(
                            "Confidence", ["Not set", "1", "2", "3", "4", "5"],
                            index=0 if task['confidence'] is None else int(task['confidence']),
                            key=f"confidence_{task['id']}")
                    revisions.append((task, hrs_str, conf_label))
                save_details = st.form_submit_button("Save study preferences", type="primary")
            if save_details:
                errors = []
                valid = []
                for task, raw_hrs, raw_conf in revisions:
                    try:
                        hours = float(raw_hrs) if raw_hrs.strip() else None
                    except ValueError:
                        errors.append(f"{task['name']}: enter a number for study hours")
                        continue
                    if hours is not None and not 0.5 <= hours <= 40:
                        errors.append(f"{task['name']}: study hours must be 0.5–40")
                    confidence = None if raw_conf == "Not set" else int(raw_conf)
                    valid.append((task['id'], hours, confidence))
                if errors:
                    for error in errors: st.error(error)
                else:
                    for task_id, hours, confidence in valid:
                        update_study_details(task_id, hours, confidence)
                    st.success("Study preferences saved.")
                    st.rerun()

        ranked = sorted(active, key=lambda t: (-study_priority(t), t["due"]))
        st.markdown("#### What to focus on first")
        for index, task in enumerate(ranked[:5], start=1):
            days = (task["due"] - date.today()).days
            timing = "overdue" if days < 0 else "due today" if days == 0 else f"due in {days} day{'s' if days != 1 else ''}"
            with st.container(border=True):
                left, right = st.columns([5, 1], vertical_alignment="center")
                with left:
                    st.markdown(f"**{index}. {html.escape(task['name'])}**")
                    st.caption(f"{task['course']} · {timing} · "
                               f"{'weight not supplied' if task['weight'] is None else str(task['weight']) + '% grade weight'} · "
                               f"{'study hours unknown' if task['hours'] is None else str(task['hours']) + 'h estimated'} · "
                               f"{'confidence unknown' if task['confidence'] is None else str(task['confidence']) + '/5 confidence'}")
                with right:
                    st.metric("Priority score", f"{study_priority(task):.1f}")
        if len(ranked) > 5:
            st.caption(f"Showing your 5 highest-priority tasks out of {len(ranked)} unfinished tasks.")
        with st.expander("How priorities are calculated"):
            st.write("The score is a planning estimate (not a predicted grade): deadline urgency up to 40 points; grading weight up to 25; low confidence up to 20; estimated hours up to 10; and the manually selected priority up to 5. Unknown weight, confidence, or hours receive neutral midpoint points—not zero. Overdue work ranks urgently but should be checked against the instructor's late policy. Ties are broken by earliest deadline.")
            st.caption("Scores update when you change estimates, mark tasks complete, or dates pass. This is an initial heuristic to test with students, not a proven optimization model.")

    with st.expander("+ Add an assignment manually"):
        with st.form("add_task_form", clear_on_submit=True):
            task_name = st.text_input("Assignment name", placeholder="e.g. Psychology Chapter 6 quiz")
            course = st.text_input("Course", placeholder="e.g. Psychology")
            left, right = st.columns(2)
            with left:
                due_date = st.date_input("Due date", value=date.today())
            with right:
                priority = st.selectbox("Priority", ["High", "Medium", "Low"])
            submitted = st.form_submit_button("Add assignment", type="primary", use_container_width=True)
        if submitted:
            if not task_name.strip():
                st.error("Please enter an assignment name.")
            elif not course.strip():
                st.error("Please enter a course name.")
            else:
                add_assignment(task_name.strip(), course.strip(), due_date.isoformat(), priority)
                register_course(course.strip())
                st.success("Assignment added!")
                st.rerun()


    # ---------- VERSION 6: WEEKLY PLAN + TODAY'S FOCUS ----------

    st.divider()
    st.subheader("Your weekly study plan")
    st.caption("Choose your available study hours, then generate a realistic seven-day plan. Study sessions are stored locally in SQLite.")
    week_start = date.today()  # Rolling seven-day planning window starting today
    week_end = week_start + timedelta(days=6)
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    saved_availability = get_availability()

    if st.session_state.pop("set_adaptive_block_on_rerun", False):
        st.session_state["preferred_study_block"] = 0.5

    with st.expander("My availability", expanded=False):
        st.write("How many hours can you study on each day? Enter 0 for unavailable days.")
        with st.form("availability_v6"):
            columns = st.columns(4)
            availability_inputs = {}
            for day_index in range(7):
                day_date = week_start + timedelta(days=day_index)
                weekday = day_date.weekday()
                with columns[day_index % 4]:
                    availability_inputs[weekday] = st.number_input(
                        f"{weekday_names[weekday]} · {day_date.strftime('%b %d')}",
                        min_value=0.0, max_value=16.0, value=float(saved_availability.get(weekday, 2.0 if weekday < 5 else 1.0)),
                        step=0.5, key=f"avail_{weekday}",
                    )
            session_duration = st.selectbox("Preferred study block", [0.5, 1.0, 1.5, 2.0], index=1,
                                            format_func=lambda hours: f"{int(hours * 60)} minutes", key="preferred_study_block")
            save_avail = st.form_submit_button("Save availability", type="primary")
        if save_avail:
            save_availability(availability_inputs)
            st.success("Availability saved. Click Generate / refresh plan below to apply it.")
            st.rerun()

    availability = get_availability()
    if not availability:
        st.info("Save your study availability above to get started.")
    else:
        capacity_by_day = [availability.get((week_start + timedelta(days=i)).weekday(), 0.0) for i in range(7)]
        current_sessions = get_sessions(week_start, week_end)
        finished = [session for session in current_sessions if session['completed']]
        planned, shortages, assumed_ids = generate_week(tasks, capacity_by_day, week_start, study_priority,
                                                            session_length=session_duration, previously_completed=finished)
        total_available = sum(capacity_by_day)
        summary_left, summary_mid, summary_right = st.columns(3)
        summary_left.metric("Available this week", f"{total_available:g}h")
        summary_mid.metric("Sessions completed", len(finished))
        summary_right.metric("Estimated hours not scheduled", f"{sum(shortages.values()):g}h")
        if assumed_ids:
            st.info(f"For {len(assumed_ids)} assignment(s) without estimates, the planner assumes 3 hours each. Set real estimates in Smart Study Planner for better results.")
        if shortages:
            st.warning(f"{sum(shortages.values()):g} study hours are not scheduled across {len(shortages)} assignments. Review your availability or assignment estimates.")
            with st.expander(f"View {len(shortages)} unscheduled assignments"):
                task_lookup = {t['id']: t for t in tasks}
                for tid, hours in shortages.items():
                    st.caption(f"{task_lookup[tid]['name']}: {hours:g}h not scheduled")
                st.caption("These can include hours intended for future weeks, not just work due this week. The planner doesn't schedule work on or after its due date.")
        # Version 7.3: explicit opt-in preview, using the same existing scheduler.
        # Do not adjust calendar merely because a Focus Mode timer was cut short.
        real_result = evaluate_real_adaptation(get_focus_history(limit=5000))
        focus_experiment = real_result.get('baseline') if real_result['status'] == 'evaluated' and real_result['keep'] else None
        st.markdown("#### Your Study Coach")
        st.caption("Optional change. Your study history is a starting clue, not proof of the best study length.")
        if focus_experiment is None:
            if real_result['status'] == 'evaluated':
                st.info("Your shorter-block trial did not meet both improvement checks. No change to your weekly calendar is recommended.")
            else:
                st.info("No plan change recommended yet. First record three longer focus sessions, then three shorter trial sessions. Your calendar stays unchanged.")
        else:
            candidate_block = 0.5  # 30-minute calendar block; closest supported to 25-minute focus test.
            st.info(
                f"Your recent longer Focus Mode sessions averaged {focus_experiment['fraction']:.0%} of their planned time. "
                "You can try 30-minute calendar blocks (a close match to the 25-minute focus experiment)."
            )
            if st.checkbox("Preview a 30-minute weekly plan", key="preview_adaptive_plan"):
                alternative, alternative_shortages, _ = generate_week(
                    tasks, capacity_by_day, week_start, study_priority,
                    session_length=candidate_block, previously_completed=finished,
                )
                current_unfinished = [s for s in current_sessions if not s['completed']]
                st.write(f"**Currently scheduled:** {len(current_unfinished)} unfinished blocks")
                st.write(f"**Proposed:** {len(alternative)} unfinished blocks at up to 30 minutes each")
                preview_rows = []
                by_id = {task['id']: task for task in tasks}
                for block in alternative:
                    preview_rows.append({
                        'Date': block['day'].strftime('%a %b %d'),
                        'Assignment': by_id[block['assignment_id']]['name'],
                        'Minutes': round(block['hours'] * 60),
                    })
                if preview_rows:
                    st.table(pd.DataFrame(preview_rows))
                else:
                    st.warning("No unfinished work can be scheduled in the available time before deadlines.")
                if alternative_shortages:
                    st.warning(f"{sum(alternative_shortages.values()):g} study hours remain unscheduled. The plan does not exceed availability or schedule on/after deadlines.")
                st.warning("Applying this will REPLACE your unfinished sessions in this seven-day window, including any manual moves. Completed sessions stay unchanged.")
                confirm_replace = st.checkbox("I understand unfinished sessions will be replaced", key="confirm_adaptive_replace")
                if st.button("Apply 30-minute plan", type="primary", disabled=not confirm_replace or not preview_rows, key="apply_adaptive_plan"):
                    replace_unfinished_sessions(week_start, week_end, alternative)
                    st.session_state['set_adaptive_block_on_rerun'] = True
                    st.success("Your new 30-minute plan has been saved.")
                    st.rerun()

        if st.button("Generate / refresh weekly plan", type="primary"):
            replace_unfinished_sessions(week_start, week_end, planned)
            st.rerun()

        current_sessions = get_sessions(week_start, week_end)
        task_lookup = {t['id']: t for t in tasks}
        valid_sessions = [s for s in current_sessions if s['assignment_id'] in task_lookup]
        st.markdown("#### Study Calendar")
        render_calendar(task_lookup, open_calendar_focus, get_active_focus() is not None)
        with st.expander("Adjust an individual study session"):
            adjustable = [s for s in valid_sessions if not s['completed']]
            if adjustable:
                options = {s['id']: f"{task_lookup[s['assignment_id']]['name']} · {s['day'].strftime('%a %b %d')} · {s['hours']:g}h" for s in adjustable}
                chosen_id = st.selectbox("Study session", list(options), format_func=lambda sid: options[sid])
                new_day = st.date_input("Move to", value=next(s['day'] for s in adjustable if s['id'] == chosen_id),
                                        min_value=week_start, max_value=week_end)
                if st.button("Move session"):
                    target = next(s for s in adjustable if s['id'] == chosen_id)
                    task = task_lookup[target['assignment_id']]
                    allocated = sum(s['hours'] for s in valid_sessions if s['day'] == new_day and s['id'] != chosen_id)
                    limit = availability.get(new_day.weekday(), 0.0)
                    if task['due'] is None or new_day >= task['due']:
                        st.error("Choose a date before this assignment is due.")
                    elif allocated + target['hours'] > limit + 0.0001:
                        st.error(f"That day only has {limit:g}h available, and this move would exceed it.")
                    else:
                        move_session(chosen_id, new_day)
                        st.rerun()
            else:
                st.caption("No unfinished sessions to move yet.")

 

if page == "Focus Mode":
    # ---------- FOCUS ----------
    st.markdown('<div class="hero"><h2>Time to focus</h2><p>One task at a time. Every minute counts.</p></div>', unsafe_allow_html=True)
    st.subheader("Your focus session")
    st.caption("Start a study session and track the time you actually spend. Timer sessions do not automatically mark assignments complete.")


    def focus_now():
        return datetime.now(timezone.utc).isoformat()


    history = get_focus_history(limit=5000)

    # Same recommendation function used in the Study Planner.
    experiment = study_experiment(history)

    focus_session = get_active_focus()
    if focus_session is None:
        focus_options = [t for t in tasks if not t["completed"]]
        if focus_options:
            with st.form("start_focus_form"):
                chosen_task = st.selectbox(
                    "What are you working on?", [t["id"] for t in focus_options],
                    format_func=lambda tid: next(f"{t['course']} — {t['name']}" for t in focus_options if t["id"] == tid))
                block_choices = [15, 25, 30, 45, 60, 90, 120]
                preferred = experiment['suggested'] if experiment else 30
                target_minutes = st.selectbox("Planned focus time", block_choices,
                                              index=block_choices.index(preferred),
                                              format_func=lambda n: f"{n} minutes")
                begin_focus = st.form_submit_button("Start focusing", type="primary")
            if begin_focus:
                try:
                    start_focus(chosen_task, target_minutes, focus_now())
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        else:
            st.info("Add an unfinished assignment to start a focus session.")
    else:
        task_name = next((f"{t['course']} — {t['name']}" for t in tasks if t['id'] == focus_session['assignment_id']), "Saved assignment")
        st.write(f"**Studying:** {html.escape(task_name)}")
        st.caption(f"Your goal: {focus_session['planned_minutes']} minutes. The timer keeps running while the app is closed until you pause or finish it.")

        @st.fragment(run_every="1s")
        def show_focus_clock():
            session = get_active_focus()
            if session is None:
                st.rerun()
                return
            elapsed = session['elapsed_seconds']
            if session['active_since']:
                elapsed += max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(session['active_since'])).total_seconds()))
            minutes, seconds = divmod(elapsed, 60)
            st.metric("Actual elapsed study time", f"{minutes:02d}:{seconds:02d}")
            st.progress(min(elapsed / (session['planned_minutes'] * 60), 1.0))
            if elapsed >= session['planned_minutes'] * 60:
                st.success("You reached your planned focus time. Finish when you're ready.")
            c1, c2 = st.columns(2)
            with c1:
                button_label = "Pause" if session['active_since'] else "Resume"
                if st.button(button_label, key="focus_pause_resume", use_container_width=True):
                    set_focus_running(session['id'], not bool(session['active_since']), focus_now())
                    st.rerun()
            with c2:
                if st.button("Finish & save", key="focus_finish", type="primary", use_container_width=True):
                    finish_focus(session['id'], focus_now())
                    st.session_state.pop('confirm_discard_focus_id', None)
                    st.rerun()
            if st.session_state.get('confirm_discard_focus_id') == session['id']:
                st.warning("Discard this session? Its recorded time will not count toward your study history or Study Coach.")
                yes, no = st.columns(2)
                with yes:
                    if st.button("Yes, discard session", key="focus_discard_confirm", use_container_width=True):
                        discard_active_focus(session['id'])
                        st.session_state.pop('confirm_discard_focus_id', None)
                        st.rerun()
                with no:
                    if st.button("Keep session", key="focus_discard_cancel", use_container_width=True):
                        st.session_state.pop('confirm_discard_focus_id', None)
                        st.rerun()
            else:
                if st.button("Discard session", key="focus_discard_open", use_container_width=True):
                    st.session_state['confirm_discard_focus_id'] = session['id']
                    st.rerun()
        show_focus_clock()

    if history:
        with st.expander("Recent focus sessions"):
            for item in history[:20]:
                studied = round(item['elapsed_seconds'] / 60, 1)
                left, right = st.columns([5, 1], vertical_alignment="center")
                with left:
                    st.write(f"**{html.escape(item['assignment_name'])}** — {studied:g} min studied / {item['planned_minutes']} min planned")
                with right:
                    if st.button("Delete", key=f"delete_saved_{item['id']}", use_container_width=True):
                        st.session_state['delete_saved_confirm_id'] = item['id']
                        st.rerun()
                if st.session_state.get('delete_saved_confirm_id') == item['id']:
                    st.warning("Permanently delete this saved focus record? Study Coach statistics will be recalculated.")
                    confirm, cancel = st.columns(2)
                    with confirm:
                        if st.button("Yes, delete record", key=f"delete_saved_yes_{item['id']}", type="primary"):
                            try:
                                delete_saved_focus(item['id'])
                                st.session_state.pop('delete_saved_confirm_id', None)
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))
                    with cancel:
                        if st.button("Cancel", key=f"delete_saved_no_{item['id']}"):
                            st.session_state.pop('delete_saved_confirm_id', None)
                            st.rerun()
            st.caption("Deleting a saved record cannot be undone. It does not change assignments or your calendar.")

    st.divider()
    st.subheader("Your Study Coach")
    real_result = evaluate_real_adaptation(history)
    if real_result['status'] == 'baseline_pending':
        st.info("Keep studying normally. After a few longer focus sessions, I can help you try a different session length.")
    elif real_result['status'] == 'followup_pending':
        st.info(f"Try a 25-minute focus session when it suits your work. You've recorded {real_result['followup_count']} of 3 sessions for this trial.")
    elif real_result['keep']:
        st.success("Shorter sessions seem promising in your recent records. You can preview a shorter weekly plan under Study Planner.")
    else:
        st.info("The shorter sessions haven't shown enough improvement. Keep your current plan for now.")
    st.caption("Your study plan won't change unless you choose to update it. These suggestions are based on time records, not grades or learning outcomes.")

    with st.expander("Detailed study insights (optional)", expanded=False):
        # Version 7.1: read-only analysis of recorded focus sessions.
        # A finished timer does not prove a planned calendar block was completed.
        st.divider()
        st.subheader("Study habits · Version 7.2")
        st.caption("Based on saved Focus Mode sessions. No automatic changes to your study plan.")
        if not history:
            st.info("Finish a focus session to start tracking your study habits.")
        else:
            count = len(history)
            planned_total = sum(int(s['planned_minutes']) for s in history)
            actual_total = sum(max(0, int(s['elapsed_seconds'])) for s in history) / 60
            reached = sum(int(s['elapsed_seconds']) >= int(s['planned_minutes']) * 60 for s in history)
            first, second, third = st.columns(3)
            first.metric("Sessions recorded", count)
            second.metric("Time studied", f"{actual_total:.1f} min")
            third.metric("Met time goal", f"{reached} of {count}")
            st.caption(f"You planned {planned_total:g} minutes across these sessions. The timer measures time, not understanding or task completion.")
            if count < 3:
                st.info("Keep tracking. At least 3 finished sessions are needed before showing an early pattern.")
            else:
                ratio = actual_total / planned_total if planned_total else 0
                if ratio < 0.5:
                    st.warning("Early pattern: recorded time is less than half of planned time. We can test shorter focus sessions later.")
                elif ratio < 0.9:
                    st.info("Early pattern: you often study less time than planned. More sessions will help us understand what works.")
                else:
                    st.success("Early pattern: recorded study time is close to or above planned time. Keep collecting data.")
                st.caption("This is a description of your records, not a prediction or a proven personalized recommendation.")
            st.markdown("#### Time by planned session length")
            session_groups = {}
            for session in history:
                length = int(session['planned_minutes'])
                bucket = session_groups.setdefault(length, {'sessions': 0, 'minutes': 0, 'goal_met': 0})
                bucket['sessions'] += 1
                bucket['minutes'] += max(0, int(session['elapsed_seconds'])) / 60
                bucket['goal_met'] += int(session['elapsed_seconds'] >= length * 60)
            summary = []
            for length in sorted(session_groups):
                bucket = session_groups[length]
                summary.append({
                    'Planned block': f"{length} min",
                    'Sessions': bucket['sessions'],
                    'Avg. studied (min)': round(bucket['minutes'] / bucket['sessions'], 1),
                    'Reached goal': f"{bucket['goal_met']}/{bucket['sessions']}",
                })
            st.table(pd.DataFrame(summary))
            st.caption("Shorter blocks may appear easier to finish simply because the goal is smaller. We'll compare actual minutes as well as goals reached.")

        st.divider()
        st.subheader("Adaptive study experiment · Version 7.2")
        st.caption("A small, optional experiment. SyllabusSense never changes your weekly calendar automatically.")
        if experiment is None:
            st.info("No adjustment suggested yet. To detect a repeated pattern, the app needs at least three finished focus sessions planned for 45 minutes or longer where study time is consistently below the goal.")
            st.caption("You can still choose any focus length. No need to create extra sessions just to reach a threshold.")
        else:
            st.warning(f"Your three most recent longer sessions reached an average of {experiment['fraction']:.0%} of their planned duration. This may be worth investigating—not proof that longer sessions are bad for you.")
            st.markdown(f"**Suggested experiment: try {experiment['suggested']}-minute focus blocks** for your next three genuine study sessions.")
            st.caption("Focus Mode preselects this length, but you can choose another. Your existing weekly schedule won't change.")
            shorter = [s for s in history if int(s['planned_minutes']) == experiment['suggested']]
            if len(shorter) >= 3:
                sample = shorter[:3]
                baseline = experiment['baseline']
                def stats(rows):
                    hit = sum(int(s['elapsed_seconds']) >= int(s['planned_minutes']) * 60 for s in rows)
                    minutes = sum(max(0, int(s['elapsed_seconds'])) for s in rows) / 60
                    return hit, minutes
                base_hits, base_minutes = stats(baseline)
                short_hits, short_minutes = stats(sample)
                st.markdown("#### Early comparison (three sessions each)")
                st.table(pd.DataFrame([
                    {'Session type': 'Longer blocks', 'Met goal': f'{base_hits}/3', 'Total minutes studied': round(base_minutes, 1)},
                    {'Session type': f"{experiment['suggested']}-minute blocks", 'Met goal': f'{short_hits}/3', 'Total minutes studied': round(short_minutes, 1)},
                ]))
                st.caption("This is an observational comparison, not a controlled experiment. Session difficulty, deadlines and motivation may differ. Meeting a shorter target more often does not prove better learning.")
            else:
                st.info(f"{len(shorter)} of 3 sessions at the suggested length are recorded so far. Keep studying normally; we'll display an early comparison once there are three.")



# ---------- VERSION 7.4: OFFLINE SIMULATION LAB ----------
# The simulator uses fictional numbers only. It does not open or change SQLite.
def simulate_adaptive_study(long_minutes, short_minutes, long_target=60, short_target=25):
    """Compare equal numbers of fictional sessions with transparent rules.

    Advisory rule: suggest short blocks if the baseline goal is often missed.
    Keep the change only when the goal-hit rate improves by >= 20 percentage
    points AND total actual study time stays at least 80% of baseline.
    This is a code demo, not evidence of effectiveness in students.
    """
    if not long_minutes or len(long_minutes) != len(short_minutes):
        raise ValueError("Both groups must contain the same nonzero number of sessions")
    if min(long_minutes + short_minutes) < 0:
        raise ValueError("Study times cannot be negative")
    n = len(long_minutes)
    before_rate = sum(m >= long_target for m in long_minutes) / n
    after_rate = sum(m >= short_target for m in short_minutes) / n
    before_total = sum(long_minutes)
    after_total = sum(short_minutes)
    baseline_problem = before_rate < 0.5
    enough_data = n >= 3
    if not enough_data:
        verdict = "Insufficient data"
    elif not baseline_problem:
        verdict = "No change needed"
    elif (after_rate - before_rate >= 0.20 and
          after_total >= 0.80 * before_total):
        verdict = "Keep shorter blocks (simulation)"
    else:
        verdict = "Do not keep this change (simulation)"
    return {
        "before_rate": before_rate, "after_rate": after_rate,
        "before_total": before_total, "after_total": after_total,
        "before_avg": before_total / n, "after_avg": after_total / n,
        "verdict": verdict, "sessions": n,
    }


if page == "Simulation Lab":
    st.title("Simulation Lab · Version 7.4")
    st.warning("SIMULATED DATA ONLY. This page uses made-up study records. It does not measure real students or alter your actual assignments, timer history, or calendar.")
    st.write("Development-only examples showing how the study coach makes decisions. These are not real student results.")
    scenario = st.selectbox("Choose a fictional student", [
        "Long sessions are a struggle; shorter blocks help",
        "Shorter blocks increase goal hits but reduce study time",
        "Long sessions already work",
        "Not enough study sessions",
    ], key="v74_scenario")
    cases = {
        "Long sessions are a struggle; shorter blocks help": ([12, 18, 20, 16], [22, 25, 24, 25]),
        "Shorter blocks increase goal hits but reduce study time": ([24, 28, 26, 27], [25, 25, 5, 25]),
        "Long sessions already work": ([65, 60, 55, 62], [25, 25, 25, 25]),
        "Not enough study sessions": ([15, 20], [25, 20]),
    }
    long_times, short_times = cases[scenario]
    result = simulate_adaptive_study(long_times, short_times)
    before, after = st.columns(2)
    with before:
        st.metric("Original 60-min plan · goals reached", f"{result['before_rate']:.0%}")
        st.metric("Total actual minutes", f"{result['before_total']} min")
    with after:
        st.metric("New 25-min plan · goals reached", f"{result['after_rate']:.0%}")
        st.metric("Total actual minutes ", f"{result['after_total']} min")
    st.subheader(result['verdict'])
    st.table(pd.DataFrame([
        {"Session": i+1, "60-min goal · actual minutes": old, "25-min goal · actual minutes": new}
        for i, (old, new) in enumerate(zip(long_times, short_times))
    ]))
    with st.expander("How the decision works"):
        st.write("First, require at least 3 sessions of each type. If at least half the longer sessions met their goal, no change is needed. Otherwise keep shorter blocks only if goal completion increases by at least 20 percentage points AND actual study minutes remain at least 80% of the longer sessions. These numbers are initial rules to test, not proven thresholds.")
    st.caption("The examples are designed to illustrate different results, not predict what a student would do. We still need real student testing to learn whether the advice helps.")

if page == "Syllabus Upload":
    # ---------- SYLLABUS UPLOAD ----------
    st.markdown('<div class="hero"><h2>Upload a syllabus</h2><p>Turn course information into a clear plan.</p></div>', unsafe_allow_html=True)
    st.subheader("Extract assignments and deadlines")
    st.write("Upload a PDF, extract its text, then use Gemini to identify academic deadlines. Review everything before saving.")

    with st.container(border=True):
        st.markdown("**Choose your syllabus PDF**")
        st.caption("Select a PDF. You'll review every assessment before anything is saved.")
        uploaded_file = st.file_uploader("PDF file", type=["pdf"], label_visibility="collapsed")

    if uploaded_file is not None:
        st.markdown(f"**Selected PDF:** {html.escape(uploaded_file.name)} · {uploaded_file.size / 1024:.1f} KB")
        file_bytes = uploaded_file.getvalue()
        file_id = hashlib.sha256(file_bytes).hexdigest()

        # A new upload must not display AI results from a previous syllabus.
        if st.session_state.get("analyzed_file_id") != file_id:
            st.session_state.pop("ai_result", None)

        try:
            from io import BytesIO
            reader = PdfReader(BytesIO(file_bytes))
            syllabus_text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            syllabus_text = ""
            st.error("Could not read this PDF. Please check that it is a valid, unencrypted PDF.")

        if syllabus_text.strip():
            st.success("PDF text extracted successfully.")
            with st.expander("View extracted text"):
                st.text_area("Syllabus text", value=syllabus_text, height=260, disabled=True)
            if len(syllabus_text) > MAX_CHARACTERS:
                st.warning("This syllabus is long. The AI will analyze only the first 30,000 characters for this prototype. Check for missing assignments.")

            st.caption("For testing, use sample syllabi without private student details. Text is sent to Gemini only when you click Analyze.")
            if st.button("Analyze syllabus with Gemini", type="primary"):
                try:
                    with st.spinner("Gemini is reading the syllabus..."):
                        result = analyze_syllabus(
                            syllabus_text,
                            st.secrets["GEMINI_API_KEY"],
                        )
                    st.session_state.ai_result = result
                    st.session_state.pop(f"date_suggestions_{file_id}", None)
                    st.session_state.analyzed_file_id = file_id
                    st.success("AI analysis complete. Review the results below.")
                except Exception as error:
                    st.error(str(error) if isinstance(error, RuntimeError) else f"Analysis did not finish: {type(error).__name__}. Please check the Gemini connection and model access.")
        elif 'reader' in locals():
            st.warning("No readable text found. This could be a scanned PDF; image OCR is not part of this version.")

        if st.session_state.get("analyzed_file_id") == file_id and st.session_state.get("ai_result"):
            result = st.session_state.ai_result
            st.subheader("Course overview")
            st.caption("AI can miss course details. Correct these before saving assignments.")
            meta_left, meta_right = st.columns(2)
            with meta_left:
                reviewed_course = st.text_input(
                    "Course name", value=result["course"] or "",
                    key=f"meta_course_{file_id}",
                )
            with meta_right:
                reviewed_instructor = st.text_input(
                    "Instructor (optional)", value=result["instructor"] or "",
                    key=f"meta_instructor_{file_id}",
                )
            if result["grading_notes"]:
                st.markdown("**Grading breakdown (as described in the syllabus)**")
                st.info(result["grading_notes"])

            items = result["items"]
            dated_items = [item for item in items if item["due_date"] is not None]
            undated_items = [item for item in items if item["due_date"] is None]

            st.markdown("#### Assessment overview")
            if not items:
                st.info("No specific assessments were identified. Check the original PDF.")
            else:
                st.caption(
                    "The table below contains the detailed assessments and dates. "
                    "Confirm each entry against your syllabus before saving."
                )
                with st.expander("View extracted assessment summary"):
                    for item in items:
                        weight_label = f" — {item['weight']}" if item["weight"] else ""
                        st.markdown(f"**{item['name']}**{weight_label}")
                        if item["due_date"] is None:
                            st.caption("Date not provided")
                        else:
                            st.caption(f"Due {item['due_date'].strftime('%b %d, %Y')}")
                st.caption("Grouped assessments remain grouped until the syllabus provides separate details.")

            st.divider()
            st.subheader("Assignment planner — review before saving")
            st.caption("Review extracted assessments. You can save items without dates; they'll stay out of deadline-based scheduling until dated.")
            left_count, right_count = st.columns(2)
            left_count.metric("Dated assessments", len(dated_items))
            right_count.metric("Awaiting dates", len(undated_items))
            if undated_items:
                st.info("Missing dates can stay blank. You may save an undated assessment to your Dashboard now and add its date later.")

            if undated_items:
                with st.expander("AI date suggestions for missing deadlines", expanded=True):
                    st.write("When the syllabus gives a week or relative timing, AI can suggest a date. Otherwise it can suggest a **planning target**, not an official deadline. You must review each suggestion before saving.")
                    dates_a, dates_b = st.columns(2)
                    with dates_a:
                        term_start = st.date_input("Semester start date (verify from school calendar)", value=None, key=f"term_start_{file_id}")
                    with dates_b:
                        term_end = st.date_input("Semester end date (verify from school calendar)", value=None, key=f"term_end_{file_id}")
                    context_key = f"date_context_{file_id}"
                    previous_voice_key = f"last_voice_clue_{file_id}"
                    last_dictation_data = st.session_state.get(f"voice_return_{file_id}")
                    last_dictation = last_dictation_data.get("text", "") if isinstance(last_dictation_data, dict) else ""
                    dictation_id = last_dictation_data.get("nonce") if isinstance(last_dictation_data, dict) else None
                    if last_dictation and dictation_id != st.session_state.get(previous_voice_key):
                        prior = st.session_state.get(context_key, "")
                        st.session_state[context_key] = (prior + " " + last_dictation).strip()[:2000]
                        st.session_state[previous_voice_key] = dictation_id
                    pending_transcript_key = f"voice_pending_transcript_{file_id}"
                    pending_transcript = st.session_state.pop(pending_transcript_key, None)
                    if pending_transcript:
                        old_clue = st.session_state.get(context_key, "")
                        st.session_state[context_key] = (old_clue + " " + pending_transcript).strip()[:2000]
                    student_context = st.text_area("Additional information for AI (optional)",
                        placeholder="Example: Professor said our first essay is due around mid-November.",
                        key=context_key, max_chars=2000)
                    st.caption("Browser dictation stays in your browser when supported. Gemini fallback sends audio only after you click Transcribe recording. Review text before suggesting dates.")
                    voice_text = voice_clues(key=f"voice_clues_{file_id}", default=None)
                    if isinstance(voice_text, dict) and voice_text.get("text") and voice_text.get("nonce") != st.session_state.get(previous_voice_key):
                        st.session_state[f"voice_return_{file_id}"] = voice_text
                        st.rerun()
                    with st.expander("Browser microphone not working? Record with Gemini (optional)", expanded=False):
                        st.caption("The audio is sent to Google's Gemini service only if you click Transcribe recording. Audio is not stored by SyllabusSense. You can always type instead.")
                        recording = st.audio_input("Record a short voice clue", key=f"voice_fallback_audio_{file_id}")
                        if st.button("Transcribe recording with Gemini", key=f"voice_transcribe_{file_id}", disabled=recording is None):
                            try:
                                from gemini_voice_fallback import transcribe_audio
                                with st.spinner("Transcribing recording..."):
                                    transcript = transcribe_audio(recording.getvalue(), st.secrets["GEMINI_API_KEY"])
                                st.session_state[pending_transcript_key] = transcript
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not transcribe audio: {str(exc)[:220]}")
                    if st.button("Suggest missing dates with AI", key=f"suggest_missing_{file_id}"):
                        if not term_start or not term_end:
                            st.error("Enter the actual semester start and end dates before requesting suggestions.")
                        elif term_end <= term_start:
                            st.error("Semester end must be later than semester start.")
                        else:
                            try:
                                with st.spinner("Finding tentative dates..."):
                                    guesses = suggest_missing_dates(syllabus_text, undated_items, term_start, term_end, st.secrets["GEMINI_API_KEY"], student_context)
                                st.session_state[f"date_suggestions_{file_id}"] = guesses
                                st.session_state[f"date_suggestion_checked_{file_id}"] = True
                            except Exception as exc:
                                st.session_state[f"date_suggestion_checked_{file_id}"] = False
                                st.error(f"Date suggestions are unavailable: {str(exc)[:260]}. Your assessments were not changed.")
                    suggestions = st.session_state.get(f"date_suggestions_{file_id}", {})
                    if st.session_state.get(f"date_suggestion_checked_{file_id}") and not suggestions:
                        st.info("No defensible calendar dates could be inferred. That's expected when a syllabus has no timing clues. Add specific instructor information above, or set your own Planning target. No dates have been changed.")
                    if suggestions:
                        st.info("These dates are unconfirmed. Suggestions do not automatically become official deadlines or get saved.")
                        for index, item in enumerate(items):
                            suggestion = suggestions.get(item['name']) if item['due_date'] is None else None
                            if suggestion:
                                st.markdown(f"**{html.escape(item['name'])}** — {suggestion['date']} · {suggestion['label']}")
                                st.caption(suggestion['reason'])
                        st.caption("In the assessment table below, select Save and enter or accept a tentative date only if you want to use it for planning.")

            if items:
                # Stable review rows while the student edits the table.
                review_key = f"review_data_{file_id}"
                if review_key not in st.session_state:
                    st.session_state[review_key] = [
                        {
                            "Save": item["due_date"] is not None,
                            "Assessment": item["name"],
                            "Due date (YYYY-MM-DD)": item["due_date"].isoformat() if item["due_date"] else "",
                            "Date status": "Confirmed" if item["due_date"] else "Not provided",
                            "Priority": "Medium",
                            "Weight (%)": parse_weight(item["weight"]),
                        }
                        for item in items
                    ]

                suggestions = st.session_state.get(f"date_suggestions_{file_id}", {})
                if suggestions and st.button("Copy suggestions into review table (not saved yet)", key=f"copy_estimates_{file_id}"):
                    for row in st.session_state[review_key]:
                        guess = suggestions.get(row['Assessment'])
                        if guess and not row['Due date (YYYY-MM-DD)']:
                            row['Due date (YYYY-MM-DD)'] = guess['date']
                            row['Date status'] = guess['label']
                            # Keep Save unchecked; the student must choose to save.
                            row['Save'] = False
                    for idx, row in enumerate(st.session_state[review_key]):
                        st.session_state[f"review_date_{file_id}_{idx}"] = row['Due date (YYYY-MM-DD)']
                        st.session_state[f"review_status_{file_id}_{idx}"] = row['Date status']
                        st.session_state[f"review_save_{file_id}_{idx}"] = False
                    st.rerun()

                st.markdown("#### Review assessments")
                st.caption("Select Save for the assessments you want. Blank dates are allowed when status is Not provided.")
                st.caption("Date status: **Confirmed** = stated by instructor; **Inferred** = estimated from evidence; **Planning target** = your own target; **Not provided** = no known date.")
                with st.form(f"compact_review_{file_id}"):
                    course_name = reviewed_course
                    edited_records = []
                    for idx, row in enumerate(st.session_state[review_key]):
                        with st.container(border=True):
                            st.markdown(f"**{html.escape(str(row['Assessment']))}**")
                            left, right = st.columns([1, 3], vertical_alignment="bottom")
                            with left:
                                save_row = st.checkbox("Save to planner", value=bool(row['Save']), key=f"review_save_{file_id}_{idx}")
                            with right:
                                assessment_name = st.text_input("Assessment", value=str(row['Assessment']), key=f"review_name_{file_id}_{idx}")
                            coldate, colstatus = st.columns(2)
                            with coldate:
                                raw_date = st.text_input("Date (YYYY-MM-DD)", value=str(row['Due date (YYYY-MM-DD)']),
                                                         placeholder="Leave blank if unknown", key=f"review_date_{file_id}_{idx}")
                            with colstatus:
                                status_options = ["Not provided", "Confirmed", "Inferred", "Planning target"]
                                status = st.selectbox("Date status", status_options,
                                                      index=status_options.index(row['Date status']) if row['Date status'] in status_options else 0,
                                                      key=f"review_status_{file_id}_{idx}")
                            colpriority, colweight = st.columns(2)
                            with colpriority:
                                priority = st.selectbox("Priority", ["High", "Medium", "Low"],
                                                        index=["High", "Medium", "Low"].index(row['Priority']),
                                                        key=f"review_priority_{file_id}_{idx}")
                            with colweight:
                                weight_raw = st.text_input("Weight % (optional)",
                                            value="" if row['Weight (%)'] is None else str(row['Weight (%)']),
                                            key=f"review_weight_{file_id}_{idx}")
                            edited_records.append({"Save":save_row,"Assessment":assessment_name,
                                                   "Due date (YYYY-MM-DD)":raw_date, "Date status":status,
                                                   "Priority":priority,"Weight (%)":weight_raw})
                    save = st.form_submit_button("Save selected assessments", type="primary", use_container_width=True)

                with st.expander("View AI evidence for each assessment"):
                    for item in items:
                        st.markdown(f"**{item['name']}**")
                        st.caption(f"Type: {item['kind']} · Reported weight: {item['weight'] or 'Not provided'}")
                        if item["source_evidence"]:
                            st.caption(f"Source excerpt: {item['source_evidence']}")

                if save:
                    selected = edited_records
                    errors = []
                    validated = []
                    if not course_name.strip():
                        errors.append("Enter a course name.")
                    for row_number, row in enumerate(selected, start=1):
                        if not row["Save"]:
                            continue
                        name = str(row["Assessment"] or "").strip()
                        raw_date = str(row["Due date (YYYY-MM-DD)"] or "").strip()
                        if not name:
                            errors.append(f"Row {row_number}: assessment name is missing.")
                        label = row.get("Date status", "Not provided")
                        try:
                            due = date.fromisoformat(raw_date) if raw_date else None
                        except ValueError:
                            errors.append(f"Row {row_number}: date must be YYYY-MM-DD, or leave blank if unknown.")
                            continue
                        if due is None and label != "Not provided":
                            errors.append(f"Row {row_number}: choose Not provided when the date is blank.")
                            continue
                        if due is not None and label == "Not provided":
                            errors.append(f"Row {row_number}: choose a date status for the entered date.")
                            continue
                        try:
                            weight = float(row["Weight (%)"]) if str(row["Weight (%)"]).strip() else None
                        except ValueError:
                            errors.append(f"Row {row_number}: grading weight must be a number.")
                            continue
                        if weight is not None and not 0 <= weight <= 100:
                            errors.append(f"Row {row_number}: grading weight must be between 0 and 100.")
                        if name:
                            validated.append((name, due.isoformat() if due else "", row["Priority"], float(weight) if weight is not None else None, label))

                    if errors:
                        for message in errors:
                            st.error(message)
                        st.warning("Nothing was saved. Fix the listed rows and try again.")
                    else:
                        existing = {
                            (t["name"].casefold(), t["course"].casefold(), t["due"].isoformat() if t["due"] else "")
                            for t in load_tasks()
                        }
                        saved = duplicates = 0
                        new_assignment_ids = []
                        for name, due, priority, weight, date_status in validated:
                            identity = (name.casefold(), course_name.strip().casefold(), due)
                            if identity in existing:
                                duplicates += 1
                                continue
                            add_assignment(name, course_name.strip(), due, priority, weight)
                            register_course(course_name.strip())
                            existing.add(identity)
                            matching_ids = [t['id'] for t in load_tasks() if
                                (t['name'].casefold(), t['course'].casefold(), t['due'].isoformat() if t['due'] else '') == identity]
                            if matching_ids:
                                new_assignment_ids.append(matching_ids[-1])
                            if date_status != "Confirmed":
                                matching_ids = [t['id'] for t in load_tasks() if (t['name'].casefold(), t['course'].casefold(), t['due'].isoformat() if t['due'] else '') == identity]
                                if matching_ids:
                                    record_date_labels(matching_ids[-1], date_status)
                            saved += 1
                        register_course(course_name.strip())
                        register_syllabus(uploaded_file.name, file_id, course_name.strip(), new_assignment_ids)
                        st.success(f"Saved {saved} assignment(s); skipped {duplicates} duplicate(s).")
                        if saved:
                            st.info("Open Dashboard to see your saved assignments.")

    st.divider()
    st.caption("SyllabusSense · Your personal study planner")


from pypdf import PdfReader
import streamlit as st 
from datetime import date, timedelta
import re
import hashlib
import html
import pandas as pd
from ai_analysis import analyze_syllabus, MAX_CHARACTERS
from database import (
    create_database,
    add_assignment,
    get_assignments,
    update_assignment_status,
    update_study_details,
    create_schedule_tables, get_availability, save_availability,
    get_sessions, replace_unfinished_sessions, set_session_completed, move_session,
)
from study_schedule import generate_week

def parse_weight(raw):
    """Convert '10%' or '45% (15% each)' to a numeric total weight.

    Grouped items retain their *total* weight until the student splits them.
    Unknown weights stay NULL rather than pretending to be zero.
    """
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*%", str(raw or ""))
    return float(match.group(1)) if match else None


create_database()
create_schedule_tables()

st.set_page_config(
    page_title="SyllabusSense",
    page_icon="🎓",
    layout="wide",
)

# ---------- DESIGN ----------
st.markdown("""
<style>
/* Visual styling only: all data remains in the existing SQLite database. */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #F4F7FC !important;
    color: #17365D !important;
}
[data-testid="stHeader"] { background: #F4F7FC !important; }
.block-container { max-width: 1160px; padding-top: 2rem; padding-bottom: 4rem; }
h1, h2, h3, h4, [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stWidgetLabel"] p,
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
    color: #17365D;
}
[data-testid="stCaptionContainer"] p { color: #56708C !important; }
.hero { background: linear-gradient(120deg,#142F56,#2B64A6);
        padding: 30px 32px; border-radius: 20px; margin-bottom: 18px;
        box-shadow: 0 10px 30px rgba(20,47,86,.10); }
.hero h2, .hero p { color:#FFFFFF !important; margin:0; }
.hero h2 { font-size: 1.65rem; }
.hero p { margin-top: 10px; opacity: .90; }
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"] {
    border-radius: 16px;
}
[data-testid="stForm"], [data-testid="stExpander"] {
    border-radius: 16px !important;
}
[data-testid="stTextInput"] input, [data-testid="stDateInput"] input,
[data-testid="stSelectbox"] > div > div, [data-testid="stTextArea"] textarea {
    background-color:#FFFFFF !important; color:#17365D !important;
    border-color:#CCD8E8 !important;
}
/* Streamlit's table uses a canvas/grid implementation: the theme controls its colors. */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    background: #FFFFFF; border-radius: 12px; overflow: hidden;
}
.stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
    border-radius: 10px; font-weight: 600;
}
hr { border-color:#DDE5F0 !important; }
/* Consistent contrast for Streamlit inputs, buttons, hints, and table. */
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {color:#667B96 !important; opacity:1 !important;}
[data-testid="stDateInput"] input {background:#FFFFFF !important; color:#17365D !important;}
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stSelectbox"] [data-baseweb="select"] input {
  background:#FFFFFF !important; color:#17365D !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] span { color:#17365D !important; }
.stButton button, [data-testid="stFormSubmitButton"] button {
  background-color:#FFFFFF !important; color:#17365D !important;
  border:1px solid #B6C9E3 !important; border-radius:10px !important;
}
.stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
  background-color:#245C9A !important; color:#FFFFFF !important;
  border-color:#245C9A !important;
}
.stButton button p, [data-testid="stFormSubmitButton"] button p {color:inherit !important;}
[data-testid="stFileUploader"] button { color:#17365D !important; background:#FFFFFF !important; }
[data-testid="stDataEditor"] {border:1px solid #DCE5F0;}
/* BaseWeb displays selectbox values in a span inside the input (not always the input itself). */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div *,
[data-testid="stSelectbox"] div[data-baseweb="select"] span,
[data-testid="stSelectbox"] div[data-baseweb="select"] input {
    color:#17365D !important;
    -webkit-text-fill-color:#17365D !important;
    opacity:1 !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] svg { fill:#17365D !important; }
/* Date and number-input legibility */
[data-testid="stNumberInput"] input {color:#17365D !important; background:#FFFFFF !important;}

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
            "due": date.fromisoformat(row[3]),
            "priority": row[4],
            "completed": bool(row[5]),
            "weight": row[6],
            "hours": row[7],
            "confidence": row[8],
        }
        for row in rows
    ]


tasks = load_tasks()

# ---------- HEADER ----------
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
    not task["completed"] and task["due"] < date.today()
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
    (task for task in tasks if not task["completed"] and task["due"] >= date.today()),
    key=lambda t: (t["due"], {"High": 0, "Medium": 1, "Low": 2}.get(t["priority"], 3)),
)[:5]
if upcoming:
    for task in upcoming:
        days_left = (task["due"] - date.today()).days
        when = "Due today" if days_left == 0 else "Due tomorrow" if days_left == 1 else f"In {days_left} days"
        left, right = st.columns([4, 1])
        with left:
            st.markdown(f"**{task['name']}**")
            st.caption(f"{task['course']} · {task['due'].strftime('%b %d, %Y')} · {task['priority']} priority")
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
        if chosen_status == "Overdue" and (task["completed"] or task["due"] >= date.today()):
            return False
        return True

    visible_tasks = sorted(
        (task for task in tasks if shown(task)),
        key=lambda t: (t["completed"], t["due"], {"High": 0, "Medium": 1, "Low": 2}.get(t["priority"], 3)),
    )
    if visible_tasks:
        for task in visible_tasks:
            due_days = (task["due"] - date.today()).days
            status = "Completed" if task["completed"] else "Overdue" if due_days < 0 else "Due today" if due_days == 0 else "Upcoming"
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
                    st.caption(f"{task['course']} · {task['priority']} priority · {weight_label}")
                with detail:
                    st.markdown(f"**{task['due'].strftime('%b %d, %Y')}**")
                    st.caption(status)
        st.caption(f"Showing {len(visible_tasks)} of {len(tasks)} saved assignments.")
    else:
        st.info("No assignments match these filters.")
else:
    st.info("No assignments saved yet.")

# ---------- SMART STUDY PLANNER ----------
st.divider()
st.subheader("Smart Study Planner")
st.caption("Personalized, rule-based priorities using real deadlines, grading weights and your estimates. This version does not use Gemini to generate study recommendations.")
active = [task for task in tasks if not task["completed"]]


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
    with st.expander("Personalize your study priorities", expanded=True):
        st.write("Enter estimated study hours and confidence (1 = not confident, 5 = very confident). Leave them blank if you don't know yet.")
        detail_rows = [{
            "ID": task["id"], "Assignment": task["name"], "Course": task["course"],
            "Study hours": task["hours"], "Confidence (1–5)": task["confidence"],
        } for task in active]
        with st.form("study_details_form"):
            edited_details = st.data_editor(
                pd.DataFrame(detail_rows), hide_index=True, use_container_width=True,
                num_rows="fixed", disabled=["ID", "Assignment", "Course"],
                column_order=["Assignment", "Course", "Study hours", "Confidence (1–5)"],
                column_config={
                    "Assignment": st.column_config.TextColumn(width="large"),
                    "Study hours": st.column_config.NumberColumn(min_value=0.5, max_value=40.0, step=0.5, format="%.1f"),
                    "Confidence (1–5)": st.column_config.NumberColumn(min_value=1, max_value=5, step=1, format="%d"),
                },
                key="study_inputs_editor",
            )
            save_details = st.form_submit_button("Save study preferences", type="primary")
        if save_details:
            import pandas as _pd
            revisions = []
            errors = []
            for r in edited_details.to_dict("records"):
                hrs = None if _pd.isna(r["Study hours"]) else float(r["Study hours"])
                conf = None if _pd.isna(r["Confidence (1–5)"]) else int(r["Confidence (1–5)"])
                if hrs is not None and not 0.5 <= hrs <= 40:
                    errors.append(f"{r['Assignment']}: study hours must be 0.5–40")
                if conf is not None and not 1 <= conf <= 5:
                    errors.append(f"{r['Assignment']}: confidence must be 1–5")
                revisions.append((int(r["ID"]), hrs, conf))
            if errors:
                for err in errors:
                    st.error(err)
            else:
                for task_id, hrs, conf in revisions:
                    update_study_details(task_id, hrs, conf)
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

with st.expander("My availability", expanded=True):
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
        st.warning("Some work cannot fit before its deadline or within your availability. The planner won't schedule past due dates or exceed daily limits.")
        task_lookup = {t['id']: t for t in tasks}
        for tid, hours in shortages.items():
            st.caption(f"{task_lookup[tid]['name']}: {hours:g}h still unallocated")
    st.caption("Unscheduled hours can include work intended for later weeks, not just time you are short this week. The calendar uses day-level estimates, not class times or submission hours. It schedules before the due date, never on it.")
    if st.button("Generate / refresh weekly plan", type="primary"):
        replace_unfinished_sessions(week_start, week_end, planned)
        st.rerun()

    current_sessions = get_sessions(week_start, week_end)
    task_lookup = {t['id']: t for t in tasks}
    valid_sessions = [s for s in current_sessions if s['assignment_id'] in task_lookup]
    st.markdown("#### Weekly calendar")
    grid = st.columns(7)
    for offset, column in enumerate(grid):
        day = week_start + timedelta(days=offset)
        day_sessions = [s for s in valid_sessions if s['day'] == day]
        count_done = sum(bool(s['completed']) for s in day_sessions)
        with column:
            with st.container(border=True):
                st.markdown(f"**{day.strftime('%a')}**")
                st.caption(day.strftime('%b %d'))
                if not day_sessions:
                    st.caption("No sessions")
                else:
                    st.caption(f"{count_done} of {len(day_sessions)} done")
                for number, sess in enumerate(day_sessions, start=1):
                    task = task_lookup[sess['assignment_id']]
                    title = html.escape(task['name'])
                    if sess['completed']:
                        st.markdown(f"<div style='color:#17613c;font-size:0.84rem'>✓ <s>{title}</s></div>", unsafe_allow_html=True)
                        st.caption(f"Session {number} · {sess['hours']:g}h · Done")
                    else:
                        st.markdown(f"<div style='color:#17365D;font-size:0.84rem'>◯ {title}</div>", unsafe_allow_html=True)
                        st.caption(f"Session {number} · {sess['hours']:g}h · To do")
    st.markdown("#### Today's focus")
    today_sessions = [sess for sess in valid_sessions if sess['day'] == date.today()]
    if today_sessions:
        for sess in today_sessions:
            task = task_lookup[sess['assignment_id']]
            left, right = st.columns([5, 2], vertical_alignment="center")
            with left:
                st.markdown(f"**{html.escape(task['name'])}**")
                st.caption(f"{task['course']} · {sess['hours']:g} study hours · due {task['due'].strftime('%b %d')}")
            with right:
                new_value = st.checkbox("Completed", value=sess['completed'], key=f"study_session_{sess['id']}")
                if new_value != sess['completed']:
                    set_session_completed(sess['id'], new_value)
                    st.rerun()
    else:
        st.info("No study sessions scheduled for today. Generate a plan or review your availability.")
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
                if new_day >= task['due']:
                    st.error("Choose a date before this assignment is due.")
                elif allocated + target['hours'] > limit + 0.0001:
                    st.error(f"That day only has {limit:g}h available, and this move would exceed it.")
                else:
                    move_session(chosen_id, new_day)
                    st.rerun()
        else:
            st.caption("No unfinished sessions to move yet.")

# ---------- SYLLABUS UPLOAD + AI REVIEW ----------
st.divider()
st.subheader("Upload a syllabus")
st.write("Upload a PDF, extract its text, then use Gemini to identify academic deadlines. Review everything before saving.")

uploaded_file = st.file_uploader("Choose a PDF syllabus", type=["pdf"])

if uploaded_file is not None:
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
                st.session_state.analyzed_file_id = file_id
                st.success("AI analysis complete. Review the results below.")
            except Exception as error:
                st.error(f"Analysis did not finish: {type(error).__name__}. Check your connection, model quota, and API setup.")
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
        st.caption("One row per extracted assessment. Correct any errors before saving. Undated items are NOT saved by default.")
        left_count, right_count = st.columns(2)
        left_count.metric("Dated assessments", len(dated_items))
        right_count.metric("Awaiting dates", len(undated_items))
        if undated_items:
            st.info("Missing dates remain blank. Enter a verified date to include an undated assessment in your dashboard.")

        if items:
            # Stable review rows while the student edits the table.
            review_key = f"review_data_{file_id}"
            if review_key not in st.session_state:
                st.session_state[review_key] = [
                    {
                        "Save": item["due_date"] is not None,
                        "Assessment": item["name"],
                        "Due date (YYYY-MM-DD)": item["due_date"].isoformat() if item["due_date"] else "",
                        "Priority": "Medium",
                        "Weight (%)": parse_weight(item["weight"]),
                    }
                    for item in items
                ]

            with st.form(f"compact_review_{file_id}"):
                course_name = reviewed_course
                edited = st.data_editor(
                    st.session_state[review_key],
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    column_config={
                        "Save": st.column_config.CheckboxColumn("Save", help="Include in dashboard"),
                        "Assessment": st.column_config.TextColumn("Assessment", required=True, width="large"),
                        "Due date (YYYY-MM-DD)": st.column_config.TextColumn("Verified due date", help="Use YYYY-MM-DD; leave blank if unknown"),
                        "Priority": st.column_config.SelectboxColumn("Priority", options=["High", "Medium", "Low"], required=True),
                        "Weight (%)": st.column_config.NumberColumn("Weight (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.1f"),
                    },
                    key=f"assessment_editor_{file_id}",
                )
                save = st.form_submit_button("Save verified assignments", type="primary")

            with st.expander("View AI evidence for each assessment"):
                for item in items:
                    st.markdown(f"**{item['name']}**")
                    st.caption(f"Type: {item['kind']} · Reported weight: {item['weight'] or 'Not provided'}")
                    if item["source_evidence"]:
                        st.caption(f"Source excerpt: {item['source_evidence']}")

            if save:
                selected = edited.to_dict("records") if hasattr(edited, "to_dict") else edited
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
                    try:
                        due = date.fromisoformat(raw_date)
                    except ValueError:
                        errors.append(f"Row {row_number}: enter a real due date as YYYY-MM-DD, or uncheck Save.")
                        continue
                    weight = row["Weight (%)"]
                    if weight is not None and not 0 <= float(weight) <= 100:
                        errors.append(f"Row {row_number}: grading weight must be between 0 and 100.")
                    if name:
                        validated.append((name, due.isoformat(), row["Priority"], float(weight) if weight is not None else None))

                if errors:
                    for message in errors:
                        st.error(message)
                    st.warning("Nothing was saved. Fix the listed rows and try again.")
                else:
                    existing = {
                        (t["name"].casefold(), t["course"].casefold(), t["due"].isoformat())
                        for t in load_tasks()
                    }
                    saved = duplicates = 0
                    for name, due, priority, weight in validated:
                        identity = (name.casefold(), course_name.strip().casefold(), due)
                        if identity in existing:
                            duplicates += 1
                            continue
                        add_assignment(name, course_name.strip(), due, priority, weight)
                        existing.add(identity)
                        saved += 1
                    st.success(f"Saved {saved} assignment(s); skipped {duplicates} duplicate(s).")
                    if saved:
                        st.info("Scroll to Your assignments to view saved items, or refresh the app.")

st.divider()
st.caption("SyllabusSense · Your personal study planner")

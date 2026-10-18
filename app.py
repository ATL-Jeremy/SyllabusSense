from pypdf import PdfReader
import streamlit as st 
from datetime import date
import hashlib
from ai_analysis import analyze_syllabus, MAX_CHARACTERS
from database import (
    create_database,
    add_assignment,
    get_assignments,
    update_assignment_status,
)

create_database()

st.set_page_config(
    page_title="SyllabusSense",
    page_icon="🎓",
    layout="wide",
)

# ---------- DESIGN ----------
st.markdown("""
<style>
/* Consistent readable text on the light dashboard (including AI findings) */
[data-testid="stMarkdownContainer"] { color: #17365D; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h4 { color: #17365D; }
.hero h2, .hero p { color: #FFFFFF !important; }
/* Make labels and captions readable */

[data-testid="stWidgetLabel"] p {
    color: #17365D !important;
}

[data-testid="stCaptionContainer"] {
    color: #365578 !important;
}

[data-testid="stCaptionContainer"] p {
    color: #365578 !important;
}
/* Force metric card backgrounds */

div[data-testid="stMarkdownContainer"] div[style*="background-color"] {
    background-image: none !important;
}

div[style*="background-color: #E0ECFF"] {
    background-color: #E0ECFF !important;
}

div[style*="background-color: #DDF7E8"] {
    background-color: #DDF7E8 !important;
}

div[style*="background-color: #FFF0D9"] {
    background-color: #FFF0D9 !important;
}
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background-color: #F1F5FB !important;
}

[data-testid="stHeader"] {
    background-color: #F1F5FB !important;
}

.block-container {
    padding-top: 2rem;
    max-width: 1200px;
}

h1, h2, h3 {
    color: #17365D !important;
}

.hero {
    background: linear-gradient(120deg, #17365D, #3267A8);
    padding: 24px;
    border-radius: 18px;
    margin-bottom: 20px;
}

.hero h2, .hero p {
    color: white !important;
}


div[data-testid="stMetric"] {
    background: #E5EEFF !important;
    border: 1px solid #C8D9F5;
    border-radius: 16px;
    padding: 20px;
}

div[data-testid="stMetricLabel"] {
    color: #365578 !important;
}

div[data-testid="stMetricValue"] {
    color: #17365D !important;
}

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
        }
        for row in rows
    ]


tasks = load_tasks()

# ---------- HEADER ----------
st.markdown("""
<div class="hero">
    <h2>Study smarter, not harder. 🎓</h2>
    <p>Your semester, organized in one place.</p>
</div>
""", unsafe_allow_html=True)

st.title("Your dashboard")
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

# ---------- ADD TASK ----------
st.subheader("➕ Add an assignment")

with st.form("add_task_form", clear_on_submit=True):
    task_name = st.text_input(
        "Assignment name",
        placeholder="e.g. Psychology Chapter 6 quiz"
    )

    course = st.text_input(
        "Course",
        placeholder="e.g. Psychology"
    )

    col1, col2 = st.columns(2)

    with col1:
        due_date = st.date_input("Due date", value=date.today())

    with col2:
        priority = st.selectbox(
            "Priority",
            ["High", "Medium", "Low"]
        )

    submitted = st.form_submit_button(
        "Add assignment",
        use_container_width=True
    )

if submitted:
    if not task_name.strip():
        st.error("Please enter an assignment name.")
    elif not course.strip():
        st.error("Please enter a course name.")
    else:
        add_assignment(
            task_name.strip(),
            course.strip(),
            due_date.isoformat(),
            priority,
        )

        st.success("Assignment added!")
        st.rerun()

st.divider()

# ---------- TASK LIST ----------
st.subheader("📚 Your assignments")

if not tasks:
    st.info("No assignments yet. Add your first assignment above!")
else:
    sort_order = {"High": 0, "Medium": 1, "Low": 2}

    ordered_tasks = sorted(
        enumerate(tasks),
        key=lambda item: (
            item[1]["completed"],
            item[1]["due"],
            sort_order[item[1]["priority"]],
        )
    )

    for original_index, task in ordered_tasks:
        with st.container(border=True):
            left, right = st.columns([4, 1])

            with left:
                st.markdown(f"**{task['name']}**")
                st.caption(
                    f"{task['course']} · Due {task['due'].strftime('%b %d, %Y')}"
                )

                if task["completed"]:
                    st.success("Completed")
                elif task["due"] < date.today():
                    st.error(f"Overdue · {task['priority']} priority")
                else:
                    st.caption(f"{task['priority']} priority")

            with right:
                is_done = st.checkbox(
                    "Completed",
                    value=task["completed"],
                    key=f"completed_{task['id']}",
                )

                
                if is_done != task["completed"]:
                    update_assignment_status(
                        task["id"],
                        is_done
                    )
                    st.rerun()

# ---------- SYLLABUS UPLOAD + AI REVIEW ----------
st.divider()
st.subheader("📄 Upload your syllabus")
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
        st.markdown(f"**Course:** {result['course'] or 'Not identified'}")
        st.markdown(f"**Instructor:** {result['instructor'] or 'Not identified'}")
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
            for item in items:
                weight_label = f" — {item['weight']}" if item["weight"] else ""
                st.markdown(f"**{item['name']}**{weight_label}")
                if item["due_date"] is None:
                    st.caption("Date not provided · Not yet in your assignment dashboard")
                else:
                    st.caption(f"Due {item['due_date'].strftime('%b %d, %Y')} · Confirm against the PDF")
            st.caption("Weights above are AI-extracted, not independently verified. Multiple assessments grouped under one heading remain grouped unless individually documented.")

        st.divider()
        st.subheader("Assignment planner — review before saving")
        st.caption("AI suggestions are not automatically saved. Confirm every deadline against the syllabus or your instructor before adding it to the dashboard.")
        left_count, right_count = st.columns(2)
        left_count.metric("Dated assessments", len(dated_items))
        right_count.metric("Awaiting dates", len(undated_items))

        if not dated_items:
            st.info("No confirmed calendar dates were found. That's OK — the syllabus may contain only grading information.")
        if undated_items:
            st.warning("Items without dates are shown below for reference. A missing date will never be replaced with today's date or saved by accident.")

        if items:
            with st.form(f"review_syllabus_{file_id}"):
                course_name = st.text_input(
                    "Course for saved assignments",
                    value=result["course"] or "",
                    key=f"review_course_{file_id}",
                )
                reviewed = []
                for i, item in enumerate(items):
                    is_dated = item["due_date"] is not None
                    heading = f"{item['name']} · {item['due_date'].strftime('%b %d, %Y')}" if is_dated else f"{item['name']} · Date not provided"
                    with st.expander(heading, expanded=is_dated):
                        include = st.checkbox(
                            "Add this assessment to my dashboard",
                            value=is_dated,
                            key=f"include_{file_id}_{i}",
                        )
                        name = st.text_input(
                            "Assignment name",
                            value=item["name"],
                            key=f"name_{file_id}_{i}",
                        )
                        has_date = st.checkbox(
                            "I have verified a due date for this assessment",
                            value=is_dated,
                            key=f"hasdate_{file_id}_{i}",
                        )
                        due = None
                        if has_date:
                            due = st.date_input(
                                "Verified due date",
                                value=item["due_date"] or date.today(),
                                key=f"due_{file_id}_{i}",
                            )
                            if not is_dated:
                                st.caption("The date picker starts at today only for convenience. Enter the actual deadline before saving.")
                        else:
                            st.caption("Date not provided — this item cannot be saved until a date is confirmed.")
                        priority = st.selectbox(
                            "Priority", ["High", "Medium", "Low"], index=1,
                            key=f"priority_{file_id}_{i}",
                        )
                        if item["weight"]:
                            st.caption(f"Grading weight: {item['weight']}")
                        if item["source_evidence"]:
                            st.caption(f"Source excerpt: {item['source_evidence']}")
                        reviewed.append((include, name.strip(), due, priority, has_date))

                save = st.form_submit_button("Save verified assignments", type="primary")

            if save:
                if not course_name.strip():
                    st.error("Please enter a course name before saving.")
                else:
                    existing = {
                        (t["name"].casefold(), t["course"].casefold(), t["due"].isoformat())
                        for t in load_tasks()
                    }
                    saved = skipped = 0
                    for include, name, due, priority, has_date in reviewed:
                        if not include:
                            continue
                        if not name or not has_date or due is None:
                            skipped += 1
                            continue
                        identity = (name.casefold(), course_name.strip().casefold(), due.isoformat())
                        if identity in existing:
                            skipped += 1
                            continue
                        add_assignment(name, course_name.strip(), due.isoformat(), priority)
                        existing.add(identity)
                        saved += 1
                    st.success(f"Saved {saved} verified assignment(s). Skipped {skipped} incomplete or duplicate item(s).")
                    if saved:
                        st.info("Assignments were added to SQLite. Refresh the dashboard to see the updated counts.")

st.divider()
st.caption("SyllabusSense · Your personal study planner")

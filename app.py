from pypdf import PdfReader
import streamlit as st 
from datetime import date
import re
import hashlib
from ai_analysis import analyze_syllabus, MAX_CHARACTERS
from database import (
    create_database,
    add_assignment,
    get_assignments,
    update_assignment_status,
)

def parse_weight(raw):
    """Convert '10%' or '45% (15% each)' to a numeric total weight.

    Grouped items retain their *total* weight until the student splits them.
    Unknown weights stay NULL rather than pretending to be zero.
    """
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*%", str(raw or ""))
    return float(match.group(1)) if match else None


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
            "weight": row[6],
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
                    + (f" · Worth {task['weight']:g}%" if task["weight"] is not None else "")
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
                course_name = st.text_input(
                    "Course for saved assignments", value=result["course"] or "",
                    key=f"review_course_{file_id}",
                )
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
                with st.expander("View AI evidence for each row"):
                    for item in items:
                        st.markdown(f"**{item['name']}**")
                        st.caption(f"Type: {item['kind']} · Reported weight: {item['weight'] or 'Not provided'}")
                        if item["source_evidence"]:
                            st.caption(f"Source excerpt: {item['source_evidence']}")
                save = st.form_submit_button("Save verified assignments", type="primary")

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

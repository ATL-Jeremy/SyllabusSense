from pypdf import PdfReader
import streamlit as st 
from datetime import date
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

# ---------- SYLLABUS UPLOAD ----------
st.divider()

st.subheader("📄 Upload your syllabus")

st.write(
    "Upload a PDF syllabus to see the information "
    "inside your document."
)

uploaded_file = st.file_uploader(
    "Choose a PDF syllabus",
    type=["pdf"]
)

if uploaded_file is not None:
    try:
        reader = PdfReader(uploaded_file)

        extracted_pages = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            extracted_pages.append(page_text)

        syllabus_text = "\n\n".join(extracted_pages)

        if syllabus_text.strip():
            st.success(
                "Syllabus uploaded and read successfully!"
            )

            st.text_area(
                "Extracted syllabus text",
                value=syllabus_text,
                height=300
            )
        else:
            st.warning(
                "No readable text was found. "
                "This PDF may contain scanned images."
            )

    except Exception as error:
        st.error(
            f"Unable to read this PDF: {error}"
        )

st.divider()
st.caption("SyllabusSense · Your personal study planner")

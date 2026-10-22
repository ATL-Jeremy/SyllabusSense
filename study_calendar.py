"""Native Streamlit calendar based on genuine study-session dates; no invented times."""
import calendar
import html
from datetime import date, timedelta
import streamlit as st
from database import get_sessions

def _choose_day(day):
    st.session_state["calendar_anchor"] = day
    st.session_state["calendar_view"] = "Day"


def _navigate(offset, view):
    anchor = st.session_state["calendar_anchor"]
    if view == "Day":
        st.session_state["calendar_anchor"] = anchor + timedelta(days=offset)
    elif view == "Week":
        st.session_state["calendar_anchor"] = anchor + timedelta(days=offset*7)
    else:
        y,m = anchor.year, anchor.month + offset
        if m==0: y,m=y-1,12
        if m==13: y,m=y+1,1
        st.session_state["calendar_anchor"] = date(y,m,min(anchor.day,calendar.monthrange(y,m)[1]))


def _today():
    st.session_state["calendar_anchor"] = date.today()


def render_calendar(task_lookup, focus_callback, active_focus):
    today = date.today()
    if "calendar_anchor" not in st.session_state:
        st.session_state["calendar_anchor"] = today
    if "calendar_view" not in st.session_state:
        st.session_state["calendar_view"] = "Week"
    view = st.radio("Calendar view", ["Day", "Week", "Month"], horizontal=True, key="calendar_view")
    anchor = st.session_state["calendar_anchor"]
    prev, heading, nxt, reset = st.columns([1, 4, 1, 1], vertical_alignment="center")
    step = 1 if view == "Day" else 7 if view == "Week" else None
    with prev:
        st.button("◀", key="calendar_prev", help="Previous period", on_click=_navigate, args=(-1,view))
    with nxt:
        st.button("▶", key="calendar_next", help="Next period", on_click=_navigate, args=(1,view))
    with reset:
        st.button("Today", key="calendar_today", on_click=_today)
    if view == "Day": start = end = anchor
    elif view == "Week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
    else:
        start = date(anchor.year, anchor.month, 1)
        end = date(anchor.year, anchor.month, calendar.monthrange(anchor.year,anchor.month)[1])
    with heading:
        label = anchor.strftime("%A, %B %d, %Y") if view == "Day" else (f"{start:%b %d} – {end:%b %d, %Y}" if view == "Week" else anchor.strftime("%B %Y"))
        st.markdown(f"**{label}**")
    sessions = [s for s in get_sessions(start,end) if s["assignment_id"] in task_lookup]
    daily = {day: [s for s in sessions if s["day"] == day] for day in (start + timedelta(days=i) for i in range((end-start).days + 1))}
    st.caption("Study blocks are scheduled by day, not time of day. Click a date to view sessions or start Focus Mode. ✓ means completed.")
    if view == "Month":
        headers = st.columns(7, gap="small")
        for col, day_name in zip(headers, ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
            col.markdown(f"**{day_name}**")
        weeks = calendar.monthcalendar(anchor.year, anchor.month)
        for week in weeks:
            columns = st.columns(7, gap="small")
            for col, n in zip(columns, week):
                with col:
                    if not n:
                        st.markdown('<div class="study-cal-empty"></div>', unsafe_allow_html=True)
                        continue
                    day = date(anchor.year,anchor.month,n)
                    items = daily.get(day,[])
                    label = f"{n} · {len(items)} block" + ("s" if len(items)!=1 else "") if items else str(n)
                    st.button(label, key=f"cal_month_{day}", use_container_width=True, type="primary" if day==anchor else "secondary", on_click=_choose_day, args=(day,))
                    for ss in items[:2]:
                        task=task_lookup[ss["assignment_id"]]
                        st.caption(("✓ " if ss["completed"] else "• ")+task["name"][:20])
                    if len(items)>2: st.caption(f"+{len(items)-2} more")
        st.divider()
    else:
        days = [start+timedelta(days=i) for i in range((end-start).days+1)]
        if view == "Week":
            columns = st.columns(7, gap="small")
            for col,day in zip(columns,days):
                with col:
                    items = daily.get(day,[])
                    st.button(day.strftime("%a %d"), key=f"cal_week_{day}", use_container_width=True, type="primary" if day==anchor else "secondary", on_click=_choose_day, args=(day,))
                    with st.container(border=True):
                        st.caption(f"{sum(s['completed'] for s in items)}/{len(items)} done")
                        for ss in items:
                            task=task_lookup[ss["assignment_id"]]
                            st.markdown(f'<div class="study-cal-event {"is-done" if ss["completed"] else ""}">{"✓" if ss["completed"] else "•"} {html.escape(task["name"][:24])}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f"#### {anchor:%A, %B %d}")
            items=daily.get(anchor,[])
            if not items: st.info("No study sessions scheduled for this day.")
            for ss in items:
                task=task_lookup[ss["assignment_id"]]
                with st.container(border=True):
                    left,right=st.columns([4,1],vertical_alignment="center")
                    with left:
                        st.markdown(f"**{'✓ ' if ss['completed'] else ''}{html.escape(task['name'])}**")
                        st.caption(f"{task['course']} · {ss['hours']:g}h · {'Done' if ss['completed'] else 'To do'}")
                    with right:
                        if not ss["completed"]:
                            st.button("Open timer" if active_focus else "Start focus",key=f"day_focus_{ss['id']}",on_click=focus_callback,args=(ss["assignment_id"],ss["hours"],ss["id"]),use_container_width=True)
    if view != "Day" and sessions:
        with st.expander("Study sessions in this period — start Focus Mode"):
            for ss in sessions:
                task=task_lookup[ss["assignment_id"]]
                col1,col2=st.columns([4,1],vertical_alignment="center")
                with col1: st.caption(f"{ss['day']:%b %d} · {task['course']} · {task['name']} · {ss['hours']:g}h · {'Done' if ss['completed'] else 'To do'}")
                with col2:
                    if not ss["completed"]: st.button("Start focus",key=f"calendar_agenda_{ss['id']}",on_click=focus_callback,args=(ss["assignment_id"],ss["hours"],ss["id"]),use_container_width=True)

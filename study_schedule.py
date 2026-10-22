"""Deterministic study scheduling with deadline-aware, balanced allocation."""
from datetime import date, timedelta

DEFAULT_ESTIMATE_HOURS = 3.0
EPS = 1e-8


def generate_week(tasks, capacities, start, priority_fn, session_length=1.0, previously_completed=None):
    """Plan a rolling seven-day window, never on/after an assignment due date.

    Balance work across assignments while protecting sooner deadlines. A completed
    session consumes capacity and reduces remaining task work. Unallocated work
    is reported, not silently discarded. All figures are estimates.
    """
    if not 0.25 <= float(session_length) <= 4.0:
        raise ValueError("Study block must be between 15 minutes and 4 hours")
    if len(capacities) != 7:
        raise ValueError("Exactly seven daily capacities are required")
    previously_completed = previously_completed or []
    completed_by_task, occupied = {}, {}
    for s in previously_completed:
        if s['completed']:
            completed_by_task[s['assignment_id']] = completed_by_task.get(s['assignment_id'], 0.0) + float(s['hours'])
            occupied[s['day']] = occupied.get(s['day'], 0.0) + float(s['hours'])

    remaining = {}
    assumed = []
    eligible = {}
    for task in tasks:
        if task['completed'] or not isinstance(task.get('due'), date):
            # Undated assignments are retained in the database but are not
            # eligible for deadline-based planning or shortage calculations.
            continue
        hours = task['hours']
        if hours is None:
            hours = DEFAULT_ESTIMATE_HOURS
            assumed.append(task['id'])
        value = round(max(0.0, float(hours) - completed_by_task.get(task['id'], 0.0)), 2)
        if value > EPS:
            remaining[task['id']] = value
            eligible[task['id']] = task

    planned = []
    # Work forward by day. Give each active task at most one preferred block
    # before coming back to it, unless one task is all that can be scheduled.
    for offset in range(7):
        day = start + timedelta(days=offset)
        space = round(max(0.0, float(capacities[offset]) - occupied.get(day, 0.0)), 2)
        scheduled_today = {}
        while space >= 0.25 - EPS:
            choices = [t for t in eligible.values() if remaining[t['id']] >= 0.25 - EPS and day < t['due']]
            if not choices:
                break
            # Deadline pressure rises as remaining effort approaches available time.
            # Tie-breaker: don't schedule a second block of one task until others
            # have received a block today.
            def ordering(task):
                task_id = task['id']
                available_days = max(1, (task['due'] - day).days)
                pressure = remaining[task_id] / available_days
                return (scheduled_today.get(task_id, 0), -pressure, task['due'], -priority_fn(task), task_id)
            pick = min(choices, key=ordering)
            hours = round(min(float(session_length), remaining[pick['id']], space), 2)
            if hours < 0.25 - EPS:
                break
            planned.append({'assignment_id': pick['id'], 'day': day, 'hours': hours, 'completed': False})
            remaining[pick['id']] = round(remaining[pick['id']] - hours, 2)
            space = round(space - hours, 2)
            scheduled_today[pick['id']] = scheduled_today.get(pick['id'], 0) + 1

    unscheduled = {tid: hours for tid, hours in remaining.items() if hours > EPS}
    return planned, unscheduled, assumed

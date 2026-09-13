---
name: smart-timetable-vocational
description: >-
  Architectural blueprint, constraint programming rules, and operational procedures for developing,
  maintaining, and customizing the Smart Timetable vocational education scheduling system using Google
  OR-Tools CP-SAT, 18-week PVS smoothing, college workload caps, conflict detection, and official Excel reporting.
---

# Smart Timetable Vocational Scheduling System Skill

This skill provides architectural guidelines, solver model patterns, business rules, and maintenance procedures for the **Smart Timetable (มาตรฐานอาชีวศึกษา)** application.

---

## 1. System Architecture

```
+-------------------------------------------------------------------------+
|                       Web Frontend (src/static/)                        |
|  - HTML5 / TailwindCSS / Lucide Icons / Vanilla JS                      |
|  - Real-Time Drag & Drop / Swap Modals / Conflict Warning Badges        |
|  - LocalStorage Auto-Save & Auto-Restore (`smart_timetable_state_v2`)   |
|  - Project Package Sharing (.json Bundle Export / Import)               |
+------------------------------------+------------------------------------+
                                     | REST API (FastAPI)
                                     v
+-------------------------------------------------------------------------+
|                        API Layer (src/api/)                             |
|  - main.py: Routing & endpoints                                         |
|  - data_manager.py: File-based persistence (`data/timetable_config.json`)|
|  - analytics.py: College workload & student balance calculations        |
|  - official_template_exporter.py: OpenPyXL-based Sattahip Form Exporter |
|  - bulk_importer.py: UTF-8 BOM CSV / XLSX course plan ingestion         |
+------------------------------------+------------------------------------+
                                     | Domain Models & Requests
                                     v
+-------------------------------------------------------------------------+
|                       Solver Engine (src/solver/)                       |
|  - timetable_solver.py: Google OR-Tools CP-SAT (Integer Optimization)   |
|  - conflict_checker.py: Real-time validation for drag-and-drop & swap   |
|  - models.py: Pydantic domain models (Teacher, Room, Group, Assignment) |
|  - benchmark_data.py: Realistic vocational college test dataset         |
+-------------------------------------------------------------------------+
```

---

## 2. Vocational Domain & Business Rules (V.2 Standards)

### 2.1 Micro-Block Rotation & 18-Week Smoothing
- **Structure**: 1 semester = 18 weeks = 6 blocks (3 weeks per block).
- **Vocational Certificate (ปวช.)**: Active in all 6 blocks (18 weeks).
- **High Vocational Certificate (ปวส.)**: Standard curriculum is 15 weeks (5 blocks), but in V.2 it is smoothed across **all 6 blocks (18 weeks)** (`active_blocks = [0, 1, 2, 3, 4, 5]`) to prevent classroom shortage and teacher overloading.

### 2.2 College Workload Caps (เกณฑ์ภาระงานสอนวิทยาลัย)
1. **Absolute College Cap**: No teacher may exceed **35 periods/week**.
2. **Department Heads / Heads of Division (`is_head: True`)**:
   - Cap: $\le \mathbf{28}$ periods/week.
   - Standard baseline: 16–28 periods/week.
3. **General Teachers (`is_head: False`)**:
   - Cap: $\le \mathbf{34}$ periods/week.
   - Standard baseline: 16–34 periods/week.
4. **Daily Load Limits**:
   - Teacher daily load: $\le \mathbf{6}$ periods/day.
   - Student daily load: $\le \mathbf{7}$ periods/day (soft-balanced to max 8 in conflict checker).

### 2.3 Time Slots & Scheduling Structure
- **5 Working Days**: Monday to Friday (Day 0–4).
- **12 Periods/Day**:
  - Period 1–4: Morning (08:00 – 12:00)
  - Period 5: Lunch Break (12:00 – 13:00) - No academic classes scheduled.
  - Period 6–9: Afternoon (13:00 – 17:00)
  - Period 10–12: Evening / Special (17:00 – 20:00)
- **Period Durations**:
  - Theory: Typically 2 periods (e.g. 08:00–10:00 or 10:00–12:00).
  - Practice / Workshop: Typically 4–6 continuous periods.

---

## 3. Solver Constraints Reference (OR-Tools CP-SAT)

When modifying or extending `TimetableSolver` in `src/solver/timetable_solver.py`:

```python
# 1. Teacher Weekly Maximum (Load Cap)
for teacher in teachers:
    teacher_periods = []
    for (assignment_id, block), lesson in lesson_vars.items():
        if teacher.id in assignment.all_teacher_ids:
            teacher_periods.append(assignment.course.periods_per_session)
    # Cap according to is_head
    cap = teacher.max_periods_per_week
    model.Add(sum(teacher_periods) <= cap)

# 2. Teacher Daily Maximum
for teacher in teachers:
    for day in range(num_days):
        day_periods = []
        for (assignment_id, block), lesson in lesson_vars.items():
            if teacher.id in assignment.all_teacher_ids:
                is_on_day = model.NewBoolVar(f"teach_{teacher.id}_{day}_{assignment_id}")
                model.Add(lesson.day == day).OnlyEnforceIf(is_on_day)
                model.Add(lesson.day != day).OnlyEnforceIf(is_on_day.Not())
                day_periods.append(is_on_day * assignment.course.periods_per_session)
        model.Add(sum(day_periods) <= teacher.max_periods_per_day)

# 3. Student Group Daily Limit
for group in groups:
    for day in range(num_days):
        # Enforce sum of scheduled periods on day <= max_student_periods_per_day (default 7)
```

---

## 4. State Persistence & Collaboration Workflow

### 4.1 Client-Side LocalStorage Auto-Save
- **Key**: `smart_timetable_state_v2`
- **Saved Entities**: `solveResult`, `currentBlock`, `currentViewMode`, `currentEntityId`, and `savedAt`.
- **Triggers**: Auto-saves after every `runSolver()`, `directMoveLesson()`, `executeSwap()`, `applyMove()`, and `saveAndSolveCurrent()`.
- **Restoration**: On page load (`init()`), detects saved schedule and renders without re-solving.

### 4.2 Project Package Sharing (.json Bundle)
- **Export**: `exportProjectFile()` dumps configuration (`project_data`), complete schedule (`solveResult`), and view state into a single `.json` file (`Smart_Timetable_Project_YYYY-MM-DD.json`).
- **Import**: `importProjectFile()` sends `project_data` to `/api/project/import`, updates database, restores schedule with all manual moves, and saves to `localStorage`.

---

## 5. Deployment Guidelines

- **Repository**: GitHub remote `origin/main`.
- **Platform**: Render Web Service (Python 3, Singapore region).
- **Start Command**: `gunicorn -k uvicorn.workers.UvicornWorker src.api.main:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
- **Health Check**: Endpoint `/api/health` returns `{"status": "ok"}`.

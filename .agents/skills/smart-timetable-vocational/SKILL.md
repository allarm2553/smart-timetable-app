---
name: smart-timetable-vocational
description: >-
  Architectural blueprint, constraint programming rules, and operational procedures for developing,
  maintaining, and customizing the Smart Timetable vocational education scheduling system using Google
  OR-Tools CP-SAT, 18-week PVS smoothing, college workload caps, conflict detection, pinned lessons,
  theory-practice course types, vocational Excel importing, and official Excel reporting.
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
|  - Pinned / Pre-assigned Lessons (Quick Lock 🔒 / 🔓 UI)                |
|  - Responsive Modal with Sticky Footer & Auto-Save Form Buffer          |
|  - LocalStorage Auto-Save & Auto-Restore (`smart_timetable_state_v2`)   |
|  - Project Package Sharing (.json Bundle Export / Import)               |
+------------------------------------+------------------------------------+
                                     | REST API (FastAPI)
                                     v
+-------------------------------------------------------------------------+
|                        API Layer (src/api/)                             |
|  - main.py: Routing & endpoints                                         |
|  - data_manager.py: File persistence (`data/timetable_config.json`)     |
|    * Clean Slate (Clear All 100%) vs Demo Dataset Load                  |
|  - analytics.py: College workload & student balance calculations        |
|  - official_template_exporter.py: OpenPyXL-based Sattahip Form Exporter |
|  - importer.py: Robust vocational Excel (.xlsx) & CSV parser            |
|    * Sub-header merging, side-by-side tables, code-name isolation       |
+------------------------------------+------------------------------------+
                                     | Domain Models & Requests
                                     v
+-------------------------------------------------------------------------+
|                       Solver Engine (src/solver/)                       |
|  - timetable_solver.py: Google OR-Tools CP-SAT (Integer Optimization)   |
|    * Hard Pinned Constraints, 18-week PVS smoothing, No-overlap         |
|  - conflict_checker.py: Real-time validation for drag-and-drop & swap   |
|  - models.py: Pydantic domain models (Teacher, Room, Group, Assignment) |
|    * CourseType (THEORY, PRACTICE, THEORY_PRACTICE, ROTATION_BASE)      |
|  - benchmark_data.py: Realistic vocational college test dataset         |
+-------------------------------------------------------------------------+
```

---

## 2. Vocational Domain & Business Rules (V.2 Standards)

### 2.1 Micro-Block Rotation & 18-Week Smoothing
- **Structure**: 1 semester = 18 weeks = 6 blocks (3 weeks per block).
- **Vocational Certificate (ปวช.)**: Active in all 6 blocks (18 weeks).
- **High Vocational Certificate (ปวส.)**: Standard curriculum is 15 weeks (5 blocks), but in V.2 it is smoothed across **all 6 blocks (18 weeks)** (`active_blocks = [0, 1, 2, 3, 4, 5]`) to prevent classroom shortage and teacher overloading.
- **Student Group Year Conventions**:
  - ปวช.1–3: Year 1–3 (`ชอ.1/x`, `ชอ.2/x`, `ชอ.3/x`)
  - ปวส.1: Year 4 (`ชอ.4/x`)
  - ปวส.2: Year 5 (`ชอ.5/x`)

### 2.2 Course Types (`CourseType`)
- **`THEORY` (ทฤษฎี)**: Standard 1–2 period lectures. Can be merged across 2 groups (`allow_merge = True`).
- **`PRACTICE` (ปฏิบัติการ)**: Continuous workshop/lab sessions (3–6 continuous periods).
- **`THEORY_PRACTICE` (ทฤษฎี+ปฏิบัติ)**: Integrated vocational subjects (e.g. 1-2-2 or 1-4-3). Automatically splits theory (1 hr) and practice ($N-1$ hrs) in official report summaries (ศธ.02).
- **`ROTATION_BASE` (ฐานหมุนเวียน 3 สัปดาห์)**: Micro-block subjects rotating across specialized training bases.

### 2.3 College Workload Caps (เกณฑ์ภาระงานสอนวิทยาลัย)
1. **Absolute College Cap**: No teacher may exceed **35 periods/week**.
2. **Department Heads / Heads of Division (`is_head: True`)**:
   - Cap: $\le \mathbf{28}$ periods/week (baseline: 16–28 periods/week).
3. **General Teachers (`is_head: False`)**:
   - Cap: $\le \mathbf{34}$ periods/week (baseline: 16–34 periods/week).
4. **Daily Load Limits**:
   - Teacher daily load: $\le \mathbf{6}$ periods/day.
   - Student daily load: $\le \mathbf{7}$ periods/day (soft-balanced up to 8).

### 2.4 Pre-assigned & Pinned Lessons (วิชาสามัญ / คาบล็อกตายตัว)
- Vocational general education courses (ภาษาไทย, ภาษาอังกฤษ, วิทย์, คณิต, ลูกเสือ) are often scheduled college-wide by the General Education Department.
- **Solver Constraint**:
  $$starts[a, fixed\_day, fixed\_start\_period - 1] = 1$$
- **Conflict Protection**: Drag-and-drop and swap actions on pinned lessons are strictly blocked until unlocked.
- **UI Interaction**: Instant 🔒/🔓 toggle icon on card, with dynamic start period options based on session duration.

---

## 3. Vocational Curriculum Importer Rules (`src/api/importer.py`)

Real Thai vocational study plan Excel files (`.xlsx`) require specialized parsing:

1. **Header Row Identification**:
   - Must have $\ge 3$ non-empty columns to avoid matching single-cell document titles on Row 1 (e.g. *"แผนการเรียน... รหัส 69"*).
   - Must contain course code keywords (`รหัสวิชา`, `code`) and name/hour indicators (`รายวิชา`, `ท`, `ป`, `น`).
2. **Multi-Line & Sub-Header Merging**:
   - When Row 4 contains semester title (`ภาคเรียนที่ 1/2569`) and Row 5 contains sub-header (`รายวิชา`), sub-headers are merged.
   - **Positional Rule**: The column immediately following the course code column is designated as the Course Name (`รายวิชา`) by default.
3. **Side-by-Side Tables**:
   - Detected by multiple code column occurrences (e.g. Column 1 and Column 7 in cover sheets `ใบปะหน้า`).
   - Sliced into independent column blocks for row parsing.
4. **Code-Name Isolation**:
   - Word `"วิชา"` is excluded from name alias search to prevent matching `"รหัสวิชา"`.
   - `exclude_keywords=["รหัส", "code"]` ensures course codes are NEVER assigned as course names.
   - Automatic fallback recovers valid Thai course names from adjacent text columns.

---

## 4. Official Sattahip Template Exporter (`src/api/official_template_exporter.py`)

- Injects timetable schedules into official Sattahip Technical College Excel templates with Garuda emblem and signatures.
- Supports 3 export scopes: Single Group, All Groups (multi-tab), and Full College Package (Groups + Teachers + Rooms).
- Accurately splits Theory and Practice hours in summary tables for `THEORY`, `PRACTICE`, and `THEORY_PRACTICE`.

---

## 5. Deployment Guidelines

- **Repository**: GitHub remote `origin/main`.
- **Platform**: Render Web Service (Python 3, Singapore region).
- **Start Command**: `gunicorn -k uvicorn.workers.UvicornWorker src.api.main:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
- **Health Check**: Endpoint `/api/health` returns `{"status": "ok"}`.


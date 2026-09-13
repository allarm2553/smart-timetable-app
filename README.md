# Smart Timetable App (ระบบจัดตารางเรียนตารางสอนอัจฉริยะ)

ระบบจัดตารางเรียนตารางสอนที่ออกแบบมาเป็นพิเศษเพื่อรองรับความซับซ้อนของสถานศึกษาและวิทยาลัยอาชีวศึกษา

## คุณสมบัติเด่น (Core Capabilities)
1. **รองรับระยะเวลาเรียนไม่เท่ากัน:** ปวช. (18 สัปดาห์) และ ปวส. (15 สัปดาห์)
2. **ระบบโมดูลหมุนเวียนฐาน (3-Week Micro-Block Rotation):**
   - ช่วงที่ 1: สัปดาห์ที่ 1–3
   - ช่วงที่ 2: สัปดาห์ที่ 4–6
   - ช่วงที่ 3: สัปดาห์ที่ 7–9
   - ช่วงที่ 4: สัปดาห์ที่ 10–12
   - ช่วงที่ 5: สัปดาห์ที่ 13–15
   - ช่วงที่ 6: สัปดาห์ที่ 16–18 (สำหรับ ปวช.)
3. **การจัดการครูผู้สอนข้ามระดับ (Shared Teachers):**
   - ตรวจจับการชนกันแบบแยกตามบล็อก (Block-by-Block Conflict Resolution)
   - ปลดล็อกคาบว่างของ ปวส. ในสัปดาห์ที่ 16–18 ให้ครูสามารถสอนเสริมหรือจัดโครงการ ปวช. ได้
4. **คาบทฤษฎีเรียนรวมพร้อมกัน 2 กลุ่ม (Merged Theory Classes):**
   - จัดตารางให้นักเรียน 2 กลุ่มเรียนวิชาทฤษฎีพร้อมกัน ครูคนเดียวกัน
   - กรองและจัดสรรห้องบรรยายขนาดใหญ่ที่มีความจุรองรับจำนวนนักเรียนทั้งสองกลุ่ม
5. **เครื่องมือจัดตารางอัตโนมัติ (Constraint Solver Engine):**
   - พัฒนาด้วย Google OR-Tools (CP-SAT Solver)

---

## สถาปัตยกรรมระบบ (Architecture)

```
smart-timetable-app/
├── src/
│   ├── api/                     # REST API (FastAPI)
│   │   ├── main.py              # Endpoints & CORS Configuration
│   │   └── schemas.py           # Pydantic DTO Models
│   └── solver/                  # Core Timetable Engine
│       ├── models.py            # Data Domain Models
│       ├── timetable_solver.py  # Google OR-Tools CP-SAT Solver
│       ├── benchmark_data.py    # ชุดข้อมูลทดสอบวิทยาลัยอาชีวศึกษา
│       └── formatter.py         # ตัวแปลงตารางเรียนตารางสอน
└── tests/
    └── test_api.py              # Automated Unit Tests สำหรับ API
```

---

## วิธีการติดตั้งและรันระบบ

### 1. ติดตั้ง Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install ortools fastapi "uvicorn[standard]" httpx
```

### 2. รัน FastAPI Server
```bash
source .venv/bin/activate
uvicorn src.api.main:app --reload --port 8000
```
- เปิดดู Interactive API Documentation (Swagger UI) ได้ที่: **http://127.0.0.1:8000/docs**
- หรือ ReDoc ได้ที่: **http://127.0.0.1:8000/redoc**

### 3. รันการทดสอบ (Automated Tests)
```bash
.venv/bin/python -m tests.test_api
```

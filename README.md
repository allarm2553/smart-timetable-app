# Smart Timetable App (ระบบจัดตารางเรียนตารางสอนอัจฉริยะ)

ระบบจัดตารางเรียนตารางสอนที่ออกแบบมาเป็นพิเศษเพื่อรองรับความซับซ้อนของสถานศึกษาและวิทยาลัยอาชีวศึกษา

## คุณสมบัติเด่น (Core Capabilities)
1. **รองรับระยะเวลาเรียนไม่เท่ากันและการเกลี่ย ปวส. 18 สัปดาห์ (18-Week Smoothing):** จัด ปวช. และ ปวส. ครบ 18 สัปดาห์เต็ม เกลี่ยการใช้ห้องปฏิบัติการและภาระงานครูอย่างสมดุล
2. **ระบบโมดูลหมุนเวียนฐาน (3-Week Micro-Block Rotation):** หมุนเวียนกลุ่มเรียนเข้าฐานปฏิบัติการเฉพาะทางทุกๆ 3 สัปดาห์อย่างแม่นยำ
3. **ระบบล็อกคาบเรียนตายตัวล่วงหน้า (Pinned Lessons 🔒 / 🔓):** ล็อกวิชาสามัญสัมพันธ์และคาบที่ลงล่วงหน้าด้วยปุ่มแม่กุญแจ โดย AI Solver จะจัดวิชาอื่นๆ หลบให้อัตโนมัติ 100%
4. **รองรับประเภทรายวิชาครบ 4 รูปแบบ:** ทฤษฎี (Theory), ปฏิบัติการ (Practice), **ทฤษฎี+ปฏิบัติ (Theory + Practice)**, และฐานหมุนเวียน 3 สัปดาห์
5. **ระบบนำเข้าแผนการเรียนอัจฉริยะ (Vocational Excel / CSV Importer):** รองรับไฟล์ `.xlsx` จริงของสถานศึกษา ข้ามหัวข้อหมวดวิชาและยอดรวมอัตโนมัติ พร้อมตรวจจับชื่อวิชาภาษาไทยได้อย่างแม่นยำ
6. **การจัดการครูผู้สอนข้ามระดับและสอนร่วม (Shared & Co-Teaching Teachers):** ตรวจจับการชนกันแบบบล็อกต่อบล็อก และรองรับครูผู้สอนร่วม 2 ท่าน
7. **คาบทฤษฎีเรียนรวมพร้อมกัน 2 กลุ่ม (Merged Theory Classes):** จัดตารางให้นักเรียน 2 กลุ่มเรียนวิชาทฤษฎีพร้อมกันในห้องบรรยายขนาดใหญ่
8. **เครื่องมือจัดตารางอัตโนมัติ (Constraint Solver Engine):** ขับเคลื่อนด้วย Google OR-Tools (CP-SAT Solver) รวดเร็วและแม่นยำ 100%
9. **ส่งออกไฟล์ทางการมาตรฐาน ศธ.02 (.xlsx):** หยอดลงแบบฟอร์มวิทยาลัยเทคนิคสัตหีบ พร้อมตราครุฑและช่องลายเซ็นครบถ้วน

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
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 📖 คู่มือการใช้งานและเอกสารอ้างอิง
- **คู่มือการใช้งานระบบฉบับสมบูรณ์ (User Manual)**: [USER_MANUAL.md](file:///Users/allarmmac/.gemini/antigravity/scratch/smart-timetable-app/USER_MANUAL.md)
- **สเปกและความสามารถ V.2 (Walkthrough)**: [walkthrough.md](file:///Users/allarmmac/.gemini/antigravity/brain/ca5268e5-8c42-4d17-8fd2-7362d42610ec/walkthrough.md)
- **Antigravity Skill Blueprint**: [.agents/skills/smart-timetable-vocational/SKILL.md](file:///Users/allarmmac/.gemini/antigravity/scratch/smart-timetable-app/.agents/skills/smart-timetable-vocational/SKILL.md)

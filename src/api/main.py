import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import base64
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import urllib.parse
from src.api.excel_exporter import VocationalExcelExporter
from src.api.official_template_exporter import OfficialTemplateExporter
from src.api.importer import BulkDataImporter
from src.api.analytics import WorkloadAnalyticsService

from src.solver.models import (
    Teacher, Room, StudentGroup, Course, LessonAssignment,
    EducationLevel, CourseType, RoomType
)
from src.solver.timetable_solver import TimetableSolver
from src.solver.benchmark_data import get_benchmark_dataset
from src.solver.conflict_checker import validate_move, validate_swap
from src.api.data_manager import data_manager
from src.api.schemas import (
    SolveRequest, SolveResponse, ScheduleEntryDTO,
    TeacherDTO, RoomDTO, StudentGroupDTO, CourseDTO, LessonAssignmentDTO,
    ValidateMoveRequest, ValidateMoveResponse, ApplyMoveRequest, ApplyMoveResponse,
    SwapLessonsRequest, SwapLessonsResponse, PinAssignmentRequest
)

app = FastAPI(
    title="Smart Timetable API",
    description="ระบบจัดตารางเรียนตารางสอนอัจฉริยะสำหรับอาชีวศึกษา (Google OR-Tools CP-SAT)",
    version="1.0.0"
)

# อนุญาต CORS สำหรับการเชื่อมต่อกับ Frontend Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DAY_NAMES = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def get_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Frontend index.html not found"}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Smart Timetable API",
        "engine": "Google OR-Tools CP-SAT"
    }

@app.get("/api/benchmark")
def get_benchmark():
    """ดึงข้อมูลตัวอย่างของวิทยาลัยอาชีวศึกษา"""
    dataset = get_benchmark_dataset()
    return {
        "teachers": [
            TeacherDTO(
                id=t.id,
                name=t.name,
                max_periods_per_day=t.max_periods_per_day,
                unavailable_slots=list(t.unavailable_slots)
            ) for t in dataset["teachers"]
        ],
        "rooms": [
            RoomDTO(
                id=r.id,
                name=r.name,
                room_type=r.room_type,
                capacity=r.capacity
            ) for r in dataset["rooms"]
        ],
        "groups": [
            StudentGroupDTO(
                id=g.id,
                name=g.name,
                level=g.level,
                student_count=g.student_count
            ) for g in dataset["groups"]
        ],
        "courses": [
            CourseDTO(
                id=c.id,
                name=c.name,
                code=c.code,
                course_type=c.course_type,
                periods_per_session=c.periods_per_session,
                sessions_per_week=c.sessions_per_week,
                required_room_type=c.required_room_type,
                allow_merge=c.allow_merge,
                base_id=c.base_id
            ) for c in dataset["courses"].values()
        ],
        "assignments": [
            LessonAssignmentDTO(
                id=a.id,
                course_id=a.course.id,
                primary_group_id=a.primary_group_id,
                teacher_id=a.teacher_id,
                secondary_group_id=a.secondary_group_id,
                is_rotation=a.is_rotation
            ) for a in dataset["assignments"]
        ]
    }

def _run_solver(
    teachers: list[Teacher],
    rooms: list[Room],
    groups: list[StudentGroup],
    assignments: list[LessonAssignment],
    days: int,
    periods_per_day: int,
    num_blocks: int,
    time_limit_seconds: float
) -> SolveResponse:
    start_time = time.time()

    if not assignments:
        return SolveResponse(
            status="EMPTY",
            is_success=True,
            execution_time_seconds=0.0,
            total_lessons_scheduled=0,
            schedule=[],
            message="ไม่มีแผนการสอนที่ต้องจัดตารางในระบบ กรุณาเพิ่มรายวิชาหรือนำเข้าข้อมูล"
        )

    try:
        solver = TimetableSolver(
            teachers=teachers,
            rooms=rooms,
            groups=groups,
            assignments=assignments,
            days=days,
            periods_per_day=periods_per_day,
            num_blocks=num_blocks
        )
        
        solver.build_model()
        raw_results = solver.solve(time_limit_seconds=time_limit_seconds)
        elapsed = round(time.time() - start_time, 3)

        if not raw_results:
            return SolveResponse(
                status="INFEASIBLE",
                is_success=False,
                execution_time_seconds=elapsed,
                total_lessons_scheduled=0,
                schedule=[],
                message="ไม่สามารถจัดตารางได้ภายใต้เงื่อนไขที่กำหนด (โปรดตรวจสอบข้อจำกัดเวลา ห้อง หรือครู)"
            )

        t_map = {t.id: t for t in teachers}
        schedule_entries = []
        for r in raw_results:
            ass: LessonAssignment = r["assignment"]
            d = r["day"]
            p = r["start_period"]
            dur = r["duration"]

            sec_t_id = getattr(ass, "secondary_teacher_id", None)
            sec_t_name = t_map[sec_t_id].name if sec_t_id and sec_t_id in t_map else None

            entry = ScheduleEntryDTO(
                assignment_id=ass.id,
                course_id=ass.course.id,
                course_name=ass.course.name,
                course_code=ass.course.code or ass.course.id,
                course_type=ass.course.course_type,
                teacher_id=r["teacher"].id,
                teacher_name=r["teacher"].name,
                secondary_teacher_id=sec_t_id,
                secondary_teacher_name=sec_t_name,
                teaching_mode=getattr(ass, "teaching_mode", "SINGLE"),
                room_id=r["room"].id,
                room_name=r["room"].name,
                primary_group_id=ass.primary_group_id,
                secondary_group_id=ass.secondary_group_id,
                is_merged=ass.secondary_group_id is not None,
                day=d,
                day_name=DAY_NAMES[d] if d < len(DAY_NAMES) else f"วันที่ {d+1}",
                start_period=p + 1,  # แปลงเป็นคาบ 1-indexed สำหรับผู้ใช้
                end_period=p + dur,
                duration=dur,
                active_blocks=[b + 1 for b in r["active_blocks"]], # บล็อก 1-6
                is_pinned=getattr(ass, "is_pinned", False),
                fixed_day=getattr(ass, "fixed_day", None),
                fixed_start_period=getattr(ass, "fixed_start_period", None),
                fixed_room_id=getattr(ass, "fixed_room_id", None),
                external_teacher_name=getattr(ass, "external_teacher_name", None)
            )
            schedule_entries.append(entry)

        return SolveResponse(
            status="FEASIBLE",
            is_success=True,
            execution_time_seconds=elapsed,
            total_lessons_scheduled=len(schedule_entries),
            schedule=schedule_entries,
            message="จัดตารางเรียนตารางสอนสำเร็จเรียบร้อย"
        )
    except Exception as exc:
        elapsed = round(time.time() - start_time, 3)
        return SolveResponse(
            status="ERROR",
            is_success=False,
            execution_time_seconds=elapsed,
            total_lessons_scheduled=0,
            schedule=[],
            message=f"เกิดข้อผิดพลาดในการประมวลผล: {str(exc)}"
        )

@app.post("/api/solve/benchmark", response_model=SolveResponse)
def solve_benchmark():
    """รันการจัดตารางด้วยชุดข้อมูลทดสอบ Benchmark ทันที"""
    dataset = get_benchmark_dataset()
    return _run_solver(
        teachers=dataset["teachers"],
        rooms=dataset["rooms"],
        groups=dataset["groups"],
        assignments=dataset["assignments"],
        days=5,
        periods_per_day=12,
        num_blocks=6,
        time_limit_seconds=15.0
    )

@app.post("/api/solve", response_model=SolveResponse)
def solve_custom(req: SolveRequest):
    """รับข้อมูลการจัดตารางที่กำหนดเองจากผู้ใช้และประมวลผลคำตอบ"""
    # แปลง DTOs เป็น Domain Models
    teachers = [
        Teacher(
            id=t.id,
            name=t.name,
            max_periods_per_day=t.max_periods_per_day,
            unavailable_slots=set((s[0], s[1]) for s in t.unavailable_slots)
        ) for t in req.teachers
    ]

    rooms = [
        Room(
            id=r.id,
            name=r.name,
            room_type=r.room_type,
            capacity=r.capacity
        ) for r in req.rooms
    ]

    groups = [
        StudentGroup(
            id=g.id,
            name=g.name,
            level=g.level,
            student_count=g.student_count
        ) for g in req.groups
    ]

    course_dict = {
        c.id: Course(
            id=c.id,
            name=c.name,
            code=c.code,
            course_type=c.course_type,
            periods_per_session=c.periods_per_session,
            sessions_per_week=c.sessions_per_week,
            required_room_type=c.required_room_type,
            allow_merge=c.allow_merge,
            base_id=c.base_id
        ) for c in req.courses
    }

    assignments = []
    for a in req.assignments:
        if a.course_id not in course_dict:
            raise HTTPException(status_code=400, detail=f"Course ID '{a.course_id}' ไม่พบในระบบ")
        assignments.append(
            LessonAssignment(
                id=a.id,
                course=course_dict[a.course_id],
                primary_group_id=a.primary_group_id,
                teacher_id=a.teacher_id,
                secondary_teacher_id=a.secondary_teacher_id,
                secondary_group_id=a.secondary_group_id,
                is_rotation=a.is_rotation,
                teaching_mode=a.teaching_mode
            )
        )

    return _run_solver(
        teachers=teachers,
        rooms=rooms,
        groups=groups,
        assignments=assignments,
        days=req.days,
        periods_per_day=req.periods_per_day,
        num_blocks=req.num_blocks,
        time_limit_seconds=req.time_limit_seconds
    )

@app.post("/api/schedule/validate-move", response_model=ValidateMoveResponse)
def api_validate_move(req: ValidateMoveRequest):
    """ตรวจสอบว่าการย้ายวิชาไปช่องเวลา/ห้องใหม่เกิดการชนหรือไม่"""
    teachers_list, rooms_list, groups_list, _, _ = data_manager.get_solver_models()
    rooms_map = {r.id: r for r in rooms_list}
    groups_map = {g.id: g for g in groups_list}
    teachers_map = {t.id: t for t in teachers_list}

    schedule_dicts = [s.model_dump() for s in req.schedule]
    is_valid, conflicts, warnings = validate_move(
        schedule=schedule_dicts,
        assignment_id=req.assignment_id,
        target_day=req.target_day,
        target_start_period=req.target_start_period,
        target_room_id=req.target_room_id,
        rooms_map=rooms_map,
        groups_map=groups_map,
        teachers_map=teachers_map
    )

    return ValidateMoveResponse(
        is_valid=is_valid,
        conflicts=conflicts,
        warnings=warnings
    )

@app.post("/api/schedule/apply-move", response_model=ApplyMoveResponse)
def api_apply_move(req: ApplyMoveRequest):
    """นำการย้ายไปอัปเดตลงในตาราง (หลังผ่านการตรวจสอบแล้ว)"""
    teachers_list, rooms_list, groups_list, _, _ = data_manager.get_solver_models()
    rooms_map = {r.id: r for r in rooms_list}
    groups_map = {g.id: g for g in groups_list}
    teachers_map = {t.id: t for t in teachers_list}

    schedule_dicts = [s.model_dump() for s in req.schedule]
    is_valid, conflicts, _ = validate_move(
        schedule=schedule_dicts,
        assignment_id=req.assignment_id,
        target_day=req.target_day,
        target_start_period=req.target_start_period,
        target_room_id=req.target_room_id,
        rooms_map=rooms_map,
        groups_map=groups_map,
        teachers_map=teachers_map
    )

    if not is_valid:
        return ApplyMoveResponse(
            is_success=False,
            message="ไม่สามารถย้ายได้เนื่องจากมีข้อขัดแย้ง: " + " | ".join(conflicts),
            updated_schedule=req.schedule
        )

    # ดำเนินการอัปเดตรายการที่ตรงกับ assignment_id
    updated_list = []
    target_room = rooms_map.get(req.target_room_id)
    room_name = target_room.name if target_room else req.target_room_id

    for item in req.schedule:
        if item.assignment_id == req.assignment_id:
            dur = item.duration
            new_item = item.model_copy(update={
                "day": req.target_day,
                "day_name": DAY_NAMES[req.target_day] if req.target_day < len(DAY_NAMES) else f"วันที่ {req.target_day+1}",
                "start_period": req.target_start_period,
                "end_period": req.target_start_period + dur - 1,
                "room_id": req.target_room_id,
                "room_name": room_name
            })
            updated_list.append(new_item)
        else:
            updated_list.append(item)

    return ApplyMoveResponse(
        is_success=True,
        message="ปรับย้ายคาบเรียนสำเร็จเรียบร้อย",
        updated_schedule=updated_list
    )

@app.post("/api/schedule/swap", response_model=SwapLessonsResponse)
def api_swap_lessons(req: SwapLessonsRequest):
    """สลับตำแหน่งคาบเรียนระหว่าง 2 วิชา (Swap Lessons) พร้อมตรวจสอบความเข้ากันได้"""
    teachers_list, rooms_list, groups_list, _, _ = data_manager.get_solver_models()
    rooms_map = {r.id: r for r in rooms_list}
    groups_map = {g.id: g for g in groups_list}
    teachers_map = {t.id: t for t in teachers_list}

    schedule_dicts = [s.model_dump() for s in req.schedule]
    is_valid, conflicts, warnings, updated_schedule_dicts = validate_swap(
        schedule=schedule_dicts,
        assignment_id_1=req.assignment_id_1,
        assignment_id_2=req.assignment_id_2,
        rooms_map=rooms_map,
        groups_map=groups_map,
        teachers_map=teachers_map
    )

    if not is_valid:
        return SwapLessonsResponse(
            is_success=False,
            message="ไม่สามารถสลับคาบเรียนได้เนื่องจากมีข้อขัดแย้ง: " + " | ".join(conflicts),
            conflicts=conflicts,
            updated_schedule=req.schedule
        )

    updated_schedule_dtos = [ScheduleEntryDTO(**item) for item in updated_schedule_dicts]
    return SwapLessonsResponse(
        is_success=True,
        message="สลับตำแหน่งคาบเรียนสำเร็จเรียบร้อย",
        conflicts=[],
        updated_schedule=updated_schedule_dtos
    )

# --- Data Management CRUD Endpoints ---

@app.get("/api/data")
def api_get_all_data():
    """ดึงข้อมูลครู ห้อง กลุ่ม รายวิชา และการมอบหมาย ทั้งหมด"""
    return data_manager.get_all_data()

@app.post("/api/data/reset")
def api_reset_data():
    """คืนค่าข้อมูลกลับสู่ค่าเริ่มต้นมาตรฐาน"""
    data_manager.reset_to_default()
    return {"message": "คืนค่าข้อมูลเริ่มต้นเรียบร้อย", "data": data_manager.get_all_data()}

@app.post("/api/teachers")
def api_add_teacher(teacher: Dict[str, Any]):
    try:
        new_t = data_manager.add_teacher(teacher)
        return {"is_success": True, "teacher": new_t}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/teachers/{teacher_id}")
def api_update_teacher(teacher_id: str, teacher: Dict[str, Any]):
    try:
        updated_t = data_manager.update_teacher(teacher_id, teacher)
        return {"is_success": True, "teacher": updated_t}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/teachers/{teacher_id}")
def api_delete_teacher(teacher_id: str):
    success = data_manager.delete_teacher(teacher_id)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบครูที่ต้องการลบ")
    return {"is_success": True, "message": "ลบครูผู้สอนเรียบร้อย"}

@app.put("/api/teachers/{teacher_id}/unavailable-slots")
def api_update_teacher_unavailable_slots(teacher_id: str, body: Dict[str, Any]):
    """อัปเดตรายการเวลาที่ไม่สะดวกสอนของครู (Unavailable Slots)"""
    slots = body.get("unavailable_slots", [])
    success = data_manager.update_teacher_unavailable_slots(teacher_id, slots)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบครูที่ต้องการอัปเดต")
    return {"is_success": True, "teacher_id": teacher_id, "unavailable_slots": slots}

@app.post("/api/rooms")
def api_add_room(room: Dict[str, Any]):
    try:
        new_r = data_manager.add_room(room)
        return {"is_success": True, "room": new_r}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/rooms/{room_id}")
def api_update_room(room_id: str, room: Dict[str, Any]):
    try:
        updated_r = data_manager.update_room(room_id, room)
        return {"is_success": True, "room": updated_r}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/rooms/{room_id}")
def api_delete_room(room_id: str):
    success = data_manager.delete_room(room_id)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบห้องเรียนที่ต้องการลบ")
    return {"is_success": True, "message": "ลบห้องเรียนเรียบร้อย"}

@app.post("/api/groups")
def api_add_group(group: Dict[str, Any]):
    try:
        new_g = data_manager.add_group(group)
        return {"is_success": True, "group": new_g}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/groups/{group_id}")
def api_update_group(group_id: str, group: Dict[str, Any]):
    try:
        updated_g = data_manager.update_group(group_id, group)
        return {"is_success": True, "group": updated_g}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/groups/{group_id}")
def api_delete_group(group_id: str):
    success = data_manager.delete_group(group_id)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบกลุ่มเรียนที่ต้องการลบ")
    return {"is_success": True, "message": "ลบกลุ่มเรียนเรียบร้อย"}

@app.post("/api/assignments")
def api_add_assignment(data: Dict[str, Any]):
    try:
        res = data_manager.add_course_assignment(data)
        return {"is_success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/assignments/{assignment_id}")
def api_update_assignment(assignment_id: str, data: Dict[str, Any]):
    try:
        res = data_manager.update_course_assignment(assignment_id, data)
        return {"is_success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/assignments/{assignment_id}")
def api_delete_assignment(assignment_id: str):
    success = data_manager.delete_course_assignment(assignment_id)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบแผนการสอนที่ต้องการลบ")
    return {"is_success": True, "message": "ลบแผนการสอนเรียบร้อย"}

@app.put("/api/assignments/{assignment_id}/pin")
def api_pin_assignment(assignment_id: str, payload: PinAssignmentRequest):
    try:
        res = data_manager.toggle_assignment_pin(
            assignment_id=assignment_id,
            is_pinned=payload.is_pinned,
            fixed_day=payload.fixed_day,
            fixed_start_period=payload.fixed_start_period,
            fixed_room_id=payload.fixed_room_id,
            external_teacher_name=payload.external_teacher_name
        )
        return {"is_success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/solve/current", response_model=SolveResponse)
def solve_current():
    """จัดตารางตามข้อมูลปัจจุบันใน Data Manager"""
    teachers, rooms, groups, _, assignments = data_manager.get_solver_models()
    return _run_solver(
        teachers=teachers,
        rooms=rooms,
        groups=groups,
        assignments=assignments,
        days=5,
        periods_per_day=12,
        num_blocks=6,
        time_limit_seconds=15.0
    )

@app.get("/api/export/excel")
def export_excel_get(view_type: str = "group", view_id: str = ""):
    """ส่งออกตารางเรียนเป็นไฟล์ Excel (.xls) จากตารางคำนวณปัจจุบัน"""
    teachers, rooms, groups, _, assignments = data_manager.get_solver_models()
    solve_res = _run_solver(
        teachers=teachers,
        rooms=rooms,
        groups=groups,
        assignments=assignments,
        days=5,
        periods_per_day=12,
        num_blocks=6,
        time_limit_seconds=15.0
    )
    
    config_data = data_manager.get_all()
    exporter = VocationalExcelExporter(
        schedule_data={"scheduled_lessons": [e.model_dump() for e in solve_res.schedule]},
        config_data=config_data
    )
    xml_content = exporter.export(view_type=view_type, view_id=view_id)
    
    filename = "timetable"
    if view_type == "all_groups":
        filename = "ตารางเรียน_ทุกกลุ่ม"
    elif view_id:
        filename = f"ตาราง_{view_type}_{view_id}"
    encoded_fn = urllib.parse.quote(f"{filename}.xls")
    
    return Response(
        content=xml_content.encode("utf-8"),
        media_type="application/vnd.ms-excel",
        headers={
            "Content-Disposition": f"attachment; filename={encoded_fn}; filename*=UTF-8''{encoded_fn}"
        }
    )

@app.post("/api/export/excel")
def export_excel_post(req: Dict[str, Any]):
    """ส่งออกตารางเรียนเป็นไฟล์ Excel (.xls) ตามข้อมูลตารางที่ระบุใน Request Body (รองรับหลัง manual move)"""
    view_type = req.get("view_type", "group")
    view_id = req.get("view_id", "")
    schedule_items = req.get("schedule", [])
    
    config_data = data_manager.get_all()
    exporter = VocationalExcelExporter(
        schedule_data={"scheduled_lessons": schedule_items},
        config_data=config_data
    )
    xml_content = exporter.export(view_type=view_type, view_id=view_id)
    
    filename = "timetable"
    if view_type == "all_groups":
        filename = "ตารางเรียน_ทุกกลุ่ม"
    elif view_id:
        filename = f"ตาราง_{view_type}_{view_id}"
    encoded_fn = urllib.parse.quote(f"{filename}.xls")
    
    return Response(
        content=xml_content.encode("utf-8"),
        media_type="application/vnd.ms-excel",
        headers={
            "Content-Disposition": f"attachment; filename={encoded_fn}; filename*=UTF-8''{encoded_fn}"
        }
    )

@app.get("/api/export/official-template")
def export_official_template_get(view_type: str = "group", view_id: str = "", block: int = 1):
    """ส่งออกตารางเรียนลงในฟอร์มแม่แบบทางการของวิทยาลัย (.xlsx) จากตารางคำนวณปัจจุบัน"""
    teachers, rooms, groups, _, assignments = data_manager.get_solver_models()
    solve_res = _run_solver(
        teachers=teachers,
        rooms=rooms,
        groups=groups,
        assignments=assignments,
        days=5,
        periods_per_day=12,
        num_blocks=6,
        time_limit_seconds=15.0
    )
    
    config_data = data_manager.get_all_data()
    schedule_dicts = [e.model_dump() for e in solve_res.schedule]
    exporter = OfficialTemplateExporter(schedule=schedule_dicts, config=config_data)

    if view_type == "all_groups":
        xlsx_bytes = exporter.export_all_groups(block=block)
        filename = f"ตารางเรียน_ทุกกลุ่ม_บล็อก{block}.xlsx"
    elif view_type == "full_college":
        xlsx_bytes = exporter.export_full_college_package(block=block)
        filename = f"ตารางเรียนตารางสอน_รวมทั้งวิทยาลัย_บล็อก{block}.xlsx"
    else:
        target_id = view_id or (groups[0].id if groups else "default")
        xlsx_bytes = exporter.export_single_view(view_type=view_type, view_id=target_id, block=block)
        filename = f"ตาราง_{view_type}_{target_id}_บล็อก{block}.xlsx"

    encoded_fn = urllib.parse.quote(filename)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={encoded_fn}; filename*=UTF-8''{encoded_fn}"
        }
    )

@app.post("/api/export/official-template")
def export_official_template_post(req: Dict[str, Any]):
    """ส่งออกตารางเรียนลงในฟอร์มแม่แบบทางการ (.xlsx) ตามสถานะปัจจุบันในเบราว์เซอร์ (รวมการลากสลับคาบ)"""
    view_type = req.get("view_type", "group")
    view_id = req.get("view_id", "")
    block = int(req.get("block", 1))
    schedule_items = req.get("schedule", [])
    
    config_data = data_manager.get_all_data()
    exporter = OfficialTemplateExporter(schedule=schedule_items, config=config_data)

    if view_type == "all_groups":
        xlsx_bytes = exporter.export_all_groups(block=block)
        filename = f"ตารางเรียน_ทุกกลุ่ม_บล็อก{block}.xlsx"
    elif view_type == "full_college":
        xlsx_bytes = exporter.export_full_college_package(block=block)
        filename = f"ตารางเรียนตารางสอน_รวมทั้งวิทยาลัย_บล็อก{block}.xlsx"
    else:
        xlsx_bytes = exporter.export_single_view(view_type=view_type, view_id=view_id, block=block)
        filename = f"ตาราง_{view_type}_{view_id}_บล็อก{block}.xlsx"

    encoded_fn = urllib.parse.quote(filename)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={encoded_fn}; filename*=UTF-8''{encoded_fn}"
        }
    )

@app.get("/api/import/template")
def get_import_template():
    """ดาวน์โหลดไฟล์แบบฟอร์มเปล่า Template (.csv พร้อม UTF-8 BOM สำหรับ Excel ภาษาไทย)"""
    csv_bytes = BulkDataImporter.get_template_csv()
    filename = "Template_แผนการเรียน_อาชีวศึกษา.csv"
    encoded_fn = urllib.parse.quote(filename)
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={encoded_fn}; filename*=UTF-8''{encoded_fn}"
        }
    )

@app.post("/api/import/process")
def process_bulk_import(req: Dict[str, Any]):
    """
    ประมวลผลนำเข้าไฟล์ CSV หรือ XLSX แบบชุด
    Body:
    - filename: str (เช่น data.csv หรือ data.xlsx)
    - content_base64: str (base64 encoded file bytes) หรือ csv_text: str
    - mode: 'replace' | 'append' (default: 'replace')
    """
    filename = req.get("filename", "upload.csv")
    mode = req.get("mode", "replace")
    
    file_bytes = None
    if "content_base64" in req and req["content_base64"]:
        # Strip potential data URL prefix (e.g. data:...;base64,)
        b64_str = req["content_base64"]
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            file_bytes = base64.b64decode(b64_str)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"ไม่สามารถถอดรหัส Base64 ของไฟล์ได้: {str(e)}")
    elif "csv_text" in req and req["csv_text"]:
        file_bytes = req["csv_text"].encode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="กรุณาระบุ content_base64 หรือ csv_text")

    try:
        result = BulkDataImporter.process_import(
            file_bytes=file_bytes,
            filename=filename,
            mode=mode,
            data_manager=data_manager
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/analytics/workload")
def api_get_workload_analytics():
    """วิเคราะห์และสรุปภาระงานสอนของครู และอัตราการใช้ห้องเรียนจากตารางปัจจุบัน"""
    teachers, rooms, groups, _, assignments = data_manager.get_solver_models()
    solve_res = _run_solver(
        teachers=teachers,
        rooms=rooms,
        groups=groups,
        assignments=assignments,
        days=5,
        periods_per_day=12,
        num_blocks=6,
        time_limit_seconds=15.0
    )
    
    config_data = data_manager.get_all_data()
    schedule_items = [e.model_dump() for e in solve_res.schedule]
    service = WorkloadAnalyticsService(schedule_items, config_data)
    return service.compute_analytics()

@app.post("/api/analytics/workload")
def api_post_workload_analytics(req: Dict[str, Any]):
    """วิเคราะห์และสรุปภาระงานสอนตามตารางที่ระบุใน Request Body (หลัง manual move)"""
    schedule_items = req.get("schedule", [])
    config_data = data_manager.get_all_data()
    service = WorkloadAnalyticsService(schedule_items, config_data)
    return service.compute_analytics()

@app.get("/api/project/export")
def api_export_project():
    """ส่งออกข้อมูลโปรเจ็คทั้งระบบ (ครู, ห้อง, กลุ่มเรียน, แผนการสอน) เป็น JSON"""
    all_data = data_manager.get_all_data()
    return {
        "version": "2.0",
        "app_name": "Smart Timetable Vocational",
        "exported_at": datetime.now().isoformat(),
        "project_data": all_data
    }

@app.post("/api/project/import")
def api_import_project(req: Dict[str, Any]):
    """นำเข้าข้อมูลโปรเจ็คเข้าสู่ฐานข้อมูลระบบ"""
    project_data = req.get("project_data", req)
    data_manager.import_project_data(project_data)
    return {
        "is_success": True,
        "message": "นำเข้าข้อมูลโปรเจ็คสำเร็จ",
        "data": data_manager.get_all_data()
    }



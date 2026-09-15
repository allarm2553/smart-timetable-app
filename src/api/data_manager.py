import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.solver.models import (
    Teacher, Room, StudentGroup, Course, LessonAssignment,
    EducationLevel, CourseType, RoomType,
    get_group_year_category, is_scout_assignment, is_activity_assignment,
    group_sort_key
)
from src.solver.benchmark_data import get_benchmark_dataset

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

def get_config_file_path() -> Path:
    env_path = os.environ.get("TIMETABLE_CONFIG_FILE")
    if env_path:
        return Path(env_path)
    return DATA_DIR / "timetable_config.json"

CONFIG_FILE = get_config_file_path()

class TimetableDataManager:
    def __init__(self):
        self.teachers: List[Dict[str, Any]] = []
        self.rooms: List[Dict[str, Any]] = []
        self.groups: List[Dict[str, Any]] = []
        self.courses: Dict[str, Dict[str, Any]] = {}
        self.assignments: List[Dict[str, Any]] = []
        self._load_or_initialize()

    def _load_or_initialize(self):
        cfg_file = get_config_file_path()
        cfg_file.parent.mkdir(exist_ok=True)
        if cfg_file.exists():
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.teachers = data.get("teachers", [])
                    self.rooms = data.get("rooms", [])
                    self.groups = data.get("groups", [])
                    self.courses = data.get("courses", {})
                    self.assignments = data.get("assignments", [])
                    self._sanitize_data()
                    return
            except Exception as e:
                print(f"Failed to load config file: {e}, resetting to benchmark.")
        self.reset_to_default()

    def _sanitize_data(self):
        """ล้างความสัมพันธ์กำพร้า (Orphan References) เพื่อป้องกัน Solver ขัดข้อง"""
        valid_group_ids = {g["id"] for g in self.groups}
        valid_teacher_ids = {t["id"] for t in self.teachers} | {"T_UNASSIGNED"}
        valid_course_ids = set(self.courses.keys())
        
        clean_assignments = []
        for a in self.assignments:
            t_id = a.get("teacher_id")
            if (a.get("primary_group_id") in valid_group_ids and
                (t_id in valid_teacher_ids or not t_id or t_id == "T_UNASSIGNED") and
                a.get("course_id") in valid_course_ids):
                
                if not t_id:
                    a["teacher_id"] = "T_UNASSIGNED"
                if a.get("secondary_group_id") and a.get("secondary_group_id") not in valid_group_ids:
                    a["secondary_group_id"] = None
                if a.get("secondary_teacher_id") and a.get("secondary_teacher_id") not in valid_teacher_ids:
                    a["secondary_teacher_id"] = None
                clean_assignments.append(a)
        
        self.assignments = clean_assignments
        self.sort_assignments()

    def sort_assignments(self):
        """จัดเรียงกลุ่มเรียนและแผนการสอนตามปี/ระดับการศึกษา (เช่น ปวช 2.2569, 2.2570, 1.2571, 2.2571) และรหัสวิชา (Natural Sort)"""
        import re
        # จัดเรียงกลุ่มเรียนตามปี/ระดับการศึกษา
        self.groups.sort(key=lambda g: group_sort_key(g.get("name", ""), g.get("id", "")))
        group_map = {g["id"]: g for g in self.groups}

        def get_sort_key(ass):
            gid = ass.get("primary_group_id", "")
            g = group_map.get(gid, {})
            g_key = group_sort_key(g.get("name", gid), gid)
            cid = ass.get("course_id", "")
            c = self.courses.get(cid, {})
            code = c.get("code", "") or cid
            chunks = re.split(r'(\d+)', str(code).strip())
            parsed_chunks = [(0, int(ch)) if ch.isdigit() else (1, ch.lower()) for ch in chunks if ch]
            return (g_key, parsed_chunks)

        self.assignments.sort(key=get_sort_key)

    def _save(self):
        cfg_file = get_config_file_path()
        cfg_file.parent.mkdir(exist_ok=True)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump({
                "teachers": self.teachers,
                "rooms": self.rooms,
                "groups": self.groups,
                "courses": self.courses,
                "assignments": self.assignments
            }, f, ensure_ascii=False, indent=2)

    def clear_all(self):
        """ล้างข้อมูลทั้งหมดในระบบออกเกลี้ยง 100% (ครู, ห้อง, กลุ่ม, วิชา, แผนการสอน)"""
        self.teachers = []
        self.rooms = []
        self.groups = []
        self.courses = {}
        self.assignments = []
        self._save()

    def reset_to_benchmark(self):
        """คืนค่าชุดข้อมูลตัวอย่างมาตรฐาน (Benchmark Dataset)"""
        dataset = get_benchmark_dataset()
        self.teachers = [
            {
                "id": t.id,
                "name": t.name,
                "max_periods_per_day": t.max_periods_per_day,
                "unavailable_slots": list(t.unavailable_slots),
                "is_head": getattr(t, "is_head", False),
                "max_periods_per_week": getattr(t, "max_periods_per_week", 28 if getattr(t, "is_head", False) else 34),
                "qualification": getattr(t, "qualification", ""),
                "special_duty": getattr(t, "special_duty", "")
            } for t in dataset["teachers"]
        ]
        self.rooms = [
            {
                "id": r.id,
                "name": r.name,
                "room_type": r.room_type.value,
                "capacity": r.capacity
            } for r in dataset["rooms"]
        ]
        self.groups = [
            {
                "id": g.id,
                "name": g.name,
                "level": g.level.value,
                "student_count": g.student_count,
                "pvs_18_weeks": getattr(g, "pvs_18_weeks", True),
                "is_internship": getattr(g, "is_internship", False)
            } for g in dataset["groups"]
        ]
        self.courses = {
            c.id: {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "course_type": c.course_type.value,
                "periods_per_session": c.periods_per_session,
                "sessions_per_week": c.sessions_per_week,
                "required_room_type": c.required_room_type.value,
                "allow_merge": c.allow_merge,
                "base_id": c.base_id
            } for c in dataset["courses"].values()
        }
        self.assignments = [
            {
                "id": a.id,
                "course_id": a.course.id,
                "primary_group_id": a.primary_group_id,
                "teacher_id": a.teacher_id,
                "secondary_teacher_id": getattr(a, "secondary_teacher_id", None),
                "secondary_group_id": a.secondary_group_id,
                "is_rotation": a.is_rotation,
                "teaching_mode": getattr(a, "teaching_mode", "SINGLE")
            } for a in dataset["assignments"]
        ]
        self._save()

    def reset_to_default(self):
        self.reset_to_benchmark()

    def get_all_data(self) -> Dict[str, Any]:
        return {
            "teachers": self.teachers,
            "rooms": self.rooms,
            "groups": self.groups,
            "courses": list(self.courses.values()),
            "assignments": self.assignments
        }

    def get_all(self) -> Dict[str, Any]:
        return self.get_all_data()

    def import_project_data(self, project_data: Dict[str, Any]):
        """นำเข้าข้อมูลโปรเจ็คทั้งระบบ (ครู, ห้อง, กลุ่มเรียน, วิชา, แผนการสอน) และบันทึกลงไฟล์"""
        if not isinstance(project_data, dict):
            return
        if "teachers" in project_data and isinstance(project_data["teachers"], list):
            self.teachers = project_data["teachers"]
        if "rooms" in project_data and isinstance(project_data["rooms"], list):
            self.rooms = project_data["rooms"]
        if "groups" in project_data and isinstance(project_data["groups"], list):
            self.groups = project_data["groups"]
        if "courses" in project_data:
            if isinstance(project_data["courses"], list):
                self.courses = {c["id"]: c for c in project_data["courses"] if isinstance(c, dict) and "id" in c}
            elif isinstance(project_data["courses"], dict):
                self.courses = project_data["courses"]
        if "assignments" in project_data and isinstance(project_data["assignments"], list):
            self.assignments = project_data["assignments"]
        self._sanitize_data()
        self._save()

    # Teachers CRUD
    def add_teacher(self, teacher_data: Dict[str, Any]) -> Dict[str, Any]:
        t_id = teacher_data.get("id") or f"T_{len(self.teachers)+1}"
        # Check if ID exists
        if any(t["id"] == t_id for t in self.teachers):
            raise ValueError(f"รหัสครู '{t_id}' มีอยู่แล้วในระบบ")
        is_head = teacher_data.get("is_head", False)
        max_week = teacher_data.get("max_periods_per_week", 28 if is_head else 34)
        new_teacher = {
            "id": t_id,
            "name": teacher_data["name"],
            "max_periods_per_day": teacher_data.get("max_periods_per_day", 6),
            "unavailable_slots": teacher_data.get("unavailable_slots", []),
            "is_head": is_head,
            "max_periods_per_week": min(max_week, 35),
            "qualification": str(teacher_data.get("qualification", "")).strip(),
            "special_duty": str(teacher_data.get("special_duty", "")).strip()
        }
        self.teachers.append(new_teacher)
        self._save()
        return new_teacher

    def delete_teacher(self, teacher_id: str) -> bool:
        before = len(self.teachers)
        self.teachers = [t for t in self.teachers if t["id"] != teacher_id]
        if len(self.teachers) < before:
            self._sanitize_data()
            self._save()
            return True
        return False

    def update_teacher(self, teacher_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        for t in self.teachers:
            if t["id"] == teacher_id:
                if "name" in data and data["name"]:
                    t["name"] = data["name"]
                if "is_head" in data:
                    t["is_head"] = bool(data["is_head"])
                    t["max_periods_per_week"] = 28 if t["is_head"] else 34
                if "max_periods_per_day" in data:
                    t["max_periods_per_day"] = int(data["max_periods_per_day"])
                if "max_periods_per_week" in data:
                    t["max_periods_per_week"] = min(int(data["max_periods_per_week"]), 35)
                if "qualification" in data:
                    t["qualification"] = str(data["qualification"]).strip()
                if "special_duty" in data:
                    t["special_duty"] = str(data["special_duty"]).strip()
                self._save()
                return t
        raise ValueError(f"ไม่พบครูผู้สอนรหัส '{teacher_id}'")

    def update_teacher_unavailable_slots(self, teacher_id: str, slots: List[List[int]]) -> bool:
        for t in self.teachers:
            if t["id"] == teacher_id:
                t["unavailable_slots"] = slots
                self._save()
                return True
        return False

    # Rooms CRUD
    def add_room(self, room_data: Dict[str, Any]) -> Dict[str, Any]:
        r_id = (room_data.get("id") or "").strip()
        if not r_id:
            idx = len(self.rooms) + 1
            while any(r["id"] == f"ROOM_{idx}" for r in self.rooms):
                idx += 1
            r_id = f"ROOM_{idx}"
        if any(r["id"] == r_id for r in self.rooms):
            raise ValueError(f"รหัสห้องเรียน '{r_id}' มีอยู่แล้วในระบบ")
        new_room = {
            "id": r_id,
            "name": room_data["name"],
            "room_type": room_data.get("room_type", RoomType.CLASSROOM.value),
            "capacity": int(room_data.get("capacity", 35))
        }
        self.rooms.append(new_room)
        self._save()
        return new_room

    def delete_room(self, room_id: str) -> bool:
        before = len(self.rooms)
        self.rooms = [r for r in self.rooms if r["id"] != room_id]
        if len(self.rooms) < before:
            self._save()
            return True
        return False

    def update_room(self, room_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        for r in self.rooms:
            if r["id"] == room_id:
                if "name" in data and data["name"]:
                    r["name"] = data["name"]
                if "room_type" in data and data["room_type"]:
                    r["room_type"] = data["room_type"]
                if "capacity" in data:
                    r["capacity"] = int(data["capacity"])
                self._save()
                return r
        raise ValueError(f"ไม่พบห้องเรียนรหัส '{room_id}'")

    # Groups CRUD
    def add_group(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        g_id = (group_data.get("id") or "").strip()
        if not g_id:
            idx = len(self.groups) + 1
            while any(g["id"] == f"G_GRP_{idx}" for g in self.groups):
                idx += 1
            g_id = f"G_GRP_{idx}"
        if any(g["id"] == g_id for g in self.groups):
            raise ValueError(f"รหัสกลุ่มเรียน '{g_id}' มีอยู่แล้วในระบบ")
        new_group = {
            "id": g_id,
            "name": group_data["name"],
            "level": group_data.get("level", EducationLevel.VOC_CERT.value),
            "student_count": int(group_data.get("student_count", 20)),
            "pvs_18_weeks": bool(group_data.get("pvs_18_weeks", True)),
            "is_internship": bool(group_data.get("is_internship", False))
        }
        self.groups.append(new_group)
        self._save()
        return new_group

    def delete_group(self, group_id: str) -> bool:
        before = len(self.groups)
        self.groups = [g for g in self.groups if g["id"] != group_id]
        if len(self.groups) < before:
            self._sanitize_data()
            self._save()
            return True
        return False

    def update_group(self, group_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        for g in self.groups:
            if g["id"] == group_id:
                if "name" in data and data["name"]:
                    g["name"] = data["name"]
                if "level" in data and data["level"]:
                    g["level"] = data["level"]
                if "student_count" in data:
                    g["student_count"] = int(data["student_count"])
                if "pvs_18_weeks" in data:
                    g["pvs_18_weeks"] = bool(data["pvs_18_weeks"])
                if "is_internship" in data:
                    g["is_internship"] = bool(data["is_internship"])
                self._save()
                return g
        raise ValueError(f"ไม่พบกลุ่มเรียนรหัส '{group_id}'")

    # Course & Assignment CRUD
    def add_course_assignment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        c_id = data.get("course_id") or f"C_{len(self.courses)+1}_{data.get('code','').replace(' ', '').replace('.', '')}"
        existing_ass_ids = {a["id"] for a in self.assignments}
        a_id = data.get("id")
        if not a_id or a_id in existing_ass_ids:
            counter = len(self.assignments) + 1
            a_id = f"L_{counter}"
            while a_id in existing_ass_ids:
                counter += 1
                a_id = f"L_{counter}"

        course_item = {
            "id": c_id,
            "name": data["name"],
            "code": data.get("code", ""),
            "course_type": data.get("course_type", CourseType.THEORY.value),
            "periods_per_session": int(data.get("periods_per_session", 2)),
            "sessions_per_week": 1,
            "required_room_type": data.get("required_room_type", RoomType.CLASSROOM.value),
            "allow_merge": bool(data.get("secondary_group_id")),
            "base_id": data.get("base_id")
        }
        self.courses[c_id] = course_item

        assignment_item = {
            "id": a_id,
            "course_id": c_id,
            "primary_group_id": data["primary_group_id"],
            "teacher_id": data["teacher_id"],
            "secondary_teacher_id": data.get("secondary_teacher_id") or None,
            "secondary_group_id": data.get("secondary_group_id") or None,
            "is_rotation": bool(data.get("is_rotation", False)),
            "teaching_mode": data.get("teaching_mode", "SINGLE"),
            "is_pinned": bool(data.get("is_pinned", False)),
            "fixed_day": data.get("fixed_day"),
            "fixed_start_period": data.get("fixed_start_period"),
            "fixed_room_id": data.get("fixed_room_id"),
            "external_teacher_name": data.get("external_teacher_name")
        }
        self.assignments.append(assignment_item)
        self._sanitize_data()
        self._save()
        return {"course": course_item, "assignment": assignment_item}

    def create_split_theory_practice_bundle(
        self,
        course_name: str,
        course_code: str,
        theory_periods: int,
        practice_periods: int,
        primary_group_id: str,
        secondary_group_id: Optional[str],
        primary_teacher_id: str,
        secondary_teacher_id: Optional[str] = None,
        teaching_mode: str = "CO_TEACHING",
        theory_room_type: str = "LECTURE_HALL",
        practice_room_type: str = "CLASSROOM",
        theory_room_id: Optional[str] = None,
        practice_room_1_id: Optional[str] = None,
        practice_room_2_id: Optional[str] = None,
        sync_parallel: bool = True,
        source_assignment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """สร้างแพ็กเกจวิชา 'ทฤษฎีเรียนรวม 2 กลุ่ม / ปฏิบัติแยกกลุ่ม'
        รองรับทั้งโหมดผู้สอนคนเดียว (Single Teacher) และสอนร่วม (Co-teaching 2 อาจารย์)
        พร้อมระบุห้องเรียนประจำหรือห้องปฏิบัติการแยกกลุ่มได้เจาะจง
        กรณี secondary_group_id=None: จัดเป็นโหมดเรียนเดี่ยว สร้างเฉพาะทฤษฎี+ปฏิบัติสำหรับ primary group เท่านั้น
        """
        import time
        import re

        clean_code = re.sub(r'[^a-zA-Z0-9]', '_', course_code).strip('_') or f"COURSE_{int(time.time())}"
        ts = int(time.time()) % 100000
        bundle_id = f"BUNDLE_{clean_code}_{ts}"

        # โหมดเรียนเดี่ยว (ไม่มีกลุ่มที่ 2)
        is_solo_mode = not secondary_group_id

        is_single_teacher = (teaching_mode == "SINGLE" or not secondary_teacher_id or secondary_teacher_id == primary_teacher_id)
        effective_secondary_teacher_id = primary_teacher_id if is_single_teacher else secondary_teacher_id
        # หากเป็นผู้สอนคนเดียว ไม่สามารถจัดคู่ขนานเวลาเดียวกันได้
        effective_sync_parallel = False if (is_single_teacher or is_solo_mode) else bool(sync_parallel)

        # ตรวจสอบประเภทห้องจากห้องจริงที่เลือก (ถ้ามี)
        rooms_dict = {r["id"]: r for r in self.rooms}
        if theory_room_id and theory_room_id in rooms_dict:
            theory_room_type = rooms_dict[theory_room_id].get("room_type", theory_room_type)
        if practice_room_1_id and practice_room_1_id in rooms_dict:
            practice_room_type = rooms_dict[practice_room_1_id].get("room_type", practice_room_type)
        elif practice_room_2_id and practice_room_2_id in rooms_dict:
            practice_room_type = rooms_dict[practice_room_2_id].get("room_type", practice_room_type)

        # 1. Master Course สำหรับทฤษฎี (สร้างเมื่อ theory_periods > 0)
        t_course_id = f"C_{clean_code}_THEORY"
        if theory_periods > 0:
            if t_course_id not in self.courses:
                self.courses[t_course_id] = {
                    "id": t_course_id,
                    "name": f"{course_name} (ทฤษฎี)",
                    "code": course_code,
                    "course_type": CourseType.THEORY.value,
                    "periods_per_session": theory_periods,
                    "sessions_per_week": 1,
                    "required_room_type": theory_room_type,
                    "allow_merge": not is_solo_mode,  # เรียนเดี่ยว = ไม่ merge
                    "base_id": None
                }
            else:
                self.courses[t_course_id]["periods_per_session"] = theory_periods
                self.courses[t_course_id]["required_room_type"] = theory_room_type

        # 2. Master Course สำหรับปฏิบัติ (สร้างเมื่อ practice_periods > 0)
        p_course_id = f"C_{clean_code}_PRAC"
        prac_code = course_code if course_code.startswith("ป.") else f"ป. {course_code}"
        if practice_periods > 0:
            if p_course_id not in self.courses:
                self.courses[p_course_id] = {
                    "id": p_course_id,
                    "name": f"{course_name} (ปฏิบัติ)",
                    "code": prac_code,
                    "course_type": CourseType.PRACTICE.value,
                    "periods_per_session": practice_periods,
                    "sessions_per_week": 1,
                    "required_room_type": practice_room_type,
                    "allow_merge": False,
                    "base_id": None
                }
            else:
                self.courses[p_course_id]["periods_per_session"] = practice_periods
                self.courses[p_course_id]["required_room_type"] = practice_room_type

        # รหัส Assignments ย่อย
        clean_g1 = re.sub(r'[^a-zA-Z0-9]', '_', primary_group_id).strip('_')
        clean_g2 = re.sub(r'[^a-zA-Z0-9]', '_', secondary_group_id).strip('_') if secondary_group_id else "SOLO"

        ass_theory_id = f"ASS_{clean_code}_T_{clean_g1}_{clean_g2}" if theory_periods > 0 else None
        ass_p1_id = f"ASS_{clean_code}_P_{clean_g1}" if practice_periods > 0 else None
        ass_p2_id = f"ASS_{clean_code}_P_{clean_g2}" if (practice_periods > 0 and not is_solo_mode) else None

        # ลบ Assignment เดิมที่ซ้ำหรือต้องการแทนที่ถ้ามี
        existing_ids = set()
        if ass_theory_id: existing_ids.add(ass_theory_id)
        if ass_p1_id: existing_ids.add(ass_p1_id)
        if ass_p2_id: existing_ids.add(ass_p2_id)
        # ลบ pattern เก่าของวิชานี้สำหรับกลุ่มนี้ด้วย
        existing_ids.add(f"ASS_{clean_code}_{clean_g1}")

        if source_assignment_id:
            src_a = self._find_assignment(source_assignment_id)
            if src_a:
                existing_ids.add(src_a["id"])
            else:
                existing_ids.add(source_assignment_id)
        self.assignments = [a for a in self.assignments if a["id"] not in existing_ids]

        assignments_to_add = []

        # 3.1 แผนการสอนทฤษฎี (ถ้ามีคาบทฤษฎี)
        if theory_periods > 0:
            ass_theory = {
                "id": ass_theory_id,
                "course_id": t_course_id,
                "primary_group_id": primary_group_id,
                "secondary_group_id": secondary_group_id if not is_solo_mode else None,
                "teacher_id": primary_teacher_id,
                "secondary_teacher_id": None,
                "is_rotation": False,
                "teaching_mode": "MERGED" if not is_solo_mode else "SINGLE",
                "is_pinned": False,
                "fixed_day": None,
                "fixed_start_period": None,
                "fixed_room_id": theory_room_id or None,
                "external_teacher_name": None,
                "parallel_with_id": None,
                "component_type": "THEORY",
                "parent_assignment_id": bundle_id
            }
            assignments_to_add.append(ass_theory)

        # 3.2 แผนการสอนปฏิบัติ กลุ่ม 1 (ถ้ามีคาบปฏิบัติ)
        if practice_periods > 0:
            ass_p1 = {
                "id": ass_p1_id,
                "course_id": p_course_id,
                "primary_group_id": primary_group_id,
                "secondary_group_id": None,
                "teacher_id": primary_teacher_id,
                "secondary_teacher_id": None,
                "is_rotation": False,
                "teaching_mode": "SINGLE",
                "is_pinned": False,
                "fixed_day": None,
                "fixed_start_period": None,
                "fixed_room_id": practice_room_1_id or None,
                "external_teacher_name": None,
                "parallel_with_id": ass_p2_id if effective_sync_parallel else None,
                "component_type": "PRACTICE",
                "parent_assignment_id": bundle_id
            }
            assignments_to_add.append(ass_p1)

            if not is_solo_mode:
                # 3.3 แผนการสอนปฏิบัติ กลุ่ม 2 (ผู้สอนคืออาจารย์ร่วม หรืออาจารย์คนเดียวกัน)
                ass_p2 = {
                    "id": ass_p2_id,
                    "course_id": p_course_id,
                    "primary_group_id": secondary_group_id,
                    "secondary_group_id": None,
                    "teacher_id": effective_secondary_teacher_id,
                    "secondary_teacher_id": None,
                    "is_rotation": False,
                    "teaching_mode": "SINGLE",
                    "is_pinned": False,
                    "fixed_day": None,
                    "fixed_start_period": None,
                    "fixed_room_id": practice_room_2_id or None,
                    "external_teacher_name": None,
                    "parallel_with_id": ass_p1_id if effective_sync_parallel else None,
                    "component_type": "PRACTICE",
                    "parent_assignment_id": bundle_id
                }
                assignments_to_add.append(ass_p2)

        self.assignments.extend(assignments_to_add)
        self._sanitize_data()
        self._save()

        return {
            "bundle_id": bundle_id,
            "theory_course": self.courses.get(t_course_id) if theory_periods > 0 else None,
            "practice_course": self.courses.get(p_course_id) if practice_periods > 0 else None,
            "assignments": assignments_to_add
        }

    def auto_add_scout_and_activities(self) -> Dict[str, Any]:
        """
        สร้างและล็อกคาบเรียนวันพุธ คาบ 7-8 อัตโนมัติ:
        - ปวช.1: วิชาลูกเสือวิสามัญ (20000-2001)
        - ปวช.2, ปวช.3: กิจกรรมองค์การวิชาชีพ (20000-2003)
        - ปวส.4 / ปวส.1-2: กิจกรรมองค์การวิชาชีพ (30000-2001)
        """
        default_teacher_id = self.teachers[0]["id"] if self.teachers else "T_UNASSIGNED"
        default_room_id = self.rooms[0]["id"] if self.rooms else None

        # ลงทะเบียนรายวิชามาตรฐานหากยังไม่มี
        if "C_SCOUT_VOC1" not in self.courses:
            self.courses["C_SCOUT_VOC1"] = {
                "name": "กิจกรรมลูกเสือวิสามัญ 1",
                "code": "20000-2001",
                "course_type": "THEORY",
                "periods_per_session": 2,
                "sessions_per_week": 1,
                "required_room_type": "CLASSROOM",
                "allow_merge": False,
                "base_id": None
            }

        if "C_ACTIVITY_VOC" not in self.courses:
            self.courses["C_ACTIVITY_VOC"] = {
                "name": "กิจกรรมองค์การวิชาชีพ 1 (ปวช.)",
                "code": "20000-2003",
                "course_type": "THEORY",
                "periods_per_session": 2,
                "sessions_per_week": 1,
                "required_room_type": "CLASSROOM",
                "allow_merge": False,
                "base_id": None
            }

        if "C_ACTIVITY_PVS" not in self.courses:
            self.courses["C_ACTIVITY_PVS"] = {
                "name": "กิจกรรมองค์การวิชาชีพ 1 (ปวส.)",
                "code": "30000-2001",
                "course_type": "THEORY",
                "periods_per_session": 2,
                "sessions_per_week": 1,
                "required_room_type": "CLASSROOM",
                "allow_merge": False,
                "base_id": None
            }

        added_count = 0
        updated_count = 0

        for g in self.groups:
            # สำหรับกลุ่มออกฝึกงานในสถานประกอบการ: ไม่ต้องล็อกตารางคาบกิจกรรม/ลูกเสือ
            if g.get("is_internship", False):
                continue

            gid = g["id"]
            gname = g.get("name", "")
            glvl = g.get("level", "VOC_CERT")
            cat = get_group_year_category(gname, glvl)

            if cat == "VOC_1":
                target_course_id = "C_SCOUT_VOC1"
                prefix = "ASG_SCOUT_"
            elif cat in ("VOC_2", "VOC_3"):
                target_course_id = "C_ACTIVITY_VOC"
                prefix = "ASG_ACT_VOC_"
            elif cat == "PVS_4":
                target_course_id = "C_ACTIVITY_PVS"
                prefix = "ASG_ACT_PVS_"
            else:
                continue

            # ตรวจสอบว่ากลุ่มนี้มี assignment ลูกเสือหรือกิจกรรมอยู่แล้วหรือไม่
            existing = None
            for a in self.assignments:
                if a.get("primary_group_id") == gid:
                    c_info = self.courses.get(a.get("course_id", ""), {})
                    c_n = c_info.get("name", "")
                    c_c = c_info.get("code", "")
                    if cat == "VOC_1" and is_scout_assignment(c_n, c_c):
                        existing = a
                        break
                    elif cat in ("VOC_2", "VOC_3", "PVS_4") and is_activity_assignment(c_n, c_c):
                        existing = a
                        break

            if existing:
                existing["is_pinned"] = True
                existing["fixed_day"] = 2
                existing["fixed_start_period"] = 7
                if not existing.get("fixed_room_id") and default_room_id:
                    existing["fixed_room_id"] = default_room_id
                updated_count += 1
            else:
                new_a = {
                    "id": f"{prefix}{gid}",
                    "course_id": target_course_id,
                    "primary_group_id": gid,
                    "teacher_id": default_teacher_id,
                    "secondary_teacher_id": None,
                    "secondary_group_id": None,
                    "is_rotation": False,
                    "teaching_mode": "SINGLE",
                    "is_pinned": True,
                    "fixed_day": 2,
                    "fixed_start_period": 7,
                    "fixed_room_id": default_room_id,
                    "external_teacher_name": None
                }
                self.assignments.append(new_a)
                added_count += 1

        self._sanitize_data()
        self._save()
        return {
            "is_success": True,
            "added_count": added_count,
            "updated_count": updated_count,
            "message": f"เพิ่ม/ล็อกคาบสำเร็จ: เพิ่มใหม่ {added_count} กลุ่ม, ปรับปรุงล็อกเวลา {updated_count} กลุ่ม (วันพุธ คาบ 7-8)"
        }


    def _find_assignment(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """ค้นหาแผนการสอนด้วย ID โดยรองรับทั้ง Exact Match และ Fallback Token/Course Code Match"""
        if not assignment_id:
            return None
        # 1. Exact match
        for a in self.assignments:
            if a["id"] == assignment_id:
                return a

        # 2. Match by alphanumeric core tokens (e.g. L_1_20000_1102 matches ASS_20000_1102_G_CHO_1_1)
        clean_id = assignment_id.replace("-", "_").replace(".", "_")
        tokens = [t for t in clean_id.split("_") if len(t) >= 4 and not t.isdigit()]
        if not tokens:
            tokens = [t for t in clean_id.split("_") if len(t) >= 3]

        if tokens:
            for a in self.assignments:
                a_clean = a["id"].replace("-", "_").replace(".", "_")
                if all(t in a_clean for t in tokens):
                    return a
            for a in self.assignments:
                a_clean = a["id"].replace("-", "_").replace(".", "_")
                if any(t in a_clean for t in tokens):
                    return a

        # 3. Match via course code or course ID
        for a in self.assignments:
            c = self.courses.get(a["course_id"], {})
            c_code = (c.get("code") or "").replace("-", "_").replace(" ", "").strip()
            if c_code and c_code in clean_id:
                return a
            if a.get("course_id", "") and a["course_id"] in clean_id:
                return a

        return None

    def delete_course_assignment(self, assignment_id: str) -> bool:
        target_a = self._find_assignment(assignment_id)
        if not target_a:
            return False
        before = len(self.assignments)
        self.assignments = [a for a in self.assignments if a["id"] != target_a["id"]]
        if len(self.assignments) < before:
            self._save()
            return True
        return False

    def update_course_assignment(self, assignment_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        target_a = self._find_assignment(assignment_id)
        if not target_a:
            raise ValueError(f"ไม่พบแผนการสอนรหัส '{assignment_id}'")

        c_id = target_a["course_id"]
        if c_id in self.courses:
            c = self.courses[c_id]
            if "name" in data and data["name"]:
                c["name"] = data["name"]
            if "code" in data:
                c["code"] = data["code"]
            if "periods_per_session" in data:
                c["periods_per_session"] = int(data["periods_per_session"])
            if "course_type" in data and data["course_type"]:
                c["course_type"] = data["course_type"]
            if "required_room_type" in data and data["required_room_type"]:
                c["required_room_type"] = data["required_room_type"]
            if "allow_merge" in data:
                c["allow_merge"] = bool(data["allow_merge"])

        if "primary_group_id" in data and data["primary_group_id"]:
            target_a["primary_group_id"] = data["primary_group_id"]
        if "secondary_group_id" in data:
            target_a["secondary_group_id"] = data["secondary_group_id"] or None
        if "teacher_id" in data:
            target_a["teacher_id"] = data["teacher_id"] or "T_UNASSIGNED"
        if "secondary_teacher_id" in data:
            target_a["secondary_teacher_id"] = data["secondary_teacher_id"] or None
        if "is_rotation" in data:
            target_a["is_rotation"] = bool(data["is_rotation"])
        if "teaching_mode" in data:
            target_a["teaching_mode"] = data["teaching_mode"]
        if "is_pinned" in data:
            target_a["is_pinned"] = bool(data["is_pinned"])
        if "fixed_day" in data:
            target_a["fixed_day"] = data["fixed_day"] if data["fixed_day"] is not None else None
        if "fixed_start_period" in data:
            target_a["fixed_start_period"] = int(data["fixed_start_period"]) if data["fixed_start_period"] is not None else None
        if "fixed_room_id" in data:
            target_a["fixed_room_id"] = data["fixed_room_id"] or None
        if "external_teacher_name" in data:
            target_a["external_teacher_name"] = data["external_teacher_name"] or None

        self._sanitize_data()
        self._save()
        return {"assignment": target_a, "course": self.courses.get(c_id)}

    def toggle_assignment_pin(self, assignment_id: str, is_pinned: bool, fixed_day: Optional[int] = None, fixed_start_period: Optional[int] = None, fixed_room_id: Optional[str] = None, external_teacher_name: Optional[str] = None) -> Dict[str, Any]:
        target_a = self._find_assignment(assignment_id)
        if not target_a:
            raise ValueError(f"ไม่พบแผนการสอนรหัส '{assignment_id}' กรุณากดปุ่ม 'ประมวลผล' เพื่อรีเฟรชตารางให้ตรงกับข้อมูลปัจจุบัน")

        target_a["is_pinned"] = is_pinned
        if is_pinned:
            if fixed_day is not None:
                target_a["fixed_day"] = fixed_day
            if fixed_start_period is not None:
                target_a["fixed_start_period"] = fixed_start_period
            if fixed_room_id is not None:
                target_a["fixed_room_id"] = fixed_room_id
            if external_teacher_name is not None:
                target_a["external_teacher_name"] = external_teacher_name
        else:
            target_a["fixed_day"] = None
            target_a["fixed_start_period"] = None
            target_a["fixed_room_id"] = None
            target_a["external_teacher_name"] = None

        self._save()
        return target_a

    # Convert to domain models for solver
    def get_solver_models(self):
        teachers = [
            Teacher(
                id=t["id"],
                name=t["name"],
                max_periods_per_day=t.get("max_periods_per_day", 6),
                unavailable_slots=set(tuple(x) for x in t.get("unavailable_slots", [])),
                is_head=t.get("is_head", False),
                max_periods_per_week=t.get("max_periods_per_week", 28 if t.get("is_head") else 34),
                qualification=t.get("qualification", ""),
                special_duty=t.get("special_duty", "")
            ) for t in self.teachers
        ]
        rooms = [
            Room(
                id=r["id"],
                name=r["name"],
                room_type=RoomType(r["room_type"]),
                capacity=r["capacity"]
            ) for r in self.rooms
        ]
        groups = [
            StudentGroup(
                id=g["id"],
                name=g["name"],
                level=EducationLevel(g["level"]),
                student_count=g["student_count"],
                pvs_18_weeks=g.get("pvs_18_weeks", True),
                is_internship=g.get("is_internship", False)
            ) for g in self.groups
        ]
        courses_dict = {
            cid: Course(
                id=c["id"],
                name=c["name"],
                code=c.get("code", ""),
                course_type=CourseType(c["course_type"]),
                periods_per_session=c["periods_per_session"],
                sessions_per_week=c.get("sessions_per_week", 1),
                required_room_type=RoomType(c["required_room_type"]),
                allow_merge=c.get("allow_merge", False),
                base_id=c.get("base_id")
            ) for cid, c in self.courses.items()
        }
        valid_group_ids = {g.id for g in groups}
        valid_teacher_ids = {t.id for t in teachers}
        assignments = []
        for a in self.assignments:
            cid = a.get("course_id")
            gid = a.get("primary_group_id")
            tid = a.get("teacher_id")

            if cid in courses_dict and gid in valid_group_ids and tid in valid_teacher_ids:
                sec_grp = a.get("secondary_group_id")
                if sec_grp and sec_grp not in valid_group_ids:
                    sec_grp = None

                sec_tch = a.get("secondary_teacher_id")
                if sec_tch and sec_tch not in valid_teacher_ids:
                    sec_tch = None

                assignments.append(
                    LessonAssignment(
                        id=a["id"],
                        course=courses_dict[cid],
                        primary_group_id=gid,
                        teacher_id=tid,
                        secondary_teacher_id=sec_tch,
                        secondary_group_id=sec_grp,
                        is_rotation=a.get("is_rotation", False),
                        teaching_mode=a.get("teaching_mode", "SINGLE"),
                        is_pinned=bool(a.get("is_pinned", False)),
                        fixed_day=a.get("fixed_day"),
                        fixed_start_period=a.get("fixed_start_period"),
                        fixed_room_id=a.get("fixed_room_id"),
                        external_teacher_name=a.get("external_teacher_name"),
                        parallel_with_id=a.get("parallel_with_id"),
                        component_type=a.get("component_type"),
                        parent_assignment_id=a.get("parent_assignment_id")
                    )
                )
        return teachers, rooms, groups, courses_dict, assignments

# Global singleton instance
data_manager = TimetableDataManager()

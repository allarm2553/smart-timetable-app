import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.solver.models import (
    Teacher, Room, StudentGroup, Course, LessonAssignment,
    EducationLevel, CourseType, RoomType
)
from src.solver.benchmark_data import get_benchmark_dataset

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CONFIG_FILE = DATA_DIR / "timetable_config.json"

class TimetableDataManager:
    def __init__(self):
        self.teachers: List[Dict[str, Any]] = []
        self.rooms: List[Dict[str, Any]] = []
        self.groups: List[Dict[str, Any]] = []
        self.courses: Dict[str, Dict[str, Any]] = {}
        self.assignments: List[Dict[str, Any]] = []
        self._load_or_initialize()

    def _load_or_initialize(self):
        DATA_DIR.mkdir(exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
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
        valid_teacher_ids = {t["id"] for t in self.teachers}
        valid_course_ids = set(self.courses.keys())
        
        clean_assignments = []
        for a in self.assignments:
            if (a.get("primary_group_id") in valid_group_ids and
                a.get("teacher_id") in valid_teacher_ids and
                a.get("course_id") in valid_course_ids):
                
                if a.get("secondary_group_id") and a.get("secondary_group_id") not in valid_group_ids:
                    a["secondary_group_id"] = None
                if a.get("secondary_teacher_id") and a.get("secondary_teacher_id") not in valid_teacher_ids:
                    a["secondary_teacher_id"] = None
                clean_assignments.append(a)
        
        self.assignments = clean_assignments

    def _save(self):
        DATA_DIR.mkdir(exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "teachers": self.teachers,
                "rooms": self.rooms,
                "groups": self.groups,
                "courses": self.courses,
                "assignments": self.assignments
            }, f, ensure_ascii=False, indent=2)

    def reset_to_default(self):
        dataset = get_benchmark_dataset()
        self.teachers = [
            {
                "id": t.id,
                "name": t.name,
                "max_periods_per_day": t.max_periods_per_day,
                "unavailable_slots": list(t.unavailable_slots),
                "is_head": getattr(t, "is_head", False),
                "max_periods_per_week": getattr(t, "max_periods_per_week", 28 if getattr(t, "is_head", False) else 34)
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
                "pvs_18_weeks": getattr(g, "pvs_18_weeks", True)
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
            "max_periods_per_week": min(max_week, 35)
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
        r_id = room_data.get("id") or f"ROOM_{len(self.rooms)+1}"
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
        g_id = group_data.get("id") or f"G_{len(self.groups)+1}"
        if any(g["id"] == g_id for g in self.groups):
            raise ValueError(f"รหัสกลุ่มเรียน '{g_id}' มีอยู่แล้วในระบบ")
        new_group = {
            "id": g_id,
            "name": group_data["name"],
            "level": group_data.get("level", EducationLevel.VOC_CERT.value),
            "student_count": int(group_data.get("student_count", 20)),
            "pvs_18_weeks": bool(group_data.get("pvs_18_weeks", True))
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
                self._save()
                return g
        raise ValueError(f"ไม่พบกลุ่มเรียนรหัส '{group_id}'")

    # Course & Assignment CRUD
    def add_course_assignment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        c_id = data.get("course_id") or f"C_{len(self.courses)+1}_{data.get('code','').replace(' ', '').replace('.', '')}"
        a_id = data.get("id") or f"L_{len(self.assignments)+1}"

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
            "teaching_mode": data.get("teaching_mode", "SINGLE")
        }
        self.assignments.append(assignment_item)
        self._sanitize_data()
        self._save()
        return {"course": course_item, "assignment": assignment_item}

    def delete_course_assignment(self, assignment_id: str) -> bool:
        before = len(self.assignments)
        self.assignments = [a for a in self.assignments if a["id"] != assignment_id]
        if len(self.assignments) < before:
            self._save()
            return True
        return False

    def update_course_assignment(self, assignment_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        target_a = None
        for a in self.assignments:
            if a["id"] == assignment_id:
                target_a = a
                break
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
        if "teacher_id" in data and data["teacher_id"]:
            target_a["teacher_id"] = data["teacher_id"]
        if "secondary_teacher_id" in data:
            target_a["secondary_teacher_id"] = data["secondary_teacher_id"] or None
        if "is_rotation" in data:
            target_a["is_rotation"] = bool(data["is_rotation"])
        if "teaching_mode" in data:
            target_a["teaching_mode"] = data["teaching_mode"]

        self._sanitize_data()
        self._save()
        return {"assignment": target_a, "course": self.courses.get(c_id)}

    # Convert to domain models for solver
    def get_solver_models(self):
        teachers = [
            Teacher(
                id=t["id"],
                name=t["name"],
                max_periods_per_day=t.get("max_periods_per_day", 6),
                unavailable_slots=set(tuple(x) for x in t.get("unavailable_slots", [])),
                is_head=t.get("is_head", False),
                max_periods_per_week=t.get("max_periods_per_week", 28 if t.get("is_head") else 34)
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
                pvs_18_weeks=g.get("pvs_18_weeks", True)
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
                        teaching_mode=a.get("teaching_mode", "SINGLE")
                    )
                )
        return teachers, rooms, groups, courses_dict, assignments

# Global singleton instance
data_manager = TimetableDataManager()

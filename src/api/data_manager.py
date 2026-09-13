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
                    return
            except Exception as e:
                print(f"Failed to load config file: {e}, resetting to benchmark.")
        self.reset_to_default()

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
            self._save()
            return True
        return False

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

    # Groups CRUD
    def add_group(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        g_id = group_data.get("id") or f"G_{len(self.groups)+1}"
        if any(g["id"] == g_id for g in self.groups):
            raise ValueError(f"รหัสกลุ่มเรียน '{g_id}' มีอยู่แล้วในระบบ")
        new_group = {
            "id": g_id,
            "name": group_data["name"],
            "level": group_data.get("level", EducationLevel.VOC_CERT.value),
            "student_count": int(group_data.get("student_count", 20))
        }
        self.groups.append(new_group)
        self._save()
        return new_group

    def delete_group(self, group_id: str) -> bool:
        before = len(self.groups)
        self.groups = [g for g in self.groups if g["id"] != group_id]
        if len(self.groups) < before:
            self._save()
            return True
        return False

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
        self._save()
        return {"course": course_item, "assignment": assignment_item}

    def delete_course_assignment(self, assignment_id: str) -> bool:
        before = len(self.assignments)
        self.assignments = [a for a in self.assignments if a["id"] != assignment_id]
        if len(self.assignments) < before:
            self._save()
            return True
        return False

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
        assignments = []
        for a in self.assignments:
            if a["course_id"] in courses_dict:
                assignments.append(
                    LessonAssignment(
                        id=a["id"],
                        course=courses_dict[a["course_id"]],
                        primary_group_id=a["primary_group_id"],
                        teacher_id=a["teacher_id"],
                        secondary_teacher_id=a.get("secondary_teacher_id"),
                        secondary_group_id=a.get("secondary_group_id"),
                        is_rotation=a.get("is_rotation", False),
                        teaching_mode=a.get("teaching_mode", "SINGLE")
                    )
                )
        return teachers, rooms, groups, courses_dict, assignments

# Global singleton instance
data_manager = TimetableDataManager()

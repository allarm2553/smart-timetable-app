import unittest
from src.solver.models import (
    Teacher, Room, StudentGroup, Course, LessonAssignment,
    EducationLevel, CourseType, RoomType
)
from src.solver.timetable_solver import TimetableSolver
from src.solver.conflict_checker import validate_move
from src.api.official_template_exporter import OfficialTemplateExporter

class TestCoTeaching(unittest.TestCase):
    def setUp(self):
        self.teachers = [
            Teacher(id="T_PONG", name="อ.พงษ์สถิต", unavailable_slots={(0, 1)}), # จันทร์ คาบ 1
            Teacher(id="T_NOPA", name="อ.นพนันท์", unavailable_slots={(1, 2)}), # อังคาร คาบ 2
            Teacher(id="T_JIRA", name="อ.จิรวัฒน์")
        ]
        self.rooms = [
            Room(id="R_546", name="546 ห้องบรรยาย", room_type=RoomType.CLASSROOM, capacity=40),
            Room(id="R_547", name="547 ช็อปยานยนต์", room_type=RoomType.LAB_ENGINE, capacity=40)
        ]
        self.groups = [
            StudentGroup(id="G1", name="ชอ.1/1", level=EducationLevel.VOC_CERT, student_count=20)
        ]
        self.courses = {
            "C_THEORY": Course(
                id="C_THEORY", name="ทฤษฎีเครื่องยนต์", code="20101-0001",
                course_type=CourseType.THEORY, periods_per_session=2,
                required_room_type=RoomType.CLASSROOM
            ),
            "C_PRACTICE_CO": Course(
                id="C_PRACTICE_CO", name="ปฏิบัติเครื่องยนต์แก๊สโซลีน", code="20101-0002",
                course_type=CourseType.PRACTICE, periods_per_session=3,
                required_room_type=RoomType.LAB_ENGINE
            )
        }
        self.assignments = [
            LessonAssignment(
                id="A_THEORY",
                course=self.courses["C_THEORY"],
                primary_group_id="G1",
                teacher_id="T_PONG"
            ),
            LessonAssignment(
                id="A_CO_PRACTICE",
                course=self.courses["C_PRACTICE_CO"],
                primary_group_id="G1",
                teacher_id="T_NOPA",
                secondary_teacher_id="T_PONG",
                teaching_mode="CO_TEACHING"
            )
        ]

    def test_solver_co_teaching_no_collision(self):
        """Solver must schedule co-teaching without collision for either primary or secondary teacher"""
        solver = TimetableSolver(
            teachers=self.teachers,
            rooms=self.rooms,
            groups=self.groups,
            assignments=self.assignments
        )
        solver.build_model()
        results = solver.solve()
        self.assertIsNotNone(results, "Solver must find a feasible solution")

        co_lesson = next((r for r in results if r["assignment"].id == "A_CO_PRACTICE"), None)
        self.assertIsNotNone(co_lesson)
        self.assertEqual(co_lesson["teacher"].id, "T_NOPA")
        self.assertEqual(co_lesson["secondary_teacher"].id, "T_PONG")

        # Must not overlap with A_THEORY
        th_lesson = next((r for r in results if r["assignment"].id == "A_THEORY"), None)
        self.assertIsNotNone(th_lesson)

        # If on same day, their period ranges must not intersect
        if co_lesson["day"] == th_lesson["day"]:
            co_range = set(range(co_lesson["start_period"], co_lesson["start_period"] + co_lesson["duration"]))
            th_range = set(range(th_lesson["start_period"], th_lesson["start_period"] + th_lesson["duration"]))
            self.assertEqual(len(co_range.intersection(th_range)), 0, "Co-taught lesson must not collide with T_PONG's theory lesson")

        # Must not be scheduled at T_PONG's unavailable slot (day 0, period 1 -> index 0)
        if co_lesson["day"] == 0:
            self.assertFalse(co_lesson["start_period"] <= 0 < co_lesson["start_period"] + co_lesson["duration"],
                             "Must respect T_PONG's unavailable slot")

        # Must not be scheduled at T_NOPA's unavailable slot (day 1, period 2 -> index 1)
        if co_lesson["day"] == 1:
            self.assertFalse(co_lesson["start_period"] <= 1 < co_lesson["start_period"] + co_lesson["duration"],
                             "Must respect T_NOPA's unavailable slot")

        print("✅ test_solver_co_teaching_no_collision passed!")

    def test_conflict_checker_secondary_teacher(self):
        """Conflict checker must block moves that collide with secondary teacher"""
        schedule = [
            {
                "assignment_id": "A_CO_PRACTICE",
                "course_name": "ปฏิบัติเครื่องยนต์แก๊สโซลีน",
                "day": 2, # พุธ
                "start_period": 1,
                "end_period": 3,
                "duration": 3,
                "room_id": "R_547",
                "room_name": "547 ช็อปยานยนต์",
                "primary_group_id": "G1",
                "teacher_id": "T_NOPA",
                "teacher_name": "อ.นพนันท์",
                "secondary_teacher_id": "T_PONG",
                "secondary_teacher_name": "อ.พงษ์สถิต",
                "active_blocks": [1, 2, 3, 4, 5, 6]
            },
            {
                "assignment_id": "A_OTHER_PONG",
                "course_name": "วิชาอื่นของพงษ์สถิต",
                "day": 3, # พฤหัสบดี
                "start_period": 1,
                "end_period": 2,
                "duration": 2,
                "room_id": "R_546",
                "room_name": "546 ห้องบรรยาย",
                "primary_group_id": "G_OTHER",
                "teacher_id": "T_PONG",
                "teacher_name": "อ.พงษ์สถิต",
                "active_blocks": [1, 2, 3, 4, 5, 6]
            }
        ]

        rooms_map = {r.id: r for r in self.rooms}
        groups_map = {g.id: g for g in self.groups}
        groups_map["G_OTHER"] = StudentGroup(id="G_OTHER", name="ชอ.1/2", level=EducationLevel.VOC_CERT, student_count=20)
        teachers_map = {t.id: t for t in self.teachers}

        # Try moving A_CO_PRACTICE to Day 3 Period 1 (collides with T_PONG's other class)
        is_valid, conflicts, warnings = validate_move(
            schedule=schedule,
            assignment_id="A_CO_PRACTICE",
            target_day=3,
            target_start_period=1,
            target_room_id="R_547",
            rooms_map=rooms_map,
            groups_map=groups_map,
            teachers_map=teachers_map
        )
        self.assertFalse(is_valid, "Should detect collision with secondary teacher T_PONG")
        self.assertTrue(any("พงษ์สถิต" in c for c in conflicts), "Conflict message should identify teacher collision")

        # Try moving A_CO_PRACTICE to Day 0 Period 1 (T_PONG unavailable slot)
        is_valid_unavail, conflicts_unavail, _ = validate_move(
            schedule=schedule,
            assignment_id="A_CO_PRACTICE",
            target_day=0,
            target_start_period=1,
            target_room_id="R_547",
            rooms_map=rooms_map,
            groups_map=groups_map,
            teachers_map=teachers_map
        )
        self.assertFalse(is_valid_unavail, "Should detect secondary teacher unavailable slot")
        self.assertTrue(any("พงษ์สถิต" in c for c in conflicts_unavail), "Should mention T_PONG unavailable slot")

        print("✅ test_conflict_checker_secondary_teacher passed!")

    def test_official_template_exporter_co_teaching(self):
        """Official template exporter must show co-taught lesson in both teachers' sheets"""
        schedule = [
            {
                "assignment_id": "A_CO_PRACTICE",
                "course_id": "C_PRACTICE_CO",
                "course_code": "20101-0002",
                "course_name": "ปฏิบัติเครื่องยนต์แก๊สโซลีน",
                "course_type": "PRACTICE",
                "day": 2,
                "start_period": 1,
                "end_period": 3,
                "duration": 3,
                "room_id": "R_547",
                "room_name": "547",
                "primary_group_id": "G1",
                "teacher_id": "T_NOPA",
                "teacher_name": "อ.นพนันท์",
                "secondary_teacher_id": "T_PONG",
                "secondary_teacher_name": "อ.พงษ์สถิต",
                "active_blocks": [1, 2, 3, 4, 5, 6]
            }
        ]

        config = {
            "teachers": [{"id": t.id, "name": t.name} for t in self.teachers],
            "rooms": [{"id": r.id, "name": r.name} for r in self.rooms],
            "groups": [{"id": g.id, "name": g.name, "student_count": g.student_count} for g in self.groups],
            "courses": [
                {
                    "id": c.id, "name": c.name, "code": c.code,
                    "course_type": c.course_type.value,
                    "periods_per_session": c.periods_per_session
                } for c in self.courses.values()
            ]
        }

        exporter = OfficialTemplateExporter(schedule=schedule, config=config)

        # 1. Export for T_NOPA (Primary Teacher)
        xlsx_nopa = exporter.export_single_view("teacher", "T_NOPA", block=1)
        self.assertGreater(len(xlsx_nopa), 5000)

        # 2. Export for T_PONG (Secondary / Co-Teacher)
        xlsx_pong = exporter.export_single_view("teacher", "T_PONG", block=1)
        self.assertGreater(len(xlsx_pong), 5000)

        # 3. Export for G1 (Student Group)
        xlsx_group = exporter.export_single_view("group", "G1", block=1)
        self.assertGreater(len(xlsx_group), 5000)

        print("✅ test_official_template_exporter_co_teaching passed!")

if __name__ == "__main__":
    unittest.main()

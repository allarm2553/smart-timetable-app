import unittest
from fastapi.testclient import TestClient
from src.solver.models import EducationLevel, CourseType, RoomType, Teacher, Room, StudentGroup, Course, LessonAssignment
from src.solver.timetable_solver import TimetableSolver
from src.api.main import app
from src.api.data_manager import data_manager

client = TestClient(app)

class TestSplitTheoryPractice(unittest.TestCase):
    def setUp(self):
        data_manager.reset_to_default()

    def test_solver_parallel_practice_and_pedagogical_precedence(self):
        """ทดสอบว่า CP-SAT จัดคาบปฏิบัติของ 2 กลุ่มให้ตรงกันเป๊ะ (Parallel) ในคนละห้อง
        และจัดทฤษฎีให้อยู่ก่อนหรือวันเดียวกับปฏิบัติ"""
        teachers = [
            Teacher(id="T_PONG", name="อ.พงษ์สถิต", max_periods_per_day=6),
            Teacher(id="T_JIRA", name="อ.จิราภรณ์", max_periods_per_day=6),
        ]
        rooms = [
            Room(id="ROOM_LECTURE", name="ห้องบรรยายรวม 541", room_type=RoomType.LECTURE_HALL, capacity=80),
            Room(id="LAB_ENG_1", name="ศูนย์ฝึกช่างยนต์ 1", room_type=RoomType.LAB_ENGINE, capacity=30),
            Room(id="LAB_ENG_2", name="ศูนย์ฝึกช่างยนต์ 2", room_type=RoomType.LAB_ENGINE, capacity=30),
        ]
        groups = [
            StudentGroup(id="G_CHO_1", name="ชอ.1/1", level=EducationLevel.VOC_CERT, student_count=25),
            StudentGroup(id="G_CHO_2", name="ชอ.1/2", level=EducationLevel.VOC_CERT, student_count=25),
        ]

        # สร้างรายวิชา ทฤษฎี (1 คาบ) และ ปฏิบัติ (3 คาบ)
        course_theory = Course(
            id="C_AUTO_THEORY",
            name="งานเครื่องยนต์ (ทฤษฎี)",
            code="20105-2001",
            course_type=CourseType.THEORY,
            periods_per_session=1,
            required_room_type=RoomType.LECTURE_HALL,
            allow_merge=True
        )
        course_practice = Course(
            id="C_AUTO_PRAC",
            name="งานเครื่องยนต์ (ปฏิบัติ)",
            code="ป. 20105-2001",
            course_type=CourseType.PRACTICE,
            periods_per_session=3,
            required_room_type=RoomType.LAB_ENGINE,
            allow_merge=False
        )

        # 3 Assignments
        ass_theory = LessonAssignment(
            id="A_THEORY_MERGED",
            course=course_theory,
            primary_group_id="G_CHO_1",
            secondary_group_id="G_CHO_2",
            teacher_id="T_PONG",
            component_type="THEORY",
            parent_assignment_id="BUNDLE_AUTO"
        )
        ass_p1 = LessonAssignment(
            id="A_PRAC_G1",
            course=course_practice,
            primary_group_id="G_CHO_1",
            teacher_id="T_PONG",
            parallel_with_id="A_PRAC_G2",
            component_type="PRACTICE",
            parent_assignment_id="BUNDLE_AUTO"
        )
        ass_p2 = LessonAssignment(
            id="A_PRAC_G2",
            course=course_practice,
            primary_group_id="G_CHO_2",
            teacher_id="T_JIRA",
            parallel_with_id="A_PRAC_G1",
            component_type="PRACTICE",
            parent_assignment_id="BUNDLE_AUTO"
        )

        solver = TimetableSolver(
            teachers=teachers,
            rooms=rooms,
            groups=groups,
            assignments=[ass_theory, ass_p1, ass_p2],
            days=5,
            periods_per_day=12
        )
        results = solver.solve(time_limit_seconds=10.0)
        self.assertEqual(len(results), 3, "ต้องจัดได้ครบทั้ง 3 รายการ")

        res_dict = {r["assignment"].id: r for r in results}
        r_theory = res_dict["A_THEORY_MERGED"]
        r_p1 = res_dict["A_PRAC_G1"]
        r_p2 = res_dict["A_PRAC_G2"]

        # 1. ตรวจสอบว่า ปฏิบัติกลุ่ม 1 และกลุ่ม 2 จัดเวลาตรงกันเป๊ะ (Parallel Start)
        self.assertEqual(r_p1["day"], r_p2["day"], "วันปฏิบัติของทั้ง 2 กลุ่มต้องตรงกัน")
        self.assertEqual(r_p1["start_period"], r_p2["start_period"], "คาบเริ่มปฏิบัติของทั้ง 2 กลุ่มต้องตรงกันเป๊ะ")

        # 2. ตรวจสอบว่า ใช้คนละห้อง และไม่ชนกัน
        self.assertNotEqual(r_p1["room"].id, r_p2["room"].id, "ห้องปฏิบัติการต้องเป็นคนละห้อง")
        self.assertIn(r_p1["room"].id, ["LAB_ENG_1", "LAB_ENG_2"])
        self.assertIn(r_p2["room"].id, ["LAB_ENG_1", "LAB_ENG_2"])

        # 3. ตรวจสอบ Pedagogical Precedence (ทฤษฎีต้องเรียนก่อนหรือวันเดียวกับปฏิบัติ)
        self.assertLessEqual(r_theory["day"], r_p1["day"], "ทฤษฎีต้องเรียนก่อนหรือวันเดียวกับปฏิบัติ")

        print("✅ test_solver_parallel_practice_and_pedagogical_precedence passed: Parallel practice and theory precedence 100% verified!")

    def test_api_split_theory_practice_bundle_creation(self):
        """ทดสอบการเรียก REST API /api/courses/split-theory-practice"""
        payload = {
            "course_name": "งานไฟฟ้ารถยนต์",
            "course_code": "20105-2003",
            "theory_periods": 1,
            "practice_periods": 4,
            "primary_group_id": "G_CHO_1_1",
            "secondary_group_id": "G_CHO_1_2",
            "primary_teacher_id": "T_PONG",
            "secondary_teacher_id": "T_THONG",
            "theory_room_type": "LECTURE_HALL",
            "practice_room_type": "CLASSROOM",
            "sync_parallel": True
        }

        res = client.post("/api/courses/split-theory-practice", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_success"])
        b_data = data["data"]
        self.assertEqual(len(b_data["assignments"]), 3)

        ass_types = {a["component_type"] for a in b_data["assignments"]}
        self.assertIn("THEORY", ass_types)
        self.assertIn("PRACTICE", ass_types)

        # ทดสอบการสั่ง Solve ตารางปัจจุบัน
        solve_res = client.post("/api/solve/current")
        self.assertEqual(solve_res.status_code, 200)
        s_data = solve_res.json()
        self.assertTrue(s_data["is_success"])

        print("✅ test_api_split_theory_practice_bundle_creation passed: API created 3 assignments and solver scheduled them successfully!")

if __name__ == "__main__":
    unittest.main()

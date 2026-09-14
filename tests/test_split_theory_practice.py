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

    def test_single_teacher_mode_and_same_room_scheduling(self):
        """ทดสอบโหมดผู้สอนคนเดียว (Single Teacher):
        ครูคนเดียวสอนทฤษฎีรวม และสอนปฏิบัติทั้งกลุ่ม 1 และกลุ่ม 2 ในห้องปฏิบัติการเดียวกัน
        ระบบต้องจัดเวลาปฏิบัติคนละช่วงเวลา โดยไม่มีการชนคาบสอนของครู และไม่มีการชนห้องเรียน"""
        payload = {
            "course_name": "งานเชื่อมโลหะแผ่น",
            "course_code": "20103-1002",
            "theory_periods": 1,
            "practice_periods": 3,
            "primary_group_id": "G_CHO_1_1",
            "secondary_group_id": "G_CHO_1_2",
            "primary_teacher_id": "T_PONG",
            "teaching_mode": "SINGLE",
            "theory_room_id": "R1",
            "practice_room_1_id": "R2",
            "practice_room_2_id": "R2",  # ทั้งสองกลุ่มใช้ห้องปฏิบัติการเดียวกัน
            "sync_parallel": False
        }

        res = client.post("/api/courses/split-theory-practice", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_success"])
        assignments = data["data"]["assignments"]

        # ตรวจสอบว่า Assignment ปฏิบัติทั้ง 2 ใช้ครูคนเดียวกัน และไม่มี parallel_with_id
        prac_ass = [a for a in assignments if a["component_type"] == "PRACTICE"]
        self.assertEqual(len(prac_ass), 2)
        self.assertEqual(prac_ass[0]["teacher_id"], "T_PONG")
        self.assertEqual(prac_ass[1]["teacher_id"], "T_PONG")
        self.assertIsNone(prac_ass[0]["parallel_with_id"])
        self.assertIsNone(prac_ass[1]["parallel_with_id"])
        self.assertEqual(prac_ass[0]["fixed_room_id"], "R2")
        self.assertEqual(prac_ass[1]["fixed_room_id"], "R2")

        # สั่งจัดตาราง
        solve_res = client.post("/api/solve/current")
        self.assertEqual(solve_res.status_code, 200)
        s_data = solve_res.json()
        self.assertTrue(s_data["is_success"])

        # ค้นหาผลลัพธ์ของคาบปฏิบัติทั้งสอง
        p1_res = next(x for x in s_data["schedule"] if x["assignment_id"] == prac_ass[0]["id"])
        p2_res = next(x for x in s_data["schedule"] if x["assignment_id"] == prac_ass[1]["id"])

        # ตรวจสอบว่าจัดในห้อง R2 ทั้งคู่
        self.assertEqual(p1_res["room_id"], "R2")
        self.assertEqual(p2_res["room_id"], "R2")

        # ตรวจสอบว่าไม่ชนเวลากัน (เพราะครูคนเดียวกัน และห้องเดียวกัน)
        if p1_res["day"] == p2_res["day"]:
            s1, e1 = p1_res["start_period"], p1_res["end_period"]
            s2, e2 = p2_res["start_period"], p2_res["end_period"]
            self.assertTrue(e1 < s2 or e2 < s1, "หากจัดในวันเดียวกัน คาบต้องไม่ซ้อนทับกันเด็ดขาด")

        print("✅ test_single_teacher_mode_and_same_room_scheduling passed: Single teacher with shared lab scheduled without conflict!")

    def test_designated_separate_lab_rooms_co_teaching(self):
        """ทดสอบโหมดสอนร่วม (Co-teaching) ที่ระบุห้องปฏิบัติการประจำคนละห้อง:
        กลุ่ม 1 ใช้ R1, กลุ่ม 2 ใช้ R2 จัดแบบคู่ขนานเวลาเดียวกัน"""
        payload = {
            "course_name": "งานทดสอบเครื่องกล",
            "course_code": "20101-2005",
            "theory_periods": 1,
            "practice_periods": 3,
            "primary_group_id": "G_CHO_1_1",
            "secondary_group_id": "G_CHO_1_2",
            "primary_teacher_id": "T_PONG",
            "secondary_teacher_id": "T_THONG",
            "teaching_mode": "CO_TEACHING",
            "theory_room_id": "R3",
            "practice_room_1_id": "R1",
            "practice_room_2_id": "R2",
            "sync_parallel": True
        }

        res = client.post("/api/courses/split-theory-practice", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        assignments = data["data"]["assignments"]

        solve_res = client.post("/api/solve/current")
        self.assertEqual(solve_res.status_code, 200)
        s_data = solve_res.json()
        self.assertTrue(s_data["is_success"])

        prac_ass = [a for a in assignments if a["component_type"] == "PRACTICE"]
        p1_res = next(x for x in s_data["schedule"] if x["assignment_id"] == prac_ass[0]["id"])
        p2_res = next(x for x in s_data["schedule"] if x["assignment_id"] == prac_ass[1]["id"])

        self.assertEqual(p1_res["room_id"], "R1", "กลุ่ม 1 ต้องได้ห้องประจำ R1")
        self.assertEqual(p2_res["room_id"], "R2", "กลุ่ม 2 ต้องได้ห้องประจำ R2")
        self.assertEqual(p1_res["day"], p2_res["day"], "ต้องเรียนวันเดียวกันแบบคู่ขนาน")
        self.assertEqual(p1_res["start_period"], p2_res["start_period"], "ต้องเริ่มคาบเดียวกันแบบคู่ขนาน")

        print("✅ test_designated_separate_lab_rooms_co_teaching passed: Separate designated rooms parallel scheduled accurately!")

if __name__ == "__main__":
    unittest.main()

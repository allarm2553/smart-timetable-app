import unittest
from src.solver.models import Teacher, StudentGroup, EducationLevel, Room, RoomType, Course, CourseType, LessonAssignment
from src.solver.timetable_solver import TimetableSolver
from src.solver.conflict_checker import validate_move
from src.api.data_manager import TimetableDataManager

class TestInternshipGroup(unittest.TestCase):
    def test_internship_group_model(self):
        """ตรวจสอบว่า StudentGroup รองรับ is_internship"""
        grp_regular = StudentGroup(id="G_REG", name="ชฟ.1/1", level=EducationLevel.VOC_CERT, student_count=20, is_internship=False)
        self.assertFalse(grp_regular.is_internship)

        grp_intern = StudentGroup(id="G_INTERN", name="ปวส.2/1 ทวิ", level=EducationLevel.HIGH_VOC_CERT, student_count=20, is_internship=True)
        self.assertTrue(grp_intern.is_internship)

    def test_internship_solver_theory_evening_and_practice_daytime(self):
        """
        ทดสอบกฎการจัดตารางสำหรับกลุ่มฝึกงานสถานประกอบการ / ทวิภาคี:
        1. รายวิชาทฤษฎี (THEORY) ต้องจัดหลัง 18:00 น. (คาบ 11-12, start_period index >= 10)
        2. รายวิชาปฏิบัติ (PRACTICE) จัดช่วงกลางวันได้ (คาบ 1-10, start_period index < 10)
        3. กลุ่มเรียนปกติ (is_internship=False) จัดช่วงกลางวันเท่านั้น
        """
        teachers = [
            Teacher(id="T1", name="อ.นิเทศ", max_periods_per_day=8, is_head=False),
            Teacher(id="T2", name="อ.ประจำกลุ่ม", max_periods_per_day=8, is_head=False)
        ]
        rooms = [
            Room(id="R1", name="ห้องทฤษฎี", room_type=RoomType.CLASSROOM, capacity=40),
            Room(id="R2", name="โรงฝึกงาน", room_type=RoomType.LAB_ENGINE, capacity=40)
        ]
        groups = [
            # กลุ่มฝึกงาน ปวส.ทวิ
            StudentGroup(id="G_INTERN", name="ปวส.2 ทวิ", level=EducationLevel.HIGH_VOC_CERT, student_count=20, is_internship=True),
            # กลุ่มเรียนปกติ ปวช.
            StudentGroup(id="G_REGULAR", name="ปวช.1 ปกติ", level=EducationLevel.VOC_CERT, student_count=25, is_internship=False)
        ]

        c_intern_theory = Course(id="C_ITH", name="สัมมนาฝึกงาน (ทฤษฎี)", course_type=CourseType.THEORY, periods_per_session=2)
        c_intern_prac = Course(id="C_IPR", name="ปฏิบัติการวิชาชีพ", course_type=CourseType.PRACTICE, periods_per_session=3, required_room_type=RoomType.LAB_ENGINE)
        c_reg_theory = Course(id="C_RTH", name="คณิตศาสตร์ช่าง", course_type=CourseType.THEORY, periods_per_session=2)

        assignments = [
            LessonAssignment(id="L_ITH", course=c_intern_theory, primary_group_id="G_INTERN", teacher_id="T1"),
            LessonAssignment(id="L_IPR", course=c_intern_prac, primary_group_id="G_INTERN", teacher_id="T1"),
            LessonAssignment(id="L_RTH", course=c_reg_theory, primary_group_id="G_REGULAR", teacher_id="T2")
        ]

        solver = TimetableSolver(teachers=teachers, rooms=rooms, groups=groups, assignments=assignments)
        solver.build_model()
        results = solver.solve()

        self.assertIsNotNone(results, "Solver ควรหาคำตอบที่ Feasible ได้")
        
        results_by_id = {r["assignment"].id: r for r in results}

        # 1. วิชาทฤษฎีของกลุ่มฝึกงาน ต้องจัดหลัง 18:00 น. (start_period index 10 หรือ 11)
        res_ith = results_by_id["L_ITH"]
        self.assertGreaterEqual(res_ith["start_period"], 10, "วิชาทฤษฎีของกลุ่มฝึกงานต้องเริ่มที่คาบ 11 (index 10) ขึ้นไป")
        self.assertLessEqual(res_ith["start_period"] + res_ith["duration"], 12)

        # 2. วิชาปฏิบัติของกลุ่มฝึกงาน จัดกลางวันได้ (start_period index < 10)
        res_ipr = results_by_id["L_IPR"]
        self.assertLess(res_ipr["start_period"], 10, "วิชาปฏิบัติของกลุ่มฝึกงานสามารถจัดช่วงกลางวันได้")
        self.assertLessEqual(res_ipr["start_period"] + res_ipr["duration"], 10)

        # 3. วิชาปกติ ต้องอยู่กลางวันเท่านั้น (start_period + duration <= 10)
        res_rth = results_by_id["L_RTH"]
        self.assertLessEqual(res_rth["start_period"] + res_rth["duration"], 10, "วิชาของกลุ่มปกติต้องอยู่ในช่วงกลางวัน")

    def test_conflict_checker_internship_theory_warning(self):
        """ทดสอบ ConflictChecker ตักเตือนเมื่อย้ายวิชาทฤษฎีของกลุ่มฝึกงานไปลงเวลากลางวัน"""
        groups_map = {
            "G_INTERN": StudentGroup(id="G_INTERN", name="ปวส.ทวิ", level=EducationLevel.HIGH_VOC_CERT, student_count=20, is_internship=True)
        }
        rooms_map = {
            "R1": Room(id="R1", name="101", room_type=RoomType.CLASSROOM, capacity=30)
        }
        schedule = [
            {
                "assignment_id": "L1",
                "course_name": "ทฤษฎีออนไลน์",
                "course_type": "theory",
                "primary_group_id": "G_INTERN",
                "teacher_id": "T1",
                "teacher_name": "อ.ทดสอบ",
                "day": 0,
                "start_period": 11,
                "duration": 2,
                "room_id": "R1"
            }
        ]

        # ย้ายไปคาบที่ 2 (09:00 กลางวัน) -> ต้องมีคำเตือน
        is_valid, conflicts, warnings = validate_move(
            schedule=schedule,
            assignment_id="L1",
            target_day=0,
            target_start_period=2,
            target_room_id="R1",
            rooms_map=rooms_map,
            groups_map=groups_map
        )
        self.assertTrue(is_valid)
        self.assertTrue(any("หลัง 18:00" in w for w in warnings), f"ควรมีคำเตือนเรื่องเวลาหลัง 18:00 แต่ได้: {warnings}")

    def test_data_manager_crud_internship(self):
        """ทดสอบว่า DataManager บันทึกและดึงข้อมูล is_internship ของกลุ่มเรียนได้ถูกต้อง"""
        from fastapi.testclient import TestClient
        from src.api.main import app
        client = TestClient(app)

        try:
            # 1. เพิ่มกลุ่มฝึกงาน
            res_add = client.post("/api/groups", json={
                "id": "G_TEST_INTERN",
                "name": "ปวส.2/1 ทวิภาคี (ทดสอบ)",
                "level": "HIGH_VOC_CERT",
                "student_count": 22,
                "is_internship": True
            })
            self.assertEqual(res_add.status_code, 200)
            self.assertTrue(res_add.json()["is_success"])

            # 2. ตรวจสอบข้อมูลจาก /api/data
            res_data = client.get("/api/data")
            groups = res_data.json()["groups"]
            g = next(x for x in groups if x["id"] == "G_TEST_INTERN")
            self.assertTrue(g.get("is_internship", False))

            # 3. แก้ไขข้อมูลผ่าน PUT
            res_put = client.put("/api/groups/G_TEST_INTERN", json={
                "is_internship": False
            })
            self.assertEqual(res_put.status_code, 200)
            self.assertFalse(res_put.json()["group"]["is_internship"])
        finally:
            client.delete("/api/groups/G_TEST_INTERN")

if __name__ == '__main__':
    unittest.main()

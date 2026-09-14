import unittest
from src.solver.models import (
    Teacher, Room, StudentGroup, Course, LessonAssignment,
    EducationLevel, CourseType, RoomType,
    get_group_year_category, is_scout_assignment, is_activity_assignment
)
from src.solver.timetable_solver import TimetableSolver
from src.solver.conflict_checker import validate_move

class TestScoutActivityWednesday(unittest.TestCase):

    def test_group_year_classification(self):
        """ทดสอบการจำแนกระดับชั้นปีของกลุ่มเรียน"""
        self.assertEqual(get_group_year_category("ชอ.1/1", "VOC_CERT"), "VOC_1")
        self.assertEqual(get_group_year_category("ปวช.1 ช่างยนต์", "VOC_CERT"), "VOC_1")
        self.assertEqual(get_group_year_category("ปวช. 1", "VOC_CERT"), "VOC_1")
        
        self.assertEqual(get_group_year_category("ชอ.2/1", "VOC_CERT"), "VOC_2")
        self.assertEqual(get_group_year_category("ปวช.2", "VOC_CERT"), "VOC_2")
        
        self.assertEqual(get_group_year_category("ชอ.3/1", "VOC_CERT"), "VOC_3")
        self.assertEqual(get_group_year_category("ปวช.3", "VOC_CERT"), "VOC_3")
        
        self.assertEqual(get_group_year_category("ชอ.4/1", "HIGH_VOC_CERT"), "PVS_4")
        self.assertEqual(get_group_year_category("ปวส.4/1", "HIGH_VOC_CERT"), "PVS_4")
        self.assertEqual(get_group_year_category("ปวส.1", "HIGH_VOC_CERT"), "PVS_4")
        self.assertEqual(get_group_year_category("ปวส.2", "HIGH_VOC_CERT"), "PVS_4")
        self.assertEqual(get_group_year_category("กลุ่ม ปวส.", "HIGH_VOC_CERT"), "PVS_4")

    def test_scout_activity_course_detection(self):
        """ทดสอบการระบุวิชาลูกเสือและวิชากิจกรรม"""
        self.assertTrue(is_scout_assignment("กิจกรรมลูกเสือวิสามัญ 1", "20000-2001"))
        self.assertTrue(is_scout_assignment("วิชาลูกเสือ", "20000-2002"))
        self.assertFalse(is_scout_assignment("งานเครื่องยนต์แก๊สโซลีน", "20101-2001"))

        self.assertTrue(is_activity_assignment("กิจกรรมองค์การวิชาชีพ 1", "20000-2003"))
        self.assertTrue(is_activity_assignment("กิจกรรมชมรมวิชาชีพ", "30000-2001"))
        self.assertFalse(is_activity_assignment("กิจกรรมลูกเสือวิสามัญ 1", "20000-2001"))

    def test_solver_pins_scout_for_voc1_and_blocks_normal_courses(self):
        """ทดสอบว่า Solver จัดวิชาลูกเสือของ ปวช.1 ในวันพุธ คาบ 7-8 และห้ามวิชาอื่นจัดทับ"""
        teachers = [
            Teacher(id="T1", name="อ. สมชาย"),
            Teacher(id="T2", name="อ. สมหญิง")
        ]
        rooms = [
            Room(id="R1", name="ห้อง 101", room_type=RoomType.CLASSROOM, capacity=40),
            Room(id="R2", name="สนาม/หอประชุม", room_type=RoomType.CLASSROOM, capacity=100)
        ]
        groups = [
            StudentGroup(id="G_VOC1", name="ชอ.1/1", level=EducationLevel.VOC_CERT, student_count=25),
            StudentGroup(id="G_PVS4", name="ชอ.4/1", level=EducationLevel.HIGH_VOC_CERT, student_count=20)
        ]

        scout_course = Course(
            id="C_SCOUT",
            name="กิจกรรมลูกเสือวิสามัญ 1",
            code="20000-2001",
            course_type=CourseType.THEORY,
            periods_per_session=2
        )
        activity_course = Course(
            id="C_ACT",
            name="กิจกรรมองค์การวิชาชีพ 1",
            code="30000-2001",
            course_type=CourseType.THEORY,
            periods_per_session=2
        )
        normal_course = Course(
            id="C_MATH",
            name="คณิตศาสตร์พื้นฐาน",
            code="20000-1401",
            course_type=CourseType.THEORY,
            periods_per_session=2
        )

        assignments = [
            LessonAssignment(id="A_SCOUT_VOC1", course=scout_course, primary_group_id="G_VOC1", teacher_id="T1"),
            LessonAssignment(id="A_ACT_PVS4", course=activity_course, primary_group_id="G_PVS4", teacher_id="T2"),
            LessonAssignment(id="A_NORM_VOC1", course=normal_course, primary_group_id="G_VOC1", teacher_id="T1")
        ]

        solver = TimetableSolver(
            teachers=teachers,
            rooms=rooms,
            groups=groups,
            assignments=assignments,
            days=5,
            periods_per_day=12
        )
        schedule = solver.solve(time_limit_seconds=10.0)
        self.assertIsNotNone(schedule)

        scout_res = next((s for s in schedule if s["assignment"].id == "A_SCOUT_VOC1"), None)
        act_res = next((s for s in schedule if s["assignment"].id == "A_ACT_PVS4"), None)
        norm_res = next((s for s in schedule if s["assignment"].id == "A_NORM_VOC1"), None)

        self.assertIsNotNone(scout_res)
        self.assertEqual(scout_res["day"], 2, "วิชาลูกเสือ ปวช.1 ต้องจัดวันพุธ (day index 2)")
        self.assertEqual(scout_res["start_period"], 6, "วิชาลูกเสือ ปวช.1 ต้องเริ่มคาบ 7 (0-indexed period 6)")
        self.assertEqual(scout_res["duration"], 2, "วิชาลูกเสือ ปวช.1 ต้องมีความยาว 2 คาบ (คาบ 7-8)")

        self.assertIsNotNone(act_res)
        self.assertEqual(act_res["day"], 2, "วิชากิจกรรม ปวส.4 ต้องจัดวันพุธ (day index 2)")
        self.assertEqual(act_res["start_period"], 6, "วิชากิจกรรม ปวส.4 ต้องเริ่มคาบ 7 (0-indexed period 6)")
        self.assertEqual(act_res["duration"], 2, "วิชากิจกรรม ปวส.4 ต้องมีความยาว 2 คาบ (คาบ 7-8)")

        # วิชาปกติของ ปวช.1 ต้องไม่จัดทับวันพุธ คาบ 7-8 (0-indexed 6 และ 7)
        if norm_res and norm_res["day"] == 2:
            p_start = norm_res["start_period"]
            p_end = p_start + norm_res["duration"] - 1
            self.assertFalse(
                max(p_start, 6) <= min(p_end, 7),
                "วิชาปกติไม่สามารถจัดทับวันพุธ คาบ 7-8 ได้"
            )

    def test_conflict_checker_wednesday_protection(self):
        """ทดสอบว่า Conflict Checker ดักจับการย้ายวิชาผิดเงื่อนไขวันพุธ คาบ 7-8 ได้อย่างถูกต้อง"""
        r1 = Room(id="R1", name="ห้อง 101", room_type=RoomType.CLASSROOM, capacity=40)
        g_voc1 = StudentGroup(id="G1", name="ปวช.1/1", level=EducationLevel.VOC_CERT, student_count=20)
        g_voc2 = StudentGroup(id="G2", name="ปวช.2/1", level=EducationLevel.VOC_CERT, student_count=20)
        rooms_map = {"R1": r1}
        groups_map = {"G1": g_voc1, "G2": g_voc2}

        # ตารางจำลอง
        schedule = [
            {
                "assignment_id": "NORM_1",
                "course_name": "ภาษาอังกฤษธุรกิจ",
                "course_code": "20000-1201",
                "course_type": "THEORY",
                "primary_group_id": "G1",
                "teacher_id": "T1",
                "teacher_name": "อ. สมคิด",
                "room_id": "R1",
                "day": 0,
                "start_period": 1,
                "end_period": 2,
                "duration": 2,
                "active_blocks": [0, 1, 2, 3, 4, 5]
            },
            {
                "assignment_id": "SCOUT_1",
                "course_name": "กิจกรรมลูกเสือวิสามัญ 1",
                "course_code": "20000-2001",
                "course_type": "THEORY",
                "primary_group_id": "G1",
                "teacher_id": "T1",
                "teacher_name": "อ. สมคิด",
                "room_id": "R1",
                "day": 2,
                "start_period": 7,
                "end_period": 8,
                "duration": 2,
                "active_blocks": [0, 1, 2, 3, 4, 5]
            }
        ]

        # 1. ย้ายวิชาปกติไปวันพุธ คาบ 7 ต้องเกิด Conflict
        is_valid, confs, warns = validate_move(
            schedule=schedule,
            assignment_id="NORM_1",
            target_day=2,
            target_start_period=7,
            target_room_id="R1",
            rooms_map=rooms_map,
            groups_map=groups_map
        )
        self.assertFalse(is_valid)
        self.assertTrue(any("สงวนไว้สำหรับวิชาลูกเสือวิสามัญ" in c for c in confs))

        # 2. ย้ายวิชาลูกเสือวิสามัญออกจากวันพุธ คาบ 7 (เช่น ไปวันจันทร์ คาบ 3) ต้องเกิด Conflict
        is_valid_scout, confs_scout, _ = validate_move(
            schedule=schedule,
            assignment_id="SCOUT_1",
            target_day=0,
            target_start_period=3,
            target_room_id="R1",
            rooms_map=rooms_map,
            groups_map=groups_map
        )
        self.assertFalse(is_valid_scout)
        self.assertTrue(any("เงื่อนไขล็อกตายตัวในวันพุธ คาบที่ 7–8" in c for c in confs_scout))

if __name__ == "__main__":
    unittest.main()

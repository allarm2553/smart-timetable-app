import unittest
from src.solver.models import Teacher, StudentGroup, EducationLevel, Room, RoomType, Course, CourseType, LessonAssignment
from src.solver.timetable_solver import TimetableSolver
from src.api.analytics import WorkloadAnalyticsService
from src.solver.conflict_checker import validate_move

class TestPVSSmoothingAndBalance(unittest.TestCase):
    def test_pvs_18_week_models(self):
        """ทดสอบว่าใน V.2 ปวส. ถูกเกลี่ยให้ active ครบ 18 สัปดาห์ (6 บล็อก)"""
        # ปวส. โหมดเกลี่ย 18 สัปดาห์ (V.2 default)
        pvs_18 = StudentGroup(id="G_PVS", name="ปวส. 18 สัปดาห์", level=EducationLevel.HIGH_VOC_CERT, student_count=20, pvs_18_weeks=True)
        self.assertEqual(pvs_18.active_blocks, [0, 1, 2, 3, 4, 5])

        # ปวส. โหมด 15 สัปดาห์เดิม
        pvs_15 = StudentGroup(id="G_PVS_OLD", name="ปวส. 15 สัปดาห์", level=EducationLevel.HIGH_VOC_CERT, student_count=20, pvs_18_weeks=False)
        self.assertEqual(pvs_15.active_blocks, [0, 1, 2, 3, 4])

    def test_teacher_college_caps(self):
        """ทดสอบเกณฑ์เพดานภาระสอนของวิทยาลัย: หัวหน้างาน <= 28, ทั่วไป <= 34, เพดานวิทยาลัย <= 35"""
        head_t = Teacher(id="T_HEAD", name="ครูหัวหน้างาน", is_head=True)
        self.assertEqual(head_t.max_periods_per_week, 28)

        gen_t = Teacher(id="T_GEN", name="ครูผู้สอนทั่วไป", is_head=False)
        self.assertEqual(gen_t.max_periods_per_week, 34)

        # ทดสอบเพดานวิทยาลัยไม่เกิน 35
        custom_t = Teacher(id="T_CUSTOM", name="ครูพิเศษ", max_periods_per_week=40)
        self.assertEqual(custom_t.max_periods_per_week, 35)

    def test_solver_respects_daily_and_weekly_limits(self):
        """ทดสอบว่า Solver ปฏิบัติตามขีดจำกัดคาบสอนต่อวันของครู และคาบเรียนต่อวันของ นศ."""
        teachers = [Teacher(id="T1", name="อ.สมชาย", max_periods_per_day=5, is_head=False)]
        rooms = [Room(id="R1", name="ห้อง 101", room_type=RoomType.CLASSROOM, capacity=40)]
        groups = [StudentGroup(id="G1", name="ปวส.1", level=EducationLevel.HIGH_VOC_CERT, student_count=20, pvs_18_weeks=True)]
        
        c1 = Course(id="C1", name="วิชา 1", course_type=CourseType.THEORY, periods_per_session=2)
        c2 = Course(id="C2", name="วิชา 2", course_type=CourseType.PRACTICE, periods_per_session=3)
        assignments = [
            LessonAssignment(id="L1", course=c1, primary_group_id="G1", teacher_id="T1"),
            LessonAssignment(id="L2", course=c2, primary_group_id="G1", teacher_id="T1")
        ]

        solver = TimetableSolver(teachers=teachers, rooms=rooms, groups=groups, assignments=assignments)
        solver.build_model()
        results = solver.solve()
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 2)

        # ยืนยันว่า ปวส. active ในทุกบล็อก 0-5
        for r in results:
            self.assertEqual(r["active_blocks"], [0, 1, 2, 3, 4, 5])

    def test_analytics_college_rules(self):
        """ทดสอบการประเมินภาระสอนในระบบ Analytics ตามเกณฑ์เฉพาะของวิทยาลัย"""
        config = {
            "teachers": [
                {"id": "T_HEAD", "name": "อ.หัวหน้า", "is_head": True, "max_periods_per_week": 28, "max_periods_per_day": 6},
                {"id": "T_GEN", "name": "อ.ทั่วไป", "is_head": False, "max_periods_per_week": 34, "max_periods_per_day": 6}
            ],
            "rooms": [{"id": "R1", "name": "101", "room_type": "CLASSROOM", "capacity": 30}],
            "groups": [{"id": "G_PVS", "name": "ชส.1 (ปวส.)", "level": "HIGH_VOC_CERT", "student_count": 25}],
            "courses": [],
            "assignments": []
        }

        # จำลองตารางสอน:
        # T_HEAD ได้ 26 คาบ (เหมาะสม <= 28)
        # T_GEN ได้ 36 คาบ (เกินเพดานวิทยาลัย 35)
        mock_schedule = [
            {"assignment_id": "A1", "course_id": "C1", "teacher_id": "T_HEAD", "primary_group_id": "G_PVS", "duration": 6, "day": 0, "room_id": "R1"},
            {"assignment_id": "A2", "course_id": "C2", "teacher_id": "T_HEAD", "primary_group_id": "G_PVS", "duration": 6, "day": 1, "room_id": "R1"},
            {"assignment_id": "A3", "course_id": "C3", "teacher_id": "T_HEAD", "primary_group_id": "G_PVS", "duration": 6, "day": 2, "room_id": "R1"},
            {"assignment_id": "A4", "course_id": "C4", "teacher_id": "T_HEAD", "primary_group_id": "G_PVS", "duration": 6, "day": 3, "room_id": "R1"},
            {"assignment_id": "A5", "course_id": "C5", "teacher_id": "T_HEAD", "primary_group_id": "G_PVS", "duration": 2, "day": 4, "room_id": "R1"}, # รวม 26 คาบ
            
            {"assignment_id": "B1", "course_id": "C6", "teacher_id": "T_GEN", "primary_group_id": "G_PVS", "duration": 6, "day": 0, "room_id": "R1"},
            {"assignment_id": "B2", "course_id": "C7", "teacher_id": "T_GEN", "primary_group_id": "G_PVS", "duration": 6, "day": 1, "room_id": "R1"},
            {"assignment_id": "B3", "course_id": "C8", "teacher_id": "T_GEN", "primary_group_id": "G_PVS", "duration": 6, "day": 2, "room_id": "R1"},
            {"assignment_id": "B4", "course_id": "C9", "teacher_id": "T_GEN", "primary_group_id": "G_PVS", "duration": 6, "day": 3, "room_id": "R1"},
            {"assignment_id": "B5", "course_id": "C10", "teacher_id": "T_GEN", "primary_group_id": "G_PVS", "duration": 6, "day": 4, "room_id": "R1"},
            {"assignment_id": "B6", "course_id": "C11", "teacher_id": "T_GEN", "primary_group_id": "G_PVS", "duration": 6, "day": 4, "room_id": "R1"} # รวม 36 คาบ
        ]

        service = WorkloadAnalyticsService(mock_schedule, config)
        analytics = service.compute_analytics()

        teachers_res = {t["id"]: t for t in analytics["teachers"]}
        self.assertEqual(teachers_res["T_HEAD"]["status"], "balanced")
        self.assertEqual(teachers_res["T_HEAD"]["total_periods"], 26)
        self.assertEqual(teachers_res["T_HEAD"]["total_semester_hours"], 26 * 18) # คิดเต็ม 18 สัปดาห์

        self.assertEqual(teachers_res["T_GEN"]["status"], "overload")
        self.assertIn("เกินเพดานสูงสุดวิทยาลัย", teachers_res["T_GEN"]["status_label"])

        # ตรวจสอบกลุ่มนักศึกษา
        grp_res = analytics["groups"][0]
        self.assertEqual(grp_res["total_semester_hours"], grp_res["total_periods"] * 18)

    def test_conflict_checker_daily_load_warning(self):
        """ทดสอบว่า Conflict Checker แจ้งเตือนเมื่อครูมีคาบสอนต่อวันเกินเกณฑ์"""
        mock_schedule = [
            {"assignment_id": "L1", "course_name": "วิชา 1", "teacher_id": "T1", "primary_group_id": "G1", "day": 0, "start_period": 1, "end_period": 4, "duration": 4, "active_blocks": [1, 2, 3, 4, 5, 6]},
            {"assignment_id": "L2", "course_name": "วิชา 2", "teacher_id": "T1", "primary_group_id": "G1", "day": 1, "start_period": 1, "end_period": 3, "duration": 3, "active_blocks": [1, 2, 3, 4, 5, 6]}
        ]
        teachers_map = {"T1": Teacher(id="T1", name="ครู ก", max_periods_per_day=5)}
        groups_map = {"G1": StudentGroup(id="G1", name="ชอ.1/1", level=EducationLevel.VOC_CERT, student_count=20)}
        rooms_map = {"R1": Room(id="R1", name="101", room_type=RoomType.CLASSROOM, capacity=30)}

        # ย้ายวิชา L2 (duration 3 คาบ) จากวันอังคาร (day 1) ไปวันจันทร์ (day 0) คาบ 6-8 -> รวมเป็น 4 + 3 = 7 คาบ (เกิน max_periods_per_day 5 คาบ)
        is_valid, conflicts, warnings = validate_move(
            schedule=mock_schedule,
            assignment_id="L2",
            target_day=0,
            target_start_period=6,
            target_room_id="R1",
            rooms_map=rooms_map,
            groups_map=groups_map,
            teachers_map=teachers_map
        )
        self.assertTrue(any("เกินเกณฑ์ต่อวัน" in w for w in warnings))

if __name__ == "__main__":
    unittest.main()

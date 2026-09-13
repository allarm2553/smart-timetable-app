import tests
import unittest
from fastapi.testclient import TestClient
from src.solver.models import EducationLevel, RoomType, CourseType
from src.api.main import app
from src.api.data_manager import data_manager
from src.solver.conflict_checker import validate_move, validate_swap

client = TestClient(app)

class TestPinnedAssignments(unittest.TestCase):
    def setUp(self):
        data_manager.reset_to_default()

    def test_pinned_lesson_solver_constraint(self):
        """ทดสอบว่า CP-SAT Solver จัดวิชาที่ล็อกไว้ลงวันและคาบตรงเป๊ะ 100%"""
        # ดึงแผนการสอนอันแรกมาล็อก เช่น วิชาภาษาไทย หรือวิชาแรกใน assignments
        all_data = data_manager.get_all_data()
        first_a = all_data["assignments"][0]
        a_id = first_a["id"]

        # ล็อกไว้ที่ วันพุธ (day=2), คาบ 1 (fixed_start_period=1), ห้อง ROOM_541
        pin_payload = {
            "is_pinned": True,
            "fixed_day": 2,
            "fixed_start_period": 1,
            "fixed_room_id": "ROOM_541",
            "external_teacher_name": "อ.สามัญ สมมติ"
        }
        res_pin = client.put(f"/api/assignments/{a_id}/pin", json=pin_payload)
        self.assertEqual(res_pin.status_code, 200)
        self.assertTrue(res_pin.json()["is_success"])

        # สั่ง Solve
        solve_res = client.post("/api/solve/current")
        self.assertEqual(solve_res.status_code, 200)
        data = solve_res.json()
        self.assertTrue(data["is_success"])

        # ตรวจสอบวิชาที่ล็อกไว้
        pinned_lesson = next((s for s in data["schedule"] if s["assignment_id"] == a_id), None)
        self.assertIsNotNone(pinned_lesson)
        self.assertEqual(pinned_lesson["day"], 2)  # วันพุธ
        self.assertEqual(pinned_lesson["start_period"], 1)  # คาบ 1
        self.assertEqual(pinned_lesson["room_id"], "ROOM_541")
        self.assertTrue(pinned_lesson["is_pinned"])
        self.assertEqual(pinned_lesson["external_teacher_name"], "อ.สามัญ สมมติ")

        # ตรวจสอบว่าไม่มีวิชาอื่นในกลุ่มเดียวกันมาทับช่วงเวลาของวิชานี้
        grp_id = pinned_lesson["primary_group_id"]
        p_dur = pinned_lesson["duration"]
        p_end = pinned_lesson["start_period"] + p_dur - 1

        for s in data["schedule"]:
            if s["assignment_id"] != a_id and (s["primary_group_id"] == grp_id or s.get("secondary_group_id") == grp_id):
                if s["day"] == 2:
                    s_start = s["start_period"]
                    s_end = s["end_period"]
                    overlap = max(1, s_start) <= min(p_end, s_end)
                    self.assertFalse(overlap, f"วิชา {s['course_name']} ชนกับวิชาที่ล็อกไว้!")

        print("✅ test_pinned_lesson_solver_constraint passed: Solver placed pinned lesson exactly at Day 2 Period 1 in ROOM_541 with 0 conflicts")

    def test_conflict_checker_blocks_pinned_move_and_swap(self):
        """ตรวจสอบว่า Conflict Checker ปฏิเสธการย้ายหรือสลับวิชาที่ถูกล็อกไว้"""
        schedule = [
            {
                "assignment_id": "A_PINNED",
                "course_name": "ภาษาไทยเพื่ออาชีพ",
                "course_type": "THEORY",
                "day": 0,
                "start_period": 1,
                "end_period": 2,
                "duration": 2,
                "room_id": "ROOM_541",
                "primary_group_id": "G_1",
                "teacher_id": "T_1",
                "is_pinned": True
            },
            {
                "assignment_id": "A_NORMAL",
                "course_name": "วงจรพัลส์",
                "course_type": "PRACTICE",
                "day": 1,
                "start_period": 6,
                "end_period": 9,
                "duration": 4,
                "room_id": "LAB_1",
                "primary_group_id": "G_1",
                "teacher_id": "T_2",
                "is_pinned": False
            }
        ]

        # 1. ทดสอบย้ายวิชาที่ล็อกไว้ -> ต้องขึ้น conflict
        is_valid, conflicts, _ = validate_move(
            schedule=schedule,
            assignment_id="A_PINNED",
            target_day=0,
            target_start_period=3,
            target_room_id="ROOM_541",
            rooms_map={},
            groups_map={}
        )
        self.assertFalse(is_valid)
        self.assertTrue(any("ถูกล็อกเวลาตายตัว" in c for c in conflicts))

        # 2. ทดสอบสลับวิชาที่มีวิชาล็อกอยู่ -> ต้องขึ้น conflict
        is_valid_swap, conflicts_swap, _, _ = validate_swap(
            schedule=schedule,
            assignment_id_1="A_PINNED",
            assignment_id_2="A_NORMAL",
            rooms_map={},
            groups_map={}
        )
        self.assertFalse(is_valid_swap)
        self.assertTrue(any("ถูกล็อกเวลาตายตัว" in c for c in conflicts_swap))

        print("✅ test_conflict_checker_blocks_pinned_move_and_swap passed: Pinned lessons are protected from accidental moves and swaps")

    def test_flexible_assignment_id_matching_and_unpin(self):
        """ตรวจสอบว่า data_manager สามารถจับคู่ assignment id ที่ขึ้นต้นด้วย L_ หรือ ASS_ ได้อย่างถูกต้อง และปลดล็อกได้โดยไม่เกิด error"""
        all_data = data_manager.get_all_data()
        first_a = all_data["assignments"][0]
        actual_id = first_a["id"]
        c_id = first_a["course_id"]
        c = next(c for c in all_data["courses"] if c["id"] == c_id)
        c_code = c["code"]

        # ล็อกวิชาไว้ก่อน
        data_manager.toggle_assignment_pin(actual_id, True, fixed_day=0, fixed_start_period=1, fixed_room_id="ROOM_541")
        self.assertTrue(first_a["is_pinned"])

        # จำลอง Client ส่ง ID ในรูปแบบเก่า/ต่าง prefix เช่น L_1_20000_1102 หรือ Course Code
        synthetic_id = f"L_1_{c_code.replace('-', '_')}"
        res = client.put(f"/api/assignments/{synthetic_id}/pin", json={"is_pinned": False})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["is_success"])
        self.assertFalse(body["data"]["is_pinned"])
        self.assertFalse(first_a["is_pinned"])

        print(f"✅ test_flexible_assignment_id_matching_and_unpin passed: Successfully matched {synthetic_id} to {actual_id} and unpinned")

if __name__ == "__main__":
    unittest.main()


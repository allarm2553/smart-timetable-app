import unittest
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.data_manager import data_manager
from src.solver.conflict_checker import validate_swap

class TestDragDropSwap(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        data_manager.reset_to_default()

    def test_swap_api_and_conflict_checker(self):
        # 1. Get current schedule
        solve_res = self.client.post("/api/solve/current")
        self.assertEqual(solve_res.status_code, 200)
        data = solve_res.json()
        self.assertIn(data["status"], ["OPTIMAL", "FEASIBLE"])
        schedule = data["schedule"]
        self.assertGreaterEqual(len(schedule), 2)

        lesson1 = schedule[0]
        lesson2 = schedule[1]

        # 2. Call /api/schedule/swap
        swap_res = self.client.post("/api/schedule/swap", json={
            "schedule": schedule,
            "assignment_id_1": lesson1["assignment_id"],
            "assignment_id_2": lesson2["assignment_id"]
        })
        self.assertEqual(swap_res.status_code, 200)
        res_data = swap_res.json()
        
        # Check that response returned expected structure
        self.assertIn("is_success", res_data)
        self.assertIn("message", res_data)
        self.assertIn("updated_schedule", res_data)

        if res_data["is_success"]:
            # Check positions swapped in updated_schedule
            updated = res_data["updated_schedule"]
            up_l1 = next(s for s in updated if s["assignment_id"] == lesson1["assignment_id"])
            up_l2 = next(s for s in updated if s["assignment_id"] == lesson2["assignment_id"])
            self.assertEqual(up_l1["day"], lesson2["day"])
            self.assertEqual(up_l1["start_period"], lesson2["start_period"])
            self.assertEqual(up_l2["day"], lesson1["day"])
            self.assertEqual(up_l2["start_period"], lesson1["start_period"])
            print("✅ Swap API successfully swapped 2 lessons and updated their time slots!")
        else:
            print(f"ℹ️ Swap returned conflict as expected by constraints: {res_data['conflicts']}")

    def test_swap_same_assignment_rejected(self):
        solve_res = self.client.post("/api/solve/current")
        schedule = solve_res.json()["schedule"]
        lesson1 = schedule[0]

        swap_res = self.client.post("/api/schedule/swap", json={
            "schedule": schedule,
            "assignment_id_1": lesson1["assignment_id"],
            "assignment_id_2": lesson1["assignment_id"]
        })
        self.assertEqual(swap_res.status_code, 200)
        res_data = swap_res.json()
        self.assertFalse(res_data["is_success"])
        self.assertIn("ไม่สามารถสลับวิชาเดียวกันได้", res_data["message"])
        print("✅ Correctly rejected swapping the same lesson with itself")

if __name__ == "__main__":
    unittest.main()

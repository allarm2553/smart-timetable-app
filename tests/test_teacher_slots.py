from fastapi.testclient import TestClient
from src.api.main import app
from src.api.data_manager import data_manager

client = TestClient(app)

def test_teacher_unavailable_slots():
    # 1. Reset data to default
    data_manager.reset_to_default()
    
    # 2. Lock teacher T_PONG (พงษ์สถิต) on Wednesday (day=2), periods 1 to 4 (morning)
    locked_slots = [[2, 1], [2, 2], [2, 3], [2, 4]]
    res = client.put("/api/teachers/T_PONG/unavailable-slots", json={"unavailable_slots": locked_slots})
    assert res.status_code == 200
    assert res.json()["is_success"] is True
    assert res.json()["unavailable_slots"] == locked_slots

    # 3. Solve timetable with these constraints
    solve_res = client.post("/api/solve/current")
    assert solve_res.status_code == 200
    s_data = solve_res.json()
    assert s_data["is_success"] is True

    # 4. Verify T_PONG has ZERO lessons on Day 2, periods 1-4
    pong_lessons = [l for l in s_data["schedule"] if l["teacher_id"] == "T_PONG"]
    for l in pong_lessons:
        if l["day"] == 2:
            start_p = l["start_period"]
            end_p = l["end_period"]
            # None of [start_p, end_p] can overlap with 1..4
            overlap = max(start_p, 1) <= min(end_p, 4)
            assert not overlap, f"Violation! Teacher T_PONG scheduled at day 2 periods {start_p}-{end_p}"
    print("✅ test_teacher_unavailable_slots: Solver strictly respected locked periods")

    # 5. Verify Conflict Checker blocks move to locked slot
    # Find a lesson of T_PONG
    first_pong_lesson = pong_lessons[0]
    validate_payload = {
        "schedule": s_data["schedule"],
        "assignment_id": first_pong_lesson["assignment_id"],
        "target_day": 2,
        "target_start_period": 1,
        "target_room_id": first_pong_lesson["room_id"]
    }
    val_res = client.post("/api/schedule/validate-move", json=validate_payload)
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["is_valid"] is False
    assert any("ติดภารกิจ/ไม่สะดวกสอน" in c for c in val_data["conflicts"])
    print("✅ test_teacher_unavailable_slots: Conflict checker correctly blocked move to unavailable slot")

    # Clean up: reset to default
    data_manager.reset_to_default()

if __name__ == "__main__":
    test_teacher_unavailable_slots()
    print("\n🎉 ALL TEACHER UNAVAILABLE SLOTS TESTS PASSED! 🎉")

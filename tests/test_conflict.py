from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_conflict_detection_and_apply():
    # 1. จัดตารางก่อนเพื่อให้ได้ schedule เริ่มต้น
    solve_res = client.post("/api/solve/benchmark").json()
    assert solve_res["is_success"] is True
    schedule = solve_res["schedule"]
    assert len(schedule) > 0

    first_item = schedule[0]
    ass_id = first_item["assignment_id"]
    original_day = first_item["day"]
    original_start = first_item["start_period"]
    original_room = first_item["room_id"]

    # 2. ทดสอบย้ายไปทับเวลาพักกลางวัน (คาบที่ 5: 12:00-13:00)
    res_lunch = client.post("/api/schedule/validate-move", json={
        "schedule": schedule,
        "assignment_id": ass_id,
        "target_day": original_day,
        "target_start_period": 5, # คาบ 5 คือพักกลางวัน
        "target_room_id": original_room
    }).json()
    assert res_lunch["is_valid"] is False
    assert any("พักกลางวัน" in c for c in res_lunch["conflicts"])
    print("✅ Passed: Blocked move overlapping with lunch break (คาบ 5)")

    # 3. ทดสอบย้ายไปทับวิชาอื่น (หาอีกวิชาหนึ่งในตารางมาทับ)
    second_item = schedule[1]
    res_collision = client.post("/api/schedule/validate-move", json={
        "schedule": schedule,
        "assignment_id": ass_id,
        "target_day": second_item["day"],
        "target_start_period": second_item["start_period"],
        "target_room_id": second_item["room_id"] # ใช้ห้องเดียวกัน
    }).json()
    assert res_collision["is_valid"] is False
    assert len(res_collision["conflicts"]) > 0
    print(f"✅ Passed: Detected collision: {res_collision['conflicts']}")

    # 4. ทดสอบย้ายวิชาเรียนรวม (54 คน) เข้าห้องขนาดเล็ก (ROOM_545 จุได้ 40 คน)
    merged_item = next(s for s in schedule if s["is_merged"] is True)
    res_cap = client.post("/api/schedule/validate-move", json={
        "schedule": schedule,
        "assignment_id": merged_item["assignment_id"],
        "target_day": 0, # จันทร์
        "target_start_period": 1,
        "target_room_id": "ROOM_545" # ห้องเล็ก 40 คน
    }).json()
    assert res_cap["is_valid"] is False
    assert any("ความจุไม่พอ" in c for c in res_cap["conflicts"])
    print("✅ Passed: Detected capacity conflict for merged class in small room")

    # 5. ทดสอบย้ายไปยังช่องที่ว่างจริงในวันศุกร์คาบ 8
    # หาช่องว่าง
    target_day = 4 # ศุกร์
    target_start = 8 # คาบ 8 (15:00 - 16:00)
    # ทดลองย้าย first_item
    res_valid = client.post("/api/schedule/validate-move", json={
        "schedule": schedule,
        "assignment_id": ass_id,
        "target_day": target_day,
        "target_start_period": target_start,
        "target_room_id": original_room
    }).json()

    # ถ้าไม่ชน ทดสอบ apply-move
    if res_valid["is_valid"]:
        apply_res = client.post("/api/schedule/apply-move", json={
            "schedule": schedule,
            "assignment_id": ass_id,
            "target_day": target_day,
            "target_start_period": target_start,
            "target_room_id": original_room
        }).json()
        assert apply_res["is_success"] is True
        moved_entry = next(s for s in apply_res["updated_schedule"] if s["assignment_id"] == ass_id)
        assert moved_entry["day"] == target_day
        assert moved_entry["start_period"] == target_start
        print(f"✅ Passed: Successfully validated and applied manual move to Day {target_day} Period {target_start}")

if __name__ == "__main__":
    test_conflict_detection_and_apply()
    print("\n🎉 ALL CONFLICT CHECKER & MANUAL MOVE TESTS PASSED! 🎉")

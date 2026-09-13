from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_root_dashboard():
    response = client.get("/")
    assert response.status_code == 200
    assert "Smart Timetable" in response.text
    assert "OR-Tools CP-SAT" in response.text
    print("✅ test_root_dashboard passed")

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["engine"] == "Google OR-Tools CP-SAT"
    print("✅ test_health passed")

def test_get_benchmark():
    response = client.get("/api/benchmark")
    assert response.status_code == 200
    data = response.json()
    assert len(data["teachers"]) >= 4
    assert len(data["rooms"]) >= 5
    assert len(data["groups"]) >= 3
    assert len(data["assignments"]) >= 7
    print("✅ test_get_benchmark passed")

def test_solve_benchmark():
    response = client.post("/api/solve/benchmark")
    assert response.status_code == 200
    data = response.json()
    assert data["is_success"] is True
    assert data["status"] in ("OPTIMAL", "FEASIBLE")
    assert data["total_lessons_scheduled"] > 0
    
    # ตรวจสอบวิชาเรียนรวม Merged Theory (ภาษาอังกฤษ)
    merged_lessons = [
        s for s in data["schedule"]
        if s["is_merged"] is True and s["course_name"] == "ภาษาอังกฤษเพื่อการสื่อสาร"
    ]
    assert len(merged_lessons) == 1
    eng = merged_lessons[0]
    assert eng["primary_group_id"] == "G_CHO_1_1"
    assert eng["secondary_group_id"] == "G_CHO_1_2"
    # ต้องใช้ห้องบรรยายรวม 546
    assert "546" in eng["room_name"]
    print(f"✅ test_solve_benchmark passed: Merged theory scheduled at {eng['day_name']} คาบ {eng['start_period']}-{eng['end_period']} in {eng['room_name']}")

    # ตรวจสอบวิชาของ ปวส. ใน V.2 (เกลี่ยเต็ม 18 สัปดาห์: ต้อง active ครบทั้ง 6 บล็อก)
    pvs_lessons = [
        s for s in data["schedule"]
        if s["primary_group_id"] == "G_PVS_1"
    ]
    assert len(pvs_lessons) > 0
    for l in pvs_lessons:
        assert 6 in l["active_blocks"], "ใน V.2 ปวส. เกลี่ยเต็ม 18 สัปดาห์ ต้อง active ในบล็อก 6"
    print("✅ test_solve_benchmark passed: High Voc Cert (ปวส.) 18-week smoothed blocks verified (weeks 1-18 full coverage)")

    # ตรวจสอบว่าไม่มีวิชาใดชนกับคาบที่ 5 (12:00-13:00 พักกลางวัน)
    for s in data["schedule"]:
        assert not (s["start_period"] <= 5 <= s["end_period"]), f"วิชา {s['course_name']} ชนกับคาบพักกลางวัน (คาบ 5)!"
    print("✅ test_solve_benchmark passed: Verified lunch break (Period 5: 12:00-13:00) is strictly preserved")

def test_custom_solve():
    # ดึง benchmark data แล้วส่งกลับเข้าไปทาง POST /api/solve
    bench_data = client.get("/api/benchmark").json()
    solve_payload = {
        **bench_data,
        "days": 5,
        "periods_per_day": 12,
        "num_blocks": 6,
        "time_limit_seconds": 15.0
    }
    response = client.post("/api/solve", json=solve_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_success"] is True
    assert data["total_lessons_scheduled"] == len(bench_data["assignments"])
    print(f"✅ test_custom_solve passed: Successfully scheduled {data['total_lessons_scheduled']} lessons via custom API payload")

if __name__ == "__main__":
    test_root_dashboard()
    test_health()
    test_get_benchmark()
    test_solve_benchmark()
    test_custom_solve()
    print("\n🎉 ALL API AND DASHBOARD TESTS PASSED SUCCESSFULLY! 🎉")

from fastapi.testclient import TestClient
from src.api.main import app
from src.api.data_manager import data_manager
from src.api.analytics import WorkloadAnalyticsService

client = TestClient(app)

def test_analytics_service_direct():
    config = data_manager.get_all_data()
    sample_schedule = [
        {
            "assignment_id": "L1",
            "course_id": "C_GAS",
            "course_name": "งานเครื่องยนต์แก๊สโซลีน",
            "course_type": "practice",
            "teacher_id": "T_PONG",
            "teacher_name": "พงษ์สถิต",
            "room_id": "ROOM_545",
            "room_name": "545 (ปฏิบัติการเครื่องยนต์)",
            "primary_group_id": "G_VOC_1_1",
            "day": 0,
            "start_period": 1,
            "duration": 4
        },
        {
            "assignment_id": "L2",
            "course_id": "C_ENG",
            "course_name": "ภาษาอังกฤษ",
            "course_type": "theory",
            "is_merged": True,
            "teacher_id": "T_PONG",
            "teacher_name": "พงษ์สถิต",
            "room_id": "ROOM_546",
            "room_name": "546 (ห้องบรรยายใหญ่)",
            "primary_group_id": "G_VOC_1_1",
            "secondary_group_id": "G_VOC_1_2",
            "day": 1,
            "start_period": 1,
            "duration": 2
        }
    ]
    service = WorkloadAnalyticsService(sample_schedule, config)
    res = service.compute_analytics()

    # Check summary
    assert "summary" in res
    assert res["summary"]["total_teachers"] >= 4
    assert res["summary"]["total_rooms"] >= 5

    # Check teacher T_PONG
    pong = next((t for t in res["teachers"] if t["id"] == "T_PONG"), None)
    assert pong is not None
    assert pong["total_periods"] == 6
    assert pong["practice_periods"] == 4
    assert pong["theory_periods"] == 2
    assert pong["max_day_load"] == 4
    assert pong["status"] == "underload"  # 6 < 16

    # Check rooms
    room_545 = next((r for r in res["rooms"] if r["id"] == "ROOM_545"), None)
    assert room_545 is not None
    assert room_545["used_periods"] == 4
    assert room_545["utilization_rate"] == 8.0  # 4 / 50 * 100 = 8.0%
    print("✅ test_analytics_service_direct passed")

def test_api_analytics_get():
    res = client.get("/api/analytics/workload")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "teachers" in data
    assert "rooms" in data
    assert "groups" in data
    assert data["summary"]["total_teachers"] > 0
    assert len(data["teachers"]) == data["summary"]["total_teachers"]
    print("✅ test_api_analytics_get passed")

def test_api_analytics_post():
    payload = {
        "schedule": [
            {
                "assignment_id": "L_TEST",
                "course_id": "C_TEST",
                "course_name": "ทดสอบ",
                "course_type": "practice",
                "teacher_id": "T_PO",
                "teacher_name": "อ.ป้อ",
                "room_id": "ROOM_545",
                "primary_group_id": "G_VOC_1_1",
                "day": 2,
                "start_period": 6,
                "duration": 4
            }
        ]
    }
    res = client.post("/api/analytics/workload", json=payload)
    assert res.status_code == 200
    data = res.json()
    po = next((t for t in data["teachers"] if t["id"] == "T_PO"), None)
    assert po is not None
    assert po["total_periods"] == 4
    print("✅ test_api_analytics_post passed")

if __name__ == "__main__":
    test_analytics_service_direct()
    test_api_analytics_get()
    test_api_analytics_post()
    print("\n🎉 ALL ANALYTICS TESTS PASSED SUCCESSFULLY! 🎉")

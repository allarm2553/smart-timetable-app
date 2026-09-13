import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.api.main import app
from src.api.data_manager import data_manager

client = TestClient(app)

def test_data_manager_crud():
    # บันทึกข้อมูลโปรเจ็คเดิมก่อนเริ่มทดสอบ เพื่อกู้คืนหลังทดสอบเสร็จ
    initial_project = client.get("/api/project/export").json()
    data_manager.reset_to_benchmark()

    try:
        # 1. ทดสอบดึงข้อมูลทั้งหมด
        res_data = client.get("/api/data")
        assert res_data.status_code == 200
        data = res_data.json()
        assert len(data["teachers"]) >= 4
        assert len(data["rooms"]) >= 5
        assert len(data["groups"]) >= 3
        print("✅ Passed: GET /api/data retrieved successfully")

        # 2. ทดสอบเพิ่มครูผู้สอน
        res_add_t = client.post("/api/teachers", json={
            "id": "T_TEST_1",
            "name": "อ. ทดสอบ สมมติ",
            "max_periods_per_day": 5
        })
        assert res_add_t.status_code == 200
        assert res_add_t.json()["is_success"] is True
        print("✅ Passed: POST /api/teachers added teacher")

        # 3. ทดสอบเพิ่มห้องเรียน
        res_add_r = client.post("/api/rooms", json={
            "id": "ROOM_TEST_555",
            "name": "ห้องปฏิบัติการทดสอบ 555",
            "room_type": "CLASSROOM",
            "capacity": 35
        })
        assert res_add_r.status_code == 200
        assert res_add_r.json()["is_success"] is True
        print("✅ Passed: POST /api/rooms added room")

        # 4. ทดสอบเพิ่มกลุ่มเรียนใหม่ (ปวช.)
        res_add_g = client.post("/api/groups", json={
            "id": "G_TEST_CHO_2",
            "name": "ชอ.2/1 (ทดสอบ)",
            "level": "VOC_CERT",
            "student_count": 22
        })
        assert res_add_g.status_code == 200
        assert res_add_g.json()["is_success"] is True
        print("✅ Passed: POST /api/groups added student group")

        # 5. ทดสอบจัดตารางด้วยข้อมูลปัจจุบัน (POST /api/solve/current)
        res_solve = client.post("/api/solve/current")
        assert res_solve.status_code == 200
        assert res_solve.json()["is_success"] is True
        print(f"✅ Passed: POST /api/solve/current scheduled {res_solve.json()['total_lessons_scheduled']} lessons")

        # 6. ทดสอบลบรายการ
        assert client.delete("/api/teachers/T_TEST_1").status_code == 200
        assert client.delete("/api/rooms/ROOM_TEST_555").status_code == 200
        assert client.delete("/api/groups/G_TEST_CHO_2").status_code == 200
        print("✅ Passed: DELETE /api/teachers, rooms, groups deleted successfully")

        # 7. ทดสอบล้างข้อมูลทั้งหมด (Clear All)
        res_clear = client.post("/api/data/clear")
        assert res_clear.status_code == 200
        assert len(res_clear.json()["data"]["teachers"]) == 0
        assert len(res_clear.json()["data"]["rooms"]) == 0
        print("✅ Passed: POST /api/data/clear cleared all data successfully")

        # 8. ทดสอบรีเซ็ตข้อมูล
        res_reset = client.post("/api/data/reset")
        assert res_reset.status_code == 200
        print("✅ Passed: POST /api/data/reset reset to empty")
    finally:
        # ล้างข้อมูลให้สะอาดเป็นค่าว่างตามที่ผู้ใช้ต้องการ
        data_manager.clear_all()


if __name__ == "__main__":
    test_data_manager_crud()
    print("\n🎉 ALL DATA MANAGER CRUD TESTS PASSED! 🎉")

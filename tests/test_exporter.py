from fastapi.testclient import TestClient
from src.api.main import app
from src.api.data_manager import data_manager
from src.api.excel_exporter import VocationalExcelExporter

client = TestClient(app)

def test_excel_exporter_direct():
    config = data_manager.get_all()
    sample_schedule = {
        "scheduled_lessons": [
            {
                "assignment_id": "ASS_VOC_1_GAS",
                "course_id": "C_GAS",
                "course_code": "20101-2001",
                "course_name": "งานเครื่องยนต์แก๊สโซลีน",
                "teacher_id": "T_PONG",
                "teacher_name": "พงษ์สถิต",
                "room_id": "ROOM_545",
                "room_name": "545 (ปฏิบัติการเครื่องยนต์)",
                "student_group_ids": ["G_VOC_1_1"],
                "student_group_names": ["ชอ.1/1"],
                "day_of_week": 0,
                "start_period": 1,
                "duration_periods": 4,
                "is_merged_theory": False,
                "is_rotation": True
            }
        ]
    }
    exporter = VocationalExcelExporter(sample_schedule, config)
    xml_output = exporter.export(view_type="group", view_id="G_VOC_1_1")
    assert "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" in xml_output
    assert "<Workbook" in xml_output
    assert "20101-2001 งานเครื่องยนต์แก๊สโซลีน" in xml_output
    assert "ss:MergeAcross=\"3\"" in xml_output
    assert "พักกลางวัน" in xml_output
    print("✅ test_excel_exporter_direct passed")

def test_excel_export_all_groups():
    config = data_manager.get_all()
    exporter = VocationalExcelExporter({"scheduled_lessons": []}, config)
    xml_output = exporter.export(view_type="all_groups")
    assert "<Workbook" in xml_output
    # Should have a worksheet for each group in config
    for g in config["groups"]:
        assert f"ss:Name=\"กลุ่ม {g['name']}\"" in xml_output
    print("✅ test_excel_export_all_groups passed")

def test_api_export_excel_get():
    response = client.get("/api/export/excel?view_type=group&view_id=G_VOC_1_1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.ms-excel")
    assert "attachment" in response.headers.get("content-disposition", "")
    assert len(response.content) > 1000
    print("✅ test_api_export_excel_get passed")

def test_api_export_excel_post():
    payload = {
        "view_type": "teacher",
        "view_id": "T_PONG",
        "schedule": [
            {
                "assignment_id": "TEST_1",
                "course_code": "20101-2001",
                "course_name": "ทดสอบวิชา",
                "teacher_id": "T_PONG",
                "teacher_name": "พงษ์สถิต",
                "room_name": "545",
                "student_group_ids": ["G_VOC_1_1"],
                "student_group_names": ["ชอ.1/1"],
                "day_of_week": 1,
                "start_period": 6,
                "duration_periods": 2
            }
        ]
    }
    response = client.post("/api/export/excel", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.ms-excel")
    assert "ทดสอบวิชา" in response.text
    print("✅ test_api_export_excel_post passed")

if __name__ == "__main__":
    test_excel_exporter_direct()
    test_excel_export_all_groups()
    test_api_export_excel_get()
    test_api_export_excel_post()
    print("\n🎉 ALL EXCEL EXPORTER TESTS PASSED SUCCESSFULLY! 🎉")

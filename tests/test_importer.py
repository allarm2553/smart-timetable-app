import tests
import base64
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.data_manager import data_manager
from src.api.importer import BulkDataImporter

client = TestClient(app)

def test_template_csv():
    csv_bytes = BulkDataImporter.get_template_csv()
    assert len(csv_bytes) > 0
    # Must have UTF-8 BOM
    assert csv_bytes.startswith(b'\xef\xbb\xbf')
    text = csv_bytes.decode('utf-8-sig')
    assert "รหัสวิชา" in text
    assert "งานเครื่องยนต์แก๊สโซลีน" in text
    print("✅ test_template_csv passed")

def test_api_get_template():
    res = client.get("/api/import/template")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers.get("content-disposition", "")
    assert len(res.content) > 100
    print("✅ test_api_get_template passed")

def test_process_import_append():
    data_manager.reset_to_default()
    csv_sample = """รหัสวิชา,ชื่อวิชา,ประเภทวิชา,จำนวนคาบ,ประเภทห้อง,ครูผู้สอน,กลุ่มผู้เรียน,กลุ่มเรียนรวม,หมุนเวียนฐาน
20101-9901,วิชาทดสอบนำเข้าใหม่,practice,4,lab,ครูทดสอบพิเศษ,ชอ.1/1,,ใช่
"""
    b64_content = base64.b64encode(csv_sample.encode("utf-8")).decode("utf-8")
    
    payload = {
        "filename": "test_import.csv",
        "content_base64": b64_content,
        "mode": "append"
    }
    res = client.post("/api/import/process", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    assert data["imported_count"] == 1
    assert data["new_teachers_count"] >= 1  # 'ครูทดสอบพิเศษ' is newly created

    # Verify teacher was added to data manager
    all_d = data_manager.get_all_data()
    assert any(t["name"] == "ครูทดสอบพิเศษ" for t in all_d["teachers"])
    print("✅ test_process_import_append passed")

def test_process_import_replace_and_solve():
    # Use template CSV with replace mode
    template_bytes = BulkDataImporter.get_template_csv()
    b64_content = base64.b64encode(template_bytes).decode("utf-8")
    
    payload = {
        "filename": "curriculum.csv",
        "content_base64": b64_content,
        "mode": "replace"
    }
    res = client.post("/api/import/process", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    assert data["imported_count"] == 5
    assert data["total_assignments"] == 5

    # Run solver on current data
    solve_res = client.post("/api/solve/current")
    assert solve_res.status_code == 200
    s_data = solve_res.json()
    assert s_data["is_success"] is True
    assert s_data["total_lessons_scheduled"] == 5
    print("✅ test_process_import_replace_and_solve passed")

    # Reset back to default
    data_manager.reset_to_default()

if __name__ == "__main__":
    test_template_csv()
    test_api_get_template()
    test_process_import_append()
    test_process_import_replace_and_solve()
    print("\n🎉 ALL BULK IMPORTER TESTS PASSED SUCCESSFULLY! 🎉")

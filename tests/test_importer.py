import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import io
import base64
import openpyxl
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.data_manager import data_manager
from src.api.importer import BulkDataImporter

client = TestClient(app)

def test_is_valid_course_code():
    # Valid course codes
    assert BulkDataImporter.is_valid_course_code("20000-1102") is True
    assert BulkDataImporter.is_valid_course_code("30000-1201") is True
    assert BulkDataImporter.is_valid_course_code("20101-2001") is True
    assert BulkDataImporter.is_valid_course_code("2101-2001") is True
    assert BulkDataImporter.is_valid_course_code("ว30101") is True
    assert BulkDataImporter.is_valid_course_code("ENG 101") is True
    assert BulkDataImporter.is_valid_course_code("20000-2001") is True

    # Invalid items (category headers, section numbers, totals, summaries, headers)
    assert BulkDataImporter.is_valid_course_code("1. หมวดวิชาสมรรถนะแกนกลาง ( 4 หน่วยกิต)") is False
    assert BulkDataImporter.is_valid_course_code("1.1 กลุ่มสมรรถนะภาษาและการสื่อสาร") is False
    assert BulkDataImporter.is_valid_course_code("2. หมวดวิชาสมรรถนะวิชาชีพ") is False
    assert BulkDataImporter.is_valid_course_code("รวมสัปดาห์ละ") is False
    assert BulkDataImporter.is_valid_course_code("รวม") is False
    assert BulkDataImporter.is_valid_course_code("รวมทั้งสิ้น") is False
    assert BulkDataImporter.is_valid_course_code("1.1") is False
    assert BulkDataImporter.is_valid_course_code("2.0") is False
    assert BulkDataImporter.is_valid_course_code("รหัสวิชา") is False
    assert BulkDataImporter.is_valid_course_code("code") is False
    assert BulkDataImporter.is_valid_course_code("") is False
    assert BulkDataImporter.is_valid_course_code(None) is False
    assert BulkDataImporter.is_valid_course_code("   ") is False
    print("✅ test_is_valid_course_code passed")

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

def test_process_import_filters_non_course_rows():
    data_manager.reset_to_default()
    # CSV containing category headers and total summaries
    csv_with_categories = """รหัสวิชา,ชื่อวิชา,ประเภทวิชา,จำนวนคาบ,ประเภทห้อง,ครูผู้สอน,กลุ่มผู้เรียน,กลุ่มเรียนรวม,หมุนเวียนฐาน
1. หมวดวิชาสมรรถนะแกนกลาง ( 4 หน่วยกิต),,,,,,,,
1.1 กลุ่มสมรรถนะภาษาและการสื่อสาร,,,,,,,,
20000-1102,ภาษาไทยเพื่ออาชีพ,ทฤษฎี,1,ห้องบรรยาย,ครูสมใจ,ชอ.1/1,,ไม่ใช่
20000-1202,ภาษาอังกฤษเพื่อการสื่อสารในงานอาชีพ,ทฤษฎี,2,ห้องบรรยาย,ครูนภา,ชอ.1/1,,ไม่ใช่
2. หมวดวิชาสมรรถนะวิชาชีพ,,,,,,,,
20101-2001,งานเครื่องยนต์แก๊สโซลีน,ปฏิบัติ,5,ห้องปฏิบัติการ,ครูพงษ์สถิต,ชอ.1/1,,ไม่ใช่
รวมสัปดาห์ละ,,,,,,,,
"""
    b64_content = base64.b64encode(csv_with_categories.encode("utf-8")).decode("utf-8")
    payload = {
        "filename": "plan_with_categories.csv",
        "content_base64": b64_content,
        "mode": "replace"
    }
    res = client.post("/api/import/process", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    # Only the 3 actual courses must be imported!
    assert data["imported_count"] == 3
    assert data["skipped_count"] == 4  # 3 category rows + 1 total row

    # Verify that NONE of the category headers or totals became courses
    all_d = data_manager.get_all_data()
    course_codes = [c["code"] for c in all_d["courses"]]
    assert "20000-1102" in course_codes
    assert "20000-1202" in course_codes
    assert "20101-2001" in course_codes
    for c in all_d["courses"]:
        assert "หมวด" not in c["name"]
        assert "กลุ่ม" not in c["name"]
        assert "รวม" not in c["name"]
        assert not c["id"].startswith("C_00") # No dummy generated codes
    print("✅ test_process_import_filters_non_course_rows passed")

def test_process_import_vocational_xlsx():
    data_manager.reset_to_default()
    # Create an in-memory vocational study plan Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2.2569"

    ws.append(["แผนการเรียนหลักสูตรประกาศนียบัตรวิชาชีพ (ปวช.) พุทธศักราช 2567"])
    ws.append(["สาขาวิชาช่างอิเล็กทรอนิกส์"])
    ws.append(["ภาคเรียนที่ 2 ปีการศึกษา 2569"])
    # Header row at row 4
    ws.append(["รหัสวิชา", "รายวิชา", "ท", "ป", "น", "หมายเหตุ"])
    ws.append(["1. หมวดวิชาสมรรถนะแกนกลาง (4 หน่วยกิต)", "", "", "", "", ""])
    ws.append(["1.1 กลุ่มสมรรถนะภาษาและการสื่อสาร", "", "", "", "", ""])
    ws.append(["20000-1102", "ภาษาไทยเพื่ออาชีพ", 1, 0, 1, ""])
    ws.append(["20000-1202", "ภาษาอังกฤษเพื่อการสื่อสารในงานอาชีพ", 1, 1, 1, ""])
    ws.append(["2. หมวดวิชาสมรรถนะวิชาชีพ", "", "", "", "", ""])
    ws.append(["20105-2001", "วงจรไฟฟ้ากระแสสลับ", 1, 4, 3, ""])
    ws.append(["20105-2002", "เครื่องวัดไฟฟ้าและอิเล็กทรอนิกส์", 1, 4, 3, ""])
    ws.append(["รวมสัปดาห์ละ", "", 4, 9, 8, ""])

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    b64_content = base64.b64encode(xlsx_bytes).decode("utf-8")
    payload = {
        "filename": "curriculum_plan.xlsx",
        "content_base64": b64_content,
        "mode": "replace"
    }
    res = client.post("/api/import/process", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    # Strictly 4 courses imported
    assert data["imported_count"] == 4
    assert data["skipped_count"] >= 3

    # Check course details
    all_d = data_manager.get_all_data()
    assert len(all_d["courses"]) == 4
    for c in all_d["courses"]:
        if c["code"] == "20000-1102":
            assert c["periods_per_session"] == 1
            assert c["course_type"] == "THEORY"
        elif c["code"] == "20105-2001":
            assert c["periods_per_session"] == 5 # 1 + 4
            assert c["course_type"] == "PRACTICE"

    # Solve should succeed
    solve_res = client.post("/api/solve/current")
    assert solve_res.status_code == 200
    assert solve_res.json()["is_success"] is True
    print("✅ test_process_import_vocational_xlsx passed")

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
    test_is_valid_course_code()
    test_template_csv()
    test_api_get_template()
    test_process_import_append()
    test_process_import_filters_non_course_rows()
    test_process_import_vocational_xlsx()
    test_process_import_replace_and_solve()
    print("\n🎉 ALL BULK IMPORTER TESTS PASSED SUCCESSFULLY! 🎉")

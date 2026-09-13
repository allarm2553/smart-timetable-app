"""
Vocational Timetable Bulk Data Importer
Supports CSV (UTF-8, UTF-8-SIG, TIS-620, CP874) and native XLSX (via standard zipfile/xml)
"""
import io
import csv
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple

from src.solver.models import CourseType, RoomType, EducationLevel

class BulkDataImporter:
    TEMPLATE_HEADERS = [
        "รหัสวิชา",
        "ชื่อวิชา",
        "ประเภทวิชา",
        "จำนวนคาบ",
        "ประเภทห้อง",
        "ครูผู้สอน",
        "กลุ่มผู้เรียน",
        "กลุ่มเรียนรวม",
        "หมุนเวียนฐาน"
    ]

    SAMPLE_ROWS = [
        ["20101-2001", "งานเครื่องยนต์แก๊สโซลีน", "ปฏิบัติ", "4", "ห้องปฏิบัติการ", "พงษ์สถิต", "ชอ.1/1", "", "ใช่"],
        ["20101-2002", "งานเครื่องยนต์ดีเซล", "ปฏิบัติ", "4", "ห้องปฏิบัติการ", "อ.ป้อ", "ชอ.1/2", "", "ใช่"],
        ["20101-2003", "งานส่งกำลังรถยนต์", "ปฏิบัติ", "4", "ห้องปฏิบัติการ", "อ.สมชาย", "ชอ.1/3", "", "ใช่"],
        ["20000-1201", "ภาษาอังกฤษเพื่อการสื่อสาร", "ทฤษฎี", "2", "ห้องบรรยาย", "ครูนภา", "ชอ.1/1", "ชอ.1/2", "ไม่ใช่"],
        ["20101-2004", "ทฤษฎีเครื่องยนต์แก๊สโซลีน", "ทฤษฎี", "2", "ห้องทั่วไป", "พงษ์สถิต", "ชอ.1/1", "", "ไม่ใช่"]
    ]

    @classmethod
    def get_template_csv(cls) -> bytes:
        """Returns CSV bytes with UTF-8 BOM so Excel opens Thai properly."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(cls.TEMPLATE_HEADERS)
        for r in cls.SAMPLE_ROWS:
            writer.writerow(r)
        
        # Prepend UTF-8 BOM (\ufeff)
        csv_text = "\ufeff" + output.getvalue()
        return csv_text.encode("utf-8")

    @classmethod
    def parse_file_to_rows(cls, file_bytes: bytes, filename: str) -> List[Dict[str, str]]:
        """Parses CSV or XLSX into a list of row dictionaries."""
        filename_lower = filename.lower()
        if filename_lower.endswith(".xlsx"):
            return cls._parse_xlsx(file_bytes)
        else:
            return cls._parse_csv(file_bytes)

    @classmethod
    def _parse_csv(cls, file_bytes: bytes) -> List[Dict[str, str]]:
        # Detect encoding
        text = None
        for enc in ["utf-8-sig", "utf-8", "cp874", "tis-620", "latin1"]:
            try:
                text = file_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if not text:
            raise ValueError("ไม่สามารถอ่านการเข้ารหัสของไฟล์ CSV ได้ (กรุณาบันทึกเป็น UTF-8)")

        # Sniff delimiter
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return []

        delimiter = ','
        first_line = lines[0]
        if '\t' in first_line:
            delimiter = '\t'
        elif ';' in first_line and ',' not in first_line:
            delimiter = ';'

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        raw_rows = list(reader)
        if not raw_rows:
            return []

        headers = [h.strip().replace('\ufeff', '') for h in raw_rows[0]]
        dict_rows = []
        for r in raw_rows[1:]:
            if not any(cell.strip() for cell in r):
                continue
            row_dict = {}
            for idx, h in enumerate(headers):
                val = r[idx].strip() if idx < len(r) else ""
                row_dict[h] = val
            dict_rows.append(row_dict)

        return dict_rows

    @classmethod
    def _parse_xlsx(cls, file_bytes: bytes) -> List[Dict[str, str]]:
        """Reads XLSX archive with standard library zipfile & ElementTree."""
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                # 1. Read shared strings
                shared_strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in tree.findall("{*}si"):
                        # Gather all <t>
                        t_parts = [t.text or "" for t in si.findall(".//{*}t")]
                        shared_strings.append("".join(t_parts))

                # 2. Read sheet1
                sheet_xml = None
                for name in z.namelist():
                    if name.startswith("xl/worksheets/sheet1"):
                        sheet_xml = z.read(name)
                        break

                if not sheet_xml:
                    raise ValueError("ไม่พบข้อมูลแผ่นงาน (sheet1.xml) ในไฟล์ Excel")

                root = ET.fromstring(sheet_xml)
                rows_data = []
                for row_el in root.findall(".//{*}sheetData/{*}row"):
                    row_cells = {}
                    for c in row_el.findall("{*}c"):
                        cell_ref = c.attrib.get("r", "") # e.g. A1, B2
                        # Extract column letters
                        col_letters = "".join(filter(str.isalpha, cell_ref))
                        cell_type = c.attrib.get("t", "")
                        v_el = c.find("{*}v")
                        val = ""
                        if v_el is not None and v_el.text:
                            if cell_type == "s":
                                str_idx = int(v_el.text)
                                val = shared_strings[str_idx] if str_idx < len(shared_strings) else ""
                            else:
                                val = v_el.text
                        elif c.find("{*}is/{*}t") is not None:
                            val = c.find("{*}is/{*}t").text or ""
                        row_cells[col_letters] = val.strip()
                    if row_cells:
                        rows_data.append(row_cells)

                if not rows_data:
                    return []

                # First row is headers
                first_row = rows_data[0]
                col_keys = sorted(first_row.keys(), key=lambda k: (len(k), k))
                headers = [first_row.get(k, "") for k in col_keys]

                dict_rows = []
                for r in rows_data[1:]:
                    row_dict = {}
                    for idx, k in enumerate(col_keys):
                        h = headers[idx]
                        if h:
                            row_dict[h] = r.get(k, "")
                    if any(row_dict.values()):
                        dict_rows.append(row_dict)

                return dict_rows
        except Exception as e:
            raise ValueError(f"เกิดข้อผิดพลาดในการเปิดไฟล์ Excel: {str(e)}")

    @classmethod
    def _find_field(cls, row: Dict[str, str], aliases: List[str]) -> str:
        for k, v in row.items():
            k_clean = k.strip().lower()
            for a in aliases:
                if a.lower() in k_clean or k_clean in a.lower():
                    return v.strip()
        return ""

    @classmethod
    def process_import(
        cls,
        file_bytes: bytes,
        filename: str,
        mode: str,
        data_manager: Any
    ) -> Dict[str, Any]:
        """
        Processes import of courses and assignments.
        mode: 'replace' | 'append'
        """
        rows = cls.parse_file_to_rows(file_bytes, filename)
        if not rows:
            raise ValueError("ไม่พบข้อมูลในไฟล์ที่อัปโหลด")

        # Load existing data
        all_data = data_manager.get_all_data()
        teachers = all_data.get("teachers", [])
        rooms = all_data.get("rooms", [])
        groups = all_data.get("groups", [])
        courses = {c["id"]: c for c in all_data.get("courses", [])}
        assignments = all_data.get("assignments", [])

        if mode == "replace":
            # Clear existing courses & assignments
            courses = {}
            assignments = []

        imported_count = 0
        new_teachers_count = 0
        new_groups_count = 0
        errors = []

        for idx, row in enumerate(rows, start=2):
            code = cls._find_field(row, ["รหัสวิชา", "code", "course_code"])
            name = cls._find_field(row, ["ชื่อวิชา", "name", "course_name", "วิชา"])
            course_type_raw = cls._find_field(row, ["ประเภทวิชา", "type", "course_type"])
            periods_raw = cls._find_field(row, ["จำนวนคาบ", "คาบ", "periods", "weekly_periods"])
            room_type_raw = cls._find_field(row, ["ประเภทห้อง", "ห้อง", "room_type", "ห้องที่ต้องการ"])
            teacher_name = cls._find_field(row, ["ครูผู้สอน", "ผู้สอน", "teacher", "อาจารย์", "ครู"])
            primary_group_name = cls._find_field(row, ["กลุ่มผู้เรียน", "กลุ่มเรียน", "group", "ห้องเรียนผู้เรียน"])
            secondary_group_name = cls._find_field(row, ["กลุ่มเรียนรวม", "เรียนรวม", "secondary_group", "กลุ่มร่วม"])
            rotation_raw = cls._find_field(row, ["หมุนเวียนฐาน", "หมุนฐาน", "rotation", "is_rotation"])

            if not name:
                errors.append(f"แถวที่ {idx}: ขาดชื่อวิชา")
                continue

            if not code:
                code = f"C_{len(courses)+1:03d}"

            # Normalize Rotation & Course Type
            is_rotation = any(w in rotation_raw.lower() for w in ["ใช่", "yes", "true", "1"])
            course_type = CourseType.THEORY.value
            if any(w in course_type_raw.lower() for w in ["ปฏิบัติ", "practice", "lab"]):
                course_type = CourseType.ROTATION_BASE.value if is_rotation else CourseType.PRACTICE.value
            elif is_rotation:
                course_type = CourseType.ROTATION_BASE.value

            # Normalize Periods
            try:
                periods = int(periods_raw) if periods_raw else (4 if course_type != CourseType.THEORY.value else 2)
            except ValueError:
                periods = 4 if course_type != CourseType.THEORY.value else 2

            # Normalize Room Type
            room_type = RoomType.CLASSROOM.value
            if any(w in room_type_raw.lower() for w in ["ปฏิบัติ", "lab", "ศูนย์", "โรงฝึก"]):
                room_type = RoomType.LAB_ENGINE.value
            elif any(w in room_type_raw.lower() for w in ["บรรยาย", "lecture"]):
                room_type = RoomType.LECTURE_HALL.value

            # Match or Create Teacher
            teacher_id = ""
            if teacher_name:
                matched_t = next((t for t in teachers if t["name"].strip() == teacher_name), None)
                if matched_t:
                    teacher_id = matched_t["id"]
                else:
                    teacher_id = f"T_AUTO_{len(teachers)+1}"
                    new_t = {
                        "id": teacher_id,
                        "name": teacher_name,
                        "max_periods_per_day": 6,
                        "unavailable_slots": []
                    }
                    teachers.append(new_t)
                    new_teachers_count += 1
            else:
                # Default to first teacher
                teacher_id = teachers[0]["id"] if teachers else "T_DEFAULT"

            # Match or Create Primary Group
            primary_group_id = ""
            if primary_group_name:
                matched_g = next((g for g in groups if g["name"].strip() == primary_group_name), None)
                if matched_g:
                    primary_group_id = matched_g["id"]
                else:
                    primary_group_id = f"G_AUTO_{len(groups)+1}"
                    level = "HIGH_VOC_CERT" if "ปวส" in primary_group_name else "VOC_CERT"
                    new_g = {
                        "id": primary_group_id,
                        "name": primary_group_name,
                        "level": level,
                        "student_count": 20
                    }
                    groups.append(new_g)
                    new_groups_count += 1
            else:
                primary_group_id = groups[0]["id"] if groups else "G_DEFAULT"

            # Match or Create Secondary Group (if any)
            secondary_group_id = None
            if secondary_group_name:
                matched_sec = next((g for g in groups if g["name"].strip() == secondary_group_name), None)
                if matched_sec:
                    secondary_group_id = matched_sec["id"]
                else:
                    secondary_group_id = f"G_AUTO_{len(groups)+1}"
                    level = "HIGH_VOC_CERT" if "ปวส" in secondary_group_name else "VOC_CERT"
                    new_g = {
                        "id": secondary_group_id,
                        "name": secondary_group_name,
                        "level": level,
                        "student_count": 20
                    }
                    groups.append(new_g)
                    new_groups_count += 1

            # Create Course
            course_id = f"C_{code.replace('-', '_')}_{primary_group_id}"
            courses[course_id] = {
                "id": course_id,
                "name": name,
                "code": code,
                "course_type": course_type,
                "periods_per_session": periods,
                "sessions_per_week": 1,
                "required_room_type": room_type,
                "allow_merge": bool(secondary_group_id),
                "base_id": f"BASE_{code}" if is_rotation else None
            }

            # Create Lesson Assignment
            ass_id = f"ASS_{code.replace('-', '_')}_{primary_group_id}"
            assignments.append({
                "id": ass_id,
                "course_id": course_id,
                "primary_group_id": primary_group_id,
                "teacher_id": teacher_id,
                "secondary_group_id": secondary_group_id,
                "is_rotation": is_rotation
            })

            imported_count += 1

        # Commit updates to data manager
        data_manager.teachers = teachers
        data_manager.groups = groups
        data_manager.courses = courses
        data_manager.assignments = assignments
        data_manager._save()

        return {
            "is_success": True,
            "imported_count": imported_count,
            "new_teachers_count": new_teachers_count,
            "new_groups_count": new_groups_count,
            "total_courses": len(courses),
            "total_assignments": len(assignments),
            "errors": errors
        }

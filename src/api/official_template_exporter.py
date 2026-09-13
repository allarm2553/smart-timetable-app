"""
Official Vocational Template Excel Exporter (.xlsx)
Populates timetable schedule data directly into the college's official
Excel workbook template (preserving formatting, logos, borders, formulas, and signatures).
"""
import os
import io
from typing import Dict, Any, List, Optional
import openpyxl
from openpyxl.styles import Alignment, Font, Border, Side

class OfficialTemplateExporter:
    TEMPLATE_PATH = os.path.join("data", "template_example.xlsx")
    
    # Grid Row definitions for 5 days (each day has 3 sub-rows)
    DAY_ROWS = [14, 17, 20, 23, 26] # Monday, Tuesday, Wednesday, Thursday, Friday
    
    BLOCK_LABELS = [
        "สัปดาห์ที่ 1–3 (บล็อก 1)",
        "สัปดาห์ที่ 4–6 (บล็อก 2)",
        "สัปดาห์ที่ 7–9 (บล็อก 3)",
        "สัปดาห์ที่ 10–12 (บล็อก 4)",
        "สัปดาห์ที่ 13–15 (บล็อก 5)",
        "สัปดาห์ที่ 16–18 (บล็อก 6 ปวช.)"
    ]

    def __init__(self, schedule: List[Dict[str, Any]], config: Dict[str, Any], template_path: Optional[str] = None):
        self.schedule = schedule
        self.config = config
        self.template_path = template_path or self.TEMPLATE_PATH
        
        # Build lookup maps
        self.teachers_map = {t["id"]: t for t in config.get("teachers", [])}
        self.rooms_map = {r["id"]: r for r in config.get("rooms", [])}
        self.groups_map = {g["id"]: g for g in config.get("groups", [])}
        self.courses_map = {c["id"]: c for c in config.get("courses", {}).values()} if isinstance(config.get("courses"), dict) else {c["id"]: c for c in config.get("courses", [])}

    def _get_clean_title(self, name: str) -> str:
        """Create a safe Excel sheet name (no / or invalid chars, max 31 chars)"""
        clean = str(name).replace("/", "-").replace("\\", "-").replace("?", "").replace("*", "").replace(":", "-").replace("[", "").replace("]", "")
        return clean[:31]

    def _safe_merge_cells(self, ws, start_row: int, start_column: int, end_row: int, end_column: int):
        """Safely merge cells by removing any overlapping merges first to prevent Excel repair errors."""
        to_remove = []
        for rng in ws.merged_cells.ranges:
            if not (rng.max_row < start_row or rng.min_row > end_row or
                    rng.max_col < start_column or rng.min_col > end_column):
                to_remove.append(rng)
        for rng in to_remove:
            ws.merged_cells.ranges.remove(rng)
        ws.merge_cells(start_row=start_row, start_column=start_column, end_row=end_row, end_column=end_column)

    def _clear_sheet_data(self, ws):
        """Clean all data and merges in course table and timetable grid so no residual data remains."""
        # 1. Clear course summary table (Rows 4 to 10)
        for r in range(4, 11):
            for col_letter in ["I", "L", "T", "U", "V", "W"]:
                ws[f"{col_letter}{r}"] = None

        # 2. Clear timetable grid (Rows 14 to 28, Cols 3 to 38) and remove any merges in this grid
        grid_merges = []
        for rng in ws.merged_cells.ranges:
            if rng.min_col >= 3 and any(r in range(14, 29) for r in range(rng.min_row, rng.max_row + 1)):
                grid_merges.append(rng)
        for rng in grid_merges:
            ws.merged_cells.ranges.remove(rng)

        for r in range(14, 29):
            for c in range(3, 39):
                ws.cell(row=r, column=c, value=None)

    def _populate_group_sheet(self, ws, group_id: str, block: int = 1):
        self._clear_sheet_data(ws)
        group = self.groups_map.get(group_id, {"id": group_id, "name": group_id, "student_count": 20})
        group_name = group["name"]
        
        # Header Info
        ws["B6"] = "1/2569"
        ws["B7"] = "อ.พงษ์สถิต" # ครูที่ปรึกษา
        ws["B8"] = "546"
        ws["B9"] = group_name
        block_idx = max(0, min(block - 1, len(self.BLOCK_LABELS) - 1))
        ws["AG1"] = self.BLOCK_LABELS[block_idx]

        # Filter lessons for this group and block
        lessons = [
            s for s in self.schedule
            if block in s.get("active_blocks", []) and (
                s.get("primary_group_id") == group_id or s.get("secondary_group_id") == group_id
            )
        ]

        # 1. Fill course summary at top right (Rows 4 to 10)
        unique_courses = {}
        for l in lessons:
            cid = l.get("course_id")
            if cid and cid not in unique_courses:
                unique_courses[cid] = l

        for r_idx, (cid, l) in enumerate(unique_courses.items(), start=4):
            if r_idx <= 10:
                c_obj = self.courses_map.get(cid)
                raw_code = c_obj.get("code") if c_obj else l.get("course_code", cid)
                code = str(raw_code).replace("ป. ", "").replace("ท. ", "").replace("ป.", "").replace("ท.", "").strip()
                c_name = c_obj.get("name") if c_obj else l.get("course_name", "")
                c_type = c_obj.get("course_type", "THEORY") if c_obj else "THEORY"
                is_prac = (c_type == "PRACTICE" or "ปฏิบัติ" in str(c_name))
                periods = c_obj.get("periods_per_session", l.get("duration", 2)) if c_obj else l.get("duration", 2)
                
                t_hrs = 0 if is_prac else periods
                p_hrs = periods if is_prac else 0
                credits_val = 2
                total_hrs = t_hrs + p_hrs

                ws[f"I{r_idx}"] = code
                ws[f"L{r_idx}"] = c_name
                ws[f"T{r_idx}"] = t_hrs
                ws[f"U{r_idx}"] = p_hrs
                ws[f"V{r_idx}"] = credits_val
                ws[f"W{r_idx}"] = total_hrs

        # 2. Fill Timetable Grid (Rows 14 to 28)
        self._fill_grid(ws, lessons, view_type="group")

    def _populate_teacher_sheet(self, ws, teacher_id: str, block: int = 1):
        self._clear_sheet_data(ws)
        teacher = self.teachers_map.get(teacher_id, {"id": teacher_id, "name": teacher_id})
        t_name = teacher["name"]

        # Header Info
        ws["B6"] = "1/2569"
        ws["B7"] = "อิเล็กทรอนิกส์"
        ws["B8"] = t_name
        ws["B9"] = "ครุศาสตร์อุตสาหกรรมมหาบัณฑิต"
        ws["B10"] = "ครูผู้สอน"
        block_idx = max(0, min(block - 1, len(self.BLOCK_LABELS) - 1))
        ws["AG1"] = self.BLOCK_LABELS[block_idx]

        # Filter lessons for this teacher and block (both primary teacher and co-teacher)
        lessons = [
            s for s in self.schedule
            if block in s.get("active_blocks", []) and (
                s.get("teacher_id") == teacher_id or s.get("secondary_teacher_id") == teacher_id
            )
        ]

        # 1. Fill course summary at top right (Rows 4 to 10)
        unique_courses = {}
        for l in lessons:
            cid = l.get("course_id")
            if cid and cid not in unique_courses:
                unique_courses[cid] = l

        for r_idx, (cid, l) in enumerate(unique_courses.items(), start=4):
            if r_idx <= 10:
                c_obj = self.courses_map.get(cid)
                raw_code = c_obj.get("code") if c_obj else l.get("course_code", cid)
                code = str(raw_code).replace("ป. ", "").replace("ท. ", "").replace("ป.", "").replace("ท.", "").strip()
                c_name = c_obj.get("name") if c_obj else l.get("course_name", "")
                c_type = c_obj.get("course_type", "THEORY") if c_obj else "THEORY"
                is_prac = (c_type == "PRACTICE" or "ปฏิบัติ" in str(c_name))
                periods = c_obj.get("periods_per_session", l.get("duration", 2)) if c_obj else l.get("duration", 2)
                
                t_hrs = 0 if is_prac else periods
                p_hrs = periods if is_prac else 0
                credits_val = 2
                total_hrs = t_hrs + p_hrs

                ws[f"I{r_idx}"] = code
                ws[f"L{r_idx}"] = c_name
                ws[f"T{r_idx}"] = t_hrs
                ws[f"U{r_idx}"] = p_hrs
                ws[f"V{r_idx}"] = credits_val
                ws[f"W{r_idx}"] = total_hrs

        # 2. Fill Timetable Grid
        self._fill_grid(ws, lessons, view_type="teacher")

    def _populate_room_sheet(self, ws, room_id: str, block: int = 1):
        self._clear_sheet_data(ws)
        room = self.rooms_map.get(room_id, {"id": room_id, "name": room_id})
        r_name = room["name"]

        # Header Info
        ws["B6"] = "1/2569"
        ws["B7"] = "อาคารเรียน 5"
        ws["B8"] = r_name
        block_idx = max(0, min(block - 1, len(self.BLOCK_LABELS) - 1))
        ws["AG1"] = self.BLOCK_LABELS[block_idx]

        # Filter lessons for this room and block
        lessons = [
            s for s in self.schedule
            if block in s.get("active_blocks", []) and s.get("room_id") == room_id
        ]

        # 1. Fill course summary at top right (Rows 4 to 10)
        unique_courses = {}
        for l in lessons:
            cid = l.get("course_id")
            if cid and cid not in unique_courses:
                unique_courses[cid] = l

        for r_idx, (cid, l) in enumerate(unique_courses.items(), start=4):
            if r_idx <= 10:
                c_obj = self.courses_map.get(cid)
                raw_code = c_obj.get("code") if c_obj else l.get("course_code", cid)
                code = str(raw_code).replace("ป. ", "").replace("ท. ", "").replace("ป.", "").replace("ท.", "").strip()
                c_name = c_obj.get("name") if c_obj else l.get("course_name", "")
                c_type = c_obj.get("course_type", "THEORY") if c_obj else "THEORY"
                is_prac = (c_type == "PRACTICE" or "ปฏิบัติ" in str(c_name))
                periods = c_obj.get("periods_per_session", l.get("duration", 2)) if c_obj else l.get("duration", 2)
                
                t_hrs = 0 if is_prac else periods
                p_hrs = periods if is_prac else 0
                credits_val = 2
                total_hrs = t_hrs + p_hrs

                ws[f"I{r_idx}"] = code
                ws[f"L{r_idx}"] = c_name
                ws[f"T{r_idx}"] = t_hrs
                ws[f"U{r_idx}"] = p_hrs
                ws[f"V{r_idx}"] = credits_val
                ws[f"W{r_idx}"] = total_hrs

        # 2. Fill Timetable Grid
        self._fill_grid(ws, lessons, view_type="room")

    def _fill_grid(self, ws, lessons: List[Dict[str, Any]], view_type: str):
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for l in lessons:
            day_idx = l.get("day", 0)
            if day_idx < 0 or day_idx >= len(self.DAY_ROWS):
                continue
            base_row = self.DAY_ROWS[day_idx]
            p = l.get("start_period", 1)
            dur = l.get("duration", 1)

            # Columns in template: Period 1 starts at Col 3 (C), each period is 3 cols
            start_col = 3 + (p - 1) * 3
            end_col = start_col + dur * 3 - 1

            cid = l.get("course_id")
            c_obj = self.courses_map.get(cid)
            c_type = c_obj.get("course_type", "THEORY") if c_obj else "THEORY"
            is_prac = (c_type == "PRACTICE" or "ปฏิบัติ" in str(l.get("course_name", "")))
            prefix = "ป. " if is_prac else "ท. "
            
            raw_code = str(l.get("course_code") or l.get("course_name") or cid).strip()
            if raw_code.startswith("ป.") or raw_code.startswith("ท."):
                line1 = raw_code
            else:
                line1 = f"{prefix}{raw_code}"
            
            t1 = l.get("teacher_name", "")
            t2 = l.get("secondary_teacher_name", "")
            teacher_label = f"{t1}/{t2}" if (t2 and t2 != t1) else t1

            if view_type == "group":
                line2 = l.get("room_name", "")
                line3 = teacher_label
            elif view_type == "teacher":
                line2 = l.get("room_name", "")
                g_id = l.get("primary_group_id")
                g_name = self.groups_map.get(g_id, {}).get("name", g_id)
                if l.get("is_merged") and l.get("secondary_group_id"):
                    g2_name = self.groups_map.get(l["secondary_group_id"], {}).get("name", l["secondary_group_id"])
                    g_name = f"{g_name}+{g2_name}"
                if t2 and t2 != t1:
                    line3 = f"{g_name} (ร่วมสอน)"
                else:
                    line3 = g_name
            else: # room
                line2 = teacher_label
                g_id = l.get("primary_group_id")
                line3 = self.groups_map.get(g_id, {}).get("name", g_id)

            # Write 3 rows
            c1 = ws.cell(row=base_row, column=start_col, value=line1)
            c2 = ws.cell(row=base_row + 1, column=start_col, value=line2)
            c3 = ws.cell(row=base_row + 2, column=start_col, value=line3)

            c1.alignment = center_align
            c2.alignment = center_align
            c3.alignment = center_align

            # Bold fonts
            c1.font = Font(name="Sarabun", size=10, bold=True)
            c2.font = Font(name="Sarabun", size=10, bold=True)
            c3.font = Font(name="Sarabun", size=9, bold=False)

            # Merge horizontally safely
            if end_col > start_col:
                self._safe_merge_cells(ws, start_row=base_row, start_column=start_col, end_row=base_row, end_column=end_col)
                self._safe_merge_cells(ws, start_row=base_row + 1, start_column=start_col, end_row=base_row + 1, end_column=end_col)
                self._safe_merge_cells(ws, start_row=base_row + 2, start_column=start_col, end_row=base_row + 2, end_column=end_col)

    def export_single_view(self, view_type: str, view_id: str, block: int = 1) -> bytes:
        """Exports a single group, teacher, or room schedule as a genuine .xlsx workbook"""
        wb = openpyxl.load_workbook(self.template_path)
        
        if view_type == "group":
            template_sheet = wb["ตารางนักเรียน"]
            grp = self.groups_map.get(view_id, {"name": view_id})
            sheet_title = self._get_clean_title(f"ตาราง_{grp['name']}")
            ws = wb.copy_worksheet(template_sheet)
            ws.title = sheet_title
            self._populate_group_sheet(ws, view_id, block)
        elif view_type == "teacher":
            template_sheet = wb["ตารางครู"]
            tea = self.teachers_map.get(view_id, {"name": view_id})
            sheet_title = self._get_clean_title(f"ตาราง_{tea['name']}")
            ws = wb.copy_worksheet(template_sheet)
            ws.title = sheet_title
            self._populate_teacher_sheet(ws, view_id, block)
        else: # room
            template_sheet = wb["ห้องเรียน"]
            rm = self.rooms_map.get(view_id, {"name": view_id})
            sheet_title = self._get_clean_title(f"ห้อง_{rm['name']}")
            ws = wb.copy_worksheet(template_sheet)
            ws.title = sheet_title
            self._populate_room_sheet(ws, view_id, block)

        # Remove the raw template sheets so only the populated sheet remains (or keep as needed)
        sheets_to_remove = ["ตารางเปล่า", "ตารางครู", "ตารางนักเรียน", "ห้องเรียน"]
        for sname in sheets_to_remove:
            if sname in wb.sheetnames and sname != ws.title:
                del wb[sname]

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def export_all_groups(self, block: int = 1) -> bytes:
        """Exports all student groups into a single genuine .xlsx workbook with multiple tabs"""
        wb = openpyxl.load_workbook(self.template_path)
        template_sheet = wb["ตารางนักเรียน"]

        groups_list = list(self.groups_map.values())
        created_sheets = []

        for grp in groups_list:
            gid = grp["id"]
            sheet_title = self._get_clean_title(f"ตาราง_{grp['name']}")
            ws = wb.copy_worksheet(template_sheet)
            ws.title = sheet_title
            self._populate_group_sheet(ws, gid, block)
            created_sheets.append(ws)

        # Remove the default templates
        sheets_to_remove = ["ตารางเปล่า", "ตารางครู", "ตารางนักเรียน", "ห้องเรียน"]
        for sname in sheets_to_remove:
            if sname in wb.sheetnames:
                del wb[sname]

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def export_full_college_package(self, block: int = 1) -> bytes:
        """Exports all groups, teachers, and rooms into one comprehensive .xlsx workbook"""
        wb = openpyxl.load_workbook(self.template_path)
        
        # 1. Groups
        t_group = wb["ตารางนักเรียน"]
        for grp in self.groups_map.values():
            ws = wb.copy_worksheet(t_group)
            ws.title = self._get_clean_title(f"กลุ่ม_{grp['name']}")
            self._populate_group_sheet(ws, grp["id"], block)

        # 2. Teachers
        t_teacher = wb["ตารางครู"]
        for tea in self.teachers_map.values():
            ws = wb.copy_worksheet(t_teacher)
            ws.title = self._get_clean_title(f"ครู_{tea['name']}")
            self._populate_teacher_sheet(ws, tea["id"], block)

        # 3. Rooms
        t_room = wb["ห้องเรียน"]
        for rm in self.rooms_map.values():
            ws = wb.copy_worksheet(t_room)
            ws.title = self._get_clean_title(f"ห้อง_{rm['name']}")
            self._populate_room_sheet(ws, rm["id"], block)

        # Remove default templates
        for sname in ["ตารางเปล่า", "ตารางครู", "ตารางนักเรียน", "ห้องเรียน"]:
            if sname in wb.sheetnames:
                del wb[sname]

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

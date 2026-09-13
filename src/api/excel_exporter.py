"""
Vocational Timetable Excel Exporter
Generates standard SpreadsheetML (.xls) compatible with Microsoft Excel,
LibreOffice, Google Sheets, and Apple Numbers without requiring external dependencies.
"""
from typing import Dict, Any, List
import html

class VocationalExcelExporter:
    DAY_NAMES = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์"]
    
    PERIOD_HEADERS = [
        ("คาบ 0", "07:30-08:00"),
        ("คาบ 1", "08:00-09:00"),
        ("คาบ 2", "09:00-10:00"),
        ("คาบ 3", "10:00-11:00"),
        ("คาบ 4", "11:00-12:00"),
        ("คาบ 5 (พัก)", "12:00-13:00"),
        ("คาบ 6", "13:00-14:00"),
        ("คาบ 7", "14:00-15:00"),
        ("คาบ 8", "15:00-16:00"),
        ("คาบ 9", "16:00-17:00"),
        ("คาบ 10", "17:00-18:00"),
        ("คาบ 11", "18:00-19:00"),
        ("คาบ 12", "19:00-20:00")
    ]

    def __init__(self, schedule_data: Dict[str, Any], config_data: Dict[str, Any]):
        self.schedule = schedule_data
        self.config = config_data
        self.scheduled_lessons = schedule_data.get("scheduled_lessons", [])
        
        # Maps for quick lookup
        self.teachers_map = {t["id"]: t["name"] for t in config_data.get("teachers", [])}
        self.rooms_map = {r["id"]: r["name"] for r in config_data.get("rooms", [])}
        self.groups_map = {g["id"]: g["name"] for g in config_data.get("groups", [])}

    def _escape(self, text: str) -> str:
        if not text:
            return ""
        return html.escape(str(text))

    def _get_styles(self) -> str:
        return """
  <Style ss:ID="Default" ss:Name="Normal">
    <Alignment ss:Vertical="Center"/>
    <Borders/>
    <Font ss:FontName="Sarabun" x:CharSet="222" ss:Size="10"/>
    <Interior/>
    <NumberFormat/>
    <Protection/>
  </Style>
  <Style ss:ID="TitleStyle">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
    <Font ss:FontName="Sarabun" ss:Size="14" ss:Bold="1" ss:Color="#0F172A"/>
  </Style>
  <Style ss:ID="SubtitleStyle">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
    <Font ss:FontName="Sarabun" ss:Size="11" ss:Bold="1" ss:Color="#334155"/>
  </Style>
  <Style ss:ID="ThDay">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
    </Borders>
    <Font ss:FontName="Sarabun" ss:Size="10" ss:Bold="1" ss:Color="#0F172A"/>
    <Interior ss:Color="#E2E8F0" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="ThPeriod">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
    </Borders>
    <Font ss:FontName="Sarabun" ss:Size="9" ss:Bold="1" ss:Color="#0F172A"/>
    <Interior ss:Color="#E2E8F0" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="DayName">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#64748B"/>
    </Borders>
    <Font ss:FontName="Sarabun" ss:Size="10" ss:Bold="1" ss:Color="#0F172A"/>
    <Interior ss:Color="#F8FAFC" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="FlagCell">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    </Borders>
    <Font ss:FontName="Sarabun" ss:Size="8" ss:Color="#64748B"/>
    <Interior ss:Color="#F1F5F9" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="LunchCell">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CBD5E1"/>
    </Borders>
    <Font ss:FontName="Sarabun" ss:Size="9" ss:Bold="1" ss:Color="#64748B"/>
    <Interior ss:Color="#F1F5F9" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="EmptyCell">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
    </Borders>
    <Font ss:FontName="Sarabun" ss:Size="9" ss:Color="#94A3B8"/>
    <Interior ss:Color="#FFFFFF" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="LessonCard">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CA8A04"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CA8A04"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CA8A04"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#CA8A04"/>
    </Borders>
    <Font ss:FontName="Sarabun" ss:Size="9" ss:Bold="1" ss:Color="#713F12"/>
    <Interior ss:Color="#FEF9C3" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="MergedLessonCard">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#9333EA"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#9333EA"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#9333EA"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#9333EA"/>
    </Borders>
    <Font ss:FontName="Sarabun" ss:Size="9" ss:Bold="1" ss:Color="#581C87"/>
    <Interior ss:Color="#F3E8FF" ss:Pattern="Solid"/>
  </Style>
"""

    def _build_sheet(self, title: str, subtitle: str, lessons_for_view: List[Dict[str, Any]]) -> str:
        grid = {d: {p: None for p in range(1, 13)} for d in range(5)}
        
        for lesson in lessons_for_view:
            d = lesson.get("day_of_week", 0)
            start_p = lesson.get("start_period", 1)
            if 0 <= d < 5 and 1 <= start_p <= 12:
                grid[d][start_p] = lesson

        rows_xml = []

        # 1. Title Row
        rows_xml.append(f"""   <Row ss:Height="24">
    <Cell ss:MergeAcross="13" ss:StyleID="TitleStyle">
     <Data ss:Type="String">{self._escape(title)}</Data>
    </Cell>
   </Row>""")

        # 2. Subtitle Row
        rows_xml.append(f"""   <Row ss:Height="20">
    <Cell ss:MergeAcross="13" ss:StyleID="SubtitleStyle">
     <Data ss:Type="String">{self._escape(subtitle)}</Data>
    </Cell>
   </Row>""")

        # Blank spacing row
        rows_xml.append('   <Row ss:Height="8"/>')

        # 3. Header Row 1 (Period numbers)
        header_row1 = ['   <Row ss:Height="22">']
        header_row1.append('    <Cell ss:StyleID="ThDay"><Data ss:Type="String">วัน / คาบ</Data></Cell>')
        for p_name, _ in self.PERIOD_HEADERS:
            header_row1.append(f'    <Cell ss:StyleID="ThPeriod"><Data ss:Type="String">{self._escape(p_name)}</Data></Cell>')
        header_row1.append('   </Row>')
        rows_xml.append('\n'.join(header_row1))

        # 4. Header Row 2 (Times)
        header_row2 = ['   <Row ss:Height="18">']
        header_row2.append('    <Cell ss:StyleID="ThDay"><Data ss:Type="String">เวลา</Data></Cell>')
        for _, p_time in self.PERIOD_HEADERS:
            header_row2.append(f'    <Cell ss:StyleID="ThPeriod"><Data ss:Type="String">{self._escape(p_time)}</Data></Cell>')
        header_row2.append('   </Row>')
        rows_xml.append('\n'.join(header_row2))

        # 5. Data Rows (Days Monday to Friday)
        for d in range(5):
            day_name = self.DAY_NAMES[d]
            row_items = [f'   <Row ss:Height="65">\n    <Cell ss:StyleID="DayName"><Data ss:Type="String">{day_name}</Data></Cell>']
            
            # Period 0 (Flag raising)
            row_items.append('    <Cell ss:StyleID="FlagCell"><Data ss:Type="String">กิจกรรม&#10;หน้าเสาธง&#10;โฮมรูม</Data></Cell>')

            p = 1
            while p <= 12:
                if p == 5:
                    row_items.append('    <Cell ss:StyleID="LunchCell"><Data ss:Type="String">พักกลางวัน&#10;(12:00-13:00)</Data></Cell>')
                    p += 1
                    continue

                lesson = grid[d][p]
                if lesson:
                    duration = lesson.get("duration_periods", 1)
                    merge_across = duration - 1
                    is_merged = lesson.get("is_merged_theory", False)
                    style_id = "MergedLessonCard" if is_merged else "LessonCard"
                    
                    code = lesson.get("course_code") or lesson.get("course_id", "")
                    name = lesson.get("course_name", "")
                    room_name = lesson.get("room_name", "")
                    teacher_name = lesson.get("teacher_name", "")
                    group_names = ", ".join(lesson.get("student_group_names", []))
                    
                    cell_text = f"{code} {name}&#10;ห้อง: {room_name}&#10;ผู้สอน: {teacher_name}&#10;กลุ่ม: {group_names}"
                    
                    if merge_across > 0:
                        row_items.append(f'    <Cell ss:MergeAcross="{merge_across}" ss:StyleID="{style_id}"><Data ss:Type="String">{cell_text}</Data></Cell>')
                    else:
                        row_items.append(f'    <Cell ss:StyleID="{style_id}"><Data ss:Type="String">{cell_text}</Data></Cell>')
                    
                    p += duration
                else:
                    row_items.append('    <Cell ss:StyleID="EmptyCell"><Data ss:Type="String">-</Data></Cell>')
                    p += 1

            row_items.append('   </Row>')
            rows_xml.append('\n'.join(row_items))

        col_specs = """   <Column ss:Width="70"/>
   <Column ss:Width="65"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>
   <Column ss:Width="65"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>
   <Column ss:Width="75"/>"""

        return f""" <Worksheet ss:Name="{self._escape(title[:31])}">
  <Table ss:DefaultColumnWidth="75" ss:DefaultRowHeight="20">
{col_specs}
{chr(10).join(rows_xml)}
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Margin="0.3"/>
    <Footer x:Margin="0.3"/>
    <PageMargins x:Bottom="0.5" x:Left="0.5" x:Right="0.5" x:Top="0.5"/>
   </PageSetup>
   <Print>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>600</VerticalResolution>
   </Print>
   <Selected/>
   <Panes>
    <Pane>
     <Number>3</Number>
     <ActiveRow>1</ActiveRow>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
  </WorksheetOptions>
 </Worksheet>"""

    def export(self, view_type: str = "group", view_id: str = "") -> str:
        worksheets = []
        semester_subtitle = "วิทยาลัยการอาชีพ/เทคนิค | ภาคเรียนที่ 1 ประจำปีการศึกษา 2567"

        if view_type == "all_groups":
            for group in self.config.get("groups", []):
                gid = group["id"]
                gname = group["name"]
                lessons = [l for l in self.scheduled_lessons if gid in l.get("student_group_ids", [])]
                sheet_xml = self._build_sheet(
                    title=f"กลุ่ม {gname}",
                    subtitle=f"{semester_subtitle} (ระดับ: {group.get('level', 'vocational')})",
                    lessons_for_view=lessons
                )
                worksheets.append(sheet_xml)
        elif view_type == "teacher":
            tname = self.teachers_map.get(view_id, view_id)
            lessons = [l for l in self.scheduled_lessons if l.get("teacher_id") == view_id]
            sheet_xml = self._build_sheet(
                title=f"ตารางสอน {tname}",
                subtitle=semester_subtitle,
                lessons_for_view=lessons
            )
            worksheets.append(sheet_xml)
        elif view_type == "room":
            rname = self.rooms_map.get(view_id, view_id)
            lessons = [l for l in self.scheduled_lessons if l.get("room_id") == view_id]
            sheet_xml = self._build_sheet(
                title=f"ตารางห้อง {rname}",
                subtitle=semester_subtitle,
                lessons_for_view=lessons
            )
            worksheets.append(sheet_xml)
        else:
            gid = view_id or (self.config.get("groups", [{}])[0].get("id", ""))
            gname = self.groups_map.get(gid, gid)
            lessons = [l for l in self.scheduled_lessons if gid in l.get("student_group_ids", [])]
            sheet_xml = self._build_sheet(
                title=f"กลุ่ม {gname}",
                subtitle=semester_subtitle,
                lessons_for_view=lessons
            )
            worksheets.append(sheet_xml)

        if not worksheets:
            worksheets.append(self._build_sheet("ตารางเรียน", semester_subtitle, self.scheduled_lessons))

        workbook_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Smart Timetable System</Author>
  <Created>2026-09-13T12:00:00Z</Created>
  <Company>Vocational College</Company>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>12000</WindowHeight>
  <WindowWidth>18000</WindowWidth>
  <WindowTopX>100</WindowTopX>
  <WindowTopY>100</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
{self._get_styles()}
 </Styles>
{chr(10).join(worksheets)}
</Workbook>"""
        return workbook_xml

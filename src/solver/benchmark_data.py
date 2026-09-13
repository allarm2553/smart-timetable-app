from typing import List, Dict
from src.solver.models import (
    Teacher, Room, StudentGroup, Course, LessonAssignment,
    EducationLevel, CourseType, RoomType
)

def get_benchmark_dataset():
    # 1. ครูผู้สอน (อิงตามตัวอย่างตารางจริงในวิทยาลัย)
    teachers = [
        Teacher(id="T_PONG", name="พงษ์สถิต"),
        Teacher(id="T_PO", name="อ.ป้อ"),
        Teacher(id="T_JIRA", name="จิรวัฒน์"),
        Teacher(id="T_ANU", name="อนุชา"),
        Teacher(id="T_CHOO", name="ชูสกุล"),
        Teacher(id="T_PAT", name="ภัสพร"),
        Teacher(id="T_NOPA", name="นพนันท์"),
        Teacher(id="T_THOD", name="เทอดศักดิ์"),
        Teacher(id="T_THONG", name="ทองคำ"),
    ]

    # 2. ห้องเรียนและศูนย์ฝึก
    rooms = [
        Room(id="ROOM_545", name="545", room_type=RoomType.CLASSROOM, capacity=35),
        Room(id="ROOM_546", name="546 (ห้องบรรยายใหญ่)", room_type=RoomType.LECTURE_HALL, capacity=80),
        Room(id="ROOM_547", name="547", room_type=RoomType.CLASSROOM, capacity=35),
        Room(id="LAB_ENG", name="ศูนย์ฝึกเครื่องยนต์", room_type=RoomType.LAB_ENGINE, capacity=45),
        Room(id="LAB_ELEC", name="ศูนย์ฝึกไฟฟ้า", room_type=RoomType.LAB_ELECTRIC, capacity=45),
    ]

    # 3. กลุ่มเรียน (ชอ. = ช่างยนต์, ชส. = ปวส. เทคนิคยานยนต์)
    groups = [
        StudentGroup(id="G_CHO_1_1", name="ชอ.1/1", level=EducationLevel.VOC_CERT, student_count=20),
        StudentGroup(id="G_CHO_1_2", name="ชอ.1/2", level=EducationLevel.VOC_CERT, student_count=20),
        StudentGroup(id="G_CHO_1_3", name="ชอ.1/3", level=EducationLevel.VOC_CERT, student_count=19),
        StudentGroup(id="G_CHO_3_3", name="ชอ.3/3", level=EducationLevel.VOC_CERT, student_count=20),
        StudentGroup(id="G_PVS_1", name="ชอ.4/1 (ปวส.)", level=EducationLevel.HIGH_VOC_CERT, student_count=25),
    ]

    # 4. รายวิชา (รหัสวิชาตรงตามรูปแบบมาตรฐานอาชีวศึกษา)
    courses = {
        # วิชาทฤษฎีเรียนรวม 2 กลุ่มได้ (เช่น ชอ.1/1 + ชอ.1/2 ในห้อง 546)
        "C_20100_100": Course(
            id="C_20100_100",
            code="20100-100",
            name="ภาษาอังกฤษเพื่อการสื่อสาร",
            course_type=CourseType.THEORY,
            periods_per_session=1,
            required_room_type=RoomType.LECTURE_HALL,
            allow_merge=True
        ),
        # วิชาทฤษฎี 1 คาบ
        "C_20105_202": Course(
            id="C_20105_202",
            code="20105-202",
            name="ทฤษฎีเครื่องยนต์แก๊สโซลีน",
            course_type=CourseType.THEORY,
            periods_per_session=1,
            required_room_type=RoomType.CLASSROOM,
            allow_merge=False
        ),
        "C_20105_201": Course(
            id="C_20105_201",
            code="20105-201",
            name="คณิตศาสตร์ช่างยนต์",
            course_type=CourseType.THEORY,
            periods_per_session=1,
            required_room_type=RoomType.CLASSROOM,
            allow_merge=False
        ),
        # วิชาปฏิบัติ 3 คาบต่อเนื่อง (ป. นำหน้า)
        "C_P_20105_2023": Course(
            id="C_P_20105_2023",
            code="ป. 20105-2023",
            name="งานระบบฉีดเชื้อเพลิงอิเล็กทรอนิกส์",
            course_type=CourseType.PRACTICE,
            periods_per_session=3,
            required_room_type=RoomType.CLASSROOM
        ),
        "C_P_20100_1005": Course(
            id="C_P_20100_1005",
            code="ป. 20100-1005",
            name="งานเครื่องยนต์แก๊สโซลีน",
            course_type=CourseType.ROTATION_BASE,
            periods_per_session=3,
            required_room_type=RoomType.CLASSROOM,
            base_id="BASE_GAS"
        ),
        "C_P_20100_1007": Course(
            id="C_P_20100_1007",
            code="ป. 20100-1007",
            name="งานเครื่องยนต์ดีเซล",
            course_type=CourseType.ROTATION_BASE,
            periods_per_session=3,
            required_room_type=RoomType.CLASSROOM,
            base_id="BASE_DIESEL"
        ),
        "C_P_20105_2017": Course(
            id="C_P_20105_2017",
            code="ป. 20105-2017",
            name="งานปรับแต่งเครื่องยนต์",
            course_type=CourseType.PRACTICE,
            periods_per_session=3,
            required_room_type=RoomType.CLASSROOM
        ),
        "C_P_20100_2204": Course(
            id="C_P_20100_2204",
            code="ป. 20100-2204",
            name="งานเครื่องล่างและส่งกำลังยานยนต์",
            course_type=CourseType.PRACTICE,
            periods_per_session=3,
            required_room_type=RoomType.CLASSROOM
        ),
        "C_P_20000_2005": Course(
            id="C_P_20000_2005",
            code="ป. 20000-2005",
            name="กิจกรรมลูกเสือ/พัฒนาทักษะ",
            course_type=CourseType.PRACTICE,
            periods_per_session=2,
            required_room_type=RoomType.CLASSROOM
        ),
        # วิชาปฏิบัติ ปวส. (15 สัปดาห์ - สิ้นสุดสัปดาห์ 15)
        "C_PVS_30101": Course(
            id="C_PVS_30101",
            code="ป. 30101-2001",
            name="เทคโนโลยียานยนต์สมัยใหม่ (ปวส.)",
            course_type=CourseType.PRACTICE,
            periods_per_session=4,
            required_room_type=RoomType.LAB_ENGINE
        ),
    }

    # 5. การมอบหมายคาบเรียน (Assignments)
    assignments = [
        # --- รายวิชาเรียนรวม (Merged Theory: ชอ.1/1 + ชอ.1/2) ---
        LessonAssignment(
            id="L_ENG_MERGE",
            course=courses["C_20100_100"],
            primary_group_id="G_CHO_1_1",
            secondary_group_id="G_CHO_1_2",
            teacher_id="T_PONG"
        ),

        # --- คาบเรียน ชอ.1/3 ---
        LessonAssignment(
            id="L_103_THEORY_1",
            course=courses["C_20105_202"],
            primary_group_id="G_CHO_1_3",
            teacher_id="T_PONG"
        ),
        LessonAssignment(
            id="L_103_PRAC_1",
            course=courses["C_P_20105_2023"],
            primary_group_id="G_CHO_1_3",
            teacher_id="T_PONG"
        ),
        LessonAssignment(
            id="L_103_PRAC_2",
            course=courses["C_P_20100_1005"],
            primary_group_id="G_CHO_1_3",
            teacher_id="T_PO",
            is_rotation=True
        ),

        # --- คาบเรียน ชอ.3/3 ---
        LessonAssignment(
            id="L_303_PRAC_1",
            course=courses["C_P_20100_1007"],
            primary_group_id="G_CHO_3_3",
            teacher_id="T_JIRA",
            is_rotation=True
        ),
        LessonAssignment(
            id="L_303_PRAC_2",
            course=courses["C_P_20105_2017"],
            primary_group_id="G_CHO_3_3",
            teacher_id="T_ANU"
        ),
        LessonAssignment(
            id="L_303_ACT",
            course=courses["C_P_20000_2005"],
            primary_group_id="G_CHO_3_3",
            teacher_id="T_PAT"
        ),

        # --- คาบเรียน ชอ.1/1 & ชอ.1/2 ---
        LessonAssignment(
            id="L_101_PRAC",
            course=courses["C_P_20100_1005"],
            primary_group_id="G_CHO_1_1",
            teacher_id="T_CHOO",
            is_rotation=True
        ),
        LessonAssignment(
            id="L_102_PRAC",
            course=courses["C_P_20100_1005"],
            primary_group_id="G_CHO_1_2",
            teacher_id="T_THONG",
            is_rotation=True
        ),
        LessonAssignment(
            id="L_101_CHASSIS",
            course=courses["C_P_20100_2204"],
            primary_group_id="G_CHO_1_1",
            teacher_id="T_NOPA"
        ),
        LessonAssignment(
            id="L_102_CHASSIS",
            course=courses["C_P_20100_2204"],
            primary_group_id="G_CHO_1_2",
            teacher_id="T_PAT"
        ),

        # --- คาบเรียน ปวส. (15 สัปดาห์: สัปดาห์ 1-15 เท่านั้น) ---
        LessonAssignment(
            id="L_PVS_PRAC",
            course=courses["C_PVS_30101"],
            primary_group_id="G_PVS_1",
            teacher_id="T_PONG", # อ.พงษ์สถิต สอนทั้ง ปวช. และ ปวส.
            is_rotation=False
        ),
    ]

    return {
        "teachers": teachers,
        "rooms": rooms,
        "groups": groups,
        "courses": courses,
        "assignments": assignments
    }

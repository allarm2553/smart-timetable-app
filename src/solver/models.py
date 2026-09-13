from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Set

class EducationLevel(str, Enum):
    VOC_CERT = "VOC_CERT"            # ปวช. (18 สัปดาห์ = 6 บล็อก)
    HIGH_VOC_CERT = "HIGH_VOC_CERT"  # ปวส. (15 สัปดาห์ = 5 บล็อก)

class CourseType(str, Enum):
    THEORY = "THEORY"                # ทฤษฎี (จัด 1-2 คาบ หรือเรียนรวมได้)
    PRACTICE = "PRACTICE"            # ปฏิบัติทั่วไป (3-4 คาบต่อเนื่อง)
    ROTATION_BASE = "ROTATION_BASE"  # วิชาปฏิบัติฐานหมุนเวียน 3 สัปดาห์ (Micro-Block)

class RoomType(str, Enum):
    CLASSROOM = "CLASSROOM"          # ห้องเรียนทฤษฎีทั่วไป (30-40 คน)
    LECTURE_HALL = "LECTURE_HALL"    # ห้องบรรยายรวม (60-100 คน)
    LAB_ENGINE = "LAB_ENGINE"        # ศูนย์ฝึกงานช่างยนต์
    LAB_ELECTRIC = "LAB_ELECTRIC"    # ศูนย์ฝึกไฟฟ้ายานยนต์
    LAB_BODY_PAINT = "LAB_BODY_PAINT"# ศูนย์ฝึกตัวถังและสี

@dataclass
class Teacher:
    id: str
    name: str
    max_periods_per_day: int = 6
    unavailable_slots: Set[Tuple[int, int]] = field(default_factory=set)  # (day, period) ที่ไม่สะดวก
    is_head: bool = False             # เป็นหัวหน้างาน/หัวหน้าแผนกหรือไม่ (เพดานไม่เกิน 28 คาบ/สัปดาห์)
    max_periods_per_week: int = 34    # เพดานคาบสอนสูงสุดต่อสัปดาห์ (หัวหน้างาน ≤ 28, ทั่วไป ≤ 34, เพดานวิทยาลัย 35)
    qualification: str = ""           # วุฒิการศึกษา เช่น ค.อ.บ., วศ.บ., วศ.ม., ปริญญาตรี ฯลฯ
    special_duty: str = ""            # หน้าที่พิเศษ เช่น หัวหน้าแผนกวิชา, งานทะเบียน, งานวัดผล ฯลฯ

    def __post_init__(self):
        # หากกำหนดเป็นหัวหน้างานและยังใช้ค่าเริ่มต้น 34 ให้ปรับเป็น 28 อัตโนมัติ
        if self.is_head and self.max_periods_per_week == 34:
            self.max_periods_per_week = 28
        # เพดานสูงสุดของวิทยาลัยคือ 35 คาบต่อสัปดาห์
        if self.max_periods_per_week > 35:
            self.max_periods_per_week = 35

@dataclass
class Room:
    id: str
    name: str
    room_type: RoomType
    capacity: int

@dataclass
class StudentGroup:
    id: str
    name: str
    level: EducationLevel
    student_count: int
    pvs_18_weeks: bool = True         # โหมดเกลี่ย ปวส. เต็ม 18 สัปดาห์ (V.2 Challenge)
    active_blocks: List[int] = field(init=False)

    def __post_init__(self):
        # ปวช. เรียนบล็อก 0-5 (18 สัปดาห์)
        # ปวส. หาก pvs_18_weeks=True (V.2 Challenge) เกลี่ยเรียนบล็อก 0-5 (18 สัปดาห์เต็ม)
        if self.level == EducationLevel.VOC_CERT or self.pvs_18_weeks:
            self.active_blocks = [0, 1, 2, 3, 4, 5]
        else:
            self.active_blocks = [0, 1, 2, 3, 4]

@dataclass
class Course:
    id: str
    name: str
    course_type: CourseType
    periods_per_session: int     # จำนวนคาบต่อครั้ง (เช่น 2 คาบ หรือ 4 คาบติดกัน)
    code: str = ""               # รหัสวิชา เช่น 20101-2001 หรือ ป. 20105-2023
    sessions_per_week: int = 1   # สัปดาห์ละกี่ครั้ง
    required_room_type: RoomType = RoomType.CLASSROOM
    allow_merge: bool = False    # สามารถเรียนรวม 2 กลุ่มได้หรือไม่
    base_id: Optional[str] = None # สำหรับ ROTATION_BASE

@dataclass
class LessonAssignment:
    """การมอบหมายวิชาให้กลุ่มและครู"""
    id: str
    course: Course
    primary_group_id: str
    teacher_id: str
    secondary_teacher_id: Optional[str] = None  # ครูคนที่สอง / ครูร่วมสอน (Co-Teacher / Practice Instructor)
    secondary_group_id: Optional[str] = None     # สำหรับวิชาเรียนรวม (Merged Class 2 กลุ่ม)
    is_rotation: bool = False                     # เป็นวิชาฐานหมุนเวียนหรือไม่
    teaching_mode: str = "SINGLE"                # โหมดการสอน: SINGLE, CO_TEACHING, SPLIT_THEORY_PRACTICE


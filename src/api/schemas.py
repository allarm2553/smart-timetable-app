from typing import List, Optional, Dict, Set, Tuple
from pydantic import BaseModel, Field
from src.solver.models import EducationLevel, CourseType, RoomType

class TeacherDTO(BaseModel):
    id: str
    name: str
    max_periods_per_day: int = 6
    unavailable_slots: List[Tuple[int, int]] = Field(default_factory=list)
    is_head: bool = False
    max_periods_per_week: int = 34
    qualification: str = ""
    special_duty: str = ""

class RoomDTO(BaseModel):
    id: str
    name: str
    room_type: RoomType
    capacity: int

class StudentGroupDTO(BaseModel):
    id: str
    name: str
    level: EducationLevel
    student_count: int
    pvs_18_weeks: bool = True
    is_internship: bool = False

class CourseDTO(BaseModel):
    id: str
    name: str
    course_type: CourseType
    periods_per_session: int
    code: str = ""
    sessions_per_week: int = 1
    required_room_type: RoomType = RoomType.CLASSROOM
    allow_merge: bool = False
    base_id: Optional[str] = None

class LessonAssignmentDTO(BaseModel):
    id: str
    course_id: str
    primary_group_id: str
    teacher_id: str
    secondary_teacher_id: Optional[str] = None
    secondary_group_id: Optional[str] = None
    is_rotation: bool = False
    teaching_mode: str = "SINGLE"
    is_pinned: bool = False
    fixed_day: Optional[int] = None
    fixed_start_period: Optional[int] = None
    fixed_room_id: Optional[str] = None
    external_teacher_name: Optional[str] = None

class SolveRequest(BaseModel):
    teachers: List[TeacherDTO]
    rooms: List[RoomDTO]
    groups: List[StudentGroupDTO]
    courses: List[CourseDTO]
    assignments: List[LessonAssignmentDTO]
    days: int = 5
    periods_per_day: int = 12
    num_blocks: int = 6
    time_limit_seconds: float = 15.0
    pvs_18_weeks: bool = True

class ScheduleEntryDTO(BaseModel):
    assignment_id: str
    course_id: str
    course_name: str
    course_code: str = ""
    course_type: CourseType
    teacher_id: str
    teacher_name: str
    secondary_teacher_id: Optional[str] = None
    secondary_teacher_name: Optional[str] = None
    teaching_mode: str = "SINGLE"
    room_id: str
    room_name: str
    primary_group_id: str
    secondary_group_id: Optional[str] = None
    is_merged: bool = False
    day: int
    day_name: str
    start_period: int
    end_period: int
    duration: int
    active_blocks: List[int]
    is_pinned: bool = False
    fixed_day: Optional[int] = None
    fixed_start_period: Optional[int] = None
    fixed_room_id: Optional[str] = None
    external_teacher_name: Optional[str] = None

class SolveResponse(BaseModel):
    status: str
    is_success: bool
    execution_time_seconds: float
    total_lessons_scheduled: int
    schedule: List[ScheduleEntryDTO] = Field(default_factory=list)
    message: str = ""

class ValidateMoveRequest(BaseModel):
    schedule: List[ScheduleEntryDTO]
    assignment_id: str
    target_day: int
    target_start_period: int
    target_room_id: str

class ValidateMoveResponse(BaseModel):
    is_valid: bool
    conflicts: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class ApplyMoveRequest(BaseModel):
    schedule: List[ScheduleEntryDTO]
    assignment_id: str
    target_day: int
    target_start_period: int
    target_room_id: str

class ApplyMoveResponse(BaseModel):
    is_success: bool
    message: str
    updated_schedule: List[ScheduleEntryDTO] = Field(default_factory=list)

class SwapLessonsRequest(BaseModel):
    schedule: List[ScheduleEntryDTO]
    assignment_id_1: str
    assignment_id_2: str

class SwapLessonsResponse(BaseModel):
    is_success: bool
    message: str
    conflicts: List[str] = Field(default_factory=list)
    updated_schedule: List[ScheduleEntryDTO] = Field(default_factory=list)

class PinAssignmentRequest(BaseModel):
    is_pinned: bool
    fixed_day: Optional[int] = None
    fixed_start_period: Optional[int] = None
    fixed_room_id: Optional[str] = None
    external_teacher_name: Optional[str] = None


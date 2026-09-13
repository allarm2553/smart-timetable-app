from typing import Dict, List, Tuple, Optional
from ortools.sat.python import cp_model
from src.solver.models import (
    Teacher, Room, StudentGroup, Course, LessonAssignment,
    EducationLevel, CourseType
)

class TimetableSolver:
    def __init__(
        self,
        teachers: List[Teacher],
        rooms: List[Room],
        groups: List[StudentGroup],
        assignments: List[LessonAssignment],
        days: int = 5,            # จันทร์-ศุกร์ (0-4)
        periods_per_day: int = 12,# 12 คาบต่อวัน (08:00 - 20:00)
        num_blocks: int = 6,      # 6 บล็อก (บล็อกละ 3 สัปดาห์: ปวช.=0-5, ปวส.=0-4)
        lunch_period: int = 4     # คาบที่ 5 (index 4: 12:00-13:00) คือพักกลางวัน
    ):
        self.teachers = {t.id: t for t in teachers}
        self.rooms = {r.id: r for r in rooms}
        self.groups = {g.id: g for g in groups}
        self.assignments = {a.id: a for a in assignments}
        self.days = days
        self.periods_per_day = periods_per_day
        self.num_blocks = num_blocks
        self.lunch_period = lunch_period

        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Variables:
        # starts[a_id, d, p] -> bool: assignment starts on day d at period p
        self.starts = {}
        # assigned_room[a_id, r_id] -> bool
        self.assigned_room = {}
        # block_active[a_id, b] -> bool: whether assignment is active in block b
        self.block_active = {}
        # occupies[a_id, d, p] -> bool: whether assignment covers period p
        self.occupies = {}

    def build_model(self):
        # 1. สร้างตัวแปรเริ่มต้น
        for a_id, a in self.assignments.items():
            duration = a.course.periods_per_session
            valid_start_periods = self.periods_per_day - duration + 1

            # ตัวแปรเวลาเริ่มต้น (day, start_period)
            start_vars = []
            for d in range(self.days):
                for p in range(valid_start_periods):
                    var = self.model.NewBoolVar(f"start_{a_id}_d{d}_p{p}")
                    self.starts[a_id, d, p] = var

                    # ห้ามวิชาใดๆ ทับคาบพักกลางวัน (index 4: 12:00-13:00)
                    overlaps_lunch = (p <= self.lunch_period < p + duration)
                    # จำกัดเวลาเรียนปกติให้อยู่ในช่วงคาบ 1-10 (08:00 - 18:00)
                    is_within_daytime = (p + duration <= 10)

                    if not overlaps_lunch and is_within_daytime:
                        start_vars.append(var)
                    else:
                        self.model.Add(var == 0)
            
            # แต่ละวิชาต้องมีเวลาเริ่ม 1 จุดต่อสัปดาห์
            self.model.AddExactlyOne(start_vars)

            # ตัวแปรการครองคาบเรียน (occupies day d, period p)
            for d in range(self.days):
                for p in range(self.periods_per_day):
                    # p ถูกครอบคลุมถ้าวิชาเริ่มที่ p_start <= p < p_start + duration
                    covering_starts = [
                        self.starts[a_id, d, p_start]
                        for p_start in range(max(0, p - duration + 1), min(valid_start_periods, p + 1))
                    ]
                    if covering_starts:
                        occ_var = self.model.NewBoolVar(f"occ_{a_id}_d{d}_p{p}")
                        self.model.Add(occ_var == sum(covering_starts))
                        self.occupies[a_id, d, p] = occ_var
                    else:
                        self.occupies[a_id, d, p] = None

            # ตัวแปรห้องเรียน
            total_students = self.groups[a.primary_group_id].student_count
            if a.secondary_group_id:
                total_students += self.groups[a.secondary_group_id].student_count

            valid_rooms = [
                r for r in self.rooms.values()
                if r.room_type == a.course.required_room_type and r.capacity >= total_students
            ]
            if not valid_rooms:
                raise ValueError(
                    f"ไม่มีห้องเรียนที่ตรงกับเงื่อนไขของวิชา {a.course.name} "
                    f"(ต้องการ {a.course.required_room_type}, ความจุ {total_students})"
                )

            room_vars = []
            for r in valid_rooms:
                r_var = self.model.NewBoolVar(f"room_{a_id}_{r.id}")
                self.assigned_room[a_id, r.id] = r_var
                room_vars.append(r_var)
            self.model.AddExactlyOne(room_vars)

            # ตัวแปร Block Activation
            primary_grp = self.groups[a.primary_group_id]
            if a.is_rotation:
                # วิชาฐานหมุนเวียน (Micro-block rotation) ให้เลือกลงเพียง 1 บล็อกในบล็อกที่กลุ่มเรียนนั้น active
                rotation_block_vars = []
                for b in range(self.num_blocks):
                    b_var = self.model.NewBoolVar(f"block_{a_id}_b{b}")
                    self.block_active[a_id, b] = b_var
                    if b in primary_grp.active_blocks:
                        rotation_block_vars.append(b_var)
                    else:
                        # กลุ่มไม่เรียนในบล็อกนี้
                        self.model.Add(b_var == 0)
                # ต้องเลือกเรียนใน 1 บล็อก
                self.model.AddExactlyOne(rotation_block_vars)
            else:
                # วิชาปกติ (Non-rotation)
                for b in range(self.num_blocks):
                    b_var = self.model.NewBoolVar(f"block_{a_id}_b{b}")
                    self.block_active[a_id, b] = b_var
                    # ปวส. ไม่ active ใน block 5 (สัปดาห์ 16-18)
                    if b in primary_grp.active_blocks:
                        self.model.Add(b_var == 1)
                    else:
                        self.model.Add(b_var == 0)

        # 2. Constraints การจัดตาราง
        self._add_group_conflict_constraints()
        self._add_teacher_conflict_constraints()
        self._add_room_conflict_constraints()
        self._add_rotation_base_constraints()
        self._add_soft_preferences()

    def _add_group_conflict_constraints(self):
        """กลุ่มเรียน 1 กลุ่ม เรียนได้ไม่เกิน 1 วิชาในแต่ละ (block, day, period)"""
        for g_id, grp in self.groups.items():
            # ค้นหาวิชาที่กลุ่มนี้มีส่วนร่วม (ทั้งเดี่ยว และ เรียนรวม)
            grp_assignments = [
                a_id for a_id, a in self.assignments.items()
                if a.primary_group_id == g_id or a.secondary_group_id == g_id
            ]

            for b in grp.active_blocks:
                for d in range(self.days):
                    for p in range(self.periods_per_day):
                        active_in_slot = []
                        for a_id in grp_assignments:
                            occ = self.occupies.get((a_id, d, p))
                            if occ is not None:
                                # lesson กำลังเรียนใน slot นี้ และ กำลัง active ใน block b
                                is_slot_active = self.model.NewBoolVar(f"g_{g_id}_b{b}_d{d}_p{p}_{a_id}")
                                self.model.AddBoolAnd([occ, self.block_active[a_id, b]]).OnlyEnforceIf(is_slot_active)
                                self.model.AddBoolOr([occ.Not(), self.block_active[a_id, b].Not()]).OnlyEnforceIf(is_slot_active.Not())
                                active_in_slot.append(is_slot_active)
                        if active_in_slot:
                            self.model.Add(sum(active_in_slot) <= 1)

    def _add_teacher_conflict_constraints(self):
        """ครู 1 คน สอนได้ไม่เกิน 1 คาบในแต่ละ (block, day, period)
        ครอบคลุมทั้งครูหลัก (teacher_id) และครูร่วมสอน (secondary_teacher_id)
        หมายเหตุ: สำหรับวิชาเรียนรวม (Merged Theory) ถูกรวมเป็น 1 assignment เดียวแล้ว จึงไม่ชนกันเอง
        """
        for t_id in self.teachers:
            t_assignments = [
                a_id for a_id, a in self.assignments.items()
                if a.teacher_id == t_id or a.secondary_teacher_id == t_id
            ]
            for b in range(self.num_blocks):
                for d in range(self.days):
                    for p in range(self.periods_per_day):
                        active_teach_slots = []
                        for a_id in t_assignments:
                            occ = self.occupies.get((a_id, d, p))
                            if occ is not None:
                                is_teach_active = self.model.NewBoolVar(f"t_{t_id}_b{b}_d{d}_p{p}_{a_id}")
                                self.model.AddBoolAnd([occ, self.block_active[a_id, b]]).OnlyEnforceIf(is_teach_active)
                                self.model.AddBoolOr([occ.Not(), self.block_active[a_id, b].Not()]).OnlyEnforceIf(is_teach_active.Not())
                                active_teach_slots.append(is_teach_active)
                        if active_teach_slots:
                            self.model.Add(sum(active_teach_slots) <= 1)

        # ห้ามจัดสอนในช่วงเวลาที่ไม่สะดวกสอน (Unavailable Slots) ของทั้งครูหลักและครูร่วมสอน
        for t_id, teacher in self.teachers.items():
            if not teacher.unavailable_slots:
                continue
            t_assignments = [
                a_id for a_id, a in self.assignments.items()
                if a.teacher_id == t_id or a.secondary_teacher_id == t_id
            ]
            for (d, p) in teacher.unavailable_slots:
                period_idx = p - 1 if p >= 1 else p
                if 0 <= d < self.days and 0 <= period_idx < self.periods_per_day:
                    for a_id in t_assignments:
                        occ = self.occupies.get((a_id, d, period_idx))
                        if occ is not None:
                            self.model.Add(occ == 0)

    def _add_room_conflict_constraints(self):
        """ห้องเรียน 1 ห้อง ใช้งานได้ไม่เกิน 1 วิชาในแต่ละ (block, day, period)"""
        for r_id in self.rooms:
            for b in range(self.num_blocks):
                for d in range(self.days):
                    for p in range(self.periods_per_day):
                        active_room_slots = []
                        for a_id in self.assignments:
                            if (a_id, r_id) in self.assigned_room:
                                occ = self.occupies.get((a_id, d, p))
                                if occ is not None:
                                    is_room_active = self.model.NewBoolVar(f"r_{r_id}_b{b}_d{d}_p{p}_{a_id}")
                                    self.model.AddBoolAnd([
                                        occ,
                                        self.block_active[a_id, b],
                                        self.assigned_room[a_id, r_id]
                                    ]).OnlyEnforceIf(is_room_active)
                                    self.model.AddBoolOr([
                                        occ.Not(),
                                        self.block_active[a_id, b].Not(),
                                        self.assigned_room[a_id, r_id].Not()
                                    ]).OnlyEnforceIf(is_room_active.Not())
                                    active_room_slots.append(is_room_active)
                        if active_room_slots:
                            self.model.Add(sum(active_room_slots) <= 1)

    def _add_rotation_base_constraints(self):
        """สำหรับกลุ่มเดียวกัน วิชาฐานหมุนเวียนต้องอยู่คนละบล็อก"""
        for g_id in self.groups:
            rot_assignments = [
                a_id for a_id, a in self.assignments.items()
                if a.is_rotation and a.primary_group_id == g_id
            ]
            # ในแต่ละบล็อก b กลุ่ม g_id ต้องมีวิชาหมุนเวียนเรียนได้ไม่เกิน 1 ฐาน
            for b in range(self.num_blocks):
                self.model.Add(sum(self.block_active[a_id, b] for a_id in rot_assignments) <= 1)

    def _add_soft_preferences(self):
        """กำหนด Objective Function:
        1. พยายามหลีกเลี่ยงคาบแรกเช้าตรู่หรือคาบเย็นถ้าไม่จำเป็น
        2. พยายามจัดวิชาที่มีชั่วโมงยาวให้เริ่มช่วงต้นคาบ (เช่น คาบ 0 หรือ คาบ 4 หลังพักเที่ยง)
        """
        penalty_terms = []
        for a_id, a in self.assignments.items():
            duration = a.course.periods_per_session
            valid_start_periods = self.periods_per_day - duration + 1
            for d in range(self.days):
                for p in range(valid_start_periods):
                    cost = 0
                    # ชอบให้วิชาปฏิบัติยาวเริ่มที่คาบ 1 (p=0) หรือ คาบ 2 (p=1) หรือ บ่ายคาบ 6 (p=5)
                    if duration >= 3 and p not in (0, 1, 5):
                        cost += 3
                    # หลีกเลี่ยงคาบเย็นหลัง 17:00 (p >= 8)
                    if p >= 8:
                        cost += 6
                    if cost > 0:
                        penalty_terms.append(self.starts[a_id, d, p] * cost)

        if penalty_terms:
            self.model.Minimize(sum(penalty_terms))

    def solve(self, time_limit_seconds: float = 20.0):
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        status = self.solver.Solve(self.model)
        
        status_name = self.solver.StatusName(status)
        print(f"Solver Status: {status_name}")

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        # แกะผลลัพธ์
        results = []
        for a_id, a in self.assignments.items():
            chosen_day = -1
            chosen_start_period = -1
            for d in range(self.days):
                for p in range(self.periods_per_day - a.course.periods_per_session + 1):
                    if self.solver.BooleanValue(self.starts[a_id, d, p]):
                        chosen_day = d
                        chosen_start_period = p
                        break
                if chosen_day != -1:
                    break

            chosen_room = None
            for (ass_id, r_id), r_var in self.assigned_room.items():
                if ass_id == a_id and self.solver.BooleanValue(r_var):
                    chosen_room = self.rooms[r_id]
                    break

            active_blocks = [
                b for b in range(self.num_blocks)
                if self.solver.BooleanValue(self.block_active[a_id, b])
            ]

            results.append({
                "assignment": a,
                "day": chosen_day,
                "start_period": chosen_start_period,
                "duration": a.course.periods_per_session,
                "room": chosen_room,
                "teacher": self.teachers[a.teacher_id],
                "secondary_teacher": self.teachers.get(a.secondary_teacher_id) if a.secondary_teacher_id else None,
                "active_blocks": active_blocks
            })

        return results

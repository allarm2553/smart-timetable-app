from typing import Dict, List, Tuple, Optional
from ortools.sat.python import cp_model
from src.solver.models import (
    Teacher, Room, StudentGroup, Course, LessonAssignment,
    EducationLevel, CourseType, RoomType
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
        # ป้องกัน Assignment กำพร้า (Orphan Assignment) หากกลุ่มหรือครูถูกลบ
        self.assignments = {
            a.id: a for a in assignments
            if a.primary_group_id in self.groups and a.teacher_id in self.teachers
        }

        # รองรับห้องภายนอก / ห้องวิชาสามัญที่ถูกระบุใน fixed_room_id โดยอัตโนมัติ
        for a in self.assignments.values():
            if getattr(a, "is_pinned", False) and getattr(a, "fixed_room_id", None):
                f_rid = a.fixed_room_id
                if f_rid not in self.rooms:
                    self.rooms[f_rid] = Room(
                        id=f_rid,
                        name=f_rid if f_rid.startswith("ห้อง") or f_rid.startswith("ROOM") else f"ห้อง {f_rid}",
                        room_type=RoomType.CLASSROOM,
                        capacity=100
                    )

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

            primary_grp = self.groups[a.primary_group_id]
            secondary_grp = self.groups.get(a.secondary_group_id)
            is_internship_grp = getattr(primary_grp, "is_internship", False) or (secondary_grp and getattr(secondary_grp, "is_internship", False))
            is_theory = (a.course.course_type == CourseType.THEORY)

            # ตัวแปรเวลาเริ่มต้น (day, start_period)
            start_vars = []
            for d in range(self.days):
                for p in range(valid_start_periods):
                    var = self.model.NewBoolVar(f"start_{a_id}_d{d}_p{p}")
                    self.starts[a_id, d, p] = var

                    # ห้ามวิชาใดๆ ทับคาบพักกลางวัน (index 4: 12:00-13:00)
                    overlaps_lunch = (p <= self.lunch_period < p + duration)

                    # ตรวจสอบการล็อกคาบเรียนตายตัวล่วงหน้า (Pinned / Pre-assigned Lessons สำหรับวิชาสามัญ)
                    is_pinned = getattr(a, "is_pinned", False)
                    fixed_day = getattr(a, "fixed_day", None)
                    fixed_start = getattr(a, "fixed_start_period", None)

                    if is_pinned and fixed_day is not None and fixed_start is not None:
                        # fixed_start เป็น 1-indexed (เช่น คาบ 1 คือ index 0)
                        target_p = fixed_start - 1
                        if d == fixed_day and p == target_p:
                            is_valid_time = True
                        else:
                            is_valid_time = False
                    elif is_internship_grp and is_theory:
                        # กลุ่มฝึกงานในสถานประกอบการ/ทวิภาคี: ทฤษฎีต้องจัดหลัง 18:00 น. (คาบ 11-12 index 10-11)
                        is_valid_time = (p >= 10 and p + duration <= self.periods_per_day)
                    else:
                        # กลุ่มปกติ หรือ ภาคปฏิบัติของกลุ่มฝึกงาน: จัดเวลากลางวัน คาบ 1-10 (08:00 - 18:00) ไม่ทับพักเที่ยง
                        is_valid_time = (not overlaps_lunch and p + duration <= 10)

                    if is_valid_time:
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
            primary_grp = self.groups[a.primary_group_id]
            total_students = primary_grp.student_count
            if a.secondary_group_id and a.secondary_group_id in self.groups:
                total_students += self.groups[a.secondary_group_id].student_count

            valid_rooms = [
                r for r in self.rooms.values()
                if r.room_type == a.course.required_room_type and r.capacity >= total_students
            ]
            if not valid_rooms:
                valid_rooms = [r for r in self.rooms.values() if r.room_type == a.course.required_room_type]
                if not valid_rooms:
                    valid_rooms = list(self.rooms.values())

            # ล็อกห้องเรียนกรณีมีการระบุห้องตายตัว (Fixed Room)
            fixed_room_id = getattr(a, "fixed_room_id", None)
            if getattr(a, "is_pinned", False) and fixed_room_id and fixed_room_id in self.rooms:
                valid_rooms = [self.rooms[fixed_room_id]]

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
        """กลุ่มเรียน 1 กลุ่ม เรียนได้ไม่เกิน 1 วิชาในแต่ละ (block, day, period)
        และควบคุมคาบเรียนต่อวันไม่เกิน 7 คาบ (ไม่มากไป) เพื่อสุขภาพการเรียนรู้ของนักศึกษา
        """
        for g_id, grp in self.groups.items():
            # ค้นหาวิชาที่กลุ่มนี้มีส่วนร่วม (ทั้งเดี่ยว และ เรียนรวม)
            grp_assignments = [
                a_id for a_id, a in self.assignments.items()
                if a.primary_group_id == g_id or a.secondary_group_id == g_id
            ]
            if not grp_assignments:
                continue

            for b in grp.active_blocks:
                for d in range(self.days):
                    daily_group_slots = []
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
                            daily_group_slots.extend(active_in_slot)

                    # จำกัดคาบเรียนต่อวันของนักศึกษาไม่เกิน 8 คาบ (ไม่เกินเกณฑ์ความเหมาะสมต่อวัน และเว้นพักเที่ยง)
                    if daily_group_slots:
                        self.model.Add(sum(daily_group_slots) <= 8)

    def _add_teacher_conflict_constraints(self):
        """ครู 1 คน สอนได้ไม่เกิน 1 คาบในแต่ละ (block, day, period)
        ครอบคลุมทั้งครูหลัก (teacher_id) และครูร่วมสอน (secondary_teacher_id)
        พร้อมบังคับเงื่อนไขตามเกณฑ์เฉพาะของวิทยาลัย:
        1. คาบสอนต่อวันไม่เกิน teacher.max_periods_per_day (เช่น ไม่เกิน 6 คาบ)
        2. คาบสอนต่อสัปดาห์ไม่เกิน teacher.max_periods_per_week (หัวหน้างาน <= 28, ทั่วไป <= 34, เพดานวิทยาลัย <= 35)
        3. ห้ามจัดสอนในช่วงเวลาที่ไม่สะดวกสอน (Unavailable Slots)
        """
        for t_id, teacher in self.teachers.items():
            # หากยังไม่ระบุครูผู้สอน (Placeholder) ไม่นำมาคิดการชนเวลาหรือภาระสอนรวม
            if t_id == "T_UNASSIGNED" or "(ยังไม่ระบุครูผู้สอน)" in teacher.name:
                continue

            t_assignments = [
                a_id for a_id, a in self.assignments.items()
                if a.teacher_id == t_id or a.secondary_teacher_id == t_id
            ]
            if not t_assignments:
                continue

            for b in range(self.num_blocks):
                weekly_teach_slots = []
                for d in range(self.days):
                    daily_teach_slots = []
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
                            daily_teach_slots.extend(active_teach_slots)

                    # จำกัดคาบสอนต่อวัน (ไม่เกิน max_periods_per_day เช่น 6 คาบ/วัน)
                    if daily_teach_slots:
                        self.model.Add(sum(daily_teach_slots) <= teacher.max_periods_per_day)
                        weekly_teach_slots.extend(daily_teach_slots)

                # ขีดจำกัดคาบสอนต่อสัปดาห์ของวิทยาลัย (หัวหน้างาน <= 28, ทั่วไป <= 34, เพดานวิทยาลัย <= 35)
                if weekly_teach_slots:
                    self.model.Add(sum(weekly_teach_slots) <= teacher.max_periods_per_week)

        # ห้ามจัดสอนในช่วงเวลาที่ไม่สะดวกสอน (Unavailable Slots) ของทั้งครูหลักและครูร่วมสอน
        for t_id, teacher in self.teachers.items():
            if t_id == "T_UNASSIGNED" or "(ยังไม่ระบุครูผู้สอน)" in teacher.name or not teacher.unavailable_slots:
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
        1. พยายามหลีกเลี่ยงคาบแรกเช้าตรู่หรือคาบเย็นถ้าไม่จำเป็น (สำหรับวิชาปกติ)
        2. พยายามจัดวิชาที่มีชั่วโมงยาวให้เริ่มช่วงต้นคาบ (เช่น คาบ 0 หรือ คาบ 5 หลังพักเที่ยง)
        """
        penalty_terms = []
        for a_id, a in self.assignments.items():
            primary_grp = self.groups[a.primary_group_id]
            secondary_grp = self.groups.get(a.secondary_group_id)
            is_internship_grp = getattr(primary_grp, "is_internship", False) or (secondary_grp and getattr(secondary_grp, "is_internship", False))
            is_theory = (a.course.course_type == CourseType.THEORY)

            duration = a.course.periods_per_session
            valid_start_periods = self.periods_per_day - duration + 1
            for d in range(self.days):
                for p in range(valid_start_periods):
                    cost = 0
                    if not (is_internship_grp and is_theory):
                        # ชอบให้วิชาปฏิบัติยาวเริ่มที่คาบ 1 (p=0) หรือ คาบ 2 (p=1) หรือ บ่ายคาบ 6 (p=5)
                        if duration >= 3 and p not in (0, 1, 5):
                            cost += 3
                        # หลีกเลี่ยงคาบเย็นหลัง 17:00 (p >= 8) สำหรับวิชาปกติ
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
                "active_blocks": active_blocks,
                "is_pinned": getattr(a, "is_pinned", False),
                "fixed_day": getattr(a, "fixed_day", None),
                "fixed_start_period": getattr(a, "fixed_start_period", None),
                "fixed_room_id": getattr(a, "fixed_room_id", None),
                "external_teacher_name": getattr(a, "external_teacher_name", None)
            })

        return results

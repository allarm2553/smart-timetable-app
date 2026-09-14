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
        # block_active[a_id, b] -> bool: whether assignment is active in block b
        self.block_active = {}
        # occupies[a_id, d, p] -> bool: whether assignment covers period p
        self.occupies = {}
        self._active_cache = {}

    def _get_active_var(self, a_id: str, b: int, d: int, p: int):
        """คืนค่าตัวแปร (หรือ None) ที่ระบุว่า assignment a_id กำลังเรียนอยู่ใน slot (b, d, p) หรือไม่"""
        occ = self.occupies.get((a_id, d, p))
        if occ is None:
            return None
        a = self.assignments[a_id]
        p_grp = self.groups[a.primary_group_id]
        if not a.is_rotation:
            return occ if b in p_grp.active_blocks else None
        else:
            if b not in p_grp.active_blocks:
                return None
            key = (a_id, b, d, p)
            if key in self._active_cache:
                return self._active_cache[key]
            v = self.model.NewBoolVar(f"act_{a_id}_{b}_{d}_{p}")
            self.model.AddBoolAnd([occ, self.block_active[a_id, b]]).OnlyEnforceIf(v)
            self.model.AddBoolOr([occ.Not(), self.block_active[a_id, b].Not()]).OnlyEnforceIf(v.Not())
            self._active_cache[key] = v
            return v

    def build_model(self):
        # 1. สร้างตัวแปรเวลาเริ่มต้นและครองคาบเรียน
        for a_id, a in self.assignments.items():
            duration = a.course.periods_per_session
            valid_start_periods = self.periods_per_day - duration + 1

            primary_grp = self.groups[a.primary_group_id]
            secondary_grp = self.groups.get(a.secondary_group_id)
            is_internship_grp = getattr(primary_grp, "is_internship", False) or (secondary_grp and getattr(secondary_grp, "is_internship", False))
            is_theory = (a.course.course_type == CourseType.THEORY)

            # ตรวจสอบการล็อกคาบเรียนตายตัวล่วงหน้า (Pinned / Pre-assigned Lessons สำหรับวิชาสามัญ)
            is_pinned = getattr(a, "is_pinned", False)
            fixed_day = getattr(a, "fixed_day", None)
            fixed_start = getattr(a, "fixed_start_period", None)

            start_vars = []
            for d in range(self.days):
                for p in range(valid_start_periods):
                    overlaps_lunch = (p <= self.lunch_period < p + duration)

                    if is_pinned and fixed_day is not None and fixed_start is not None:
                        target_p = fixed_start - 1 if fixed_start >= 1 else fixed_start
                        is_valid_time = (d == fixed_day and p == target_p)
                    elif is_internship_grp and is_theory:
                        # กลุ่มฝึกงานในสถานประกอบการ: ทฤษฎีจัดหลัง 18:00 (คาบ 11-12)
                        is_valid_time = (p >= 10 and p + duration <= self.periods_per_day)
                    else:
                        # ปกติ: กลางวัน ไม่ทับพักเที่ยง ไม่เกินคาบ 10
                        is_valid_time = (not overlaps_lunch and p + duration <= 10)

                    if is_valid_time:
                        var = self.model.NewBoolVar(f"start_{a_id}_d{d}_p{p}")
                        self.starts[a_id, d, p] = var
                        start_vars.append(var)

            # แต่ละวิชาต้องมีเวลาเริ่ม 1 จุดต่อสัปดาห์
            self.model.AddExactlyOne(start_vars)

            # ตัวแปรการครองคาบเรียน (occupies day d, period p)
            for d in range(self.days):
                for p in range(self.periods_per_day):
                    covering_starts = [
                        self.starts[a_id, d, sp]
                        for sp in range(max(0, p - duration + 1), min(valid_start_periods, p + 1))
                        if (a_id, d, sp) in self.starts
                    ]
                    if not covering_starts:
                        self.occupies[a_id, d, p] = None
                    elif len(covering_starts) == 1:
                        self.occupies[a_id, d, p] = covering_starts[0]
                    else:
                        occ_var = self.model.NewBoolVar(f"occ_{a_id}_d{d}_p{p}")
                        self.model.Add(occ_var == sum(covering_starts))
                        self.occupies[a_id, d, p] = occ_var

            # ตัวแปร Block Activation
            if a.is_rotation:
                rotation_block_vars = []
                for b in range(self.num_blocks):
                    if b in primary_grp.active_blocks:
                        b_var = self.model.NewBoolVar(f"block_{a_id}_b{b}")
                        self.block_active[a_id, b] = b_var
                        rotation_block_vars.append(b_var)
                self.model.AddExactlyOne(rotation_block_vars)
            else:
                for b in range(self.num_blocks):
                    if b in primary_grp.active_blocks:
                        b_var = self.model.NewBoolVar(f"block_{a_id}_b{b}")
                        self.block_active[a_id, b] = b_var
                        self.model.Add(b_var == 1)

        # 2. Constraints การจัดตาราง
        self._add_group_conflict_constraints()
        self._add_teacher_conflict_constraints()
        self._add_room_capacity_constraints()
        self._add_rotation_base_constraints()
        self._add_parallel_and_pedagogical_constraints()
        self._add_soft_preferences()

    def _add_group_conflict_constraints(self):
        """กลุ่มเรียน 1 กลุ่ม เรียนได้ไม่เกิน 1 วิชาในแต่ละ (block, day, period)
        และควบคุมคาบเรียนต่อวันไม่เกิน 8 คาบ (ไม่มากไป) เพื่อสุขภาพการเรียนรู้ของนักศึกษา
        """
        for g_id, grp in self.groups.items():
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
                            act_v = self._get_active_var(a_id, b, d, p)
                            if act_v is not None:
                                active_in_slot.append(act_v)
                        if active_in_slot:
                            self.model.Add(sum(active_in_slot) <= 1)
                            daily_group_slots.extend(active_in_slot)

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
                            act_v = self._get_active_var(a_id, b, d, p)
                            if act_v is not None:
                                active_teach_slots.append(act_v)
                        if active_teach_slots:
                            self.model.Add(sum(active_teach_slots) <= 1)
                            daily_teach_slots.extend(active_teach_slots)

                    if daily_teach_slots:
                        self.model.Add(sum(daily_teach_slots) <= teacher.max_periods_per_day)
                        weekly_teach_slots.extend(daily_teach_slots)

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

    def _add_room_capacity_constraints(self):
        """ห้องเรียน: จำกัดจำนวนวิชาที่เรียนพร้อมกันตามความจุห้องแต่ละประเภท (Room Capacity by RoomType)
        และป้องกันการชนกันของวิชาที่ระบุห้องเรียนตายตัว (Fixed / Pinned Rooms)
        """
        # 1. จัดกลุ่มห้องเรียนตามประเภทห้อง
        rooms_by_type = {}
        for r in self.rooms.values():
            rooms_by_type.setdefault(r.room_type, []).append(r)

        for r_type, r_list in rooms_by_type.items():
            cap = len(r_list)
            type_ass = [
                a_id for a_id, a in self.assignments.items()
                if a.course.required_room_type == r_type
            ]
            if len(type_ass) <= cap:
                continue

            for b in range(self.num_blocks):
                for d in range(self.days):
                    for p in range(self.periods_per_day):
                        active_in_slot = []
                        for a_id in type_ass:
                            act_v = self._get_active_var(a_id, b, d, p)
                            if act_v is not None:
                                active_in_slot.append(act_v)
                        if active_in_slot:
                            self.model.Add(sum(active_in_slot) <= cap)

        # 2. วิชาที่ล็อกห้องเรียนตายตัว (Pinned / Fixed Rooms) ต้องไม่ชนกันในห้องเดียวกัน
        pinned_rooms = {}
        for a_id, a in self.assignments.items():
            f_room = getattr(a, "fixed_room_id", None)
            if getattr(a, "is_pinned", False) and f_room and f_room in self.rooms:
                pinned_rooms.setdefault(f_room, []).append(a_id)

        for f_room, p_assignments in pinned_rooms.items():
            if len(p_assignments) <= 1:
                continue
            for b in range(self.num_blocks):
                for d in range(self.days):
                    for p in range(self.periods_per_day):
                        active_pinned = []
                        for a_id in p_assignments:
                            act_v = self._get_active_var(a_id, b, d, p)
                            if act_v is not None:
                                active_pinned.append(act_v)
                        if active_pinned:
                            self.model.Add(sum(active_pinned) <= 1)

    def _add_rotation_base_constraints(self):
        """สำหรับกลุ่มเดียวกัน วิชาฐานหมุนเวียนต้องอยู่คนละบล็อก"""
        for g_id in self.groups:
            rot_assignments = [
                a_id for a_id, a in self.assignments.items()
                if a.is_rotation and a.primary_group_id == g_id
            ]
            for b in range(self.num_blocks):
                act_b = [self.block_active[a_id, b] for a_id in rot_assignments if (a_id, b) in self.block_active]
                if act_b:
                    self.model.Add(sum(act_b) <= 1)

    def _add_parallel_and_pedagogical_constraints(self):
        """จัดการข้อกำหนดวิชาที่ต้องจัดเวลาคู่ขนาน (Parallel Start)
        และข้อกำหนดวิชาทฤษฎีต้องเรียนก่อนหรือวันเดียวกับปฏิบัติ (Pedagogical Precedence)
        """
        # 1. Parallel Start Constraints
        processed_pairs = set()
        for a_id, a in self.assignments.items():
            par_id = getattr(a, "parallel_with_id", None)
            if par_id and par_id in self.assignments:
                pair_key = tuple(sorted([a_id, par_id]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)

                # ผูกเวลาเริ่มต้นของ a_id และ par_id ให้ตรงกันเป๊ะในทุก (day, start_period)
                for d in range(self.days):
                    for p in range(self.periods_per_day):
                        var_a = self.starts.get((a_id, d, p))
                        var_b = self.starts.get((par_id, d, p))
                        if var_a is not None and var_b is not None:
                            self.model.Add(var_a == var_b)
                        elif var_a is not None:
                            self.model.Add(var_a == 0)
                        elif var_b is not None:
                            self.model.Add(var_b == 0)

        # 2. Pedagogical Precedence: ทฤษฎีต้องเรียนก่อนหรือวันเดียวกับปฏิบัติสำหรับกลุ่มวิชาเดียวกัน
        grouped_by_parent = {}
        for a_id, a in self.assignments.items():
            parent_id = getattr(a, "parent_assignment_id", None)
            if parent_id:
                grouped_by_parent.setdefault(parent_id, []).append(a)

        for parent_id, a_list in grouped_by_parent.items():
            theory_assignments = [a for a in a_list if getattr(a, "component_type", None) == "THEORY"]
            practice_assignments = [a for a in a_list if getattr(a, "component_type", None) == "PRACTICE"]

            for t_a in theory_assignments:
                t_starts = [
                    (d, p, self.starts[t_a.id, d, p])
                    for d in range(self.days)
                    for p in range(self.periods_per_day)
                    if (t_a.id, d, p) in self.starts
                ]
                if not t_starts:
                    continue
                day_t = sum(d * v for d, p, v in t_starts)

                for p_a in practice_assignments:
                    p_starts = [
                        (d, p, self.starts[p_a.id, d, p])
                        for d in range(self.days)
                        for p in range(self.periods_per_day)
                        if (p_a.id, d, p) in self.starts
                    ]
                    if not p_starts:
                        continue
                    day_p = sum(d * v for d, p, v in p_starts)

                    t_pinned = getattr(t_a, "is_pinned", False)
                    p_pinned = getattr(p_a, "is_pinned", False)
                    if not t_pinned and not p_pinned:
                        self.model.Add(day_t <= day_p)

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
                    if (a_id, d, p) not in self.starts:
                        continue
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

    def _assign_rooms(self, results: list) -> None:
        """จัดสรรห้องเรียนจริงที่ตรงประเภทและความจุให้กับแต่ละรายวิชาโดยไม่มีการชนเวลา"""
        assigned = {}
        # 1. วิชาที่ล็อกห้องเรียนตายตัว (Pinned Room)
        for r in results:
            a = r["assignment"]
            f_rid = getattr(a, "fixed_room_id", None)
            if getattr(a, "is_pinned", False) and f_rid and f_rid in self.rooms:
                assigned[a.id] = self.rooms[f_rid]
                r["room"] = self.rooms[f_rid]

        # 2. จัดกลุ่มห้องเรียนตามประเภท
        rooms_by_type = {}
        for room in self.rooms.values():
            rooms_by_type.setdefault(room.room_type, []).append(room)

        # 3. จัดสรรห้องเรียนให้วิชาที่ยังไม่ได้ระบุห้อง
        for r_type, r_list in rooms_by_type.items():
            unassigned = [
                r for r in results
                if r["assignment"].id not in assigned and r["assignment"].course.required_room_type == r_type
            ]
            unassigned.sort(key=lambda x: (x["day"], x["start_period"]))

            for item in unassigned:
                a = item["assignment"]
                p_grp = self.groups[a.primary_group_id]
                total_students = p_grp.student_count
                if a.secondary_group_id and a.secondary_group_id in self.groups:
                    total_students += self.groups[a.secondary_group_id].student_count

                # เรียงลำดับห้อง: ห้องที่ความจุพอดีก่อน
                sorted_rooms = sorted(
                    r_list,
                    key=lambda rm: (rm.capacity < total_students, rm.capacity)
                )

                chosen = None
                for room in sorted_rooms:
                    collision = False
                    for other_id, other_room in assigned.items():
                        if other_room.id == room.id:
                            other_item = next(x for x in results if x["assignment"].id == other_id)
                            # เช็กว่าเรียนในบล็อกเดียวกันหรือไม่
                            if set(item["active_blocks"]) & set(other_item["active_blocks"]):
                                if item["day"] == other_item["day"]:
                                    s1 = item["start_period"]
                                    e1 = s1 + item["duration"]
                                    s2 = other_item["start_period"]
                                    e2 = s2 + other_item["duration"]
                                    if max(s1, s2) < min(e1, e2):
                                        collision = True
                                        break
                    if not collision:
                        chosen = room
                        break

                if not chosen:
                    chosen = r_list[0] if r_list else list(self.rooms.values())[0]

                assigned[a.id] = chosen
                item["room"] = chosen

    def solve(self, time_limit_seconds: float = 20.0):
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.num_search_workers = 1
        self.solver.parameters.linearization_level = 0
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
            valid_start_periods = self.periods_per_day - a.course.periods_per_session + 1
            for d in range(self.days):
                for p in range(valid_start_periods):
                    if (a_id, d, p) in self.starts and self.solver.BooleanValue(self.starts[a_id, d, p]):
                        chosen_day = d
                        chosen_start_period = p
                        break
                if chosen_day != -1:
                    break

            primary_grp = self.groups[a.primary_group_id]
            if a.is_rotation:
                active_blocks = [
                    b for b in primary_grp.active_blocks
                    if (a_id, b) in self.block_active and self.solver.BooleanValue(self.block_active[a_id, b])
                ]
            else:
                active_blocks = list(primary_grp.active_blocks)

            results.append({
                "assignment": a,
                "day": chosen_day,
                "start_period": chosen_start_period,
                "duration": a.course.periods_per_session,
                "room": None,
                "teacher": self.teachers[a.teacher_id],
                "secondary_teacher": self.teachers.get(a.secondary_teacher_id) if a.secondary_teacher_id else None,
                "active_blocks": active_blocks,
                "is_pinned": getattr(a, "is_pinned", False),
                "fixed_day": getattr(a, "fixed_day", None),
                "fixed_start_period": getattr(a, "fixed_start_period", None),
                "fixed_room_id": getattr(a, "fixed_room_id", None),
                "external_teacher_name": getattr(a, "external_teacher_name", None),
                "parallel_with_id": getattr(a, "parallel_with_id", None),
                "component_type": getattr(a, "component_type", None),
                "parent_assignment_id": getattr(a, "parent_assignment_id", None)
            })

        # จัดสรรห้องเรียนให้ทุกรายวิชาอย่างเป็นระบบ
        self._assign_rooms(results)
        return results

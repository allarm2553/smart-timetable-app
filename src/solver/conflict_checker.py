from typing import List, Dict, Optional, Tuple, Any
from src.solver.models import get_group_year_category, is_scout_assignment, is_activity_assignment

DAY_NAMES = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์"]

def validate_move(
    schedule: List[Dict[str, Any]],
    assignment_id: str,
    target_day: int,
    target_start_period: int,
    target_room_id: str,
    rooms_map: Dict[str, Any],
    groups_map: Dict[str, Any],
    teachers_map: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str], List[str]]:
    """
    ตรวจสอบว่าการย้ายวิชา assignment_id ไปยัง (target_day, target_start_period, target_room_id)
    ถูกต้องตามเงื่อนไขหรือไม่
    คืนค่า (is_valid, conflicts, warnings)
    """
    conflicts: List[str] = []
    warnings: List[str] = []

    # 1. ค้นหาวิชาที่ต้องการย้าย
    moving_lesson = next((s for s in schedule if s["assignment_id"] == assignment_id), None)
    if not moving_lesson:
        return False, [f"ไม่พบวิชา ID '{assignment_id}' ในตาราง"], []

    if moving_lesson.get("is_pinned"):
        conflicts.append(f"วิชา '{moving_lesson.get('course_name', assignment_id)}' ถูกล็อกเวลาตายตัวไว้ล่วงหน้า (Pinned Lesson) หากต้องการย้าย กรุณาปลดล็อกก่อน")

    duration = moving_lesson["duration"]
    target_end_period = target_start_period + duration - 1

    # 2. ตรวจสอบขอบเขตช่วงคาบ
    if target_start_period < 1 or target_end_period > 12:
        conflicts.append(f"ช่วงคาบเรียน ({target_start_period}–{target_end_period}) อยู่นอกช่วงเวลา 1–12")

    # ตรวจสอบกลุ่มฝึกงานสถานประกอบการ / ทวิภาคี (ทฤษฎีต้องจัดหลัง 18:00 น. คาบ 11-12)
    g1 = groups_map.get(moving_lesson["primary_group_id"])
    g2 = groups_map.get(moving_lesson.get("secondary_group_id")) if moving_lesson.get("secondary_group_id") else None
    is_internship = (getattr(g1, "is_internship", False) if g1 else False) or (getattr(g2, "is_internship", False) if g2 else False)
    if not is_internship and isinstance(g1, dict):
        is_internship = g1.get("is_internship", False) or (g2.get("is_internship", False) if isinstance(g2, dict) else False)

    course_type_str = str(moving_lesson.get("course_type", "")).lower()
    is_theory = ("theory" in course_type_str)

    if is_internship and is_theory:
        if target_start_period < 11:
            warnings.append("กลุ่มผู้เรียนออกฝึกงานในสถานประกอบการ: รายวิชาทฤษฎีต้องจัดหลัง 18:00 น. (คาบ 11–12)")
    else:
        # คาบ 1-10 คือเวลาปกติ (08:00 - 18:00), คาบ 11-12 คือช่วงค่ำ
        if target_end_period > 10:
            warnings.append(f"วิชานี้จะสิ้นสุดที่คาบที่ {target_end_period} (หลัง 18:00 น. ช่วงค่ำ สำหรับกลุ่มเรียนปกติ)")

    # 3. ตรวจสอบคาบพักกลางวัน (คาบที่ 5: 12:00 - 13:00)
    if target_start_period <= 5 <= target_end_period:
        conflicts.append("ไม่สามารถจัดทับคาบที่ 5 (12:00–13:00 น.) ได้ เนื่องจากเป็นเวลาพักกลางวัน")

    # 3.01 ตรวจสอบเงื่อนไขล็อกคาบเรียนวันพุธ คาบ 7-8 (ลูกเสือ ปวช.1 / กิจกรรม ปวช.2, 3, ปวส.4)
    c_name = moving_lesson.get("course_name", "")
    c_code = moving_lesson.get("course_code", "")
    is_scout = is_scout_assignment(c_name, c_code)
    is_act = is_activity_assignment(c_name, c_code)

    def _get_grp_cat(grp):
        if not grp:
            return "OTHER"
        if isinstance(grp, dict):
            return get_group_year_category(grp.get("name", ""), str(grp.get("level", "VOC_CERT")))
        return get_group_year_category(getattr(grp, "name", ""), str(getattr(grp, "level", "VOC_CERT")))

    grp_cats = [_get_grp_cat(g1)]
    if g2:
        grp_cats.append(_get_grp_cat(g2))

    overlaps_wed_7_8 = (target_day == 2 and max(target_start_period, 7) <= min(target_end_period, 8))

    for g_cat in grp_cats:
        if g_cat == "VOC_1":
            if overlaps_wed_7_8 and not is_scout:
                conflicts.append("วันพุธ คาบที่ 7–8 สงวนไว้สำหรับวิชาลูกเสือวิสามัญ (ปวช.1) เท่านั้น ไม่อนุญาตให้จัดวิชาเรียนอื่นในช่วงเวลานี้")
                break
            if is_scout and not (target_day == 2 and target_start_period == 7 and duration == 2):
                conflicts.append("วิชาลูกเสือวิสามัญสำหรับ ปวช.1 มีเงื่อนไขล็อกตายตัวในวันพุธ คาบที่ 7–8 เท่านั้น")
                break
        elif g_cat in ("VOC_2", "VOC_3", "PVS_4"):
            if overlaps_wed_7_8 and not is_act:
                conflicts.append("วันพุธ คาบที่ 7–8 สงวนไว้สำหรับคาบกิจกรรมวิทยาลัย (ปวช.2, 3, ปวส.4) เท่านั้น ไม่อนุญาตให้จัดวิชาเรียนอื่นในช่วงเวลานี้")
                break
            if is_act and not (target_day == 2 and target_start_period == 7 and duration == 2):
                conflicts.append("คาบกิจกรรมวิทยาลัยสำหรับ ปวช.2, 3, ปวส.4 มีเงื่อนไขล็อกตายตัวในวันพุธ คาบที่ 7–8 เท่านั้น")
                break

    def is_slot_unavail(unavail_obj, d, p):
        if not unavail_obj:
            return False
        if (d, p) in unavail_obj:
            return True
        if isinstance(unavail_obj, list) and [d, p] in unavail_obj:
            return True
        return False

    # 3.1 ตรวจสอบช่วงเวลาที่ไม่สะดวกสอนของครูผู้สอน
    if teachers_map and moving_lesson.get("teacher_id"):
        t_obj = teachers_map.get(moving_lesson["teacher_id"])
        if t_obj:
            unavail = getattr(t_obj, "unavailable_slots", None)
            if unavail is None and isinstance(t_obj, dict):
                unavail = t_obj.get("unavailable_slots", [])
            if unavail:
                day_label = DAY_NAMES[target_day] if target_day < len(DAY_NAMES) else f"วันที่ {target_day+1}"
                for p in range(target_start_period, target_end_period + 1):
                    if is_slot_unavail(unavail, target_day, p):
                        conflicts.append(
                            f"ครูผู้สอน ({moving_lesson['teacher_name']}) ติดภารกิจ/ไม่สะดวกสอนใน{day_label} คาบที่ {p}"
                        )

    # 3.2 ตรวจสอบช่วงเวลาที่ไม่สะดวกสอนของครูร่วมสอน (secondary_teacher)
    if teachers_map and moving_lesson.get("secondary_teacher_id"):
        sec_id = moving_lesson["secondary_teacher_id"]
        sec_obj = teachers_map.get(sec_id)
        if sec_obj:
            unavail = getattr(sec_obj, "unavailable_slots", None)
            if unavail is None and isinstance(sec_obj, dict):
                unavail = sec_obj.get("unavailable_slots", [])
            if unavail:
                day_label = DAY_NAMES[target_day] if target_day < len(DAY_NAMES) else f"วันที่ {target_day+1}"
                sec_name = moving_lesson.get("secondary_teacher_name") or (getattr(sec_obj, "name", sec_id) if not isinstance(sec_obj, dict) else sec_obj.get("name", sec_id))
                for p in range(target_start_period, target_end_period + 1):
                    if is_slot_unavail(unavail, target_day, p):
                        conflicts.append(
                            f"ครูร่วมสอน ({sec_name}) ติดภารกิจ/ไม่สะดวกสอนใน{day_label} คาบที่ {p}"
                        )

    # 4. ตรวจสอบห้องเรียนและความจุ
    target_room = rooms_map.get(target_room_id)
    if not target_room:
        conflicts.append(f"ไม่พบข้อมูลห้องเรียน ID '{target_room_id}'")
    else:
        # คำนวณจำนวนนักเรียนรวม
        g1 = groups_map.get(moving_lesson["primary_group_id"])
        total_students = g1.student_count if g1 else 0
        if moving_lesson.get("is_merged") and moving_lesson.get("secondary_group_id"):
            g2 = groups_map.get(moving_lesson["secondary_group_id"])
            if g2:
                total_students += g2.student_count
        
        if target_room.capacity < total_students:
            conflicts.append(
                f"ห้อง {target_room.name} รองรับได้เพียง {target_room.capacity} คน "
                f"แต่มีผู้เรียนรวม {total_students} คน (ความจุไม่พอ)"
            )

    # 5. ตรวจสอบการชนกับวิชาอื่นในตาราง
    moving_blocks = set(moving_lesson.get("active_blocks", []))
    moving_groups = {moving_lesson["primary_group_id"]}
    if moving_lesson.get("secondary_group_id"):
        moving_groups.add(moving_lesson["secondary_group_id"])

    moving_teachers = {moving_lesson["teacher_id"]}
    if moving_lesson.get("secondary_teacher_id"):
        moving_teachers.add(moving_lesson["secondary_teacher_id"])

    for other in schedule:
        if other["assignment_id"] == assignment_id:
            continue  # ข้ามวิชาของตัวเอง

        # เช็กว่า active ในบล็อกเดียวกันหรือไม่
        other_blocks = set(other.get("active_blocks", []))
        shared_blocks = moving_blocks.intersection(other_blocks)
        if not shared_blocks:
            continue  # ไม่ได้เรียนในสัปดาห์เดียวกัน ไม่ชน

        # เช็กวันเดียวกันหรือไม่
        if other["day"] != target_day:
            continue

        # เช็กเวลาคาบซ้อนทับกันหรือไม่
        # ช่วง [target_start, target_end] vs [other.start, other.end]
        overlap = max(target_start_period, other["start_period"]) <= min(target_end_period, other["end_period"])
        if not overlap:
            continue

        day_label = DAY_NAMES[target_day] if target_day < len(DAY_NAMES) else f"วันที่ {target_day+1}"
        period_label = f"คาบที่ {other['start_period']}–{other['end_period']}"

        # 5.1 ชนครูผู้สอน (ทั้งครูหลักและครูร่วมสอน)
        other_teachers = {other["teacher_id"]}
        if other.get("secondary_teacher_id"):
            other_teachers.add(other["secondary_teacher_id"])

        clashing_teachers = moving_teachers.intersection(other_teachers)
        for t_clash_id in clashing_teachers:
            t_name = t_clash_id
            if teachers_map and t_clash_id in teachers_map:
                t_inst = teachers_map[t_clash_id]
                t_name = getattr(t_inst, "name", t_clash_id) if not isinstance(t_inst, dict) else t_inst.get("name", t_clash_id)
            elif t_clash_id == moving_lesson.get("teacher_id"):
                t_name = moving_lesson.get("teacher_name", t_clash_id)
            elif t_clash_id == moving_lesson.get("secondary_teacher_id"):
                t_name = moving_lesson.get("secondary_teacher_name", t_clash_id)

            conflicts.append(
                f"ครูผู้สอน ({t_name}) ติดสอนวิชา '{other['course_name']}' "
                f"ใน{day_label} {period_label} (บล็อก {sorted(list(shared_blocks))})"
            )

        # 5.2 ชนห้องเรียน
        if other["room_id"] == target_room_id:
            conflicts.append(
                f"ห้องเรียน ({target_room.name if target_room else target_room_id}) มีวิชา '{other['course_name']}' "
                f"ใช้งานอยู่แล้วใน{day_label} {period_label}"
            )

        # 5.3 ชนกลุ่มผู้เรียน
        other_groups = {other["primary_group_id"]}
        if other.get("secondary_group_id"):
            other_groups.add(other["secondary_group_id"])

        clashing_groups = moving_groups.intersection(other_groups)
        if clashing_groups:
            group_names = ", ".join([groups_map[g_id].name if g_id in groups_map else g_id for g_id in clashing_groups])
            conflicts.append(
                f"กลุ่มเรียน ({group_names}) มีเรียนวิชา '{other['course_name']}' "
                f"ใน{day_label} {period_label}"
            )

    # 6. ตรวจสอบความเหมาะสมของภาระงานสอนครูและคาบเรียนนักศึกษาต่อวัน (Daily Workload Suitability)
    if teachers_map:
        for t_id in moving_teachers:
            t = teachers_map.get(t_id)
            if t:
                other_day_periods = sum(
                    other.get("duration", 1) for other in schedule
                    if other["assignment_id"] != assignment_id and other["day"] == target_day and (
                        other["teacher_id"] == t_id or other.get("secondary_teacher_id") == t_id
                    )
                )
                new_day_periods = other_day_periods + duration
                max_allowed = getattr(t, "max_periods_per_day", 6)
                if new_day_periods > max_allowed:
                    warnings.append(
                        f"ครู ({t.name}) จะมีภาระสอนในวันดังกล่าว {new_day_periods} คาบ ซึ่งเกินเกณฑ์ต่อวัน ({max_allowed} คาบ)"
                    )

    for g_id in moving_groups:
        g = groups_map.get(g_id)
        other_day_periods = sum(
            other.get("duration", 1) for other in schedule
            if other["assignment_id"] != assignment_id and other["day"] == target_day and (
                other["primary_group_id"] == g_id or other.get("secondary_group_id") == g_id
            )
        )
        new_day_periods = other_day_periods + duration
        if new_day_periods > 8:
            warnings.append(
                f"กลุ่มเรียน ({g.name if g else g_id}) จะมีคาบเรียนในวันดังกล่าว {new_day_periods} คาบ ซึ่งเกินเกณฑ์ความเหมาะสมต่อวัน (สูงสุด 8 คาบ)"
            )

    is_valid = len(conflicts) == 0
    return is_valid, conflicts, warnings


def validate_swap(
    schedule: List[Dict[str, Any]],
    assignment_id_1: str,
    assignment_id_2: str,
    rooms_map: Dict[str, Any],
    groups_map: Dict[str, Any],
    teachers_map: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str], List[str], List[Dict[str, Any]]]:
    """
    ตรวจสอบและจำลองการสลับคาบเรียนระหว่าง assignment_id_1 และ assignment_id_2
    คืนค่า (is_valid, conflicts, warnings, updated_schedule)
    """
    conflicts: List[str] = []
    warnings: List[str] = []

    l1 = next((s for s in schedule if s["assignment_id"] == assignment_id_1), None)
    l2 = next((s for s in schedule if s["assignment_id"] == assignment_id_2), None)

    if not l1:
        return False, [f"ไม่พบวิชา ID '{assignment_id_1}' ในตาราง"], [], []
    if not l2:
        return False, [f"ไม่พบวิชา ID '{assignment_id_2}' ในตาราง"], [], []

    if assignment_id_1 == assignment_id_2:
        return False, ["ไม่สามารถสลับวิชาเดียวกันได้"], [], []

    if l1.get("is_pinned") or l2.get("is_pinned"):
        pinned_name = l1.get("course_name") if l1.get("is_pinned") else l2.get("course_name")
        conflicts.append(f"วิชา '{pinned_name}' ถูกล็อกเวลาตายตัวไว้ล่วงหน้า (Pinned Lesson) หากต้องการสลับ กรุณาปลดล็อกก่อน")

    # 1. เช็กความยาวคาบ
    if l1["duration"] != l2["duration"]:
        warnings.append(
            f"ความยาวคาบไม่เท่ากัน: '{l1['course_name']}' ({l1['duration']} คาบ) "
            f"กับ '{l2['course_name']}' ({l2['duration']} คาบ)"
        )

    # กำหนดตำแหน่งใหม่: l1 ไปตำแหน่งของ l2, และ l2 ไปตำแหน่งของ l1
    target1_day = l2["day"]
    target1_start = l2["start_period"]
    target2_day = l1["day"]
    target2_start = l1["start_period"]

    # เลือกห้องเรียน: ตรวจสอบความจุของห้องที่สลับกัน
    def get_students_count(item):
        g1 = groups_map.get(item["primary_group_id"])
        cnt = g1.student_count if g1 else 0
        if item.get("is_merged") and item.get("secondary_group_id"):
            g2 = groups_map.get(item["secondary_group_id"])
            if g2:
                cnt += g2.student_count
        return cnt

    students1 = get_students_count(l1)
    students2 = get_students_count(l2)

    # ห้องเป้าหมาย: ลองใช้ห้องของกันและกันก่อน ถ้าความจุพอดี
    target1_room_id = l2["room_id"]
    r_target1 = rooms_map.get(target1_room_id)
    if r_target1 and r_target1.capacity < students1:
        # หากห้องของ l2 เล็กเกินไปสำหรับ l1 ให้คงห้องเดิมของ l1 ไว้
        target1_room_id = l1["room_id"]

    target2_room_id = l1["room_id"]
    r_target2 = rooms_map.get(target2_room_id)
    if r_target2 and r_target2.capacity < students2:
        target2_room_id = l2["room_id"]

    # 2. ตรวจสอบเงื่อนไข l1 ที่ตำแหน่งใหม่ (โดยลบ l2 ออกจากตารางอ้างอิงชั่วคราว)
    schedule_without_l2 = [s for s in schedule if s["assignment_id"] != assignment_id_2]
    valid1, conf1, warn1 = validate_move(
        schedule=schedule_without_l2,
        assignment_id=assignment_id_1,
        target_day=target1_day,
        target_start_period=target1_start,
        target_room_id=target1_room_id,
        rooms_map=rooms_map,
        groups_map=groups_map,
        teachers_map=teachers_map
    )

    # 3. ตรวจสอบเงื่อนไข l2 ที่ตำแหน่งใหม่ (โดยลบ l1 ออกจากตารางอ้างอิงชั่วคราว)
    schedule_without_l1 = [s for s in schedule if s["assignment_id"] != assignment_id_1]
    valid2, conf2, warn2 = validate_move(
        schedule=schedule_without_l1,
        assignment_id=assignment_id_2,
        target_day=target2_day,
        target_start_period=target2_start,
        target_room_id=target2_room_id,
        rooms_map=rooms_map,
        groups_map=groups_map,
        teachers_map=teachers_map
    )

    conflicts.extend([f"วิชา '{l1['course_name']}': {c}" for c in conf1])
    conflicts.extend([f"วิชา '{l2['course_name']}': {c}" for c in conf2])
    warnings.extend(warn1 + warn2)

    # 4. ตรวจสอบว่าตำแหน่งใหม่ของ l1 และ l2 ไม่ชนกันเอง (ในกรณีที่วันเดียวกันและคาบอาจซ้อนทับกัน)
    if target1_day == target2_day:
        end1 = target1_start + l1["duration"] - 1
        end2 = target2_start + l2["duration"] - 1
        overlap = max(target1_start, target2_start) <= min(end1, end2)
        if overlap:
            conflicts.append("ตำแหน่งใหม่ของทั้ง 2 วิชาเกิดการทับซ้อนกันเอง")

    is_valid = len(conflicts) == 0

    # 5. สร้าง updated_schedule หากถูกต้อง
    updated_schedule: List[Dict[str, Any]] = []
    if is_valid:
        r1_obj = rooms_map.get(target1_room_id)
        r2_obj = rooms_map.get(target2_room_id)
        r1_name = r1_obj.name if r1_obj else target1_room_id
        r2_name = r2_obj.name if r2_obj else target2_room_id

        for s in schedule:
            if s["assignment_id"] == assignment_id_1:
                new_s = dict(s)
                dur = l1["duration"]
                new_s["day"] = target1_day
                new_s["day_name"] = DAY_NAMES[target1_day] if target1_day < len(DAY_NAMES) else f"วันที่ {target1_day+1}"
                new_s["start_period"] = target1_start
                new_s["end_period"] = target1_start + dur - 1
                new_s["room_id"] = target1_room_id
                new_s["room_name"] = r1_name
                updated_schedule.append(new_s)
            elif s["assignment_id"] == assignment_id_2:
                new_s = dict(s)
                dur = l2["duration"]
                new_s["day"] = target2_day
                new_s["day_name"] = DAY_NAMES[target2_day] if target2_day < len(DAY_NAMES) else f"วันที่ {target2_day+1}"
                new_s["start_period"] = target2_start
                new_s["end_period"] = target2_start + dur - 1
                new_s["room_id"] = target2_room_id
                new_s["room_name"] = r2_name
                updated_schedule.append(new_s)
            else:
                updated_schedule.append(dict(s))

    return is_valid, conflicts, warnings, updated_schedule


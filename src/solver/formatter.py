from typing import List, Dict, Any

DAYS = ["จันทร์ (Mon)", "อังคาร (Tue)", "พุธ (Wed)", "พฤหัสบดี (Thu)", "ศุกร์ (Fri)"]

def format_timetable_by_group(results: List[Dict[str, Any]], group_id: str, group_name: str, num_blocks: int = 6):
    lines = []
    lines.append(f"\n=======================================================")
    lines.append(f"  ตารางเรียน: {group_name} ({group_id})")
    lines.append(f"=======================================================")

    for b in range(num_blocks):
        week_range = f"สัปดาห์ที่ {b*3 + 1}–{(b+1)*3}"
        lines.append(f"\n--- [บล็อกที่ {b+1}: {week_range}] ---")
        
        # ตรวจสอบวิชาที่ active ในบล็อกนี้
        block_lessons = [
            r for r in results
            if b in r["active_blocks"] and (
                r["assignment"].primary_group_id == group_id or
                r["assignment"].secondary_group_id == group_id
            )
        ]

        if not block_lessons:
            lines.append("  (ไม่มีการเรียนการสอนในบล็อกนี้ / สิ้นสุดภาคการศึกษา)")
            continue

        # จัดตาราง 5 วัน x 8 คาบ
        grid = [["[ว่าง]" for _ in range(8)] for _ in range(5)]
        for r in block_lessons:
            d = r["day"]
            p_start = r["start_period"]
            dur = r["duration"]
            ass = r["assignment"]
            c_name = ass.course.name
            t_name = r["teacher"].name
            room_name = r["room"].name
            is_merged = ass.secondary_group_id is not None
            merge_tag = " (เรียนรวม)" if is_merged else ""

            label = f"{c_name}{merge_tag}\n{t_name}\nห้อง: {room_name}"
            for p in range(p_start, p_start + dur):
                grid[d][p] = f"[{c_name}{merge_tag} | {room_name}]"

        for d_idx, day_name in enumerate(DAYS):
            slots_str = " | ".join([f"คาบ{p+1}: {grid[d_idx][p]}" for p in range(8) if grid[d_idx][p] != "[ว่าง]"])
            if slots_str:
                lines.append(f"  {day_name}: {slots_str}")
            else:
                lines.append(f"  {day_name}: [ไม่มีคาบเรียน]")

    return "\n".join(lines)

def format_teacher_schedule(results: List[Dict[str, Any]], teacher_id: str, teacher_name: str, num_blocks: int = 6):
    lines = []
    lines.append(f"\n=======================================================")
    lines.append(f"  ตารางสอนครู: {teacher_name} ({teacher_id})")
    lines.append(f"=======================================================")

    for b in range(num_blocks):
        week_range = f"สัปดาห์ที่ {b*3 + 1}–{(b+1)*3}"
        lines.append(f"\n--- [บล็อกที่ {b+1}: {week_range}] ---")

        t_lessons = [
            r for r in results
            if b in r["active_blocks"] and r["assignment"].teacher_id == teacher_id
        ]

        if not t_lessons:
            lines.append("  >> [ว่าง ไม่มีคาบสอนในบล็อกนี้ สามารถจัดสอนเสริม/งานโครงการได้] <<")
            continue

        for r in t_lessons:
            d = DAYS[r["day"]]
            p_start = r["start_period"] + 1
            p_end = r["start_period"] + r["duration"]
            ass = r["assignment"]
            groups = ass.primary_group_id
            if ass.secondary_group_id:
                groups += f" + {ass.secondary_group_id} (เรียนรวม)"
            lines.append(
                f"  - {d} คาบที่ {p_start}–{p_end}: {ass.course.name} "
                f"| กลุ่ม: {groups} | ห้อง: {r['room'].name}"
            )

    return "\n".join(lines)

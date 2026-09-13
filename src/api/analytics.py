"""
Teacher Workload & Facility Analytics Service
Calculates teacher teaching loads, distribution, compliance with vocational standards,
and room utilization rates.
"""
from typing import Dict, Any, List
from collections import defaultdict

class WorkloadAnalyticsService:
    # Standard vocational teaching load thresholds (สอศ.)
    MIN_STANDARD_LOAD = 16  # Underload if < 16
    MAX_STANDARD_LOAD = 22  # Overload if > 22
    TOTAL_DAYTIME_PERIODS = 50  # 5 days x 10 periods (excluding lunch)

    def __init__(self, schedule: List[Dict[str, Any]], config: Dict[str, Any]):
        self.schedule = schedule
        self.config = config
        self.teachers = config.get("teachers", [])
        self.rooms = config.get("rooms", [])
        self.groups = config.get("groups", [])
        self.courses = {c["id"]: c for c in config.get("courses", [])}
        self.assignments = {a["id"]: a for a in config.get("assignments", [])}

    def compute_analytics(self) -> Dict[str, Any]:
        teachers_data = self._compute_teachers()
        rooms_data = self._compute_rooms()
        groups_data = self._compute_groups()
        summary_kpi = self._compute_summary(teachers_data, rooms_data, groups_data)

        return {
            "summary": summary_kpi,
            "teachers": teachers_data,
            "rooms": rooms_data,
            "groups": groups_data
        }

    def _compute_teachers(self) -> List[Dict[str, Any]]:
        # Index scheduled lessons by teacher
        teacher_lessons = defaultdict(list)
        for item in self.schedule:
            t_id = item.get("teacher_id")
            if t_id:
                teacher_lessons[t_id].append(item)

        results = []
        for t in self.teachers:
            t_id = t["id"]
            lessons = teacher_lessons[t_id]

            total_periods = 0
            theory_periods = 0
            practice_periods = 0
            day_periods = defaultdict(int)
            unique_courses = set()

            for l in lessons:
                dur = l.get("duration", l.get("duration_periods", 1))
                day = l.get("day", l.get("day_of_week", 0))
                total_periods += dur
                day_periods[day] += dur
                
                c_id = l.get("course_id")
                if c_id:
                    unique_courses.add(c_id)

                # Check course type
                c_type = l.get("course_type", "").lower()
                is_merged = l.get("is_merged", l.get("is_merged_theory", False))
                if "theory" in c_type or is_merged:
                    theory_periods += dur
                else:
                    practice_periods += dur

            max_day_load = max(day_periods.values()) if day_periods else 0
            days_active = len(day_periods)
            avg_daily = round(total_periods / days_active, 1) if days_active > 0 else 0.0

            # Evaluation status based on vocational standards
            status = "balanced"
            status_label = "พอดีตามเกณฑ์ (16-22 คาบ)"
            status_color = "emerald"

            max_allowed = t.get("max_periods_per_day", 6)
            if total_periods > self.MAX_STANDARD_LOAD or max_day_load > max_allowed:
                status = "overload"
                status_label = f"ภาระงานแน่นเกินเกณฑ์ ({total_periods} คาบ)"
                status_color = "red"
            elif total_periods < self.MIN_STANDARD_LOAD:
                status = "underload"
                status_label = f"ต่ำกว่าเกณฑ์ขั้นต่ำ ({total_periods} คาบ)"
                status_color = "amber"

            unavailable_count = len(t.get("unavailable_slots", []))

            results.append({
                "id": t_id,
                "name": t["name"],
                "total_periods": total_periods,
                "theory_periods": theory_periods,
                "practice_periods": practice_periods,
                "course_count": len(unique_courses),
                "days_teaching": days_active,
                "max_day_load": max_day_load,
                "avg_daily_load": avg_daily,
                "status": status,
                "status_label": status_label,
                "status_color": status_color,
                "unavailable_slots_count": unavailable_count
            })

        # Sort by total periods descending
        results.sort(key=lambda x: x["total_periods"], reverse=True)
        return results

    def _compute_rooms(self) -> List[Dict[str, Any]]:
        room_lessons = defaultdict(list)
        for item in self.schedule:
            r_id = item.get("room_id")
            if r_id:
                room_lessons[r_id].append(item)

        results = []
        for r in self.rooms:
            r_id = r["id"]
            lessons = room_lessons[r_id]
            used_periods = sum(l.get("duration", l.get("duration_periods", 1)) for l in lessons)
            util_rate = round((used_periods / self.TOTAL_DAYTIME_PERIODS) * 100, 1)

            results.append({
                "id": r_id,
                "name": r["name"],
                "room_type": r.get("room_type", "CLASSROOM"),
                "capacity": r.get("capacity", 35),
                "used_periods": used_periods,
                "utilization_rate": min(util_rate, 100.0),
                "lessons_count": len(lessons)
            })

        results.sort(key=lambda x: x["utilization_rate"], reverse=True)
        return results

    def _compute_groups(self) -> List[Dict[str, Any]]:
        group_periods = defaultdict(int)
        for item in self.schedule:
            dur = item.get("duration", item.get("duration_periods", 1))
            g1 = item.get("primary_group_id")
            if g1:
                group_periods[g1] += dur
            g2 = item.get("secondary_group_id")
            if g2:
                group_periods[g2] += dur

        results = []
        for g in self.groups:
            g_id = g["id"]
            periods = group_periods[g_id]
            results.append({
                "id": g_id,
                "name": g["name"],
                "level": g.get("level", "VOC_CERT"),
                "student_count": g.get("student_count", 20),
                "total_periods": periods
            })
        return results

    def _compute_summary(self, teachers: List[Dict[str, Any]], rooms: List[Dict[str, Any]], groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_teachers = len(teachers)
        total_teach_periods = sum(t["total_periods"] for t in teachers)
        avg_teacher_load = round(total_teach_periods / total_teachers, 1) if total_teachers > 0 else 0.0

        overload_count = sum(1 for t in teachers if t["status"] == "overload")
        underload_count = sum(1 for t in teachers if t["status"] == "underload")
        balanced_count = sum(1 for t in teachers if t["status"] == "balanced")

        avg_room_util = round(sum(r["utilization_rate"] for r in rooms) / len(rooms), 1) if rooms else 0.0

        return {
            "total_teachers": total_teachers,
            "total_rooms": len(rooms),
            "total_groups": len(groups),
            "total_scheduled_lessons": len(self.schedule),
            "total_college_periods": total_teach_periods,
            "avg_periods_per_teacher": avg_teacher_load,
            "avg_room_utilization": avg_room_util,
            "balanced_teachers_count": balanced_count,
            "overloaded_teachers_count": overload_count,
            "underloaded_teachers_count": underload_count
        }

import sys
from src.solver.benchmark_data import get_benchmark_dataset
from src.solver.timetable_solver import TimetableSolver
from src.solver.formatter import format_timetable_by_group, format_teacher_schedule

def main():
    print("=========================================================")
    print("   ระบบจัดตารางเรียนตารางสอนอัจฉริยะ (Smart Timetable App)")
    print("      Testing Core Constraint Solver Engine (CP-SAT)")
    print("=========================================================\n")

    dataset = get_benchmark_dataset()
    print(f"โหลดข้อมูลทดสอบ:")
    print(f"- จำนวนครูผู้สอน: {len(dataset['teachers'])} ท่าน")
    print(f"- จำนวนห้องเรียน/ศูนย์ฝึก: {len(dataset['rooms'])} ห้อง")
    print(f"- จำนวนกลุ่มเรียน: {len(dataset['groups'])} กลุ่ม (ปวช. 18 สัปดาห์ & ปวส. 15 สัปดาห์)")
    print(f"- จำนวนรายการวิชา/การมอบหมาย: {len(dataset['assignments'])} รายการ")
    print("\nกำลังสร้างแบบจำลอง CP-SAT และประมวลผลเงื่อนไข...")

    solver = TimetableSolver(
        teachers=dataset["teachers"],
        rooms=dataset["rooms"],
        groups=dataset["groups"],
        assignments=dataset["assignments"],
        days=5,
        periods_per_day=8,
        num_blocks=6
    )

    solver.build_model()
    print("สร้าง Constraints เสร็จสิ้น เริ่มกระบวนการค้นหาคำตอบ (Solving)...")

    results = solver.solve(time_limit_seconds=10.0)

    if not results:
        print("❌ ไม่พบคำตอบที่เป็นไปได้ภายใต้เงื่อนไขที่กำหนด (Infeasible)")
        sys.exit(1)

    print("\n🎉 จัดตารางสำเร็จ! (Feasible/Optimal Solution Found)\n")

    # แสดงผลตารางของกลุ่มเรียน
    for grp in dataset["groups"]:
        print(format_timetable_by_group(results, grp.id, grp.name))

    # แสดงผลตารางสอนของครู สมศักดิ์ (ผู้สอนทั้ง ปวช. และ ปวส.)
    print(format_teacher_schedule(
        results,
        "T_AUTO_1",
        "อ. สมศักดิ์ (หัวหน้าแผนกช่างยนต์ - ครูสอนข้ามระดับ ปวช./ปวส.)"
    ))

    # แสดงผลตารางสอนของครู สุภาวดี (วิชาเรียนรวม Merged Theory)
    print(format_teacher_schedule(
        results,
        "T_ENG",
        "อ. สุภาวดี (หมวดภาษาอังกฤษ - วิชาเรียนรวม 2 กลุ่ม)"
    ))

if __name__ == "__main__":
    main()

import os
import tempfile
from pathlib import Path

# ป้องกันไม่ให้ชุดแบบทดสอบเขียนทับไฟล์ timetable_config.json ที่ใช้งานจริง
test_dir = Path(tempfile.gettempdir()) / "smart_timetable_tests"
test_dir.mkdir(exist_ok=True)
os.environ["TIMETABLE_CONFIG_FILE"] = str(test_dir / "test_timetable_config.json")

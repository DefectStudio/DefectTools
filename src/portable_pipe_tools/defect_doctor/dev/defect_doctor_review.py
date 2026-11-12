"""Development visual review; uses an isolated history folder."""

from pathlib import Path
import subprocess
import sys
import tempfile
import tkinter as tk

source_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(source_root))
from portable_pipe_tools.defect_doctor.app import DoctorApp
from portable_pipe_tools.defect_doctor.storage import Store

with tempfile.TemporaryDirectory(prefix="defect-doctor-review-") as directory:
    root = tk.Tk()
    app = DoctorApp(root, Store(Path(directory)))
    root.title("Defect Doctor — Layout Review")
    root.attributes("-topmost", True)

    def capture():
        try:
            result = subprocess.run(
                [sys.executable,
                 "C:/Users/Admin/.codex/skills/windows-screenshot/scripts/capture_screen.py",
                 "--window-title", "Defect Doctor — Layout Review", "--output",
                 str(source_root.parent / "LocalSaveFiles" / "defect_doctor_updated.png")],
                capture_output=True, text=True, encoding="utf-8", timeout=10,
            )
            print(result.stdout.strip() or result.stderr.strip())
            if result.returncode:
                raise RuntimeError("Could not capture layout preview")
        finally:
            app.close()

    root.after(500, capture)
    root.mainloop()

"""Run Defect Doctor directly from a checkout, without installing a package."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from portable_pipe_tools.defect_doctor.app import main


if __name__ == "__main__":
    main()

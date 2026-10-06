"""Compatibility entrypoint for the V2-only Rendering Tool verification."""

from pathlib import Path
import runpy


verify = runpy.run_path(str(Path(__file__).with_name("verify_render_farm_v2_only.py")))["verify"]


if __name__ == "__main__":
    verify()

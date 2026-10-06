"""Compatibility entrypoint for the V2-only Rendering Tool migration."""

from pathlib import Path
import runpy


apply = runpy.run_path(str(Path(__file__).with_name("apply_render_farm_v2_only.py")))["apply"]


if __name__ == "__main__":
    apply()

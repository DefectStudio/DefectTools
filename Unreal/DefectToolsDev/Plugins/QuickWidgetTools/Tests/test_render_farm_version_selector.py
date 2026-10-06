"""Legacy widget state must never send jobs to V1 after the V2-only migration."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "Content/Python/render_farm_version_selector.py"
spec = importlib.util.spec_from_file_location("farm_v2_only", SCRIPT_PATH)
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class FarmV2OnlyTests(unittest.TestCase):
    def test_legacy_v1_selection_cannot_route_to_v1(self):
        v1, v2 = Mock(), Mock()
        for v1_checked, v2_checked in ((True, False), (False, True), (True, True), (False, False)):
            v1.is_checked.return_value = v1_checked
            v2.is_checked.return_value = v2_checked
            self.assertTrue(selector.use_v2(v1, v2))

    def test_initialization_supports_new_and_legacy_widget_assets(self):
        for v1 in (None, Mock()):
            v2 = Mock()
            selector.initialize(v1, v2)
            if v1 is not None:
                v1.remove_from_parent.assert_called_once()
                v1.on_check_state_changed.clear.assert_called_once()
            v2.remove_from_parent.assert_called_once()
            v2.on_check_state_changed.clear.assert_called_once()
            v2.on_check_state_changed.add_callable.assert_not_called()


if __name__ == "__main__":
    unittest.main()

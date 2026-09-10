import unittest
from unittest.mock import Mock

from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherClient, DispatcherError


class ProjectRegistryClientTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(DispatcherClient)
        self.client._request = Mock()

    def test_worker_list_defaults_to_active_only(self):
        self.client._request.return_value = {"projects": [{"project_id": "bishop"}]}
        self.assertEqual([{"project_id": "bishop"}], self.client.list_projects())
        self.client._request.assert_called_once_with("GET", "/api/v1/projects", query={"include_inactive": None})

    def test_manager_can_request_inactive_projects(self):
        self.client._request.return_value = {"projects": []}
        self.client.list_projects(include_inactive=True)
        self.client._request.assert_called_once_with("GET", "/api/v1/projects", query={"include_inactive": "true"})

    def test_update_sends_revision_and_preserves_project_id(self):
        self.client._request.return_value = {"project": {"project_id": "bishop", "revision": 3}}
        result = self.client.update_project("bishop", "Bishop", active=False, revision=2)
        self.assertEqual(3, result["revision"])
        self.client._request.assert_called_once_with("PUT", "/api/v1/projects/bishop", body={
            "display_name": "Bishop", "active": False, "revision": 2,
        })

    def test_create_sends_explicit_id_and_name(self):
        self.client._request.return_value = {"project": {"project_id": "bishop"}}
        self.client.create_project("bishop", "Bishop")
        self.client._request.assert_called_once_with("POST", "/api/v1/projects", body={
            "project_id": "bishop", "display_name": "Bishop", "active": True,
        })

    def test_invalid_server_list_is_reported(self):
        for projects in [None, {}, ["bishop"]]:
            self.client._request.return_value = {"projects": projects}
            with self.assertRaises(DispatcherError):
                self.client.list_projects()


if __name__ == "__main__":
    unittest.main()

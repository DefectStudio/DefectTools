"""Company-managed SQL dispatcher connection; no per-operator connection setup."""

from portable_pipe_tools.app_runtime import resource_root
from portable_pipe_tools.render_farm.cloud_dispatch import (
    DispatcherConfigurationError, DispatcherConnection, load_dispatcher_connection,
)
from portable_pipe_tools.render_farm.queue import read_json_object


def load_company_worker_connection() -> DispatcherConnection:
    try:
        settings = read_json_object(resource_root() / "worker_company_connection.json")
        return DispatcherConnection(settings["api_url"], "worker", settings["worker_token"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise DispatcherConfigurationError(
            "The company V2 worker connection is missing or invalid. Update the complete Defect Tools checkout, including worker_company_connection.json."
        ) from error

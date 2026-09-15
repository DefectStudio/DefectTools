"""Company-managed SQL dispatcher connection; no per-operator connection setup."""

from portable_pipe_tools.app_runtime import is_frozen, resource_root
from portable_pipe_tools.render_farm.cloud_dispatch import (
    DispatcherConfigurationError, DispatcherConnection, load_dispatcher_connection,
)
from portable_pipe_tools.render_farm.queue import read_json_object


def load_company_worker_connection() -> DispatcherConnection:
    if not is_frozen():
        # Source checkouts use the developer's separate V2 service configuration.
        return load_dispatcher_connection("worker", required=True)
    try:
        settings = read_json_object(resource_root() / "worker_company_connection.json")
        return DispatcherConnection(settings["api_url"], "worker", settings["worker_token"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise DispatcherConfigurationError(
            "This worker build has no valid company V2 service configuration. Contact the administrator for a configured build."
        ) from error

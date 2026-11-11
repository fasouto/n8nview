"""Fetch executions from the n8n public API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .convert import WorkflowError


@dataclass(frozen=True)
class N8nApi:
    base_url: str
    api_key: str

    def latest_execution(self, workflow_id: str | None = None) -> dict:
        """The execution that is running now, or else the most recent one, with its data."""
        # The default listing leaves out executions that are still running.
        found = self._list(workflow_id, status="running") or self._list(workflow_id)
        if not found:
            raise WorkflowError("n8n has no executions to show yet")
        return self._get(f"/executions/{found[0]['id']}", includeData="true")

    def _list(self, workflow_id: str | None, **filters: str) -> list[dict]:
        if workflow_id:
            filters["workflowId"] = workflow_id
        return self._get("/executions", limit="1", **filters).get("data") or []

    def _get(self, path: str, **query: str) -> dict:
        url = f"{self.base_url.rstrip('/')}/api/v1{path}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(url, headers={"X-N8N-API-KEY": self.api_key, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise WorkflowError("n8n rejected the API key (check N8N_API_KEY)") from error
            raise WorkflowError(f"n8n answered {error.code} for {path}") from error
        except (urllib.error.URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise WorkflowError(f"cannot reach n8n at {self.base_url}: {reason}") from error
        except json.JSONDecodeError as error:
            raise WorkflowError(f"n8n at {self.base_url} did not answer with JSON") from error

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
import urllib.error
import urllib.parse
import urllib.request


class GitHubApiError(RuntimeError):
    def __init__(self, status: int, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status = status
        self.details = details or {}


@dataclass
class GitHubResponse:
    status: int
    headers: Dict[str, str]
    data: Any


class GitHubApi:
    def __init__(self, token: str, user_agent: str = "gh-actions-orchestrator") -> None:
        self._token = token
        self._base = "https://api.github.com"
        self._user_agent = user_agent

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, str]] = None,
        accept: Optional[str] = None,
    ) -> GitHubResponse:
        url = f"{self._base}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        data_bytes = None
        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": accept or "application/vnd.github+json",
            "User-Agent": self._user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if data_bytes is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method)
        return self._request_with_retry(req)

    def get(self, path: str, query: Optional[Dict[str, str]] = None) -> GitHubResponse:
        return self.request("GET", path, query=query)

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> GitHubResponse:
        return self.request("POST", path, payload=payload)

    def put(self, path: str, payload: Optional[Dict[str, Any]] = None) -> GitHubResponse:
        return self.request("PUT", path, payload=payload)

    def patch(self, path: str, payload: Optional[Dict[str, Any]] = None) -> GitHubResponse:
        return self.request("PATCH", path, payload=payload)

    def paginate(self, path: str, query: Optional[Dict[str, str]] = None) -> Iterable[Any]:
        page = 1
        while True:
            q = dict(query or {})
            q.update({"per_page": "100", "page": str(page)})
            resp = self.request("GET", path, query=q)
            if not isinstance(resp.data, list):
                raise GitHubApiError(resp.status, "Expected list response for pagination")
            if not resp.data:
                break
            for item in resp.data:
                yield item
            if "link" not in {k.lower() for k in resp.headers.keys()}:
                break
            link = resp.headers.get("Link") or resp.headers.get("link")
            if link and "rel=\"next\"" not in link:
                break
            page += 1

    def _request_with_retry(self, req: urllib.request.Request) -> GitHubResponse:
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    status = resp.status
                    headers = {k: v for k, v in resp.headers.items()}
                    body = resp.read()
                    data = json.loads(body.decode("utf-8")) if body else None
                    return GitHubResponse(status=status, headers=headers, data=data)
            except urllib.error.HTTPError as exc:
                status = exc.code
                body = exc.read().decode("utf-8") if exc.fp else ""
                data = None
                try:
                    data = json.loads(body) if body else None
                except json.JSONDecodeError:
                    data = None
                if status in (403, 429, 500, 502, 503, 504):
                    wait = self._retry_after_seconds(exc.headers) or min(2 ** attempt, 20)
                    time.sleep(wait)
                    continue
                message = data.get("message") if isinstance(data, dict) else body
                raise GitHubApiError(status, message or "GitHub API error", data if isinstance(data, dict) else None)
            except urllib.error.URLError as exc:
                if attempt == max_attempts:
                    raise GitHubApiError(0, f"Network error: {exc}") from exc
                time.sleep(min(2 ** attempt, 20))
        raise GitHubApiError(0, "GitHub API retry limit exceeded")

    @staticmethod
    def _retry_after_seconds(headers: Optional[Dict[str, str]]) -> Optional[int]:
        if not headers:
            return None
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                return None
        reset = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
        if reset:
            try:
                reset_epoch = int(reset)
                return max(0, reset_epoch - int(time.time()))
            except ValueError:
                return None
        return None

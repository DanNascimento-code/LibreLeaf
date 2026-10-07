import logging
import time
from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Any

import httpx

from libreleaf.errors import ApiError

LOGGER = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class JsonHttpClient:
    """Small JSON API client with explicit timeouts, pacing, and bounded retries."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 15.0,
        max_retries: int = 2,
        minimum_interval: float = 0.0,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_retries = max_retries
        self._minimum_interval = minimum_interval
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request_at: float | None = None
        self._owns_client = client is None
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    def __enter__(self) -> "JsonHttpClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request("GET", url, params=params, headers=headers)

    def get_text(
        self,
        url: str,
        *,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[str, Mapping[str, str]]:
        response = self._request_response("GET", url, params=params, headers=headers)
        return response.text, response.headers

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", url, json=payload, headers=headers)

    def post_form(
        self,
        url: str,
        data: Mapping[str, str],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", url, data=data, headers=headers)

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request_response(method, url, **kwargs)
        try:
            payload = response.json()
        except ValueError as error:
            raise ApiError(f"{method} {url} returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise ApiError(f"{method} {url} returned a non-object JSON response")
        return payload

    def _request_response(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        attempts = self._max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            self._pace()
            try:
                response = self._client.request(method, url, **kwargs)
                self._last_request_at = self._monotonic()
            except httpx.RequestError as error:
                self._last_request_at = self._monotonic()
                last_error = error
                if attempt < attempts - 1:
                    self._backoff(attempt)
                continue

            if response.status_code not in RETRYABLE_STATUS_CODES:
                if response.is_error:
                    detail = response.text[:240].replace("\n", " ")
                    raise ApiError(f"{method} {url} returned HTTP {response.status_code}: {detail}")
                return response

            last_error = ApiError(f"{method} {url} returned HTTP {response.status_code}")
            if attempt < attempts - 1:
                retry_after = response.headers.get("Retry-After")
                self._backoff(attempt, retry_after)

        raise ApiError(f"{method} {url} failed after {attempts} attempt(s)") from last_error

    def _pace(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self._minimum_interval - (self._monotonic() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)

    def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        delay = float(retry_after) if retry_after and retry_after.isdigit() else float(2**attempt)
        delay = min(delay, 30.0)
        LOGGER.warning("API request failed; retrying in %.1f second(s)", delay)
        self._sleep(delay)

import httpx
import pytest

from libreleaf.errors import ApiError
from libreleaf.http import JsonHttpClient


def test_http_client_retries_and_returns_json() -> None:
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "slow"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    transport = httpx.MockTransport(lambda request: next(responses))
    sleeps: list[float] = []
    client = JsonHttpClient(
        user_agent="test",
        max_retries=1,
        client=httpx.Client(transport=transport),
        sleep=sleeps.append,
    )
    assert client.get("https://example.test")["ok"] is True
    assert sleeps == [0.0]


@pytest.mark.parametrize(
    "response",
    [httpx.Response(404, text="missing"), httpx.Response(200, text="not-json")],
)
def test_http_client_reports_bad_responses(response: httpx.Response) -> None:
    transport = httpx.MockTransport(lambda request: response)
    client = JsonHttpClient(user_agent="test", client=httpx.Client(transport=transport))
    with pytest.raises(ApiError):
        client.get("https://example.test")


def test_http_client_rejects_array_json() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
    client = JsonHttpClient(user_agent="test", client=httpx.Client(transport=transport))
    with pytest.raises(ApiError, match="non-object"):
        client.get("https://example.test")


def test_http_client_retries_transport_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(200, json={"ok": True})

    client = JsonHttpClient(
        user_agent="test",
        max_retries=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda seconds: None,
    )
    assert client.post_json("https://example.test", {"a": 1}) == {"ok": True}

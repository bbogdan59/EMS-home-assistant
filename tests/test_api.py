from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ems_home_assistant.api import (
    BridgeClient,
    BridgeError,
    InvalidAuth,
    InvalidPairing,
    normalize_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://ems.example",
        "https://user:pass@ems.example",
        "https://ems.example/path",
        "https://ems.example?token=secret",
        "https://ems.example#secret",
        "https://ems.example:99999",
    ],
)
def test_url_rejects_unsafe_credential_destinations(url):
    with pytest.raises(ValueError):
        normalize_url(url)


@pytest.mark.parametrize(
    ("status", "path", "error"),
    [
        (401, "bridge/samples", InvalidAuth),
        (400, "pairing/redeem", InvalidPairing),
        (302, "bridge/samples", BridgeError),
    ],
)
async def test_auth_and_redirects_are_not_followed(status, path, error):
    session = MagicMock()
    session.request.return_value.__aenter__ = AsyncMock(return_value=MagicMock(status=status))
    session.request.return_value.__aexit__ = AsyncMock(return_value=False)
    client = BridgeClient(session, "https://ems.example", "secret")
    with pytest.raises(error):
        await client.request("POST", path, {})
    kwargs = session.request.call_args.kwargs
    assert kwargs["allow_redirects"] is False
    assert kwargs["headers"] == {"Authorization": "Bearer secret"}
    assert kwargs["timeout"].total == 15

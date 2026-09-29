"""Small HTTPS client. Credentials never cross redirects or appear in errors."""

import json
from contextlib import suppress
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout


class BridgeError(Exception):
    """An EMS request failed without exposing its payload."""


class CannotConnect(BridgeError):
    """A bounded request could not reach EMS."""


class InvalidAuth(BridgeError):
    """A credential was revoked or expired."""


class InvalidPairing(BridgeError):
    """The pairing code is invalid, expired or already used."""


class MappingConflict(BridgeError):
    """The local mapping generation no longer matches EMS."""


def normalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Use the HTTPS origin of the EMS server")
    # Accessing port validates its range and rejects malformed URLs.
    _ = parsed.port
    return f"https://{parsed.netloc.lower()}"


class BridgeClient:
    def __init__(self, session: ClientSession, base_url: str, token: str | None = None):
        self.session = session
        self.base_url = normalize_url(base_url)
        self.token = token

    async def request(self, method: str, path: str, data=None) -> dict:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            async with self.session.request(
                method,
                self.base_url + "/api/v1/home-assistant/" + path,
                json=data,
                headers=headers,
                allow_redirects=False,
                timeout=ClientTimeout(total=15),
            ) as result:
                if result.status == 401:
                    raise InvalidAuth
                if result.status == 400 and path == "pairing/redeem":
                    raise InvalidPairing
                if result.status == 409:
                    raise MappingConflict
                if result.status >= 500 or result.status == 429:
                    raise CannotConnect
                if not 200 <= result.status < 300:
                    raise BridgeError
                raw = bytearray()
                async for chunk in result.content.iter_chunked(4096):
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise BridgeError
                response = json.loads(raw)
                if not isinstance(response, dict):
                    raise BridgeError
                return response
        except (ClientError, TimeoutError) as exc:
            raise CannotConnect from exc
        except (ValueError, UnicodeError) as exc:
            raise BridgeError from exc

    async def redeem(self, code, instance_id, instance_name):
        result = await self.request(
            "POST",
            "pairing/redeem",
            {
                "schema_version": 1,
                "code": code.strip(),
                "instance_id": instance_id,
                "instance_name": instance_name,
            },
        )
        if (
            result.get("schema_version") != 1
            or not isinstance(result.get("token"), str)
            or len(result["token"]) < 32
            or not isinstance(result.get("mapping_version"), int)
            or not isinstance(result.get("station_id"), str)
            or not isinstance(result.get("station_name"), str)
            or result.get("instance_id") != instance_id
        ):
            raise BridgeError
        self.token = result["token"]
        return result

    async def configure(self, config: dict):
        result = await self.request(
            "PUT",
            "bridge/mappings",
            {
                "schema_version": 1,
                "expected_version": config["mapping_version"],
                "consent": True,
                "occupancy_consent": config["occupancy_consent"],
                "insights_consent": config["insights_consent"],
                "mappings": [
                    {k: v for k, v in m.items() if k != "registry_id"} for m in config["mappings"]
                ],
            },
        )
        version = result.get("mapping_version")
        if type(version) is not int or version < 1:
            raise BridgeError
        return version

    async def send(self, version, samples):
        result = await self.request(
            "POST",
            "bridge/samples",
            {
                "schema_version": 1,
                "mapping_version": version,
                "samples": samples,
            },
        )
        if result.get("mapping_version") != version or type(result.get("accepted")) is not int:
            raise BridgeError
        return result

    async def disconnect(self):
        # An already revoked credential satisfies disconnect's postcondition.
        with suppress(InvalidAuth):
            await self.request("DELETE", "bridge")

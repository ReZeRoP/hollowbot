"""
3X-UI (Sanaei) panel API client.

Handles cookie/session auth, automatic re-login on 401/expired session,
retries with exponential backoff, and the core client-management endpoints:

    login()                    -> authenticate, store session cookie
    list_inbounds()            -> GET /panel/api/inbounds/list
    get_inbound(id)            -> GET /panel/api/inbounds/get/{id}
    add_client(...)            -> POST /panel/api/inbounds/addClient
    update_client(...)         -> POST /panel/api/inbounds/updateClient/{uuid}
    delete_client(...)         -> POST /panel/api/inbounds/{inboundId}/delClient/{uuid}
    reset_client_traffic(...)  -> POST /panel/api/inbounds/{inboundId}/resetClientTraffic/{email}
    get_client_traffic(email)  -> GET /panel/api/inbounds/getClientTraffics/{email}
    health()                   -> lightweight reachability check

NOTE: 3X-UI encodes the client list inside inbound.settings as a JSON *string*,
so add/update send `settings` as a JSON-encoded string. This client abstracts that.

The panel base_url should include any custom path prefix, e.g.
    https://panel.example.com:2053/secretpath
"""
from __future__ import annotations

import json
import uuid as uuidlib
from typing import Any

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.logger import get_logger
from app.panel.exceptions import (
    PanelAuthError,
    PanelRequestError,
    PanelUnavailableError,
)

log = get_logger(__name__)

_RETRY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(PanelUnavailableError),
    reraise=True,
)


class XUIClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int = 15,
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.verify_ssl = verify_ssl
        self._session: aiohttp.ClientSession | None = None
        self._authed = False

    # ------------------------------------------------------------------ #
    #  Session lifecycle
    # ------------------------------------------------------------------ #
    async def __aenter__(self) -> "XUIClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
            self._session = aiohttp.ClientSession(
                timeout=self.timeout, connector=connector
            )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------ #
    #  Auth
    # ------------------------------------------------------------------ #
    @retry(**_RETRY)
    async def login(self) -> None:
        await self._ensure_session()
        url = f"{self.base_url}/login"
        try:
            async with self._session.post(
                url, data={"username": self.username, "password": self.password}
            ) as resp:
                if resp.status != 200:
                    raise PanelAuthError(f"login HTTP {resp.status}")
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as e:
            raise PanelUnavailableError(str(e)) from e

        if not data or not data.get("success"):
            raise PanelAuthError(f"login rejected: {data}")
        self._authed = True
        log.info("Panel login OK: %s", self.base_url)

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Wrapper that (re)authenticates and parses the panel envelope."""
        await self._ensure_session()
        if not self._authed:
            await self.login()

        url = f"{self.base_url}{path}"
        try:
            async with self._session.request(method, url, **kwargs) as resp:
                # Session expired -> re-login once and retry
                if resp.status in (401, 403):
                    self._authed = False
                    await self.login()
                    async with self._session.request(method, url, **kwargs) as resp2:
                        return await self._parse(resp2)
                return await self._parse(resp)
        except aiohttp.ClientError as e:
            raise PanelUnavailableError(str(e)) from e

    @staticmethod
    async def _parse(resp: aiohttp.ClientResponse) -> dict[str, Any]:
        try:
            data = await resp.json(content_type=None)
        except Exception as e:  # noqa: BLE001
            raise PanelRequestError(f"invalid JSON (HTTP {resp.status})") from e
        if not isinstance(data, dict) or not data.get("success", False):
            msg = (data or {}).get("msg", "unknown panel error")
            raise PanelRequestError(msg)
        return data

    # ------------------------------------------------------------------ #
    #  Inbounds
    # ------------------------------------------------------------------ #
    @retry(**_RETRY)
    async def list_inbounds(self) -> list[dict]:
        data = await self._request("GET", "/panel/api/inbounds/list")
        return data.get("obj", [])

    @retry(**_RETRY)
    async def get_inbound(self, inbound_id: int) -> dict:
        data = await self._request("GET", f"/panel/api/inbounds/get/{inbound_id}")
        return data.get("obj", {})

    # ------------------------------------------------------------------ #
    #  Clients
    # ------------------------------------------------------------------ #
    @retry(**_RETRY)
    async def add_client(
        self,
        inbound_id: int,
        *,
        email: str,
        client_uuid: str | None = None,
        total_gb: float = 0.0,
        expiry_ts_ms: int = 0,
        sub_id: str | None = None,
        flow: str = "",
        limit_ip: int = 0,
        enable: bool = True,
    ) -> str:
        """
        Create a client on an inbound. Returns the client's uuid.

        `total_gb`   – 0 means unlimited
        `expiry_ts_ms` – epoch millis; 0 means never expires
        """
        client_uuid = client_uuid or str(uuidlib.uuid4())
        client = {
            "id": client_uuid,
            "email": email,
            "enable": enable,
            "totalGB": int(total_gb * 1024**3),
            "expiryTime": int(expiry_ts_ms),
            "flow": flow,
            "limitIp": limit_ip,
            "subId": sub_id or email,
            "tgId": "",
            "reset": 0,
        }
        payload = {"id": inbound_id, "settings": json.dumps({"clients": [client]})}
        await self._request("POST", "/panel/api/inbounds/addClient", json=payload)
        log.info("Added client %s to inbound %s", email, inbound_id)
        return client_uuid

    @retry(**_RETRY)
    async def update_client(
        self,
        inbound_id: int,
        client_uuid: str,
        *,
        email: str,
        total_gb: float,
        expiry_ts_ms: int,
        sub_id: str | None = None,
        enable: bool = True,
        flow: str = "",
    ) -> None:
        """Edit an existing client's volume/time/enable state."""
        client = {
            "id": client_uuid,
            "email": email,
            "enable": enable,
            "totalGB": int(total_gb * 1024**3),
            "expiryTime": int(expiry_ts_ms),
            "flow": flow,
            "subId": sub_id or email,
            "tgId": "",
            "reset": 0,
        }
        payload = {"id": inbound_id, "settings": json.dumps({"clients": [client]})}
        await self._request(
            "POST", f"/panel/api/inbounds/updateClient/{client_uuid}", json=payload
        )
        log.info("Updated client %s on inbound %s", email, inbound_id)

    @retry(**_RETRY)
    async def delete_client(self, inbound_id: int, client_uuid: str) -> None:
        await self._request(
            "POST", f"/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}"
        )
        log.info("Deleted client %s from inbound %s", client_uuid, inbound_id)

    @retry(**_RETRY)
    async def reset_client_traffic(self, inbound_id: int, email: str) -> None:
        await self._request(
            "POST", f"/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}"
        )
        log.info("Reset traffic for %s on inbound %s", email, inbound_id)

    @retry(**_RETRY)
    async def get_client_traffic(self, email: str) -> dict | None:
        """Return {up, down, total, expiryTime, enable, ...} or None if not found."""
        data = await self._request(
            "GET", f"/panel/api/inbounds/getClientTraffics/{email}"
        )
        return data.get("obj")

    # ------------------------------------------------------------------ #
    #  Health
    # ------------------------------------------------------------------ #
    async def health(self) -> bool:
        """Cheap reachability probe used by the scheduler."""
        try:
            await self._ensure_session()
            async with self._session.get(f"{self.base_url}/") as resp:
                return resp.status < 500
        except aiohttp.ClientError:
            return False

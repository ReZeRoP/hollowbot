"""
Build subscription links and individual config URIs from 3X-UI inbound data.

3X-UI has no single "give me the sub link" endpoint unless the Subscription
Server is enabled. This module supports BOTH strategies:

  1) Subscription Server enabled  -> return `{sub_base_url}/{sub_id}`
  2) Manually build per-protocol URIs (VLESS / VMess / Trojan / Shadowsocks)
     from the inbound's streamSettings (reality/tls, sni, pbk, sid, fp, ...).

The individual URIs can be concatenated + base64-encoded to form a self-hosted
subscription payload if you don't use the panel's sub server.
"""
from __future__ import annotations

import base64
import json
import urllib.parse
from typing import Any


# --------------------------------------------------------------------------- #
#  Helpers to dig fields out of the inbound streamSettings blob
# --------------------------------------------------------------------------- #
def _load(obj: Any) -> dict:
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            return {}
    return obj or {}


def _stream_params(stream: dict) -> dict[str, str]:
    """Extract the query params common to VLESS/Trojan links."""
    p: dict[str, str] = {}
    network = stream.get("network", "tcp")
    security = stream.get("security", "none")
    p["type"] = network
    p["security"] = security

    if network == "ws":
        ws = stream.get("wsSettings", {})
        p["path"] = ws.get("path", "/")
        host = (ws.get("headers") or {}).get("Host")
        if host:
            p["host"] = host
    elif network == "grpc":
        grpc = stream.get("grpcSettings", {})
        p["serviceName"] = grpc.get("serviceName", "")

    if security == "reality":
        r = stream.get("realitySettings", {})
        settings = r.get("settings", {})
        p["pbk"] = settings.get("publicKey", "")
        p["fp"] = settings.get("fingerprint", "chrome")
        snis = r.get("serverNames") or [""]
        p["sni"] = snis[0]
        sids = r.get("shortIds") or [""]
        p["sid"] = sids[0]
        spx = settings.get("spiderX")
        if spx:
            p["spx"] = spx
    elif security == "tls":
        t = stream.get("tlsSettings", {})
        p["sni"] = t.get("serverName", "")
        p["fp"] = (t.get("settings") or {}).get("fingerprint", "chrome")

    return {k: v for k, v in p.items() if v not in ("", None)}


def _qs(params: dict[str, str]) -> str:
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


# --------------------------------------------------------------------------- #
#  Per-protocol builders
# --------------------------------------------------------------------------- #
def build_vless(host: str, port: int, client_uuid: str, stream: dict, remark: str) -> str:
    params = _stream_params(stream)
    flow = stream.get("_flow", "")
    if flow:
        params["flow"] = flow
    query = _qs(params)
    frag = urllib.parse.quote(remark)
    return f"vless://{client_uuid}@{host}:{port}?{query}#{frag}"


def build_trojan(host: str, port: int, password: str, stream: dict, remark: str) -> str:
    params = _stream_params(stream)
    query = _qs(params)
    frag = urllib.parse.quote(remark)
    return f"trojan://{password}@{host}:{port}?{query}#{frag}"


def build_vmess(host: str, port: int, client_uuid: str, stream: dict, remark: str) -> str:
    net = stream.get("network", "tcp")
    tls = stream.get("security", "none")
    ws = stream.get("wsSettings", {})
    conf = {
        "v": "2",
        "ps": remark,
        "add": host,
        "port": str(port),
        "id": client_uuid,
        "aid": "0",
        "scy": "auto",
        "net": net,
        "type": "none",
        "host": (ws.get("headers") or {}).get("Host", ""),
        "path": ws.get("path", ""),
        "tls": "tls" if tls == "tls" else "",
        "sni": _stream_params(stream).get("sni", ""),
    }
    raw = base64.b64encode(json.dumps(conf).encode()).decode()
    return f"vmess://{raw}"


def build_shadowsocks(host: str, port: int, password: str, method: str, remark: str) -> str:
    userinfo = base64.urlsafe_b64encode(f"{method}:{password}".encode()).decode().rstrip("=")
    frag = urllib.parse.quote(remark)
    return f"ss://{userinfo}@{host}:{port}#{frag}"


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #
def build_configs_for_inbound(
    *,
    host: str,
    inbound: dict,
    client_uuid: str,
    client_password: str,
    remark: str,
) -> list[str]:
    """
    Given a raw inbound dict (from the panel) + a client's credentials,
    return a list of individual config URIs (usually one per inbound).
    """
    protocol = inbound.get("protocol", "vless")
    port = inbound.get("port")
    stream = _load(inbound.get("streamSettings"))

    # carry flow into stream for vless
    settings = _load(inbound.get("settings"))
    flow = ""
    for c in settings.get("clients", []):
        if c.get("id") == client_uuid or c.get("password") == client_password:
            flow = c.get("flow", "")
    stream["_flow"] = flow

    if protocol == "vless":
        return [build_vless(host, port, client_uuid, stream, remark)]
    if protocol == "trojan":
        return [build_trojan(host, port, client_password, stream, remark)]
    if protocol == "vmess":
        return [build_vmess(host, port, client_uuid, stream, remark)]
    if protocol == "shadowsocks":
        method = settings.get("method", "aes-256-gcm")
        return [build_shadowsocks(host, port, client_password, method, remark)]
    return []


def build_subscription_link(sub_base_url: str, sub_id: str) -> str:
    """Panel Subscription Server link, e.g. https://host:2096/sub/<subId>."""
    return f"{sub_base_url.rstrip('/')}/{sub_id}"


def build_selfhosted_subscription(configs: list[str]) -> str:
    """Base64 payload of joined configs (import as a 'subscription' in clients)."""
    joined = "\n".join(configs)
    return base64.b64encode(joined.encode()).decode()

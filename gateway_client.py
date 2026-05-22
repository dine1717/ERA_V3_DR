"""Thin wrapper around llm_gatewayV3's HTTP API.

Every LLM call in agent6 routes through this module. We never import provider
SDKs directly; the gateway at http://localhost:8101 is the only LLM substrate.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx

GATEWAY_URL = os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")
DEFAULT_TIMEOUT = 600.0


def ensure_gateway() -> None:
    """Probe the gateway. Raises with a clear hint if it isn't running."""
    try:
        r = httpx.get(f"{GATEWAY_URL}/v1/routers", timeout=5)
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(
            f"LLM Gateway V3 is not reachable at {GATEWAY_URL}. "
            f"Start it with:  cd llm_gatewayV3 && ./run.sh\n"
            f"Underlying error: {e}"
        ) from e


def chat(
    *,
    prompt: Optional[str] = None,
    messages: Optional[list[dict[str, Any]]] = None,
    system: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Optional[str | dict[str, Any]] = None,
    response_format: Optional[dict[str, Any]] = None,
    auto_route: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "prompt": prompt,
        "messages": messages,
        "system": system,
        "provider": provider,
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        "tools": tools,
        "tool_choice": tool_choice,
        "response_format": response_format,
        "auto_route": auto_route,
    }
    body = {k: v for k, v in body.items() if v is not None}
    r = httpx.post(f"{GATEWAY_URL}/v1/chat", json=body, timeout=timeout)
    if r.status_code >= 400:
        # Surface the gateway's error body — it carries the real provider error
        # in `attempted[]` and a human-readable `detail` field. Without this we
        # only see "502 Bad Gateway" with no idea which provider failed why.
        try:
            err_json = r.json()
        except Exception:
            err_json = {"raw": r.text[:1000]}
        raise RuntimeError(
            f"Gateway HTTP {r.status_code} on /v1/chat\n"
            f"  request: provider={body.get('provider')} model={body.get('model')} "
            f"auto_route={body.get('auto_route')}\n"
            f"  response: {json.dumps(err_json, indent=2)[:2000]}"
        )
    return r.json()


def structured(
    *,
    prompt: str,
    schema: dict[str, Any],
    system: Optional[str] = None,
    provider: Optional[str] = None,
    auto_route: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Convenience: call with response_format={'type': 'json_schema', ...}.
    Returns the parsed dict (gateway already validates server-side)."""
    resp = chat(
        prompt=prompt,
        system=system,
        provider=provider,
        auto_route=auto_route,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_schema", "schema": schema, "name": "out"},
    )
    parsed = resp.get("parsed")
    if parsed is None:
        # Some providers return JSON only in text. Try to parse leniently.
        import json
        text = resp.get("text", "") or ""
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
    return {"parsed": parsed, "raw": resp}

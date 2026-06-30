"""LaMetric transport: local device notifications + cloud DIY app frames.

Stdlib only (urllib). Both methods are best-effort and never raise on network
errors — a hook must not break the Claude Code session because a clock is offline.
"""

from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import Config

# LaMetric self-signs its HTTPS cert on the device; the cloud endpoint is fine.
_INSECURE_CTX = ssl.create_default_context()
_INSECURE_CTX.check_hostname = False
_INSECURE_CTX.verify_mode = ssl.CERT_NONE


@dataclass
class PushResult:
    target: str          # "local" | "cloud"
    ok: bool
    status: int | None = None
    error: str | None = None

    def __str__(self) -> str:
        if self.ok:
            return f"{self.target}: ok ({self.status})"
        return f"{self.target}: FAILED ({self.error})"


def _post(url: str, body: dict, headers: dict, timeout: float, insecure: bool) -> PushResult:
    target = "local" if "/device/notifications" in url else "cloud"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    ctx = _INSECURE_CTX if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return PushResult(target, ok=200 <= resp.status < 300, status=resp.status)
    except urllib.error.HTTPError as e:
        return PushResult(target, ok=False, status=e.code, error=f"HTTP {e.code}: {e.reason}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return PushResult(target, ok=False, error=str(e))


class LaMetricClient:
    def __init__(self, config: Config, timeout: float = 4.0):
        self.config = config
        self.timeout = timeout

    # --- Local device: transient notification popup ----------------------
    def notify_local(
        self,
        frames: list[dict],
        *,
        priority: str = "info",     # "info" | "warning" | "critical"
        icon_type: str = "none",    # "none" | "info" | "alert"
        sound: str | None = None,   # e.g. "notification", "cat", "knock-knock"
        cycles: int = 1,            # 0 = stay until dismissed
    ) -> PushResult:
        local = self.config.local
        if not local.configured:
            return PushResult("local", ok=False, error="not configured")

        model: dict = {"frames": frames, "cycles": cycles}
        if sound:
            model["sound"] = {"category": "notifications", "id": sound}

        token = base64.b64encode(f"dev:{local.api_key}".encode()).decode()
        url = f"http://{local.ip}:8080/api/v2/device/notifications"
        body = {"priority": priority, "icon_type": icon_type, "model": model}
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Basic {token}",
        }
        return _post(url, body, headers, self.timeout, insecure=False)

    # --- Cloud DIY app: persistent status frames -------------------------
    def push_cloud(self, frames: list[dict]) -> PushResult:
        cloud = self.config.cloud
        if not cloud.configured:
            return PushResult("cloud", ok=False, error="not configured")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Access-Token": cloud.access_token,
        }
        return _post(cloud.push_url, {"frames": frames}, headers, self.timeout, insecure=False)

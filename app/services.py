"""App-lifetime resources and signed opaque browser fairness."""

import asyncio
import hashlib
import hmac
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.classifier import Result
from app.config import Settings
from app.lifecycle import AuditStore, Capacity


class Detector(Protocol):
    """Classifier interface shared by real calls and injected operational tests."""

    public_key: str | None

    async def classify(
        self, message: str, request_id: str, *, langfuse_public_key: str | None = None
    ) -> Result: ...
    async def close(self) -> None: ...


@dataclass
class Services:
    """Bounded resources for the supported single-worker topology."""

    settings: Settings
    database: AuditStore
    detector: Detector | None
    diagnostics: Counter[str] = field(default_factory=Counter)
    cleanups: set[asyncio.Task[None]] = field(default_factory=set)
    http_capacity: Capacity = field(init=False)
    model_active: int = 0
    last_capacity_log: float = 0

    def __post_init__(self) -> None:
        self.http_capacity = Capacity(
            inflight=self.settings.http_max_inflight,
            window_limit=self.settings.http_window_limit,
        )

    def session(self, cookie: str | None) -> tuple[str, str]:
        """Validate or renew the timed cookie and derive a separate persistent quota key."""
        key = self.settings.session_signing_key.get_secret_value()
        serializer = URLSafeTimedSerializer(key, salt="sarcasm-session-v1")
        identity = None
        if cookie:
            try:
                identity = serializer.loads(cookie, max_age=self.settings.session_ttl_seconds)
            except BadSignature:
                identity = None
        if not isinstance(identity, str) or len(identity) != 32:
            identity = uuid4().hex
        quota_key = hmac.new(
            key.encode(), ("quota:" + identity).encode(), hashlib.sha256
        ).hexdigest()
        return serializer.dumps(identity), quota_key

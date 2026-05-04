from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from psycopg import AsyncConnection


ETL_STATUS_IDENTIFIER = "etl.status"


@dataclass
class EtlStatus:
    state: str = "not_started"
    message: str = ""
    current_action: str | None = None
    completed_actions: list[str] = field(default_factory=list)
    failed_action: str | None = None
    finished: bool = False
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EtlStatusStore:
    """Loads and persists the ETL status object stored in etl_values."""

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn
        self.status = EtlStatus()

    async def load(self) -> EtlStatus:
        row = await (await self._conn.execute(
            "SELECT data FROM etl_values WHERE identifier = %s",
            (ETL_STATUS_IDENTIFIER,),
        )).fetchone()
        if not row:
            self.status = EtlStatus()
            return self.status

        try:
            raw = json.loads(row["data"])
        except json.JSONDecodeError:
            self.status = EtlStatus(state="unknown", message=row["data"])
            return self.status

        if not isinstance(raw, dict):
            self.status = EtlStatus(state="unknown", message=str(raw))
            return self.status

        self.status = EtlStatus(
            state=str(raw.get("state", "not_started")),
            message=str(raw.get("message", "")),
            current_action=raw.get("current_action"),
            completed_actions=list(raw.get("completed_actions", [])),
            failed_action=raw.get("failed_action"),
            finished=bool(raw.get("finished", False)),
            timestamp_utc=str(raw.get("timestamp_utc", datetime.now(timezone.utc).isoformat())),
        )
        return self.status

    async def update(self, **changes: Any) -> EtlStatus:
        for key, value in changes.items():
            if not hasattr(self.status, key):
                raise AttributeError(f"EtlStatus has no field named '{key}'")
            setattr(self.status, key, value)
        self.status.timestamp_utc = datetime.now(timezone.utc).isoformat()
        await self.save()
        return self.status

    async def mark_action_started(self, action_name: str) -> EtlStatus:
        return await self.update(
            state="running",
            message=f"Running action: {action_name}",
            current_action=action_name,
            failed_action=None,
            finished=False,
        )

    async def mark_action_finished(self, action_name: str) -> EtlStatus:
        completed = list(self.status.completed_actions)
        if action_name not in completed:
            completed.append(action_name)
        return await self.update(
            state="running",
            message=f"Finished action: {action_name}",
            current_action=None,
            completed_actions=completed,
            failed_action=None,
            finished=False,
        )

    async def mark_finished(self) -> EtlStatus:
        return await self.update(
            state="finished",
            message="ETL pipeline finished successfully.",
            current_action=None,
            failed_action=None,
            finished=True,
        )

    async def mark_failed(self, action_name: str | None, error: BaseException) -> EtlStatus:
        return await self.update(
            state="failed",
            message=str(error),
            current_action=None,
            failed_action=action_name,
            finished=False,
        )

    async def save(self) -> None:
        await self._conn.execute(
            """
            INSERT INTO etl_values (identifier, data, updated)
            VALUES (%s, %s, NOW())
            ON CONFLICT (identifier)
            DO UPDATE SET data = EXCLUDED.data, updated = NOW()
            """,
            (ETL_STATUS_IDENTIFIER, json.dumps(asdict(self.status), indent=2)),
        )
        await self._conn.commit()

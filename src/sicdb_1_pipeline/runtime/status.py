from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from psycopg import AsyncConnection


ETL_STATUS_IDENTIFIER = "etl.status"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EtlStatus:
    state: str = "not_started"
    message: str = ""
    current_action: str | None = None

    # Stores per-action state, for example:
    # {
    #   "name": "load_customers",
    #   "progress": 100,
    #   "version": "v1",
    #   "completed": True,
    #   "timestamp_utc": "..."
    # }
    action_states: list[dict[str, Any]] = field(default_factory=list)

    failed_action: str | None = None
    finished: bool = False
    timestamp_utc: str = field(default_factory=utc_now_iso)


class EtlStatusStore:
    """Loads and persists the ETL status object stored in etl_values."""

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn
        self.status = EtlStatus()

    async def load(self) -> EtlStatus:
        row = await (
            await self._conn.execute(
                "SELECT data FROM etl_values WHERE identifier = %s",
                (ETL_STATUS_IDENTIFIER,),
            )
        ).fetchone()

        if not row:
            self.status = EtlStatus()
            return self.status

        data = row["data"]

        try:
            raw = json.loads(data)
        except json.JSONDecodeError:
            self.status = EtlStatus(state="unknown", message=str(data))
            return self.status

        if not isinstance(raw, dict):
            self.status = EtlStatus(state="unknown", message=str(raw))
            return self.status

        # Backward compatibility:
        # If old stored data still has "completed_actions", migrate it into "action_states".
        raw_action_states = raw.get("action_states", raw.get("completed_actions", []))

        if not isinstance(raw_action_states, list):
            raw_action_states = []

        self.status = EtlStatus(
            state=str(raw.get("state", "not_started")),
            message=str(raw.get("message", "")),
            current_action=raw.get("current_action"),
            action_states=list(raw_action_states),
            failed_action=raw.get("failed_action"),
            finished=bool(raw.get("finished", False)),
            timestamp_utc=str(raw.get("timestamp_utc", utc_now_iso())),
        )

        return self.status

    async def update(self, **changes: Any) -> EtlStatus:
        for key, value in changes.items():
            if not hasattr(self.status, key):
                raise AttributeError(f"EtlStatus has no field named '{key}'")
            setattr(self.status, key, value)

        self.status.timestamp_utc = utc_now_iso()
        await self.save()
        return self.status

    async def get_action_status(self, name: str) -> dict[str, Any]:
        for action in self.status.action_states:
            if action.get("name") == name:
                return action

        return {
            "name": name,
            "progress": 0,
            "version": None,
            "completed": False,
            "timestamp_utc": None,
        }

    async def update_action(
        self,
        name: str,
        progress: int,
        version: str | None,
        completed: bool,
    ) -> EtlStatus:
        action_states = list(self.status.action_states)

        for action in action_states:
            if action.get("name") == name:
                action["progress"] = progress
                action["version"] = version
                action["completed"] = completed
                action["timestamp_utc"] = utc_now_iso()
                break
        else:
            action_states.append(
                {
                    "name": name,
                    "progress": progress,
                    "version": version,
                    "completed": completed,
                    "timestamp_utc": utc_now_iso(),
                }
            )

        return await self.update(action_states=action_states)

    async def mark_action_started(self, action_name: str) -> EtlStatus:
        await self.update_action(
            name=action_name,
            progress=0,
            version=None,
            completed=False,
        )

        return await self.update(
            state="running",
            message=f"Running action: {action_name}",
            current_action=action_name,
            failed_action=None,
            finished=False,
        )

    async def mark_action_finished(
        self,
        action_name: str,
        version: str | None = None,
    ) -> EtlStatus:
        await self.update_action(
            name=action_name,
            progress=100,
            version=version,
            completed=True,
        )

        return await self.update(
            state="running",
            message=f"Finished action: {action_name}",
            current_action=None,
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

    async def mark_failed(
        self,
        action_name: str | None,
        error: BaseException,
    ) -> EtlStatus:
        if action_name is not None:
            current = await self.get_action_status(action_name)

            await self.update_action(
                name=action_name,
                progress=int(current.get("progress", 0)),
                version=current.get("version"),
                completed=False,
            )

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
            (
                ETL_STATUS_IDENTIFIER,
                json.dumps(asdict(self.status), indent=2),
            ),
        )
        await self._conn.commit()
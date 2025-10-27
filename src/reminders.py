"""Reminder scheduling and dispatch utilities for the MCP server."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

try:  # Optional dependency: required only when PostgreSQL is used.
    import psycopg  # type: ignore[import-not-found]
    from psycopg.rows import dict_row  # type: ignore[import-not-found]
    from psycopg.types.json import Jsonb  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - keep SQLite-only deployments working
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    Jsonb = None  # type: ignore[assignment]

LOGGER = logging.getLogger("mcp.reminders")
UTC = timezone.utc


def _to_utc_iso(value: datetime) -> str:
    """Return an ISO-8601 string in UTC with a trailing Z."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _ensure_datetime(value: datetime | str | None) -> datetime | None:
    """Normalize datetime values from SQLite (str) or Postgres (datetime)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class ReminderPayloadModel(BaseModel):
    """Channel-specific payload required by downstream automation (e.g., n8n)."""

    to: str = Field(..., description="Recipient identifier for the downstream channel.")
    message: str = Field(..., description="Full message payload for the channel.")

    model_config = ConfigDict(extra="forbid")

    @field_validator("to", mode="before")
    @classmethod
    def _strip_to(cls, value: Any) -> str:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("payload.to must be provided.")
        return str(value)

    @field_validator("message", mode="before")
    @classmethod
    def _strip_message(cls, value: Any) -> str:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("payload.message must be provided.")
        return str(value)


class ReminderRequestModel(BaseModel):
    """Validated reminder request emitted by LangChain / MCP tooling."""

    title: str = Field(..., description="Human friendly name for the reminder.")
    message: str = Field(..., description="Context message for internal use.")
    target_time: datetime = Field(
        ..., alias="target_time_iso", description="When the reminder should fire."
    )
    payload: ReminderPayloadModel

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("title", "message", mode="before")
    @classmethod
    def _strip_text(cls, value: Any) -> str:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("Field must not be empty.")
        return str(value)

    @field_validator("target_time")
    @classmethod
    def _ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("target_time_iso must include timezone information.")
        return value.astimezone(UTC)


@dataclass(slots=True)
class ReminderRecord:
    """Runtime representation of reminders sourced from persistent storage."""

    id: str
    title: str
    message: str
    target_time: datetime
    payload: dict[str, Any]
    webhook_url: str
    status: str
    attempts: int
    created_at: datetime
    updated_at: datetime
    earliest_run: datetime
    last_error: str | None = None
    sent_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the reminder for API/tool responses."""
        return {
            "reminder_id": self.id,
            "title": self.title,
            "message": self.message,
            "target_time_iso": _to_utc_iso(self.target_time),
            "payload": self.payload,
            "webhook_url": self.webhook_url,
            "status": self.status,
            "attempts": self.attempts,
            "created_at": _to_utc_iso(self.created_at),
            "updated_at": _to_utc_iso(self.updated_at),
            "earliest_run": _to_utc_iso(self.earliest_run),
            "sent_at": _to_utc_iso(self.sent_at) if self.sent_at else None,
            "last_error": self.last_error,
        }


class ReminderRepository:
    """Persistence layer for reminders backed by SQLite or PostgreSQL."""

    def __init__(
        self,
        *,
        sqlite_path: Path | None = None,
        database_url: str | None = None,
    ) -> None:
        if database_url and sqlite_path:
            raise ValueError("Provide only one storage backend: database_url or sqlite_path.")
        if database_url:
            if psycopg is None or dict_row is None or Jsonb is None:  # pragma: no cover - runtime guard
                raise RuntimeError(
                    "PostgreSQL support requires the 'psycopg' package. Install it via "
                    "`pip install psycopg[binary]`."
                )
            self._mode = "postgres"
            self._dsn = database_url
            self._initialize_postgres()
        else:
            if sqlite_path is None:
                raise ValueError("sqlite_path must be provided when DATABASE_URL is not set.")
            self._mode = "sqlite"
            self._db_path = Path(sqlite_path)
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_sqlite()

    # -- Initialization -------------------------------------------------

    def _initialize_sqlite(self) -> None:
        with self._connect_sqlite() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    webhook_url TEXT NOT NULL,
                    target_time TEXT NOT NULL,
                    earliest_run TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sent_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reminders_status_time
                ON reminders (status, earliest_run)
                """
            )

    def _initialize_postgres(self) -> None:
        assert psycopg is not None
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reminders (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        payload_json JSONB NOT NULL,
                        webhook_url TEXT NOT NULL,
                        target_time TIMESTAMPTZ NOT NULL,
                        earliest_run TIMESTAMPTZ NOT NULL,
                        status TEXT NOT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        last_error TEXT,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        sent_at TIMESTAMPTZ
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_reminders_status_time
                    ON reminders (status, earliest_run)
                    """
                )

    # -- Connections ----------------------------------------------------

    def _connect_sqlite(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_postgres(self):
        assert psycopg is not None and dict_row is not None
        return psycopg.connect(self._dsn, row_factory=dict_row)

    # -- CRUD -----------------------------------------------------------

    def create(self, request: ReminderRequestModel, webhook_url: str, *, now: datetime) -> ReminderRecord:
        reminder_id = uuid4().hex
        if self._mode == "postgres":
            payload = request.payload.model_dump()
            with self._connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO reminders (
                            id, title, message, payload_json, webhook_url,
                            target_time, earliest_run, status, attempts,
                            last_error, created_at, updated_at, sent_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, 'pending', 0,
                            NULL, %s, %s, NULL
                        )
                        """,
                        (
                            reminder_id,
                            request.title,
                            request.message,
                            Jsonb(payload),
                            webhook_url,
                            request.target_time,
                            request.target_time,
                            now,
                            now,
                        ),
                    )
        else:
            payload_json = json.dumps(request.payload.model_dump())
            target_iso = _to_utc_iso(request.target_time)
            now_iso = _to_utc_iso(now)
            with self._connect_sqlite() as conn:
                conn.execute(
                    """
                    INSERT INTO reminders (
                        id, title, message, payload_json, webhook_url,
                        target_time, earliest_run, status, attempts,
                        last_error, created_at, updated_at, sent_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, NULL, ?, ?, NULL)
                    """,
                    (
                        reminder_id,
                        request.title,
                        request.message,
                        payload_json,
                        webhook_url,
                        target_iso,
                        target_iso,
                        now_iso,
                        now_iso,
                    ),
                )
        record = self.get(reminder_id)
        if record is None:  # pragma: no cover - defensive guard
            raise RuntimeError("Reminder creation failed unexpectedly.")
        return record

    def get(self, reminder_id: str) -> ReminderRecord | None:
        if self._mode == "postgres":
            with self._connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM reminders WHERE id = %s", (reminder_id,))
                    row = cur.fetchone()
        else:
            with self._connect_sqlite() as conn:
                row = conn.execute(
                    "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
                ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_reminders(self, *, status: str | None = None, limit: int = 20) -> list[ReminderRecord]:
        limit = max(1, min(limit, 1000))
        if self._mode == "postgres":
            where = ""
            params: list[Any] = []
            if status:
                where = "WHERE status = %s"
                params.append(status)
            params.append(limit)
            with self._connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT * FROM reminders
                        {where}
                        ORDER BY earliest_run ASC
                        LIMIT %s
                        """,
                        params,
                    )
                    rows = cur.fetchall()
        else:
            query = "SELECT * FROM reminders"
            params = []
            if status:
                query += " WHERE status = ?"
                params.append(status)
            query += " ORDER BY earliest_run ASC LIMIT ?"
            params.append(limit)
            with self._connect_sqlite() as conn:
                rows = conn.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def acquire_due(self, *, now: datetime, limit: int) -> list[ReminderRecord]:
        limit = max(1, limit)
        if self._mode == "postgres":
            with self._connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM reminders
                        WHERE status = 'pending' AND earliest_run <= %s
                        ORDER BY earliest_run ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                        """,
                        (now, limit),
                    )
                    rows = cur.fetchall()
                    ids = [row["id"] for row in rows]
                    if ids:
                        cur.executemany(
                            "UPDATE reminders SET status = 'dispatching', updated_at = %s WHERE id = %s",
                            [(now, reminder_id) for reminder_id in ids],
                        )
        else:
            iso_now = _to_utc_iso(now)
            with self._connect_sqlite() as conn:
                conn.execute("BEGIN IMMEDIATE")
                rows = conn.execute(
                    """
                    SELECT * FROM reminders
                    WHERE status = 'pending' AND earliest_run <= ?
                    ORDER BY earliest_run ASC
                    LIMIT ?
                    """,
                    (iso_now, limit),
                ).fetchall()
                ids = [row["id"] for row in rows]
                if ids:
                    conn.executemany(
                        "UPDATE reminders SET status = 'dispatching', updated_at = ? WHERE id = ?",
                        [(iso_now, reminder_id) for reminder_id in ids],
                    )
                conn.commit()
        return [self._row_to_record(row) for row in rows]

    def mark_sent(self, reminder_id: str, *, sent_at: datetime) -> None:
        if self._mode == "postgres":
            with self._connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE reminders
                        SET status = 'sent', sent_at = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (sent_at, sent_at, reminder_id),
                    )
        else:
            iso_now = _to_utc_iso(sent_at)
            with self._connect_sqlite() as conn:
                conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'sent', sent_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (iso_now, iso_now, reminder_id),
                )

    def record_failure(
        self,
        reminder_id: str,
        *,
        attempts: int,
        next_attempt: datetime,
        error: str,
        updated_at: datetime,
    ) -> None:
        if self._mode == "postgres":
            with self._connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE reminders
                        SET status = 'pending',
                            earliest_run = %s,
                            attempts = %s,
                            last_error = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (next_attempt, attempts, error[:512], updated_at, reminder_id),
                    )
        else:
            iso_next = _to_utc_iso(next_attempt)
            iso_now = _to_utc_iso(updated_at)
            with self._connect_sqlite() as conn:
                conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'pending',
                        earliest_run = ?,
                        attempts = ?,
                        last_error = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (iso_next, attempts, error[:512], iso_now, reminder_id),
                )

    def cancel(self, reminder_id: str, *, cancelled_at: datetime) -> bool:
        if self._mode == "postgres":
            with self._connect_postgres() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE reminders
                        SET status = 'cancelled', updated_at = %s, last_error = NULL
                        WHERE id = %s AND status IN ('pending', 'dispatching')
                        """,
                        (cancelled_at, reminder_id),
                    )
                    return cur.rowcount > 0
        else:
            iso_now = _to_utc_iso(cancelled_at)
            with self._connect_sqlite() as conn:
                cursor = conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'cancelled', updated_at = ?, last_error = NULL
                    WHERE id = ? AND status IN ('pending', 'dispatching')
                    """,
                    (iso_now, reminder_id),
                )
                return cursor.rowcount > 0

    # -- Helpers --------------------------------------------------------

    def _row_to_record(self, row: Mapping[str, Any]) -> ReminderRecord:
        payload_raw = row["payload_json"]
        if isinstance(payload_raw, str):
            payload = json.loads(payload_raw)
        else:
            payload = dict(payload_raw)

        target_time = _ensure_datetime(row["target_time"])
        earliest_run = _ensure_datetime(row["earliest_run"])
        created_at = _ensure_datetime(row["created_at"])
        updated_at = _ensure_datetime(row["updated_at"])
        sent_at = _ensure_datetime(row.get("sent_at"))

        if target_time is None or earliest_run is None or created_at is None or updated_at is None:
            raise ValueError("Reminder record is missing required timestamps.")

        return ReminderRecord(
            id=row["id"],
            title=row["title"],
            message=row["message"],
            target_time=target_time,
            payload=payload,
            webhook_url=row["webhook_url"],
            status=row["status"],
            attempts=int(row["attempts"]),
            last_error=row["last_error"],
            created_at=created_at,
            updated_at=updated_at,
            earliest_run=earliest_run,
            sent_at=sent_at,
        )


class ReminderDispatcher:
    """Background worker that polls for due reminders and delivers them."""

    def __init__(
        self,
        repository: ReminderRepository,
        *,
        poll_interval: float = 30.0,
        batch_size: int = 10,
        http_timeout: float = 10.0,
        retry_base_seconds: float = 30.0,
        retry_max_seconds: float = 600.0,
    ) -> None:
        self._repository = repository
        self._poll_interval = max(1.0, poll_interval)
        self._batch_size = max(1, batch_size)
        self._http_timeout = max(1.0, http_timeout)
        self._retry_base = max(1.0, retry_base_seconds)
        self._retry_max = max(self._retry_base, retry_max_seconds)
        self._starter_lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def ensure_running(self) -> None:
        async with self._starter_lock:
            if self._task and not self._task.done():
                return
            self._stop_event.clear()
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run(), name="reminder-dispatcher")
            LOGGER.info(
                "Reminder dispatcher started (poll_interval=%ss, batch_size=%s)",
                self._poll_interval,
                self._batch_size,
            )

    async def shutdown(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:  # pragma: no cover - expected on shutdown
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                while not self._stop_event.is_set():
                    now = datetime.now(UTC)
                    reminders = self._repository.acquire_due(now=now, limit=self._batch_size)
                    if not reminders:
                        await asyncio.sleep(self._poll_interval)
                        continue
                    for reminder in reminders:
                        await self._process_reminder(client, reminder)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Reminder dispatcher stopped due to error: %s", exc)
        finally:
            LOGGER.debug("Reminder dispatcher stopped.")

    async def _process_reminder(self, client: httpx.AsyncClient, reminder: ReminderRecord) -> None:
        try:
            await self._dispatch(client, reminder)
        except Exception as exc:  # noqa: BLE001 - surface delivery errors
            LOGGER.warning("Reminder %s delivery failed: %s", reminder.id, exc)
            now = datetime.now(UTC)
            attempts = reminder.attempts + 1
            delay = min(self._retry_max, self._retry_base * (2 ** (attempts - 1)))
            next_attempt = now + timedelta(seconds=delay)
            error_message = str(exc)
            self._repository.record_failure(
                reminder.id,
                attempts=attempts,
                next_attempt=next_attempt,
                error=error_message,
                updated_at=now,
            )
        else:
            now = datetime.now(UTC)
            self._repository.mark_sent(reminder.id, sent_at=now)
            LOGGER.info("Reminder %s delivered successfully.", reminder.id)

    async def _dispatch(self, client: httpx.AsyncClient, reminder: ReminderRecord) -> None:
        payload = {
            "reminder_id": reminder.id,
            "title": reminder.title,
            "message": reminder.message,
            "target_time_iso": _to_utc_iso(reminder.target_time),
            "payload": reminder.payload,
        }
        response = await client.post(
            reminder.webhook_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Reminder-Id": reminder.id,
                "X-Reminder-Attempts": str(reminder.attempts),
            },
        )
        response.raise_for_status()


class ReminderService:
    """Facade used by MCP tools to interact with reminder infrastructure."""

    def __init__(
        self,
        *,
        repository: ReminderRepository,
        dispatcher: ReminderDispatcher,
        webhook_url: str,
        min_lead_seconds: float = 5.0,
    ) -> None:
        if not webhook_url:
            raise ValueError("REMINDER_WEBHOOK_URL must not be empty.")
        self._repository = repository
        self._dispatcher = dispatcher
        self._webhook_url = webhook_url
        self._min_lead = timedelta(seconds=max(0.0, min_lead_seconds))

    async def schedule_reminder(
        self,
        *,
        title: str,
        message: str,
        target_time_iso: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            request = ReminderRequestModel.model_validate(
                {
                    "title": title,
                    "message": message,
                    "target_time_iso": target_time_iso,
                    "payload": payload,
                }
            )
        except ValidationError as exc:
            messages = "; ".join(err["msg"] for err in exc.errors())
            raise ValueError(f"Invalid reminder request: {messages}") from exc

        now = datetime.now(UTC)
        if request.target_time <= now + self._min_lead:
            raise ValueError(
                "target_time_iso must be in the future and respect the minimum lead time."
            )

        record = self._repository.create(request, self._webhook_url, now=now)
        await self._dispatcher.ensure_running()
        return {
            "note": "Reminder scheduled successfully.",
            **record.to_dict(),
        }

    def list_reminders(self, *, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        records = self._repository.list_reminders(status=status, limit=limit)
        return [record.to_dict() for record in records]

    def cancel_reminder(self, reminder_id: str) -> dict[str, Any]:
        reminder_id = reminder_id.strip()
        if not reminder_id:
            raise ValueError("reminder_id must not be empty.")
        now = datetime.now(UTC)
        cancelled = self._repository.cancel(reminder_id, cancelled_at=now)
        if not cancelled:
            raise ValueError(
                "Reminder could not be cancelled. It may not exist or has already been processed."
            )
        return {
            "reminder_id": reminder_id,
            "status": "cancelled",
            "cancelled_at": _to_utc_iso(now),
        }


class MessageSender:
    """Lightweight helper for sending immediate webhook notifications."""

    def __init__(self, *, webhook_url: str, http_timeout: float = 10.0) -> None:
        webhook_url = (webhook_url or "").strip()
        if not webhook_url:
            raise ValueError("MESSAGE_WEBHOOK_URL must not be empty.")
        self._webhook_url = webhook_url
        self._http_timeout = max(1.0, http_timeout)

    async def send(self, *, to: str, message: str) -> dict[str, Any]:
        to = to.strip()
        message = message.strip()
        if not to:
            raise ValueError("to must not be empty.")
        if not message:
            raise ValueError("message must not be empty.")

        message_id = str(uuid4())
        dispatched_at = datetime.now(UTC)
        dispatched_at_iso = _to_utc_iso(dispatched_at)
        body = {"to": to, "message": message}

        response: httpx.Response
        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.post(
                self._webhook_url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Message-Id": message_id,
                },
            )
        response.raise_for_status()

        return {
            "note": "Message dispatched successfully.",
            "message_id": message_id,
            "to": to,
            "message": message,
            "payload": body,
            "webhook_url": self._webhook_url,
            "status_code": response.status_code,
            "sent_at": dispatched_at_iso,
        }


class DeepResearchSender:
    """Trigger deep research workflows via the configured n8n webhook."""

    def __init__(self, *, webhook_url: str, http_timeout: float = 10.0) -> None:
        webhook_url = (webhook_url or "").strip()
        if not webhook_url:
            raise ValueError("DEEP_RESEARCH_WEBHOOK_URL must not be empty.")
        self._webhook_url = webhook_url
        self._http_timeout = max(1.0, http_timeout)

    async def trigger(self, *, search_topic: str, email: str) -> dict[str, Any]:
        search_topic = search_topic.strip()
        email = email.strip()
        if not search_topic:
            raise ValueError("search_topic must not be empty.")
        if not email:
            raise ValueError("email must not be empty.")

        request_id = str(uuid4())
        dispatched_at = datetime.now(UTC)
        dispatched_at_iso = _to_utc_iso(dispatched_at)
        payload = [{"Search Topic": search_topic, "Email": email}]

        response: httpx.Response
        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.post(
                self._webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Deep-Research-Id": request_id,
                },
            )
        response.raise_for_status()

        return {
            "note": "Deep research workflow triggered successfully.",
            "request_id": request_id,
            "search_topic": search_topic,
            "email": email,
            "payload": payload,
            "webhook_url": self._webhook_url,
            "status_code": response.status_code,
            "sent_at": dispatched_at_iso,
        }

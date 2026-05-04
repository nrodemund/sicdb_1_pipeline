from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from typing import Any


class CliProgressReporter:
    """Shared progress reporter passed into every ETL module."""

    _ALLOWED_PROGRESS_FIELDS = {
        "title",
        "module",
        "description",
        "overall_progress",
        "progress",
        "progress_max",
        "detail",
    }

    _RESET = "\033[0m"
    _DIM = "\033[2m"
    _BOLD = "\033[1m"
    _CYAN = "\033[36m"
    _GREEN = "\033[32m"
    _YELLOW = "\033[33m"
    _RED = "\033[31m"
    _BLUE = "\033[34m"
    _MAGENTA = "\033[35m"
    _CLEAR_LINE = "\033[K"
    _CURSOR_UP = "\033[F"

    def __init__(self, *, heartbeat_seconds: float = 10.0, use_colors: bool | None = None) -> None:
        self.heartbeat_seconds = heartbeat_seconds
        self._current_action: str | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._progress_state: dict[str, Any] | None = None
        self._progress_rendered_lines = 0
        self._progress_animation_task: asyncio.Task[None] | None = None
        self._progress_animation_frame = 0
        self._output_lock = asyncio.Lock()
        self._use_colors = sys.stdout.isatty() if use_colors is None else use_colors

    async def info(self, message: str, **details: Any) -> None:
        await self._emit("INFO", message, **details)

    async def success(self, message: str, **details: Any) -> None:
        await self._emit("OK", message, **details)

    async def warning(self, message: str, **details: Any) -> None:
        await self._emit("WARN", message, **details)

    async def error(self, message: str, **details: Any) -> None:
        await self._emit("ERROR", message, **details)

    async def init_progress(self, values: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Show a modern multi-line progress panel.

        Supported fields are: title, module, description, overall_progress,
        progress, progress_max, and detail. Omitted fields get sensible defaults.
        """
        async with self._output_lock:
            updates = self._merge_progress_values(values, kwargs)
            self._validate_progress_fields(updates)
            self._progress_state = {
                "title": "Working",
                "module": self._current_action or "pipeline",
                "description": "Processing current step",
                "overall_progress": "",
                "progress": 0,
                "progress_max": 100,
                "detail": "Starting...",
            }
            self._progress_state.update(updates)
            self._normalise_progress_state()
            self._sync_progress_animation_locked()
            self._render_progress_locked()

    async def update_progress(self, values: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Update one or more visible progress fields."""
        async with self._output_lock:
            updates = self._merge_progress_values(values, kwargs)
            self._validate_progress_fields(updates)
            if self._progress_state is None:
                self._progress_state = {
                    "title": "Working",
                    "module": self._current_action or "pipeline",
                    "description": "Processing current step",
                    "overall_progress": "",
                    "progress": 0,
                    "progress_max": 100,
                    "detail": "",
                }
            self._progress_state.update(updates)
            self._normalise_progress_state()
            self._sync_progress_animation_locked()
            self._render_progress_locked()

    async def end_progress(self) -> None:
        """Remove the active progress panel from the terminal."""
        async with self._output_lock:
            self._clear_progress_locked()
            self._progress_state = None
            self._sync_progress_animation_locked()

    async def start_action(self, action_name: str) -> None:
        self._current_action = action_name
        await self.info(f"Starting action: {action_name}")
        await self.stop_heartbeat()
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def finish_action(self, action_name: str) -> None:
        await self.end_progress()
        await self.stop_heartbeat()
        await self.success(f"Finished action: {action_name}")
        self._current_action = None

    async def stop_heartbeat(self) -> None:
        if self._heartbeat_task is None:
            return
        self._heartbeat_task.cancel()
        try:
            await self._heartbeat_task
        except asyncio.CancelledError:
            pass
        self._heartbeat_task = None

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            if self._current_action:
                await self.info(f"Still running action: {self._current_action}")

    async def _animate_progress(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            async with self._output_lock:
                if self._progress_state is None or self._progress_state.get("progress") != -1:
                    return
                self._progress_animation_frame += 1
                self._render_progress_locked()

    async def _emit(self, level: str, message: str, **details: Any) -> None:
        async with self._output_lock:
            had_progress = self._progress_state is not None
            self._clear_progress_locked()

            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            detail_text = "" if not details else " " + " ".join(f"{key}={value}" for key, value in details.items())
            level_text = self._format_level(level)
            print(f"{self._dim(timestamp)} {level_text} {message}{detail_text}", flush=True)

            if had_progress:
                self._render_progress_locked()

    @staticmethod
    def _merge_progress_values(values: dict[str, Any] | None, kwargs: dict[str, Any]) -> dict[str, Any]:
        if values is None:
            return dict(kwargs)
        if not isinstance(values, dict):
            raise TypeError("progress values must be passed as keyword arguments or as a dict")
        merged = dict(values)
        merged.update(kwargs)
        return merged

    def _validate_progress_fields(self, values: dict[str, Any]) -> None:
        unknown = sorted(set(values) - self._ALLOWED_PROGRESS_FIELDS)
        if unknown:
            allowed = ", ".join(sorted(self._ALLOWED_PROGRESS_FIELDS))
            raise ValueError(f"Unsupported progress field(s): {', '.join(unknown)}. Allowed fields: {allowed}")

    def _normalise_progress_state(self) -> None:
        if self._progress_state is None:
            return
        progress_max = self._coerce_int(self._progress_state.get("progress_max"), default=100)
        progress_max = max(progress_max, 1)
        progress = self._coerce_int(self._progress_state.get("progress"), default=0)
        if progress != -1:
            progress = max(0, min(progress, progress_max))
        self._progress_state["progress"] = progress
        self._progress_state["progress_max"] = progress_max

        for key in ("title", "module", "description", "overall_progress", "detail"):
            value = self._progress_state.get(key, "")
            self._progress_state[key] = "" if value is None else str(value)

    def _render_progress_locked(self) -> None:
        if self._progress_state is None:
            return
        self._clear_progress_locked()

        state = self._progress_state
        progress = int(state["progress"])
        progress_max = int(state["progress_max"])
        if progress == -1:
            percent_text = "working"
            progress_text = f"—/{progress_max}"
            bar = self._indeterminate_progress_bar()
        else:
            percent = (progress / progress_max) * 100
            percent_text = f"{percent:.1f}%"
            progress_text = f"{progress}/{progress_max}"
            bar = self._progress_bar(progress, progress_max)
        overall = str(state.get("overall_progress", "")).strip()

        title = self._bold(str(state.get("title") or "Working"))
        module = self._badge(str(state.get("module") or "pipeline"))
        description = str(state.get("description") or "Processing current step")
        detail = str(state.get("detail") or "")

        lines = [
            f"{self._cyan('╭─')} {title} {module}" + (f" {self._dim('overall')} {overall}" if overall else ""),
            f"{self._cyan('│')} {self._dim(description)}",
            f"{self._cyan('│')} {bar} {self._bold(progress_text)} {self._dim(f'({percent_text})')}",
            f"{self._cyan('╰─')} {detail}",
        ]

        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
        self._progress_rendered_lines = len(lines)

    def _clear_progress_locked(self) -> None:
        if self._progress_rendered_lines <= 0:
            return
        if not self._use_colors:
            self._progress_rendered_lines = 0
            return
        for _ in range(self._progress_rendered_lines):
            sys.stdout.write(self._CURSOR_UP + "\r" + self._CLEAR_LINE)
        sys.stdout.flush()
        self._progress_rendered_lines = 0

    def _progress_bar(self, progress: int, progress_max: int, width: int = 28) -> str:
        filled = round(width * progress / progress_max)
        empty = width - filled
        return f"{self._green('█' * filled)}{self._dim('░' * empty)}"

    def _indeterminate_progress_bar(self, width: int = 28, block_width: int = 7) -> str:
        span = max(width - block_width, 1)
        position = self._progress_animation_frame % (span * 2)
        if position > span:
            position = span * 2 - position
        before = position
        after = width - block_width - before
        return f"{self._dim('░' * before)}{self._green('█' * block_width)}{self._dim('░' * after)}"

    def _sync_progress_animation_locked(self) -> None:
        should_animate = self._progress_state is not None and self._progress_state.get("progress") == -1
        if should_animate and self._progress_animation_task is None:
            self._progress_animation_task = asyncio.create_task(self._animate_progress())
            return
        if not should_animate and self._progress_animation_task is not None:
            self._progress_animation_task.cancel()
            self._progress_animation_task = None
            self._progress_animation_frame = 0

    def _format_level(self, level: str) -> str:
        colours = {
            "INFO": self._BLUE,
            "OK": self._GREEN,
            "WARN": self._YELLOW,
            "ERROR": self._RED,
        }
        return self._colour(f"[{level}]", colours.get(level, self._MAGENTA))

    def _badge(self, text: str) -> str:
        return self._colour(f" {text} ", self._MAGENTA)

    def _bold(self, text: str) -> str:
        return self._colour(text, self._BOLD)

    def _dim(self, text: str) -> str:
        return self._colour(text, self._DIM)

    def _cyan(self, text: str) -> str:
        return self._colour(text, self._CYAN)

    def _green(self, text: str) -> str:
        return self._colour(text, self._GREEN)

    def _colour(self, text: str, colour: str) -> str:
        if not self._use_colors:
            return text
        return f"{colour}{text}{self._RESET}"

    @staticmethod
    def _coerce_int(value: Any, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
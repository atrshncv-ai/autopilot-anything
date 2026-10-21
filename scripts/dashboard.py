#!/usr/bin/env python3
"""Local, read-only dashboard and event tracker for Autopilot Anything."""

from __future__ import annotations

import argparse
import copy
import datetime as _datetime
import http.server
import ipaddress
import json
import os
import re
import signal
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
MAX_EVENTS = 200
MAX_TEXT_LENGTH = 4000
LOOPBACK = "127.0.0.1"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
ENTITY_ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,63}\Z")

MODES = {"full", "semi", "interview", "manual"}
DEPTHS = {"strict", "normal", "deep"}
COMPLEXITIES = {"simple", "medium", "complex"}
RISKS = {"low", "medium", "high", "critical", "unknown"}
STAGE_STATUSES = {"pending", "active", "waiting", "completed", "failed", "skipped", "blocked"}
REQUIREMENT_STATUSES = {"pending", "in-progress", "satisfied", "deferred", "not-applicable"}
ITEM_STATUSES = {"pending", "active", "waiting", "completed", "blocked", "failed", "skipped"}
CHECK_STATUSES = {"passed", "failed", "not-run"}
GATE_STATUSES = {"pending", "passed", "failed", "blocked", "not-applicable"}
FINISH_STATUSES = {"completed", "failed", "cancelled"}

DEFAULT_STAGES = (
    ("brief", "Brief", "active"),
    ("manifest", "Requirements", "pending"),
    ("specification", "Specification", "pending"),
    ("plan", "Plan", "pending"),
    ("execution", "Work", "pending"),
    ("review", "Review", "pending"),
    ("acceptance", "Final acceptance", "pending"),
)


DASHBOARD_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_TEMPLATE_PATH = DASHBOARD_PACKAGE_ROOT / "dashboard.html"


def load_dashboard_template() -> str:
    """Read the canonical UI template from the installed skill package."""
    if DASHBOARD_TEMPLATE_PATH.is_symlink():
        raise RuntimeError("dashboard template must not be a symlink")
    try:
        resolved_template = DASHBOARD_TEMPLATE_PATH.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError("dashboard template is missing from the installed skill package") from exc
    if resolved_template.parent != DASHBOARD_PACKAGE_ROOT:
        raise RuntimeError("dashboard template must remain inside the installed skill package")
    try:
        template = resolved_template.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("dashboard template could not be read from the installed skill package") from exc
    if template.count("{{STATE_JSON}}") != 1:
        raise RuntimeError("dashboard template must contain exactly one {{STATE_JSON}} marker")
    return template


DEFAULT_TEMPLATE = load_dashboard_template()


def _utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> _datetime.datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("timestamp must be an ISO 8601 string")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = _datetime.datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO 8601 string") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(_datetime.timezone.utc)


def _format_timestamp(value: _datetime.datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _event_timestamp(event: Mapping[str, Any]) -> str:
    return _format_timestamp(_parse_timestamp(event.get("timestamp", _utc_now())))


def _require_id(value: Any, label: str = "ID") -> str:
    if not isinstance(value, str) or not ENTITY_ID_PATTERN.fullmatch(value):
        raise ValueError("%s must start with a letter and contain only letters, digits, dots, underscores, or hyphens" % label)
    return value


def _require_run_id(value: Any) -> str:
    if not isinstance(value, str) or not RUN_ID_PATTERN.fullmatch(value) or value in {".", ".."}:
        raise ValueError("run ID must be 1–64 safe letters, digits, dots, underscores, or hyphens")
    return value


def _text(value: Any, label: str, *, optional: bool = False, limit: int = MAX_TEXT_LENGTH) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str):
        raise ValueError("%s must be text" % label)
    if len(value) > limit or any(ord(character) < 32 and character not in "\n\r\t" for character in value):
        raise ValueError("%s is too long or contains unsupported control characters" % label)
    if not optional and not value.strip():
        raise ValueError("%s must not be empty" % label)
    return value


def _choice(value: Any, allowed: Iterable[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError("invalid %s" % label)
    return value


def _safe_artifact_path(value: Any) -> str:
    text = _text(value, "artifact path", optional=True, limit=500)
    if not text:
        return text
    if "\\" in text or text.startswith("/"):
        raise ValueError("artifact path must be relative to the project")
    path = PurePosixPath(text)
    if not path.parts or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or ":" in path.parts[0]:
        raise ValueError("artifact path must be a safe project-relative path")
    return text


def _safe_id_list(value: Any, label: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)) or len(value) > 100:
        raise ValueError("%s must be a list of IDs" % label)
    return [_require_id(item, label) for item in value]


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _run_paths(project_root: os.PathLike, run_id: str, *, create: bool = False) -> Tuple[Path, Path]:
    run_id = _require_run_id(run_id)
    root = Path(project_root).expanduser().resolve()
    base = root / ".autopilot" / "anything"
    if create:
        base.mkdir(parents=True, exist_ok=True)
    resolved_base = base.resolve()
    if not _path_is_within(resolved_base, root):
        raise ValueError("run state directory must remain inside the project workspace")
    run_dir = base / run_id
    if create:
        run_dir.mkdir(parents=True, exist_ok=True)
    resolved_run = run_dir.resolve()
    if not _path_is_within(resolved_run, resolved_base):
        raise ValueError("run directory must remain inside the state directory")
    state_path = run_dir / "state.json"
    if state_path.is_symlink() or not _path_is_within(state_path.resolve(), resolved_run):
        raise ValueError("state file must remain inside the run directory")
    return run_dir, state_path


def create_run_state(
    run_id: str,
    *,
    title: str = "Autopilot run",
    mode: str = "semi",
    depth: str = "normal",
    complexity: str = "simple",
    risk: str = "unknown",
    route: str = "",
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    run_id = _require_run_id(run_id)
    title = _text(title, "title", limit=300)
    mode = _choice(mode, MODES, "mode")
    depth = _choice(depth, DEPTHS, "depth")
    complexity = _choice(complexity, COMPLEXITIES, "complexity")
    risk = _choice(risk, RISKS, "risk")
    route = _text(route, "route", optional=True, limit=300)
    created_at = _format_timestamp(_parse_timestamp(timestamp or _utc_now()))
    stages = [{"id": stage_id, "label": label, "status": status} for stage_id, label, status in DEFAULT_STAGES]
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "title": title,
        "status": "active",
        "mode": mode,
        "depth": depth,
        "complexity": complexity,
        "risk": risk,
        "route": route,
        "created_at": created_at,
        "started_at": created_at,
        "current_stage_started_at": created_at,
        "updated_at": created_at,
        "completed_at": None,
        "revision": 0,
        "elapsed_seconds": 0,
        "stages": stages,
        "requirements": [],
        "work_items": [],
        "checks": [],
        "gates": {"G%d" % number: {"status": "pending", "updated_at": None, "note": ""} for number in range(1, 5)},
        "waiting_intervals": [],
        "checkpoint": {"stage": "brief", "label": "Brief", "status": "active"},
        "events": [],
        "completion_summary": "",
    }


def _find_or_create(records: List[Dict[str, Any]], identifier: str, fields: Mapping[str, Any], *, required: Sequence[str]) -> Dict[str, Any]:
    for record in records:
        if record.get("id") == identifier:
            record.update(fields)
            return record
    missing = [name for name in required if name not in fields or fields[name] in (None, "")]
    if missing:
        raise ValueError("new record requires %s" % ", ".join(missing))
    record = {"id": identifier}
    record.update(fields)
    records.append(record)
    return record


def _elapsed_seconds(state: Mapping[str, Any], at: _datetime.datetime) -> int:
    started = _parse_timestamp(state["started_at"])
    end = min(at, _parse_timestamp(state["completed_at"])) if state.get("completed_at") else at
    total = max(0.0, (end - started).total_seconds())
    waiting = 0.0
    for interval in state.get("waiting_intervals", []):
        wait_start = _parse_timestamp(interval["started_at"])
        wait_end = _parse_timestamp(interval["ended_at"]) if interval.get("ended_at") else end
        left = max(started, wait_start)
        right = min(end, wait_end)
        if right > left:
            waiting += (right - left).total_seconds()
    return max(0, int(total - waiting))


def apply_event(state: Mapping[str, Any], event: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, Mapping) or not isinstance(event, Mapping):
        raise ValueError("state and event must be objects")
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported run state schema")
    _require_run_id(state.get("run_id"))
    if isinstance(state.get("revision"), bool) or not isinstance(state.get("revision"), int) or state["revision"] < 0:
        raise ValueError("run revision must be a non-negative integer")
    if state.get("status") in FINISH_STATUSES:
        raise ValueError("finished runs cannot accept events")
    event_type = event.get("type")
    if event_type not in {"stage", "gate", "requirement", "item", "check", "wait", "answered", "note", "finish", "resume"}:
        raise ValueError("unsupported event type")
    timestamp = _event_timestamp(event)
    result = copy.deepcopy(dict(state))
    result.setdefault("current_stage_started_at", None)
    event_record: Dict[str, Any] = {"type": event_type, "timestamp": timestamp}
    if event_type == "stage":
        identifier = _require_id(event.get("id"), "stage ID")
        status = _choice(event.get("status"), STAGE_STATUSES, "stage status")
        label = _text(event.get("label", identifier), "stage label", limit=200)
        stage = next((item for item in result["stages"] if item.get("id") == identifier), None)
        checkpoint = result.get("checkpoint") or {}
        current_stage_id = checkpoint.get("stage")
        previous_status = checkpoint.get("status") if current_stage_id == identifier else (stage.get("status") if stage else None)
        enters_stage = current_stage_id != identifier or (
            status == "active" and previous_status in {"pending", "completed", "failed", "skipped", "blocked"}
        )
        if stage is None:
            stage = {"id": identifier, "label": label, "status": status}
            result["stages"].append(stage)
        else:
            stage.update({"label": label, "status": status})
        result["checkpoint"] = {"stage": identifier, "label": label, "status": status}
        if enters_stage:
            result["current_stage_started_at"] = timestamp
        event_record.update({"id": identifier, "label": label, "status": status})
    elif event_type == "gate":
        identifier = _require_id(event.get("id"), "gate ID")
        if identifier not in {"G1", "G2", "G3", "G4"}:
            raise ValueError("gate ID must be G1, G2, G3, or G4")
        status = _choice(event.get("status"), GATE_STATUSES, "gate status")
        note = _text(event.get("note"), "gate note", optional=True)
        result["gates"][identifier] = {"status": status, "updated_at": timestamp, "note": note}
        event_record.update({"id": identifier, "status": status, "note": note})
    elif event_type == "requirement":
        identifier = _require_id(event.get("id"), "requirement ID")
        status = _choice(event.get("status"), REQUIREMENT_STATUSES, "requirement status")
        fields: Dict[str, Any] = {"status": status, "updated_at": timestamp}
        for key, label, limit in (("text", "requirement text", 2000), ("source", "requirement source", 500), ("rationale", "requirement rationale", 1000)):
            if key in event:
                fields[key] = _text(event[key], label, optional=(key != "text"), limit=limit)
        if "artifact" in event:
            fields["artifact"] = _safe_artifact_path(event["artifact"])
        record = _find_or_create(result["requirements"], identifier, fields, required=("text",))
        event_record.update({"id": identifier, "status": status, "text": record.get("text", "")})
    elif event_type == "item":
        identifier = _require_id(event.get("id"), "work item ID")
        status = _choice(event.get("status"), ITEM_STATUSES, "work item status")
        fields = {"status": status, "updated_at": timestamp}
        for key, label, limit in (("title", "work item title", 500), ("owner", "work item owner", 200), ("inputs", "work item inputs", 1000), ("result", "work item result", 2000)):
            if key in event:
                fields[key] = _text(event[key], label, optional=(key != "title"), limit=limit)
        if "requirement_ids" in event:
            fields["requirement_ids"] = _safe_id_list(event["requirement_ids"], "requirement IDs")
        if "dependencies" in event:
            fields["dependencies"] = _safe_id_list(event["dependencies"], "dependency IDs")
        if "acceptance_checks" in event:
            checks = event["acceptance_checks"]
            if not isinstance(checks, (list, tuple)) or len(checks) > 100:
                raise ValueError("acceptance checks must be a list of short descriptions")
            fields["acceptance_checks"] = [_text(item, "acceptance check", limit=500) for item in checks]
        if "artifact" in event:
            fields["artifact"] = _safe_artifact_path(event["artifact"])
        record = _find_or_create(result["work_items"], identifier, fields, required=("title",))
        event_record.update({"id": identifier, "status": status, "title": record.get("title", "")})
    elif event_type == "check":
        identifier = _require_id(event.get("id"), "check ID")
        status = _choice(event.get("status"), CHECK_STATUSES, "check status")
        fields = {"status": status, "updated_at": timestamp}
        for key, label, limit in (("check_type", "check type", 300), ("result", "check result", 2000), ("reason", "check reason", 1000)):
            if key in event:
                fields[key] = _text(event[key], label, optional=(key != "check_type"), limit=limit)
        record = _find_or_create(result["checks"], identifier, fields, required=("check_type",))
        event_record.update({"id": identifier, "status": status, "check_type": record.get("check_type", "")})
    elif event_type == "wait":
        if result.get("status") == "waiting":
            raise ValueError("run is already waiting for a user response")
        reason = _text(event.get("reason"), "waiting reason", limit=2000)
        result["waiting_intervals"].append({"reason": reason, "started_at": timestamp, "ended_at": None, "duration_seconds": 0})
        result["status"] = "waiting"
        checkpoint = result.get("checkpoint") or {}
        checkpoint["status"] = "waiting"
        result["checkpoint"] = checkpoint
        event_record.update({"reason": reason})
    elif event_type == "answered":
        if result.get("status") != "waiting" or not result.get("waiting_intervals") or result["waiting_intervals"][-1].get("ended_at"):
            raise ValueError("run is not waiting for a user response")
        note = _text(event.get("note"), "answer note", optional=True, limit=2000)
        interval = result["waiting_intervals"][-1]
        started = _parse_timestamp(interval["started_at"])
        ended = _parse_timestamp(timestamp)
        interval["ended_at"] = timestamp
        interval["duration_seconds"] = max(0, int((ended - started).total_seconds()))
        result["status"] = "active"
        checkpoint = result.get("checkpoint") or {}
        if checkpoint.get("status") == "waiting":
            checkpoint["status"] = "active"
        result["checkpoint"] = checkpoint
        event_record.update({"note": note})
    elif event_type == "note":
        text = _text(event.get("text"), "note", limit=2000)
        event_record.update({"text": text})
    elif event_type == "finish":
        if result.get("status") == "waiting":
            raise ValueError("answer the open wait before finishing the run")
        status = _choice(event.get("status", "completed"), FINISH_STATUSES, "finish status")
        summary = _text(event.get("summary"), "completion summary", optional=True, limit=2000)
        result["status"] = status
        result["completed_at"] = timestamp
        result["completion_summary"] = summary
        checkpoint = result.get("checkpoint") or {}
        checkpoint["status"] = "completed" if status == "completed" else status
        result["checkpoint"] = checkpoint
        event_record.update({"status": status, "summary": summary})
    elif event_type == "resume":
        if result.get("status") in FINISH_STATUSES:
            raise ValueError("finished runs cannot be resumed")
        event_record.update({"label": "Run resumed"})

    result["revision"] += 1
    event_record["revision"] = result["revision"]
    result["events"].append(event_record)
    result["events"] = result["events"][-MAX_EVENTS:]
    result["updated_at"] = timestamp
    result["elapsed_seconds"] = _elapsed_seconds(result, _parse_timestamp(timestamp))
    return result


def save_run(project_root: os.PathLike, run_id: str, state: Mapping[str, Any]) -> None:
    run_id = _require_run_id(run_id)
    if not isinstance(state, Mapping) or state.get("schema_version") != SCHEMA_VERSION or state.get("run_id") != run_id:
        raise ValueError("state must use the supported schema and selected run ID")
    run_dir, state_path = _run_paths(project_root, run_id, create=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(run_dir), prefix=".state-", suffix=".tmp", delete=False) as stream:
            temporary_path = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, state_path)
        temporary_path = None
        try:
            directory_fd = os.open(str(run_dir), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Some supported filesystems do not allow syncing a directory handle.
            pass
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def load_run(project_root: os.PathLike, run_id: str) -> Dict[str, Any]:
    run_id = _require_run_id(run_id)
    _, state_path = _run_paths(project_root, run_id)
    try:
        with state_path.open("r", encoding="utf-8") as stream:
            state = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("run state JSON is invalid") from exc
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA_VERSION or state.get("run_id") != run_id:
        raise ValueError("run state does not match the selected run ID or schema")
    state.setdefault("current_stage_started_at", None)
    return state


def render_snapshot(template: str, state: Mapping[str, Any]) -> str:
    if not isinstance(template, str) or template.count("{{STATE_JSON}}") != 1:
        raise ValueError("dashboard template must contain exactly one {{STATE_JSON}} marker")
    if not isinstance(state, Mapping):
        raise ValueError("dashboard state must be an object")
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    payload = (payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
               .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return template.replace("{{STATE_JSON}}", payload)


def _is_allowed_host_header(host_header: Optional[str], expected_port: int) -> bool:
    if not isinstance(host_header, str) or not host_header or host_header != host_header.strip():
        return False
    if any(character.isspace() or ord(character) < 32 for character in host_header):
        return False
    if any(character in host_header for character in ("%", "@", ",", "/", "\\", "?", "#")):
        return False
    try:
        parsed = urlsplit("//" + host_header)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if not hostname or parsed.path or parsed.query or parsed.fragment or port != expected_port:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return address.is_loopback


def _make_handler(project_root: Path, run_id: str):
    class DashboardRequestHandler(http.server.BaseHTTPRequestHandler):
        server_version = "AutopilotDashboard/1"
        sys_version = ""

        def log_message(self, format_string: str, *args: Any) -> None:
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _reject(self, status: int, message: str) -> None:
            body = json.dumps({"error": message}, separators=(",", ":")).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def do_GET(self) -> None:
            host_values = self.headers.get_all("Host", [])
            expected_port = self.server.server_address[1]
            if len(host_values) != 1 or not _is_allowed_host_header(host_values[0], expected_port):
                self._reject(403, "host is not a permitted local dashboard host")
                return
            path = urlsplit(self.path).path
            if path not in {"/", "/state.json", "/healthz"}:
                self._reject(404, "not found")
                return
            try:
                state = load_run(project_root, run_id)
                if path == "/":
                    body = render_snapshot(DEFAULT_TEMPLATE, state).encode("utf-8")
                    self._send(200, body, "text/html; charset=utf-8")
                elif path == "/state.json":
                    body = json.dumps(state, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                else:
                    body = json.dumps({"status": "ok", "run_id": run_id, "pid": os.getpid()}, separators=(",", ":")).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
            except (OSError, ValueError):
                self._reject(503, "selected run state is unavailable")

        def do_HEAD(self) -> None:
            self._reject(405, "method not allowed")

        def do_POST(self) -> None:
            self._reject(405, "method not allowed")

        def do_PUT(self) -> None:
            self._reject(405, "method not allowed")

        def do_PATCH(self) -> None:
            self._reject(405, "method not allowed")

        def do_DELETE(self) -> None:
            self._reject(405, "method not allowed")

        def do_OPTIONS(self) -> None:
            self._reject(405, "method not allowed")

    return DashboardRequestHandler


class DashboardServer(http.server.ThreadingHTTPServer):
    """Threaded read-only HTTP server bound to IPv4 loopback."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, project_root: os.PathLike, run_id: str, port: int = 0):
        self.project_root = Path(project_root).expanduser().resolve()
        self.run_id = _require_run_id(run_id)
        super().__init__((LOOPBACK, int(port)), _make_handler(self.project_root, self.run_id))


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), prefix=".server-", suffix=".tmp", delete=False) as stream:
            temporary_path = stream.name
            json.dump(value, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _server_file(project_root: os.PathLike, run_id: str) -> Path:
    run_dir, _ = _run_paths(project_root, run_id, create=True)
    marker = run_dir / "server.json"
    if marker.is_symlink() or not _path_is_within(marker.resolve(), run_dir.resolve()):
        raise ValueError("dashboard server marker must remain inside the run directory")
    return marker


def _write_server_marker(project_root: os.PathLike, run_id: str, port: int) -> Path:
    marker = _server_file(project_root, run_id)
    _atomic_write_json(marker, {"run_id": run_id, "pid": os.getpid(), "port": port, "started_at": _utc_now()})
    return marker


def _serve(project_root: os.PathLike, run_id: str, port: int) -> int:
    server = DashboardServer(project_root, run_id, port=port)
    marker = _write_server_marker(project_root, run_id, server.server_address[1])
    print("Dashboard: http://%s:%d/" % (LOOPBACK, server.server_address[1]))
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def stop_on_sigterm(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_on_sigterm)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        server.server_close()
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
    return 0


def _stop(project_root: os.PathLike, run_id: str) -> int:
    marker = _server_file(project_root, run_id)
    if not marker.is_file():
        raise ValueError("no dashboard server is recorded for this run")
    try:
        details = json.loads(marker.read_text(encoding="utf-8"))
        pid = details.get("pid")
        port = details.get("port")
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError("dashboard server marker is invalid") from exc
    if details.get("run_id") != run_id or isinstance(pid, bool) or not isinstance(pid, int) or not isinstance(port, int):
        raise ValueError("dashboard server marker is invalid")
    request = urllib.request.Request("http://%s:%d/healthz" % (LOOPBACK, port), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            health = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
        raise ValueError("recorded dashboard server is not responding")
    if health.get("run_id") != run_id or health.get("pid") != pid:
        raise ValueError("dashboard server identity does not match its marker")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        raise ValueError("could not stop the recorded dashboard server") from exc
    print("Stopped dashboard server for %s" % run_id)
    return 0


def _add_common(parser: argparse.ArgumentParser, *, needs_run_id: bool) -> None:
    parser.add_argument("--project-root", default=".", help="workspace root (default: current directory)")
    parser.add_argument("--run-id", required=needs_run_id, help="selected run ID")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track an Autopilot Anything run and serve its read-only dashboard.")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a new isolated run")
    _add_common(init, needs_run_id=False)
    init.add_argument("--title", default="Autopilot run")
    init.add_argument("--mode", choices=sorted(MODES), default="semi")
    init.add_argument("--depth", choices=sorted(DEPTHS), default="normal")
    init.add_argument("--complexity", choices=sorted(COMPLEXITIES), default="simple")
    init.add_argument("--risk", choices=sorted(RISKS), default="unknown")
    init.add_argument("--route", default="")

    resume = commands.add_parser("resume", help="reopen an existing unfinished run by ID")
    _add_common(resume, needs_run_id=True)

    for command_name, help_text in (("stage", "update a workflow stage"), ("gate", "update a G1–G4 gate")):
        item_parser = commands.add_parser(command_name, help=help_text)
        _add_common(item_parser, needs_run_id=True)
        item_parser.add_argument("--id", required=True)
        item_parser.add_argument("--status", required=True)
        item_parser.add_argument("--label", default=None)
        item_parser.add_argument("--note", default=None)

    requirement = commands.add_parser("requirement", help="add or update a requirement")
    _add_common(requirement, needs_run_id=True)
    requirement.add_argument("--id", required=True)
    requirement.add_argument("--status", required=True)
    requirement.add_argument("--text")
    requirement.add_argument("--source")
    requirement.add_argument("--rationale")
    requirement.add_argument("--artifact")

    work_item = commands.add_parser("item", help="add or update a universal work item")
    _add_common(work_item, needs_run_id=True)
    work_item.add_argument("--id", required=True)
    work_item.add_argument("--status", required=True)
    work_item.add_argument("--title")
    work_item.add_argument("--owner")
    work_item.add_argument("--inputs")
    work_item.add_argument("--result")
    work_item.add_argument("--requirement-ids", nargs="*")
    work_item.add_argument("--dependencies", nargs="*")
    work_item.add_argument("--acceptance-checks", nargs="*")
    work_item.add_argument("--artifact")

    check = commands.add_parser("check", help="record an artifact or outcome check")
    _add_common(check, needs_run_id=True)
    check.add_argument("--id", required=True)
    check.add_argument("--status", required=True)
    check.add_argument("--type", dest="check_type")
    check.add_argument("--result")
    check.add_argument("--reason")

    wait = commands.add_parser("wait", help="start a user-wait interval")
    _add_common(wait, needs_run_id=True)
    wait.add_argument("--reason", required=True)

    answered = commands.add_parser("answered", help="close the current user-wait interval")
    _add_common(answered, needs_run_id=True)
    answered.add_argument("--note", default="")

    note = commands.add_parser("note", help="append a short activity note")
    _add_common(note, needs_run_id=True)
    note.add_argument("text")

    finish = commands.add_parser("finish", help="finish the selected run")
    _add_common(finish, needs_run_id=True)
    finish.add_argument("--status", choices=sorted(FINISH_STATUSES), default="completed")
    finish.add_argument("--summary", default="")

    snapshot = commands.add_parser("snapshot", help="write a self-contained HTML snapshot")
    _add_common(snapshot, needs_run_id=True)
    snapshot.add_argument("--output", help="output HTML path (default: run directory/snapshot.html)")

    serve = commands.add_parser("serve", help="serve this run on loopback until interrupted")
    _add_common(serve, needs_run_id=True)
    serve.add_argument("--port", type=int, default=8765)

    stop = commands.add_parser("stop", help="stop the recorded local dashboard server")
    _add_common(stop, needs_run_id=True)
    return parser


def _generated_run_id() -> str:
    import secrets

    return "run-%s-%s" % (_datetime.datetime.now(_datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), secrets.token_hex(4))


def _apply_and_save(project_root: os.PathLike, run_id: str, event: Mapping[str, Any]) -> Dict[str, Any]:
    state = load_run(project_root, run_id)
    updated = apply_event(state, event)
    save_run(project_root, run_id, updated)
    return updated


def _event_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    if args.command in {"stage", "gate"}:
        event = {"type": args.command, "id": args.id, "status": args.status}
        if args.label is not None:
            event["label"] = args.label
        if args.note is not None:
            event["note"] = args.note
        return event
    if args.command == "requirement":
        event = {"type": "requirement", "id": args.id, "status": args.status}
        for key in ("text", "source", "rationale", "artifact"):
            value = getattr(args, key)
            if value is not None:
                event[key] = value
        return event
    if args.command == "item":
        event = {"type": "item", "id": args.id, "status": args.status}
        for key in ("title", "owner", "inputs", "result", "requirement_ids", "dependencies", "acceptance_checks", "artifact"):
            value = getattr(args, key)
            if value is not None:
                event[key] = value
        return event
    if args.command == "check":
        event = {"type": "check", "id": args.id, "status": args.status}
        for key in ("check_type", "result", "reason"):
            value = getattr(args, key)
            if value is not None:
                event[key] = value
        return event
    if args.command == "wait":
        return {"type": "wait", "reason": args.reason}
    if args.command == "answered":
        return {"type": "answered", "note": args.note}
    if args.command == "note":
        return {"type": "note", "text": args.text}
    if args.command == "finish":
        return {"type": "finish", "status": args.status, "summary": args.summary}
    raise ValueError("unsupported command")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    project_root = Path(args.project_root)
    run_id = args.run_id
    try:
        if args.command == "init":
            run_id = _require_run_id(run_id or _generated_run_id())
            try:
                load_run(project_root, run_id)
            except FileNotFoundError:
                pass
            else:
                raise ValueError("run ID already exists; choose a new ID or use resume")
            state = create_run_state(run_id, title=args.title, mode=args.mode, depth=args.depth,
                                     complexity=args.complexity, risk=args.risk, route=args.route)
            save_run(project_root, run_id, state)
            print("Created run %s" % run_id)
            return 0
        run_id = _require_run_id(run_id)
        if args.command == "resume":
            state = load_run(project_root, run_id)
            if state.get("status") in FINISH_STATUSES:
                raise ValueError("finished runs cannot be resumed")
            updated = apply_event(state, {"type": "resume"})
            save_run(project_root, run_id, updated)
            print("Resumed run %s" % run_id)
            return 0
        if args.command in {"stage", "gate", "requirement", "item", "check", "wait", "answered", "note", "finish"}:
            updated = _apply_and_save(project_root, run_id, _event_from_args(args))
            print("Updated run %s (revision %d)" % (run_id, updated["revision"]))
            return 0
        if args.command == "snapshot":
            state = load_run(project_root, run_id)
            run_dir, _ = _run_paths(project_root, run_id, create=True)
            output = Path(args.output).expanduser() if args.output else run_dir / "snapshot.html"
            output.parent.mkdir(parents=True, exist_ok=True)
            rendered = render_snapshot(DEFAULT_TEMPLATE, state)
            output.write_text(rendered, encoding="utf-8")
            print("Snapshot: %s" % output)
            return 0
        if args.command == "serve":
            if not 0 <= args.port <= 65535:
                raise ValueError("port must be between 0 and 65535")
            load_run(project_root, run_id)
            return _serve(project_root, run_id, args.port)
        if args.command == "stop":
            return _stop(project_root, run_id)
        raise ValueError("unsupported command")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print("dashboard: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

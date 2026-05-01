#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
DEFAULT_STATE = PROJECT_ROOT / "_logs" / "supervisor_reports" / "telegram_notify_state.json"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_notification_env() -> None:
    load_env_file(Path.home() / ".hermes" / ".env")
    load_env_file(PROJECT_ROOT / "_metadata" / ".env")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def compact_text(text: str, limit: int = 3700) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    compact = "\n".join(line for line in lines if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 80].rstrip() + "\n\n[truncated; see Project 3 logs for full detail]"


def status_file_message(path: Path, title: str) -> str:
    if not path.exists():
        return title
    if path.suffix == ".json":
        payload = read_json(path, {})
        if isinstance(payload, dict):
            machine = payload.get("machine", "unknown")
            tier = payload.get("tier", "unknown tier")
            status = payload.get("status", "unknown")
            generated = payload.get("generated_at", "unknown time")
            detail = str(payload.get("detail", "")).strip()
            detail = detail.replace("```json", "").replace("```", "").strip()
            return compact_text(
                f"{title}\n"
                f"machine: {machine}\n"
                f"tier: {tier}\n"
                f"status: {status}\n"
                f"generated_at: {generated}\n"
                f"detail: {detail}",
                limit=3700,
            )
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if len(lines) > 90:
        text = "\n".join(lines[:90]) + "\n\n[truncated; see full global_status.md]"
    return compact_text(f"{title}\n\n{text}", limit=3700)


def send_telegram(token: str, chat_id: str, text: str) -> None:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(endpoint, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(body)
    if not parsed.get("ok"):
        raise RuntimeError(body)


def discover_chats(token: str) -> list[dict]:
    endpoint = f"https://api.telegram.org/bot{token}/getUpdates"
    with urllib.request.urlopen(endpoint, timeout=20) as response:
        parsed = json.loads(response.read().decode("utf-8", errors="replace"))
    chats = {}
    for update in parsed.get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        chats[str(chat_id)] = {
            "id": str(chat_id),
            "type": chat.get("type"),
            "title": chat.get("title") or chat.get("username") or chat.get("first_name"),
        }
    return sorted(chats.values(), key=lambda item: item["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Project 3 Telegram notification helper")
    parser.add_argument("--event", default="project3")
    parser.add_argument("--title", default="Project 3 status")
    parser.add_argument("--message", default="")
    parser.add_argument("--status-file", default="")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE))
    parser.add_argument("--min-interval-minutes", type=float, default=20.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--discover", action="store_true", help="Print recent Telegram chats for the configured bot")
    args = parser.parse_args()

    load_notification_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = (
        os.environ.get("PROJECT3_TELEGRAM_CHAT_ID", "").strip()
        or os.environ.get("TELEGRAM_HOME_CHANNEL", "").strip()
    )

    if not token:
        print("telegram_notify skipped: TELEGRAM_BOT_TOKEN is not configured")
        return 0

    if args.discover:
        chats = discover_chats(token)
        out = PROJECT_ROOT / "_logs" / "supervisor_reports" / "telegram_chat_discovery.json"
        write_json(out, {"generated_at": int(time.time()), "chats": chats})
        print(json.dumps(chats, indent=2))
        return 0

    if not chat_id:
        print("telegram_notify skipped: TELEGRAM_HOME_CHANNEL or PROJECT3_TELEGRAM_CHAT_ID is not configured")
        return 0

    if args.message:
        message = compact_text(f"{args.title}\n\n{args.message}")
    elif args.status_file:
        message = status_file_message(Path(args.status_file), args.title)
    else:
        message = args.title

    state_path = Path(args.state_file)
    state = read_json(state_path, {})
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()
    event_state = state.get(args.event, {})
    now = time.time()
    elapsed = now - float(event_state.get("last_sent_at", 0))
    min_elapsed = args.min_interval_minutes * 60.0

    if not args.force and event_state.get("digest") == digest and elapsed < min_elapsed:
        print(f"telegram_notify skipped: unchanged event {args.event}")
        return 0

    send_telegram(token, chat_id, message)
    state[args.event] = {"digest": digest, "last_sent_at": now}
    write_json(state_path, state)
    print(f"telegram_notify sent: {args.event}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"telegram_notify failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

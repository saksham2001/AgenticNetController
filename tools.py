import json
import os
import re
from datetime import datetime, timezone

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "log_checkin",
        "description": "Log a station check-in to the net roster",
        "parameters": {
            "type": "object",
            "properties": {
                "call_sign": {"type": "string", "description": "Station callsign"},
                "name": {"type": "string", "description": "Operator name"},
                "location": {"type": "string", "description": "Operator location"},
                "notes": {"type": "string", "description": "Optional notes"},
            },
            "required": ["call_sign"],
        },
    },
    {
        "type": "function",
        "name": "log_update",
        "description": "Log an update or traffic note for a checked-in station",
        "parameters": {
            "type": "object",
            "properties": {
                "call_sign": {"type": "string", "description": "Station callsign"},
                "update_text": {"type": "string", "description": "Update content"},
                "category": {
                    "type": "string",
                    "description": "Category: general, traffic, announcement",
                },
            },
            "required": ["call_sign", "update_text"],
        },
    },
    {
        "type": "function",
        "name": "declare_emergency",
        "description": "Declare emergency traffic for a station",
        "parameters": {
            "type": "object",
            "properties": {
                "call_sign": {"type": "string", "description": "Station callsign"},
                "summary": {"type": "string", "description": "Emergency summary"},
                "priority": {
                    "type": "string",
                    "description": "Priority level: emergency, priority, welfare",
                },
            },
            "required": ["call_sign", "summary"],
        },
    },
    {
        "type": "function",
        "name": "list_checkins",
        "description": "List all currently checked-in stations",
        "parameters": {"type": "object", "properties": {}},
    },
]


def _valid_callsign(cs: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9]{3,7}$", cs.strip()))


class ToolExecutor:
    def __init__(self, log_dir: str = "logs"):
        self.checked_in: list[dict] = []
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        self.log_path = os.path.join(log_dir, f"net_{stamp}.jsonl")

    def _append_log(self, entry: dict):
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def execute(self, name: str, args_json: str) -> str:
        try:
            args = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON arguments"})

        handler = {
            "log_checkin": self._log_checkin,
            "log_update": self._log_update,
            "declare_emergency": self._declare_emergency,
            "list_checkins": self._list_checkins,
        }.get(name)

        if not handler:
            return json.dumps({"error": f"Unknown tool: {name}"})
        return handler(args)

    def _log_checkin(self, args: dict) -> str:
        cs = args.get("call_sign", "").strip().upper()
        if not cs:
            return json.dumps({"error": "call_sign is required"})
        if not _valid_callsign(cs):
            return json.dumps({"error": f"Invalid callsign format: {cs}"})

        # Deduplication
        for station in self.checked_in:
            if station["call_sign"] == cs:
                note = args.get("notes", "")
                if note:
                    station["notes"] = (station.get("notes") or "") + "; " + note
                entry = {"tool": "log_checkin", "action": "duplicate_noted", **station}
                self._append_log(entry)
                return json.dumps({"status": "already_checked_in", "call_sign": cs})

        record = {
            "call_sign": cs,
            "name": args.get("name", ""),
            "location": args.get("location", ""),
            "notes": args.get("notes", ""),
        }
        self.checked_in.append(record)
        self._append_log({"tool": "log_checkin", "action": "new", **record})
        return json.dumps({"status": "checked_in", **record})

    def _log_update(self, args: dict) -> str:
        cs = args.get("call_sign", "").strip().upper()
        update = args.get("update_text", "")
        category = args.get("category", "general")
        entry = {
            "tool": "log_update",
            "call_sign": cs,
            "update_text": update,
            "category": category,
        }
        self._append_log(entry)
        return json.dumps({"status": "logged", "call_sign": cs})

    def _declare_emergency(self, args: dict) -> str:
        cs = args.get("call_sign", "").strip().upper()
        summary = args.get("summary", "")
        priority = args.get("priority", "emergency")
        entry = {
            "tool": "declare_emergency",
            "call_sign": cs,
            "summary": summary,
            "priority": priority,
        }
        self._append_log(entry)
        return json.dumps(
            {"status": "emergency_declared", "call_sign": cs, "priority": priority}
        )

    def _list_checkins(self, args: dict) -> str:
        return json.dumps({"stations": self.checked_in, "count": len(self.checked_in)})

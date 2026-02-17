import time
from enum import Enum

SESSION_WARN_MINUTES = 55


class NetMode(Enum):
    IDLE = "idle"
    CHECKIN = "checkin"
    RAGCHEW = "ragchew"
    EMERGENCY = "emergency"
    WRAPUP = "wrapup"


def _format_roster(stations: list[dict]) -> str:
    if not stations:
        return "No stations currently checked in."
    lines = []
    for i, s in enumerate(stations, 1):
        parts = [s["call_sign"]]
        if s.get("name"):
            parts.append(s["name"])
        if s.get("location"):
            parts.append(s["location"])
        lines.append(f"  {i}. {' — '.join(parts)}")
    return f"{len(stations)} station(s) checked in:\n" + "\n".join(lines)


_MODE_DIRECTIVES = {
    NetMode.IDLE: (
        "OPERATOR DIRECTIVE: Net is idle. Stand by for instructions."
    ),
    NetMode.CHECKIN: (
        "OPERATOR DIRECTIVE: We are now in CHECKIN mode. "
        "Call for check-ins and log each station as they respond. "
        "Follow the CHECKIN MODE BEHAVIOR procedure."
    ),
    NetMode.RAGCHEW: (
        "OPERATOR DIRECTIVE: We are now in RAGCHEW mode. "
        "The net is already in progress — do NOT re-read the opening script or ask for check-ins. "
        "Call each checked-in station in roster order for brief updates or ragchew. "
        "If nobody responds after a moment, start a conversation topic yourself "
        "(weather, ham radio, local events, etc.). "
        "Follow the RAGCHEW MODE BEHAVIOR procedure."
    ),
    NetMode.EMERGENCY: (
        "OPERATOR DIRECTIVE: We are now in EMERGENCY mode. "
        "Emergency traffic has priority. All other stations stand by. "
        "Follow the EMERGENCY MODE BEHAVIOR procedure."
    ),
    NetMode.WRAPUP: (
        "OPERATOR DIRECTIVE: We are now in WRAPUP mode. "
        "The net is wrapping up — do NOT re-read the opening script. "
        "Ask for final traffic, thank all stations, and close the net. "
        "Follow the WRAPUP MODE BEHAVIOR procedure."
    ),
}


class NetController:
    def __init__(self):
        self.mode = NetMode.IDLE
        self.session_start_time = time.time()

    def set_mode(self, mode: NetMode, stations: list[dict] | None = None) -> str:
        self.mode = mode
        directive = _MODE_DIRECTIVES[mode]
        if stations is not None:
            roster = _format_roster(stations)
            directive += f"\n\nCURRENT ROSTER:\n{roster}"
        return directive

    def get_mode_directive(self) -> str:
        return _MODE_DIRECTIVES[self.mode]

    def should_warn_session_timeout(self) -> bool:
        elapsed = time.time() - self.session_start_time
        return elapsed >= SESSION_WARN_MINUTES * 60

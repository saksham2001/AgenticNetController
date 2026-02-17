import time
from enum import Enum

SESSION_WARN_MINUTES = 55


class NetMode(Enum):
    IDLE = "idle"
    CHECKIN = "checkin"
    RAGCHEW = "ragchew"
    EMERGENCY = "emergency"
    WRAPUP = "wrapup"


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
        "Call each checked-in station in roster order for updates. "
        "Follow the RAGCHEW MODE BEHAVIOR procedure."
    ),
    NetMode.EMERGENCY: (
        "OPERATOR DIRECTIVE: We are now in EMERGENCY mode. "
        "Emergency traffic has priority. All other stations stand by. "
        "Follow the EMERGENCY MODE BEHAVIOR procedure."
    ),
    NetMode.WRAPUP: (
        "OPERATOR DIRECTIVE: We are now in WRAPUP mode. "
        "Ask for final traffic, thank all stations, and close the net. "
        "Follow the WRAPUP MODE BEHAVIOR procedure."
    ),
}


class NetController:
    def __init__(self):
        self.mode = NetMode.IDLE
        self.session_start_time = time.time()

    def set_mode(self, mode: NetMode) -> str:
        self.mode = mode
        return _MODE_DIRECTIVES[mode]

    def get_mode_directive(self) -> str:
        return _MODE_DIRECTIVES[self.mode]

    def should_warn_session_timeout(self) -> bool:
        elapsed = time.time() - self.session_start_time
        return elapsed >= SESSION_WARN_MINUTES * 60

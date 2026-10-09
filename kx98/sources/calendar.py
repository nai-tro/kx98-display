"""Calendar data source polling calpeek EventKit CLI."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from kx98.config import PROJECT_ROOT

logger = logging.getLogger("kx98.sources.calendar")

CALPEEK_BIN = PROJECT_ROOT / "sources" / "calpeek"


@dataclass
class CalendarData:
    busy: bool
    is_soon: bool
    current_title: Optional[str] = None
    current_end: Optional[datetime] = None
    next_title: Optional[str] = None
    next_start: Optional[datetime] = None


def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # ISO-8601 parsing
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


class CalendarSource:
    def __init__(self, binary_path: Path = CALPEEK_BIN):
        self.binary_path = binary_path
        self._last_data: Optional[CalendarData] = None
        self._last_log_time: float = 0.0

    def poll(self) -> Optional[CalendarData]:
        if not self.binary_path.is_file():
            logger.warning(f"calpeek binary not found at {self.binary_path}")
            return None

        try:
            res = subprocess.run(
                [str(self.binary_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                logger.debug(f"calpeek returned exit code {res.returncode}: {res.stderr}")
                return self._last_data

            data = json.loads(res.stdout.strip())
            if data.get("error"):
                logger.debug(f"calpeek reported error: {data.get('error')}")
                # Access denied or not yet permitted; treat as not busy
                return CalendarData(busy=False, is_soon=False)

            busy = bool(data.get("busy", False))
            curr = data.get("current")
            nxt = data.get("next")

            curr_title = curr.get("title") if curr else None
            curr_end = parse_iso(curr.get("end")) if curr else None
            nxt_title = nxt.get("title") if nxt else None
            nxt_start = parse_iso(nxt.get("start")) if nxt else None

            # Calculate is_soon: within 10 minutes (600s) of next meeting
            is_soon = False
            if not busy and nxt_start:
                now_utc = datetime.now(timezone.utc)
                diff = (nxt_start - now_utc).total_seconds()
                if 0 <= diff <= 600:
                    is_soon = True

            cal_data = CalendarData(
                busy=busy,
                is_soon=is_soon,
                current_title=curr_title,
                current_end=curr_end,
                next_title=nxt_title,
                next_start=nxt_start,
            )
            self._last_data = cal_data
            return cal_data

        except Exception as e:
            logger.debug(f"Error polling calendar: {e}")
            return self._last_data

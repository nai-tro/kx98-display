"""omp usage data source with account disambiguation and window filtering."""

from dataclasses import dataclass
import logging
from pathlib import Path
import sqlite3
import time
from typing import Optional

from kx98.palette import OMP_OK, OMP_WARN, OMP_HOT

logger = logging.getLogger("kx98.sources.omp")

DB_PATH = Path.home() / ".omp" / "agent" / "agent.db"


@dataclass
class OmpUsageItem:
    provider: str
    email: str
    prefix: str        # "C", "C1", "C2", "G1", "G2", "X"
    pct_text: str      # "15%", "67%"
    used_fraction: float
    color: tuple[int, int, int]
    window_label: str


class OmpSource:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._last_items: list[OmpUsageItem] = []
        self._last_success_time: float = 0.0

    def poll_all(self) -> list[OmpUsageItem]:
        """Poll latest usage filtering out weekly windows and assigning C/G/X prefixes."""
        if not self.db_path.is_file():
            return self._last_items

        now = time.time()
        now_ms = int(now * 1000)
        cutoff_ms = now_ms - (24 * 60 * 60 * 1000)  # 24 hours lookback so all accounts stay present

        for attempt in range(2):
            try:
                uri = f"file:{self.db_path}?mode=ro"
                conn = sqlite3.connect(uri, uri=True, timeout=1.0)
                cur = conn.cursor()

                query = """
                WITH latest AS (
                    SELECT provider, account_key, email, limit_id, label, window_label, used_fraction, resets_at,
                           ROW_NUMBER() OVER (PARTITION BY provider, account_key, limit_id, window_label ORDER BY recorded_at DESC) as rn
                    FROM usage_history
                    WHERE recorded_at >= ? AND status != 'unavailable' AND used_fraction IS NOT NULL
                )
                SELECT provider, account_key, email, limit_id, label, window_label, used_fraction, resets_at
                FROM latest
                WHERE rn = 1;
                """
                rows = cur.execute(query, (cutoff_ms,)).fetchall()
                conn.close()

                if not rows:
                    if now - self._last_success_time <= 600:
                        return self._last_items
                    return []

                # Group by (provider, email)
                claude_by_account: dict[str, tuple] = {}
                gemini_by_account: dict[str, tuple] = {}
                codex_by_account: dict[str, tuple] = {}

                for r in rows:
                    p, acc, email, lid, label, wlabel, uf, resets = r
                    w_lower = (wlabel or "").lower()
                    lid_lower = lid.lower()

                    # RULE: Exclude all weekly / 7-day stats!
                    if "week" in w_lower or "7 day" in w_lower or "weekly" in lid_lower:
                        continue

                    # 1. Claude: monthly / extra limit only
                    if p == "anthropic":
                        acct_id = email or acc
                        # Keep highest usage extra/month limit per account
                        if acct_id not in claude_by_account or uf > claude_by_account[acct_id][6]:
                            claude_by_account[acct_id] = r

                    # 2. Gemini: 5 Hour limit only
                    elif p == "google-antigravity":
                        if "5 hour" in w_lower or "5h" in lid_lower:
                            # Only gemini model (or general google limit)
                            if "gemini" in lid_lower or "gemini" in label.lower():
                                acct_id = email or acc
                                if acct_id not in gemini_by_account or uf > gemini_by_account[acct_id][6]:
                                    gemini_by_account[acct_id] = r

                    # 3. Codex: 5 hours (or monthly)
                    elif p == "openai-codex":
                        if "5 hour" in w_lower or "30 day" in w_lower or "month" in w_lower:
                            acct_id = email or acc
                            if acct_id not in codex_by_account or uf > codex_by_account[acct_id][6]:
                                codex_by_account[acct_id] = r

                items = []

                # Process Claude accounts
                c_accounts = sorted(claude_by_account.keys())
                for idx, acct in enumerate(c_accounts):
                    r = claude_by_account[acct]
                    uf = float(r[6])
                    prefix = f"C{idx + 1}" if len(c_accounts) > 1 else "C"
                    pct_text = f"{int(round(uf * 100))}%"
                    color = OMP_OK if uf < 0.60 else (OMP_WARN if uf < 0.85 else OMP_HOT)
                    items.append(
                        OmpUsageItem(
                            provider="anthropic",
                            email=r[2] or "",
                            prefix=prefix,
                            pct_text=pct_text,
                            used_fraction=uf,
                            color=color,
                            window_label=r[5] or "",
                        )
                    )

                # Process Gemini accounts
                g_accounts = sorted(gemini_by_account.keys())
                for idx, acct in enumerate(g_accounts):
                    r = gemini_by_account[acct]
                    uf = float(r[6])
                    prefix = f"G{idx + 1}" if len(g_accounts) > 1 else "G"
                    pct_text = f"{int(round(uf * 100))}%"
                    color = OMP_OK if uf < 0.60 else (OMP_WARN if uf < 0.85 else OMP_HOT)
                    items.append(
                        OmpUsageItem(
                            provider="google-antigravity",
                            email=r[2] or "",
                            prefix=prefix,
                            pct_text=pct_text,
                            used_fraction=uf,
                            color=color,
                            window_label=r[5] or "",
                        )
                    )

                # Process Codex accounts
                x_accounts = sorted(codex_by_account.keys())
                for idx, acct in enumerate(x_accounts):
                    r = codex_by_account[acct]
                    uf = float(r[6])
                    prefix = f"X{idx + 1}" if len(x_accounts) > 1 else "X"
                    pct_text = f"{int(round(uf * 100))}%"
                    color = OMP_OK if uf < 0.60 else (OMP_WARN if uf < 0.85 else OMP_HOT)
                    items.append(
                        OmpUsageItem(
                            provider="openai-codex",
                            email=r[2] or "",
                            prefix=prefix,
                            pct_text=pct_text,
                            used_fraction=uf,
                            color=color,
                            window_label=r[5] or "",
                        )
                    )

                self._last_items = items
                self._last_success_time = now
                return items

            except sqlite3.OperationalError as e:
                logger.debug(f"SQLite busy (attempt {attempt + 1}/2): {e}")
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Error querying omp db: {e}")
                break

        if now - self._last_success_time <= 600:
            return self._last_items
        return []

    def poll(self) -> Optional[OmpUsageItem]:
        items = self.poll_all()
        return items[0] if items else None

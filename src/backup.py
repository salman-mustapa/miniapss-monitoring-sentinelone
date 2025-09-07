# src/backup.py
import os
import json
from datetime import datetime
from typing import Iterable

from src.logger import log_info, log_error

STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "events")


def ensure_storage_dir():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        # create .gitkeep so folder exists in repo if needed
        gitkeep = os.path.join(os.path.dirname(STORAGE_DIR), ".gitkeep")
        try:
            open(gitkeep, "a").close()
        except Exception:
            pass


def daily_filename_for(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.utcnow()
    name = dt.strftime("%Y-%m-%d") + ".jsonl"
    return os.path.join(STORAGE_DIR, name)


def append_events(events: Iterable[dict]) -> int:
    """
    Append a list/iterable of event dictionaries to today's jsonl file.
    Returns number of events appended.
    """
    ensure_storage_dir()
    filepath = daily_filename_for()
    count = 0
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            for ev in events:
                # ensure serializable
                try:
                    line = json.dumps(ev, ensure_ascii=False)
                except Exception:
                    # fallback: convert non-serializable values
                    line = json.dumps(json.loads(json.dumps(ev, default=str)), ensure_ascii=False)
                f.write(line + "\n")
                count += 1
        log_info(f"Appended {count} event(s) to archive: {filepath}")
    except Exception as e:
        log_error(f"Failed to append events to {filepath}: {e}")
    return count


def read_events_for_date(date_str: str):
    """
    Read events for given date string 'YYYY-MM-DD' returning generator of dicts.
    """
    filepath = os.path.join(STORAGE_DIR, f"{date_str}.jsonl")
    if not os.path.exists(filepath):
        return []
    results = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except Exception:
                    # skip invalid line
                    continue
    except Exception as e:
        log_error(f"Failed to read events from {filepath}: {e}")
    return results

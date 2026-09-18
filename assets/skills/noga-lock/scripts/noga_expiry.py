#!/usr/bin/env python3
"""Seconds past expiry for a NOGA lock_time_out string.

NOGA reports lock_time_out in **UTC**, formatted 'DD-MON-YY HH.MM.SS.ffffff AM/PM'
(local CST = UTC+8). Converting it in your head has caused a 23-minute error before.

Output: a single integer. > 0 means the lease has already lapsed by that many seconds.
NOGA does NOT clear lock_owner when a lease expires, so an expired-but-owned lock is
the normal case for a box that is actually free.

Usage:  noga_expiry.py "13-AUG-26 09.05.12.123456 AM"
        noga_expiry.py --human "13-AUG-26 09.05.12.123456 AM"
Exit:   0 = expired, 1 = still valid, 2 = unparseable
"""
import sys
from datetime import datetime, timezone

FMT = "%d-%b-%y %I.%M.%S.%f %p"


def seconds_past_expiry(s: str) -> int:
    dt = datetime.strptime(s.strip(), FMT).replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - dt).total_seconds())


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--human"]
    human = "--human" in sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    raw = " ".join(args)
    try:
        past = seconds_past_expiry(raw)
    except ValueError as e:
        # An empty or 'None' value is what NOGA returns for an unlocked host.
        print(f"unparseable lock_time_out {raw!r}: {e}", file=sys.stderr)
        return 2
    if human:
        state = "EXPIRED" if past > 0 else "valid"
        print(f"{past} s ({state}, {abs(past) // 60} min {'ago' if past > 0 else 'left'})")
    else:
        print(past)
    return 0 if past > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

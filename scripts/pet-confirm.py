#!/usr/bin/env python3
"""Create a pet question, then wait for an explicit user's answer. No auto-answer CLI."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import time
from pathlib import Path
from pet_confirmation import ConfirmationStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--file", required=True, help="UTF-8 JSON question file")
    create.add_argument("--ttl", type=float, default=600)
    wait = sub.add_parser("wait")
    wait.add_argument("--id", required=True)
    wait.add_argument("--seconds", type=int, default=55, choices=range(0, 61), metavar="0..60")
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--id", required=True)
    args = parser.parse_args()
    store = ConfirmationStore()
    try:
        if args.command == "create":
            path = Path(args.file)
            if path.stat().st_size > 48000:
                raise ValueError("确认文件过大")
            data = store.create(json.loads(path.read_text(encoding="utf-8-sig")), args.ttl)
        elif args.command == "cancel":
            data = store.cancel(args.id)
        else:
            deadline = time.monotonic() + args.seconds
            while True:
                data = store.read(args.id)
                if data["status"] != "pending" or time.monotonic() >= deadline:
                    break
                time.sleep(min(.25, max(0, deadline - time.monotonic())))
        result = {"id": data["id"], "status": data["status"]}
        if "answer" in data:
            result["answer"] = data["answer"]
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.command == "create":
            return 0
        return {"answered": 0, "pending": 2, "expired": 3, "cancelled": 3}[data["status"]]
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

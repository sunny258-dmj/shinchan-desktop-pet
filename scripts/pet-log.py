#!/usr/bin/env python3
"""Show the same safe event projection used by the pet; never print message bodies."""
import argparse
import json
import sys
import time
sys.dont_write_bytecode = True
from pet_events import TranscriptWatcher, STATE_LABEL, TOOL_LABEL, classify


def display(ev):
    state = classify(ev.get('event'), ev)
    label = TOOL_LABEL.get(ev.get('tool_name'), '') or STATE_LABEL.get(state, ev.get('event', ''))
    stamp = time.strftime('%H:%M:%S', time.localtime(ev['ts']/1000))
    print(f"[{stamp}] {ev['session_id'][:8]} | {label} | {ev.get('snippet', '')}")


def main():
    parser = argparse.ArgumentParser(description='桌宠结构事件日志（不读取思考/消息/命令正文）')
    parser.add_argument('-n', type=int, default=10)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    watcher = TranscriptWatcher()
    try:
        watcher._ensure_conn()
        if watcher._conn is None:
            print('未找到可读取的 TeleAgent 数据库')
            return 1
        watcher._scan_titles()
        rows = watcher._conn.execute(watcher._projection_sql() + ' ORDER BY p.rowid DESC LIMIT ?',
                                     (max(1, min(args.n, 1000)),)).fetchall()
        for row in reversed(rows):
            if watcher._probe_sys_sid(row['session_id']):
                continue
            ev = watcher._part_to_event(json.loads(row['data']),row['time_created'],row['session_id'],row['role'])
            if ev:
                display(ev)
        if args.watch:
            watcher.poll()
            while True:
                for ev in watcher.poll():
                    display(ev)
                time.sleep(0.5)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if watcher._conn:
            watcher._conn.close()


if __name__ == '__main__':
    sys.exit(main())

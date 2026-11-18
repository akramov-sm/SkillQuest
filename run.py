#!/usr/bin/env python3
"""Start SkillQuest:  python3 run.py  →  http://127.0.0.1:8000"""
import argparse
import signal
import sys
import webbrowser

from backend import config
from backend.server import make_server


def main():
    ap = argparse.ArgumentParser(description="SkillQuest local server")
    ap.add_argument("--host", default=config.HOST)
    ap.add_argument("--port", type=int, default=config.PORT)
    ap.add_argument("--open", action="store_true", help="open the browser after start")
    ap.add_argument("--quiet", action="store_true", help="disable request logging")
    args = ap.parse_args()
    fatal, warnings = config.startup_problems(args.host)
    for w in warnings:
        print("WARNING:", w, file=sys.stderr)
    if fatal:
        sys.exit("Configuration error:\n  - " + "\n  - ".join(fatal))
    try:
        srv = make_server(args.host, args.port, quiet=args.quiet)
    except OSError as e:
        sys.exit(f"Cannot start on {args.host}:{args.port} — {e}. Try: python3 run.py --port 8010")
    url = f"http://{args.host}:{srv.server_address[1]}"
    print(f"SkillQuest running at {url}  (database: {config.DB_PATH})\nPress Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    print("HTTP Basic Auth: " + ("enabled" if config.BASIC_AUTH else "off (local use only)"))

    def _terminate(*_):  # docker stop / systemd: shut down cleanly
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _terminate)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()

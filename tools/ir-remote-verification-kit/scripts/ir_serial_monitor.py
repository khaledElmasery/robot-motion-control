#!/usr/bin/env python3
"""Read-only serial monitor for the standalone Arduino IR test sketch.

This script only reads text from the serial port; it never transmits commands.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import serial
import serial.tools.list_ports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM8", help="Serial port (default: COM8)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--log", type=Path, help="Optional path for a plain-text log")
    parser.add_argument("--list-ports", action="store_true", help="List serial ports and exit")
    return parser.parse_args()


def display_line(line: str) -> str:
    if not line.startswith("IR;"):
        return line

    fields: dict[str, str] = {}
    for item in line.split(";")[1:]:
        key, separator, value = item.partition("=")
        if separator:
            fields[key] = value

    protocol = fields.get("protocol", "?")
    address = fields.get("address", "?")
    command = fields.get("command", "?")
    raw = fields.get("raw", "?")
    button = fields.get("button")
    candidate = fields.get("candidate_label")
    status = fields.get("map_status", "")

    if button and button != "UNMAPPED":
        label = button
        prefix = "BUTTON"
    elif candidate and candidate != "UNMAPPED":
        label = f"{candidate} (candidate; verify on SG-555)"
        prefix = "BUTTON?"
    else:
        label = "UNMAPPED (raw code only)"
        prefix = "BUTTON?"

    suffix = f" | {status}" if status else ""
    return (
        f"{prefix} {label} | {protocol} address={address} "
        f"command={command} raw={raw}{suffix}"
    )


def main() -> int:
    args = parse_args()
    ports = list(serial.tools.list_ports.comports())

    if args.list_ports:
        for port in ports:
            print(f"{port.device}\t{port.description}")
        return 0

    log_file = args.log.open("a", encoding="utf-8") if args.log else None
    try:
        with serial.Serial(args.port, args.baud, timeout=0.5) as connection:
            print(f"Listening read-only on {args.port} at {args.baud} baud. Press Ctrl+C to stop.")
            while True:
                raw = connection.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                rendered = display_line(line)
                timestamped = f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] {rendered}"
                print(timestamped, flush=True)
                if log_file:
                    log_file.write(timestamped + "\n")
                    log_file.flush()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1
    finally:
        if log_file:
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Guided, read-only calibration of the Super Gold X3 / SG-555 IR remote.

The script listens to the standalone Arduino sketch, prompts for each key in
photo order, saves each accepted NEC frame, and generates a C++ keymap header.
It never sends commands to the Arduino or to robot hardware.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import serial
    import serial.tools.list_ports
except ModuleNotFoundError as exc:  # pragma: no cover - exercised when pyserial is absent.
    raise SystemExit(
        "pyserial is required. Install it with: python -m pip install -r scripts/requirements.txt"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "sg555_button_map.csv"
JSON_PATH = DATA_DIR / "sg555_button_map.json"
TRANSCRIPT_PATH = DATA_DIR / "learning_transcript.txt"
HEADER_PATH = ROOT / "include" / "sg555_keymap.h"

# Order follows the visible button layout in the user's SG-555 remote photo.
BUTTONS: tuple[tuple[str, str], ...] = (
    ("POWER", "زر التشغيل الأحمر بجوار MUTE"),
    ("MUTE", "كتم الصوت"),
    ("RED", "الزر الأحمر"),
    ("GREEN", "الزر الأخضر"),
    ("YELLOW", "الزر الأصفر"),
    ("BLUE", "الزر الأزرق"),
    ("ZOOM", "تكبير الصورة"),
    ("SUB", "الترجمة SUB"),
    ("TSHIFT", "الإزاحة الزمنية T.SHIFT"),
    ("SOURCE", "المصدر SOURCE"),
    ("TV_RADIO", "TV/RADIO"),
    ("TTX_CC", "TTX/CC"),
    ("FILELIST", "قائمة الملفات FILELIST"),
    ("TIMER", "المؤقت TIMER"),
    ("PLAY", "تشغيل الوسائط ▶"),
    ("PAUSE", "إيقاف مؤقت ⏸"),
    ("STOP", "إيقاف الوسائط ■"),
    ("RECORD", "تسجيل ●"),
    ("MENU", "القائمة MENU"),
    ("EXIT", "خروج EXIT"),
    ("UP", "السهم لأعلى ▲"),
    ("LEFT", "السهم لليسار ◀"),
    ("OK", "الزر الأوسط OK"),
    ("RIGHT", "السهم لليمين ▶"),
    ("DOWN", "السهم لأسفل ▼"),
    ("EPG", "دليل البرامج EPG"),
    ("INFO", "المعلومات INFO"),
    ("PREVIOUS_TRACK", "المسار السابق ⏮"),
    ("AUDIO", "اختيار الصوت AUDIO"),
    ("REWIND", "إرجاع سريع ⏪"),
    ("SAT", "القمر الصناعي SAT"),
    ("FAST_FORWARD", "تقديم سريع ⏩"),
    ("NEXT_TRACK", "المسار التالي ⏭"),
    ("DIGIT_1", "الرقم 1"),
    ("DIGIT_2", "الرقم 2"),
    ("DIGIT_3", "الرقم 3"),
    ("DIGIT_4", "الرقم 4"),
    ("DIGIT_5", "الرقم 5"),
    ("DIGIT_6", "الرقم 6"),
    ("DIGIT_7", "الرقم 7"),
    ("DIGIT_8", "الرقم 8"),
    ("DIGIT_9", "الرقم 9"),
    ("FAV", "المفضلة FAV"),
    ("DIGIT_0", "الرقم 0"),
    ("RECALL", "استرجاع القناة RECALL"),
)


@dataclass
class CapturedKey:
    label: str
    description_ar: str
    address: int | None = None
    command: int | None = None
    raw: int | None = None
    protocol: str | None = None
    bits: int | None = None
    status: str = "pending"
    captured_at_utc: str | None = None


def parse_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    if not line.startswith("IR;"):
        return fields
    for part in line.split(";")[1:]:
        key, sep, value = part.partition("=")
        if sep:
            fields[key] = value
    return fields


def parse_ir_line(line: str) -> dict[str, Any] | None:
    fields = parse_fields(line)
    if fields.get("protocol") != "NEC":
        return None
    try:
        address = int(fields["address"], 16)
        command = int(fields["command"], 16)
        raw = int(fields["raw"], 16)
        bits = int(fields.get("bits", "0"))
    except (KeyError, ValueError):
        return None
    return {
        "protocol": "NEC",
        "address": address,
        "command": command,
        "raw": raw,
        "bits": bits,
        "serial_line": line.strip(),
    }


def capture_one(connection: serial.Serial, timeout_seconds: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        raw_line = connection.readline()
        if not raw_line:
            continue
        line = raw_line.decode("utf-8", errors="replace").strip()
        if line.startswith("IR;"):
            event = parse_ir_line(line)
            if event is not None:
                return event
            print(f"  تجاهلت إطارًا غير NEC/غير مكتمل: {line}")
    return None


def load_state(restart: bool) -> list[CapturedKey]:
    if JSON_PATH.exists() and not restart:
        try:
            payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
            existing = {item["label"]: item for item in payload.get("keys", [])}
            keys: list[CapturedKey] = []
            for label, description in BUTTONS:
                item = existing.get(label, {})
                keys.append(CapturedKey(
                    label=label,
                    description_ar=description,
                    address=item.get("address"),
                    command=item.get("command"),
                    raw=item.get("raw"),
                    protocol=item.get("protocol"),
                    bits=item.get("bits"),
                    status=item.get("status", "pending"),
                    captured_at_utc=item.get("captured_at_utc"),
                ))
            print("وجدت خريطة سابقة؛ سأستكمل الأزرار غير المسجلة. استخدم --restart للبدء من جديد.")
            return keys
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"تعذر قراءة الخريطة السابقة ({exc})؛ سأبدأ سجلًا جديدًا.")

    return [CapturedKey(label=label, description_ar=description) for label, description in BUTTONS]


def write_outputs(keys: list[CapturedKey]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HEADER_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "remote_model": "SUPER GOLD X3 / SG-555",
        "protocol_expected": "NEC",
        "serial_baud": 115200,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "keys": [asdict(item) for item in keys],
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    columns = ["label", "description_ar", "protocol", "address", "command", "raw", "bits", "status", "captured_at_utc"]
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for key in keys:
            row = asdict(key)
            for field in ("address", "command", "raw"):
                value = row[field]
                row[field] = "" if value is None else f"0x{value:02X}" if field != "raw" else f"0x{value:08X}"
            writer.writerow({column: row.get(column, "") for column in columns})

    mapped = [key for key in keys if key.status == "mapped" and key.address is not None and key.command is not None]
    header_lines = [
        "#pragma once",
        "#include <Arduino.h>",
        "",
        "// Generated by scripts/learn_buttons.py from physical SG-555 button presses.",
        "struct SG555KeyMapEntry",
        "{",
        "  uint16_t address;",
        "  uint16_t command;",
        "  const char *label;",
        "};",
        "",
        "static const SG555KeyMapEntry SG555_KEYS[] =",
        "{",
    ]
    if mapped:
        for key in mapped:
            label = key.label.replace("\\", "\\\\").replace('"', '\\"')
            header_lines.append(f'  {{ 0x{key.address:04X}, 0x{key.command:04X}, "{label}" }},')
    else:
        header_lines.append('  { 0xFFFF, 0xFFFF, "" }')
    header_lines.extend([
        "};",
        f"static constexpr size_t SG555_KEY_COUNT = {len(mapped)};",
        "",
    ])
    HEADER_PATH.write_text("\n".join(header_lines), encoding="utf-8")


def append_transcript(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with TRANSCRIPT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] {message}\n")


def duplicate_label(keys: list[CapturedKey], current_label: str, event: dict[str, Any]) -> str | None:
    for key in keys:
        if key.label != current_label and key.status == "mapped" and key.address == event["address"] and key.command == event["command"]:
            return key.label
    return None


def learn_buttons(
    connection: serial.Serial,
    keys: list[CapturedKey],
    timeout_seconds: float,
    confirm_each: bool,
    pause_seconds: float,
) -> None:
    append_transcript("=== Calibration session started ===")
    total = len(keys)

    for index, key in enumerate(keys, start=1):
        if key.status == "mapped":
            print(f"[{index:02d}/{total}] {key.label}: محفوظ مسبقًا؛ تخطيت هذا الزر.")
            continue

        while True:
            try:
                connection.reset_input_buffer()
            except (serial.SerialException, OSError):
                pass
            print(f"\n[{index:02d}/{total}] اضغط الآن: {key.label} — {key.description_ar}")
            print(f"سأنتظر إطار NEC لمدة {timeout_seconds:.0f} ثانية. اضغط هذا الزر مرة واحدة فقط.")
            append_transcript(f"PROMPT {index}/{total}: {key.label} — {key.description_ar}")
            event = capture_one(connection, timeout_seconds)

            if event is None:
                print("لم يصل رمز في الوقت المحدد. اكتب r لإعادة الانتظار، s لتخطي هذا الزر، أو q للحفظ والخروج.")
                choice = input("> ").strip().lower()
                if choice == "r":
                    continue
                if choice == "s":
                    key.status = "skipped"
                    write_outputs(keys)
                    append_transcript(f"SKIPPED {key.label}: timeout")
                    break
                if choice == "q":
                    append_transcript("=== User stopped calibration ===")
                    write_outputs(keys)
                    return
                continue

            prior = duplicate_label(keys, key.label, event)
            print(
                f"تم الالتقاط: address=0x{event['address']:02X} "
                f"command=0x{event['command']:02X} raw=0x{event['raw']:08X}"
            )
            if prior:
                print(f"تحذير: هذا الرمز مسجل بالفعل للزر {prior}. لن أضع الاسمين على الرمز نفسه؛ أعد الضغط على {key.label} أو تخطّه.")
                append_transcript(f"DUPLICATE {key.label} matches {prior}: {event['serial_line']}")
                choice = input("اكتب r لإعادة الالتقاط، s لتخطي، أو q للحفظ والخروج: ").strip().lower()
                if choice == "s":
                    key.status = "skipped_duplicate"
                    write_outputs(keys)
                    break
                if choice == "q":
                    write_outputs(keys)
                    append_transcript("=== User stopped calibration ===")
                    return
                continue

            if confirm_each:
                print("اكتب Enter للحفظ والانتقال؛ r لإعادة هذا الزر؛ s لتخطيه؛ q للحفظ والخروج.")
                choice = input("> ").strip().lower()
                if choice == "r":
                    continue
                if choice == "s":
                    key.status = "skipped"
                    write_outputs(keys)
                    append_transcript(f"SKIPPED {key.label}: user choice")
                    break
                if choice == "q":
                    write_outputs(keys)
                    append_transcript("=== User stopped calibration ===")
                    return

            key.address = event["address"]
            key.command = event["command"]
            key.raw = event["raw"]
            key.protocol = event["protocol"]
            key.bits = event["bits"]
            key.status = "mapped"
            key.captured_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
            write_outputs(keys)
            append_transcript(f"MAPPED {key.label}: {event['serial_line']}")
            print(f"حُفظ {key.label}: command=0x{event['command']:02X}، والانتقال للزر التالي بعد {pause_seconds:.1f} ثانية.")
            if pause_seconds > 0:
                time.sleep(pause_seconds)
            break

    write_outputs(keys)
    mapped_count = sum(key.status == "mapped" for key in keys)
    print(f"\nاكتملت الجولة: {mapped_count}/{total} زرًا سُجّل بنجاح.")
    print(f"الملفات الناتجة:\n  {CSV_PATH}\n  {JSON_PATH}\n  {HEADER_PATH}\n  {TRANSCRIPT_PATH}")
    print("الخطوة التالية: أوقف هذا البرنامج، ارفع الاختبار مرة أخرى ليُضمّن الخريطة الجديدة، ثم اختبر الأزرار عبر Serial Monitor.")
    append_transcript(f"=== Calibration finished: {mapped_count}/{total} mapped ===")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM8", help="منفذ Arduino (الافتراضي COM8)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=12.0, help="مهلة انتظار كل زر بالثواني")
    parser.add_argument("--pause-seconds", type=float, default=1.5, help="الفاصل بين التقاط زر والطلب التالي")
    parser.add_argument("--confirm-each", action="store_true", help="اطلب Enter لتأكيد كل التقاط قبل حفظه")
    parser.add_argument("--list-ports", action="store_true", help="عرض المنافذ المتاحة")
    parser.add_argument("--restart", action="store_true", help="بدء معايرة جديدة بدل استكمال الخريطة السابقة")
    args = parser.parse_args()

    if args.list_ports:
        for port in serial.tools.list_ports.comports():
            print(f"{port.device}\t{port.description}")
        return 0
    keys = load_state(args.restart)
    write_outputs(keys)
    mapped = sum(key.status == "mapped" for key in keys)
    print("المعايرة التفاعلية لريموت SUPER GOLD X3 / SG-555")
    print(f"عدد الأزرار في الترتيب: {len(keys)}؛ المحفوظ مسبقًا: {mapped}.")
    print("افتراضيًا: اضغط الزر المطلوب فقط؛ سيُحفظ تلقائيًا ثم يظهر الزر التالي.")
    print("استخدم --confirm-each إذا أردت الضغط على Enter لتأكيد كل زر يدويًا.")
    print(f"منفذ الاتصال: {args.port} بسرعة {args.baud} baud.")
    print("تأكد أن اختبار IR مرفوع على Uno، وأغلق أي Serial Monitor آخر قبل المتابعة.")
    print("لإيقاف المعايرة بأمان: Ctrl+C؛ النتائج السابقة لا تُحذف.")

    try:
        with serial.Serial(args.port, args.baud, timeout=0.25) as connection:
            # Opening the Uno serial port may reset the board; let IRremote initialize.
            time.sleep(2.0)
            connection.reset_input_buffer()
            learn_buttons(connection, keys, args.timeout, args.confirm_each, args.pause_seconds)
    except serial.SerialException as exc:
        print(f"خطأ في Serial: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        write_outputs(keys)
        print("\nأُوقفت المعايرة؛ النتائج المحفوظة حتى الآن لم تُحذف.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

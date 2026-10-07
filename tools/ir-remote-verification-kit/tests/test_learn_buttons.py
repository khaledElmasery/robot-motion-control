from __future__ import annotations

import contextlib
import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import learn_buttons as learner  # noqa: E402


class FakeSerial:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = iter(lines)

    def reset_input_buffer(self) -> None:
        pass

    def readline(self) -> bytes:
        return next(self.lines, b"")


class LearnButtonsTests(unittest.TestCase):
    def test_power_is_first_and_inventory_has_45_buttons(self) -> None:
        self.assertEqual(learner.BUTTONS[0][0], "POWER")
        self.assertEqual(learner.BUTTONS[1][0], "MUTE")
        self.assertEqual(len(learner.BUTTONS), 45)

    def test_parse_nec_event(self) -> None:
        line = "IR;protocol=NEC;address=0x00;command=0x07;raw=0xF807FF00;bits=32;button=UNMAPPED;map_status=NO_LEARNED_ENTRY"
        event = learner.parse_ir_line(line)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["address"], 0)
        self.assertEqual(event["command"], 7)
        self.assertEqual(event["raw"], 0xF807FF00)
        self.assertIsNone(learner.parse_ir_line(line.replace("protocol=NEC", "protocol=UNKNOWN")))

    def test_duplicate_code_is_detected(self) -> None:
        first = learner.CapturedKey("POWER", "power", address=0, command=6, status="mapped")
        second = learner.CapturedKey("MUTE", "mute")
        event = {"address": 0, "command": 6}
        self.assertEqual(learner.duplicate_label([first, second], "MUTE", event), "POWER")

    def test_generated_header_contains_only_mapped_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            csv_path = root / "map.csv"
            json_path = root / "map.json"
            transcript_path = root / "transcript.txt"
            header_path = root / "include" / "sg555_keymap.h"
            with (
                patch.object(learner, "DATA_DIR", root),
                patch.object(learner, "CSV_PATH", csv_path),
                patch.object(learner, "JSON_PATH", json_path),
                patch.object(learner, "TRANSCRIPT_PATH", transcript_path),
                patch.object(learner, "HEADER_PATH", header_path),
            ):
                keys = [
                    learner.CapturedKey("POWER", "زر التشغيل", 0, 6, 0xF906FF00, "NEC", 32, "mapped"),
                    learner.CapturedKey("MUTE", "كتم الصوت"),
                ]
                learner.write_outputs(keys)
                header = header_path.read_text(encoding="utf-8")
                self.assertIn('{ 0x0000, 0x0006, "POWER" }', header)
                self.assertIn("SG555_KEY_COUNT = 1", header)
                with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["status"], "mapped")
                self.assertEqual(rows[1]["status"], "pending")

    def test_auto_calibration_saves_all_45_unique_codes(self) -> None:
        lines = []
        for index in range(len(learner.BUTTONS)):
            command = index + 1
            raw = 0xF0000000 + index
            lines.append(
                f"IR;protocol=NEC;address=0x00;command=0x{command:02X};"
                f"raw=0x{raw:08X};bits=32;button=UNMAPPED;map_status=NO_LEARNED_ENTRY\n".encode()
            )
        fake_serial = FakeSerial(lines)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            csv_path = root / "map.csv"
            json_path = root / "map.json"
            transcript_path = root / "transcript.txt"
            header_path = root / "include" / "sg555_keymap.h"
            with (
                patch.object(learner, "DATA_DIR", root),
                patch.object(learner, "CSV_PATH", csv_path),
                patch.object(learner, "JSON_PATH", json_path),
                patch.object(learner, "TRANSCRIPT_PATH", transcript_path),
                patch.object(learner, "HEADER_PATH", header_path),
                patch.object(learner.time, "sleep", return_value=None),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                keys = [learner.CapturedKey(label, description) for label, description in learner.BUTTONS]
                learner.learn_buttons(fake_serial, keys, 0.1, False, 0)
                self.assertEqual(sum(key.status == "mapped" for key in keys), 45)
                self.assertIn("SG555_KEY_COUNT = 45", header_path.read_text(encoding="utf-8"))
                with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 45)
                self.assertEqual(rows[0]["label"], "POWER")
                self.assertEqual(rows[-1]["label"], "RECALL")
                self.assertTrue(transcript_path.exists())


if __name__ == "__main__":
    unittest.main()

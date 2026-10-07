from __future__ import annotations

import csv
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import learn_buttons as learner  # noqa: E402


class CapturedKeymapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.keys = json.loads((ROOT / "data" / "sg555_button_map.json").read_text(encoding="utf-8"))["keys"]
        with (ROOT / "data" / "sg555_button_map.csv").open(encoding="utf-8-sig", newline="") as handle:
            cls.csv_rows = list(csv.DictReader(handle))
        with (ROOT / "docs" / "SG555_BUTTON_INVENTORY.csv").open(encoding="utf-8-sig", newline="") as handle:
            cls.inventory_rows = list(csv.DictReader(handle))
        cls.header = (ROOT / "include" / "sg555_keymap.h").read_text(encoding="utf-8")
        cls.transcript = (ROOT / "data" / "learning_transcript.txt").read_text(encoding="utf-8")

    def test_all_45_buttons_are_mapped_and_unique(self) -> None:
        self.assertEqual(len(self.keys), 45)
        self.assertEqual([key["label"] for key in self.keys], [label for label, _ in learner.BUTTONS])
        self.assertTrue(all(key["status"] == "mapped" for key in self.keys))
        self.assertTrue(all(key["protocol"] == "NEC" and key["address"] == 0 for key in self.keys))
        code_pairs = [(key["address"], key["command"]) for key in self.keys]
        self.assertEqual(len(code_pairs), len(set(code_pairs)))

    def test_csv_matches_json_exactly(self) -> None:
        self.assertEqual(len(self.csv_rows), 45)
        by_label = {key["label"]: key for key in self.keys}
        self.assertEqual(set(by_label), {row["label"] for row in self.csv_rows})
        for row in self.csv_rows:
            key = by_label[row["label"]]
            self.assertEqual(row["protocol"], key["protocol"])
            self.assertEqual(row["status"], key["status"])
            self.assertEqual(int(row["address"], 16), key["address"])
            self.assertEqual(int(row["command"], 16), key["command"])
            self.assertEqual(int(row["raw"], 16), key["raw"])
            self.assertEqual(int(row["bits"]), key["bits"])

    def test_document_inventory_matches_captured_csv(self) -> None:
        self.assertEqual(self.inventory_rows, self.csv_rows)

    def test_active_cpp_header_matches_all_learned_codes(self) -> None:
        found = re.findall(
            r'\{\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),\s*"([A-Z0-9_]+)"\s*\}',
            self.header,
        )
        actual = {(int(address, 16), int(command, 16)): label for address, command, label in found}
        expected = {(key["address"], key["command"]): key["label"] for key in self.keys}
        self.assertEqual(actual, expected)
        self.assertIn("SG555_KEY_COUNT = 45", self.header)

    def test_transcript_captures_match_the_json_map(self) -> None:
        pattern = re.compile(
            r"\bMAPPED\s+([A-Z0-9_]+): IR;protocol=([^;]+);address=0x([0-9A-Fa-f]+);"
            r"command=0x([0-9A-Fa-f]+);raw=0x([0-9A-Fa-f]+);bits=(\d+)"
        )
        events = pattern.findall(self.transcript)
        self.assertEqual(len(events), 45)
        by_label = {key["label"]: key for key in self.keys}
        for label, protocol, address, command, raw, bits in events:
            key = by_label[label]
            self.assertEqual(protocol, key["protocol"])
            self.assertEqual(int(address, 16), key["address"])
            self.assertEqual(int(command, 16), key["command"])
            self.assertEqual(int(raw, 16), key["raw"])
            self.assertEqual(int(bits), key["bits"])
        self.assertIn("Calibration finished: 45/45 mapped", self.transcript)


if __name__ == "__main__":
    unittest.main()

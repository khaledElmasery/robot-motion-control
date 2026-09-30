from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from bridge import (  # noqa: E402
    CommandSender,
    SerialStatusReader,
    dpad_pulse,
    movement_from_axes,
    movement_from_bumpers,
    movement_from_triggers,
    normalize_command,
    spin_from_modifier,
    tone_from_axes,
)


class FakeSerial:
    def __init__(self) -> None:
        self.written = bytearray()
        self.in_waiting = 0
        self.to_read = bytearray()

    def write(self, payload: bytes) -> int:
        self.written.extend(payload)
        return len(payload)

    def read(self, count: int) -> bytes:
        result = bytes(self.to_read[:count])
        del self.to_read[:count]
        self.in_waiting = len(self.to_read)
        return result


class BridgeMappingTests(unittest.TestCase):
    def test_left_stick_cardinal_motion_and_deadzone(self) -> None:
        self.assertEqual(movement_from_axes(0.0, -0.8, 0.22), "F")
        self.assertEqual(movement_from_axes(0.0, 0.8, 0.22), "B")
        self.assertEqual(movement_from_axes(-0.8, 0.0, 0.22), "L")
        self.assertEqual(movement_from_axes(0.8, 0.0, 0.22), "R")
        self.assertEqual(movement_from_axes(0.05, -0.05, 0.22), "S")

    def test_y_modifier_and_triggers_drive_spins(self) -> None:
        self.assertEqual(spin_from_modifier(True, True, False), "C")
        self.assertEqual(spin_from_modifier(True, False, True), "c")
        self.assertEqual(spin_from_modifier(True, True, True), "S")
        self.assertIsNone(spin_from_modifier(False, True, False))
        self.assertIsNone(spin_from_modifier(True, False, False))

    def test_triggers_move_forward_and_reverse_or_stop(self) -> None:
        self.assertEqual(movement_from_triggers(True, False), "F")
        self.assertEqual(movement_from_triggers(False, True), "B")
        self.assertEqual(movement_from_triggers(True, True), "S")
        self.assertIsNone(movement_from_triggers(False, False))

    def test_bumpers_select_single_wheel(self) -> None:
        self.assertEqual(movement_from_bumpers(True, False), "L")
        self.assertEqual(movement_from_bumpers(False, True), "R")
        self.assertEqual(movement_from_bumpers(True, True), "S")
        self.assertIsNone(movement_from_bumpers(False, False))

    def test_dpad_is_edge_triggered_and_cardinal(self) -> None:
        self.assertEqual(dpad_pulse((0, 1), (0, 0)), "^")
        self.assertEqual(dpad_pulse((0, -1), (0, 0)), "V")
        self.assertEqual(dpad_pulse((-1, 0), (0, 0)), "<")
        self.assertEqual(dpad_pulse((1, 0), (0, 0)), ">")
        self.assertIsNone(dpad_pulse((1, 0), (1, 0)))
        self.assertIsNone(dpad_pulse((0, 0), (1, 0)))

    def test_right_stick_selects_buzzer_patterns(self) -> None:
        self.assertEqual(tone_from_axes(0.0, -0.8, 0.22), "1")
        self.assertEqual(tone_from_axes(0.8, 0.0, 0.22), "2")
        self.assertEqual(tone_from_axes(0.0, 0.8, 0.22), "3")
        self.assertEqual(tone_from_axes(-0.8, 0.0, 0.22), "4")
        self.assertIsNone(tone_from_axes(0.0, 0.0, 0.22))

    def test_command_normalization_keeps_clockwise_case(self) -> None:
        self.assertEqual(normalize_command("v"), "V")
        self.assertEqual(normalize_command("c"), "c")
        with self.assertRaises(ValueError):
            normalize_command("FF")
        with self.assertRaises(ValueError):
            normalize_command("?")


class SerialProtocolTests(unittest.TestCase):
    def test_sender_deduplicates_states_and_sends_heartbeat(self) -> None:
        fake = FakeSerial()
        sender = CommandSender(fake)
        self.assertTrue(sender.send("F"))
        self.assertFalse(sender.send("F"))
        self.assertTrue(sender.send("F", force=True))
        sender.heartbeat()
        self.assertEqual(bytes(fake.written), b"FFZ")
        self.assertNotIn(b"\n", fake.written)
        self.assertNotIn(b"\r", fake.written)

    def test_status_reader_handles_partial_lines(self) -> None:
        fake = FakeSerial()
        reader = SerialStatusReader()
        fake.to_read.extend(b"SPEED_LEVEL=6 PWM=")
        fake.in_waiting = len(fake.to_read)
        self.assertEqual(reader.poll(fake), [])
        fake.to_read.extend(b"163\r\nWATCHDOG: heartbeat lost\n")
        fake.in_waiting = len(fake.to_read)
        self.assertEqual(reader.poll(fake), ["SPEED_LEVEL=6 PWM=163", "WATCHDOG: heartbeat lost"])


if __name__ == "__main__":
    unittest.main()

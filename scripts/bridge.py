#!/usr/bin/env python3
"""PS1/Xbox-style controller bridge for the Arduino Uno firmware.

The bridge sends single ASCII command characters at 9600 baud. The firmware
has no serial watchdog or command acknowledgement, so this script can request
S on release/exit but cannot guarantee a stop after a cable or power failure.
See docs/SAFETY_AND_TESTING.md before connecting motors.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

COMMANDS = frozenset("FBLRSCc<>^VJH1234+-*/")
CONTINUOUS = frozenset("FBLRSCc")
PULSES = frozenset("<>^VJH1234+-*/")


def normalize_command(raw: str) -> str:
    """Match the USB firmware's case handling (lowercase c is special)."""
    if len(raw) != 1:
        raise ValueError("A command must be exactly one character")
    command = "c" if raw == "c" else raw.upper()
    if command not in COMMANDS:
        raise ValueError(f"Unsupported firmware command: {raw!r}")
    return command


def movement_from_axes(x: float, y: float, deadzone: float) -> str:
    """Map left-stick axes to the source's F/B/L/R/S commands.

    Vertical wins on diagonals. In the firmware L and R activate only one
    motor each; they are not differential steering or a safe turning mode.
    """
    x = 0.0 if abs(x) < deadzone else x
    y = 0.0 if abs(y) < deadzone else y
    if x == 0.0 and y == 0.0:
        return "S"
    if abs(y) >= abs(x):
        return "F" if y < 0 else "B"
    return "L" if x < 0 else "R"


def tone_from_axes(x: float, y: float, deadzone: float) -> Optional[str]:
    """Map right-stick directions to horn/tone commands 1-4; vertical wins."""
    x = 0.0 if abs(x) < deadzone else x
    y = 0.0 if abs(y) < deadzone else y
    if x == 0.0 and y == 0.0:
        return None
    if abs(y) >= abs(x):
        return "1" if y < 0 else "3"
    return "2" if x > 0 else "4"


def parse_button_binding(value: str) -> tuple[str, int]:
    """Parse --bind COMMAND=BUTTON for commands without a fixed button map."""
    if "=" not in value:
        raise argparse.ArgumentTypeError("Expected COMMAND=BUTTON, e.g. ^=6")
    raw_command, raw_button = value.split("=", 1)
    try:
        command = normalize_command(raw_command)
        button = int(raw_button)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if command not in PULSES:
        raise argparse.ArgumentTypeError(
            "--bind accepts one-shot commands only (H, 1-4, <, >, ^, V, J, +, -, *, /)"
        )
    if button < 0:
        raise argparse.ArgumentTypeError("Button index must be zero or greater")
    return command, button


class CommandSender:
    """Deduplicated command writes plus a stop/action/stop one-shot pulse."""

    def __init__(self, port, pulse_ms: int) -> None:
        self.port = port
        self.pulse_seconds = pulse_ms / 1000.0
        self.last_sent: Optional[str] = None
        self.pending: Optional[dict] = None

    def send(self, command: str, force: bool = False) -> None:
        if not force and command == self.last_sent:
            return
        self.port.write(command.encode("ascii"))
        self.port.flush()
        self.last_sent = command

    def start_pulse(self, command: str, now: float) -> bool:
        if self.pending is not None:
            return False
        self.send("S", force=True)
        # Give the firmware's 20 ms loop an opportunity to see S before a
        # blocking sound/spin action. There is no acknowledgement from firmware.
        self.pending = {"command": command, "phase": "action", "at": now + self.pulse_seconds}
        return True

    def tick(self, now: float) -> None:
        if self.pending is None or now < self.pending["at"]:
            return
        if self.pending["phase"] == "action":
            self.send(self.pending["command"], force=True)
            self.pending["phase"] = "stop"
            self.pending["at"] = now + self.pulse_seconds
        else:
            self.send("S", force=True)
            self.pending = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read a pygame controller and send firmware command characters over USB serial."
    )
    parser.add_argument("--port", help="serial port, e.g. COM3 or /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=9600, help="must match Serial.begin() (default: 9600)")
    parser.add_argument("--joystick", type=int, default=0, help="pygame controller index (default: 0)")
    parser.add_argument("--deadzone", type=float, default=0.22, help="stick deadzone from 0.05 to 0.80")
    parser.add_argument("--loop-hz", type=int, default=50, help="controller polling rate (default: 50 Hz)")
    parser.add_argument("--left-x", type=int, default=0, help="left-stick X axis index")
    parser.add_argument("--left-y", type=int, default=1, help="left-stick Y axis index")
    parser.add_argument("--right-x", type=int, default=2, help="right-stick X axis index")
    parser.add_argument("--right-y", type=int, default=3, help="right-stick Y axis index")
    parser.add_argument("--hat", type=int, default=0, help="D-pad hat index")
    parser.add_argument("--horn-button", type=int, default=9, help="R3/horn button index; inspect with --list-controllers")
    parser.add_argument("--left-bumper-button", type=int, default=4, help="momentary counter-clockwise spin (<)")
    parser.add_argument("--right-bumper-button", type=int, default=5, help="momentary clockwise spin (>)")
    parser.add_argument(
        "--bind", action="append", type=parse_button_binding, default=[], metavar="COMMAND=BUTTON",
        help="optional pulse binding, repeatable; example: --bind=^=6 --bind=V=7 --bind=+=0",
    )
    parser.add_argument("--pulse-ms", type=int, default=40, help="stop/action pulse phase in milliseconds")
    parser.add_argument("--settle", type=float, default=2.0, help="wait after opening Uno serial (bootloader reset)")
    parser.add_argument("--list-ports", action="store_true", help="list serial ports and exit")
    parser.add_argument("--list-controllers", action="store_true", help="list pygame controller axes/buttons and exit")
    parser.add_argument("--self-test", action="store_true", help="test pure command mapping functions and exit")
    return parser


def self_test() -> None:
    assert movement_from_axes(0.0, -0.8, 0.2) == "F"
    assert movement_from_axes(0.0, 0.8, 0.2) == "B"
    assert movement_from_axes(-0.8, 0.0, 0.2) == "L"
    assert movement_from_axes(0.8, 0.0, 0.2) == "R"
    assert movement_from_axes(0.1, 0.1, 0.2) == "S"
    assert tone_from_axes(0.0, -0.8, 0.2) == "1"
    assert tone_from_axes(0.8, 0.0, 0.2) == "2"
    assert tone_from_axes(0.0, 0.8, 0.2) == "3"
    assert tone_from_axes(-0.8, 0.0, 0.2) == "4"
    assert tone_from_axes(0.0, 0.0, 0.2) is None
    assert normalize_command("h") == "H"
    assert normalize_command("v") == "V"
    assert normalize_command("c") == "c"
    assert normalize_command("C") == "C"
    print("Bridge mapping self-test passed.")


def list_ports() -> int:
    try:
        from serial.tools import list_ports
    except ImportError:
        print("pyserial is missing; install scripts/requirements.txt", file=sys.stderr)
        return 2
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
    for port in ports:
        print(f"{port.device}\t{port.description}")
    return 0


def list_controllers() -> int:
    try:
        import pygame
    except ImportError:
        print("pygame is missing; install scripts/requirements.txt", file=sys.stderr)
        return 2
    pygame.init()
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    if not count:
        print("No pygame joystick detected.")
    for index in range(count):
        joystick = pygame.joystick.Joystick(index)
        joystick.init()
        print(
            f"{index}: {joystick.get_name()} | axes={joystick.get_numaxes()} "
            f"buttons={joystick.get_numbuttons()} hats={joystick.get_numhats()}"
        )
        joystick.quit()
    pygame.quit()
    return 0


def _safe_axis(joystick, index: int) -> float:
    if 0 <= index < joystick.get_numaxes():
        return float(joystick.get_axis(index))
    return 0.0


def _safe_button(joystick, index: int) -> bool:
    return 0 <= index < joystick.get_numbuttons() and bool(joystick.get_button(index))


def _key_movement(pygame, keys) -> Optional[str]:
    x = float(keys[pygame.K_RIGHT]) - float(keys[pygame.K_LEFT])
    y = float(keys[pygame.K_DOWN]) - float(keys[pygame.K_UP])
    if x == 0.0 and y == 0.0:
        if keys[pygame.K_q]:
            return "C"
        if keys[pygame.K_e]:
            return "c"
        return None
    return movement_from_axes(x, y, 0.1)


def run_controller(args: argparse.Namespace) -> int:
    if not args.port:
        print("--port is required unless using --list-ports, --list-controllers, or --self-test", file=sys.stderr)
        return 2
    if args.baud != 9600:
        print("Warning: supplied firmware uses Serial.begin(9600); a different baud will not communicate correctly.", file=sys.stderr)
    if not 0.05 <= args.deadzone <= 0.80:
        print("--deadzone must be between 0.05 and 0.80", file=sys.stderr)
        return 2
    if args.loop_hz < 10 or args.loop_hz > 200:
        print("--loop-hz must be between 10 and 200", file=sys.stderr)
        return 2
    if not 10 <= args.pulse_ms <= 250:
        print("--pulse-ms must be between 10 and 250", file=sys.stderr)
        return 2

    try:
        import pygame
        import serial
    except ImportError as exc:
        print(f"Missing dependency: {exc}. Run: python -m pip install -r scripts/requirements.txt", file=sys.stderr)
        return 2

    pygame.init()
    pygame.joystick.init()
    if args.joystick < 0 or args.joystick >= pygame.joystick.get_count():
        print("No selected joystick. Run --list-controllers and connect the controller first.", file=sys.stderr)
        pygame.quit()
        return 2

    joystick = pygame.joystick.Joystick(args.joystick)
    joystick.init()
    instance_id = joystick.get_instance_id()
    bindings = {
        args.horn_button: "H",
        args.left_bumper_button: "<",
        args.right_bumper_button: ">",
    }
    for command, button in args.bind:
        if button in bindings:
            print(f"Button {button} already maps to {bindings[button]}; use a different button or change defaults.", file=sys.stderr)
            joystick.quit()
            pygame.quit()
            return 2
        bindings[button] = command

    serial_port = None
    window = None
    try:
        serial_port = serial.Serial(args.port, args.baud, timeout=0.05, write_timeout=0.5)
        time.sleep(max(0.0, args.settle))
        serial_port.reset_input_buffer()
        sender = CommandSender(serial_port, args.pulse_ms)
        sender.send("S", force=True)
        window = pygame.display.set_mode((640, 180))
        pygame.display.set_caption("Robot controller bridge — close/Space sends S")
        font = pygame.font.Font(None, 25)
        clock = pygame.time.Clock()
        previous_buttons: dict[int, bool] = {}
        previous_tone: Optional[str] = None
        focused = True
        print(f"Controller: {joystick.get_name()} | Serial: {args.port} @ {args.baud} baud")
        print("Left stick/arrows: F/B/L/R; neutral or Space: S; D-pad left/right: C/c.")
        print("Right stick: tones 1-4; R3: H; bumpers: < and >. Q/E spin; custom --bind for ^, V, J and speed.")
        print("This firmware has no command timeout; keep a physical power cutoff accessible.")

        running = True
        while running:
            now = time.monotonic()
            key_pulses: list[str] = []
            space_stop_event = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    raw = getattr(event, "unicode", "")
                    if raw:
                        try:
                            command = normalize_command(raw)
                        except ValueError:
                            command = None
                        if command in PULSES:
                            key_pulses.append(command)
                    if event.key == pygame.K_SPACE:
                        space_stop_event = True
                elif event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
                    focused = False
                    sender.send("S", force=True)
                elif event.type == getattr(pygame, "WINDOWFOCUSGAINED", -2):
                    focused = True
                elif event.type == pygame.JOYDEVICEREMOVED and event.instance_id == instance_id:
                    print("Selected controller disconnected; requesting S and exiting.")
                    sender.send("S", force=True)
                    running = False

            sender.tick(time.monotonic())
            keys = pygame.key.get_pressed()
            movement = "S"
            selected_tone = None
            space_stop = space_stop_event or bool(keys[pygame.K_SPACE])
            if focused and not space_stop:
                keyboard_movement = _key_movement(pygame, keys)
                if keyboard_movement is not None:
                    movement = keyboard_movement
                else:
                    x = _safe_axis(joystick, args.left_x)
                    y = _safe_axis(joystick, args.left_y)
                    movement = movement_from_axes(x, y, args.deadzone)
                    hat_spin = None
                    if 0 <= args.hat < joystick.get_numhats():
                        hat_x, _hat_y = joystick.get_hat(args.hat)
                        if hat_x < 0:
                            hat_spin = "C"
                        elif hat_x > 0:
                            hat_spin = "c"
                    if hat_spin:
                        movement = hat_spin
                    selected_tone = tone_from_axes(
                        _safe_axis(joystick, args.right_x),
                        _safe_axis(joystick, args.right_y),
                        args.deadzone,
                    )

            pressed: list[str] = []
            for button, command in sorted(bindings.items()):
                is_down = focused and _safe_button(joystick, button)
                was_down = previous_buttons.get(button, False)
                if is_down and not was_down:
                    pressed.append(command)
                previous_buttons[button] = is_down

            pulse = key_pulses[0] if key_pulses else (pressed[0] if pressed else None)
            if pulse is None and selected_tone and selected_tone != previous_tone:
                pulse = selected_tone
            previous_tone = selected_tone

            if space_stop:
                sender.pending = None
                sender.send("S", force=True)
            elif sender.pending is None and pulse is not None:
                sender.start_pulse(pulse, time.monotonic())
            elif sender.pending is None:
                sender.send(movement)

            sender.tick(time.monotonic())
            if window is not None:
                window.fill((20, 25, 34))
                lines = [
                    "Controller bridge — serial only; no firmware watchdog",
                    f"Port: {args.port}   Controller: {joystick.get_name()}",
                    f"Command: {sender.last_sent or 'S'}   Pending one-shot: {sender.pending['command'] if sender.pending else 'none'}",
                    "Left stick/arrows F/B/L/R; D-pad C/c; right stick tones 1-4; Space stop; Esc/close exit",
                ]
                for row, text in enumerate(lines):
                    window.blit(font.render(text, True, (230, 235, 242)), (16, 18 + row * 36))
                pygame.display.flip()
            if pygame.key.get_pressed()[pygame.K_ESCAPE]:
                running = False
            clock.tick(args.loop_hz)

    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1
    finally:
        if serial_port is not None:
            try:
                serial_port.write(b"S")
                serial_port.flush()
            except Exception:
                pass
            serial_port.close()
        if joystick.get_init():
            joystick.quit()
        pygame.quit()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if args.list_ports:
        return list_ports()
    if args.list_controllers:
        return list_controllers()
    return run_controller(args)


if __name__ == "__main__":
    raise SystemExit(main())

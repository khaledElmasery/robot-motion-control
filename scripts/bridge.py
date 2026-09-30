#!/usr/bin/env python3
"""PS1/X360CE controller bridge for the robot's one-byte Serial protocol.

A USB serial port or a Bluetooth Classic SPP virtual COM port can be used.
The bridge never writes newline-delimited commands; it sends raw ASCII bytes.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Optional

CONTINUOUS_COMMANDS = {"F", "B", "L", "R", "C", "c", "S", "J"}
PULSE_COMMANDS = {"^", "V", "<", ">", "H", "1", "2", "3", "4", "+", "-", "*", "/"}
VALID_COMMANDS = CONTINUOUS_COMMANDS | PULSE_COMMANDS
TIMED_ACTIONS = {"^", "V", "<", ">"}
DEFAULT_PULSE_MS = {"^": 150, "V": 150, "<": 200, ">": 200}


def normalize_command(value: str) -> str:
    """Normalize a single command while preserving lowercase clockwise `c`."""
    if len(value) != 1:
        raise ValueError("Commands must contain exactly one character.")
    if value == "c":
        command = "c"
    else:
        command = value.upper()
    if command not in VALID_COMMANDS:
        raise ValueError(f"Unsupported command: {value!r}")
    return command


def movement_from_axes(x: float, y: float, deadzone: float) -> str:
    """Convert left-stick axes to F/B/L/R/S with dominant-axis priority."""
    if abs(x) < deadzone and abs(y) < deadzone:
        return "S"
    if abs(y) >= abs(x):
        return "B" if y > 0 else "F"
    return "R" if x > 0 else "L"


def spin_from_modifier(modifier: bool, r2: bool, l2: bool) -> Optional[str]:
    """Y+R2 spins counter-clockwise; Y+L2 clockwise; both triggers stop."""
    if not modifier:
        return None
    if r2 and l2:
        return "S"
    if r2:
        return "C"
    if l2:
        return "c"
    return None


def movement_from_triggers(r2: bool, l2: bool) -> Optional[str]:
    """R2 requests forward, L2 reverse, and both triggers request stop."""
    if r2 and l2:
        return "S"
    if r2:
        return "F"
    if l2:
        return "B"
    return None


def movement_from_bumpers(l1: bool, r1: bool) -> Optional[str]:
    """L1 runs the left wheel; R1 runs the right wheel; both request stop."""
    if l1 and r1:
        return "S"
    if l1:
        return "L"
    if r1:
        return "R"
    return None


def dpad_pulse(hat: tuple[int, int], previous: tuple[int, int]) -> Optional[str]:
    """Return one timed action on a newly pressed cardinal D-pad direction."""
    if hat == previous:
        return None
    x, y = hat
    if y > 0:
        return "^"
    if y < 0:
        return "V"
    if x < 0:
        return "<"
    if x > 0:
        return ">"
    return None


def tone_from_axes(x: float, y: float, deadzone: float) -> Optional[str]:
    """Map a right-stick cardinal direction to one of four buzzer patterns."""
    if abs(x) < deadzone and abs(y) < deadzone:
        return None
    if abs(y) >= abs(x):
        return "1" if y < 0 else "3"
    return "2" if x > 0 else "4"


def _safe_axis(joystick, index: int) -> float:
    if index < 0 or index >= joystick.get_numaxes():
        return 0.0
    return float(joystick.get_axis(index))


def _safe_button(joystick, index: int) -> bool:
    return 0 <= index < joystick.get_numbuttons() and bool(joystick.get_button(index))


def _button_bindings(args: argparse.Namespace) -> dict[int, list[str]]:
    bindings: dict[int, list[str]] = {}
    pairs = (
        (args.speed_up_button, "+"),
        (args.speed_down_button, "-"),
        (args.horn_button, "H"),
    )
    for button, command in pairs:
        if button >= 0:
            bindings.setdefault(button, []).append(command)
    for specification in args.bind:
        try:
            raw_command, raw_button = specification.split("=", 1)
            command = normalize_command(raw_command)
            button = int(raw_button)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid --bind={specification!r}; use --bind=COMMAND=BUTTON.") from exc
        if command not in PULSE_COMMANDS:
            raise ValueError(f"--bind requires a one-shot command, got {command!r}.")
        if button < 0:
            raise ValueError("A custom button index must be zero or greater.")
        bindings.setdefault(button, []).append(command)
    return bindings


@dataclass
class CommandSender:
    """Deduplicate state commands but allow explicit events and periodic keepalive."""

    serial_port: object
    last_sent: Optional[str] = None

    def send(self, command: str, force: bool = False) -> bool:
        command = normalize_command(command)
        if not force and command == self.last_sent:
            return False
        self.serial_port.write(command.encode("ascii"))
        self.last_sent = command
        return True

    def heartbeat(self) -> None:
        """The firmware arms a stop-on-timeout watchdog after receiving `Z`."""
        self.serial_port.write(b"Z")


@dataclass
class SerialStatusReader:
    buffer: bytearray | None = None

    def __post_init__(self) -> None:
        if self.buffer is None:
            self.buffer = bytearray()

    def poll(self, serial_port, max_bytes: int = 1024) -> list[str]:
        waiting = min(int(getattr(serial_port, "in_waiting", 0)), max_bytes)
        if waiting <= 0:
            return []
        chunk = serial_port.read(waiting)
        if not chunk:
            return []
        self.buffer.extend(chunk)
        lines: list[str] = []
        while b"\n" in self.buffer:
            raw, _, remainder = self.buffer.partition(b"\n")
            self.buffer = bytearray(remainder)
            decoded = raw.decode("utf-8", errors="replace").strip("\r\x00 ")
            if decoded:
                lines.append(decoded)
        if len(self.buffer) > 4096:
            self.buffer = self.buffer[-1024:]
        return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bridge a PS1/X360CE controller to the robot over USB or Bluetooth Serial."
    )
    parser.add_argument("--port", help="Serial port (USB COM/tty or Bluetooth SPP virtual COM).")
    parser.add_argument("--baud", type=int, default=9600, help="Uno UART baud; default: 9600.")
    parser.add_argument("--joystick", type=int, default=0, help="pygame controller index; default: 0.")
    parser.add_argument("--left-x", type=int, default=0)
    parser.add_argument("--left-y", type=int, default=1)
    parser.add_argument("--right-x", type=int, default=5)
    parser.add_argument("--right-y", type=int, default=2)
    parser.add_argument("--hat", type=int, default=0, help="D-pad hat index; default: 0.")
    parser.add_argument("--deadzone", type=float, default=0.22)
    parser.add_argument("--forward-trigger-button", type=int, default=7, help="R2 button index; forward alone, spin with Y.")
    parser.add_argument("--reverse-trigger-button", type=int, default=6, help="L2 button index; reverse alone, spin with Y.")
    parser.add_argument("--spin-modifier-button", type=int, default=0, help="Y/triangle button index for R2/L2 spin.")
    parser.add_argument("--left-bumper-button", type=int, default=4, help="L1 button index; left-wheel action.")
    parser.add_argument("--right-bumper-button", type=int, default=5, help="R1 button index; right-wheel action.")
    parser.add_argument("--speed-up-button", type=int, default=2, help="Xbox A button index; sends +2 levels.")
    parser.add_argument("--speed-down-button", type=int, default=3, help="Xbox X button index; sends -2 levels.")
    parser.add_argument("--horn-button", type=int, default=11, help="R3/right-stick click index; sends H.")
    parser.add_argument("--bind", action="append", default=[], metavar="COMMAND=BUTTON",
                        help="Add a one-shot button binding, e.g. --bind=*=8 or --bind=1=9.")
    parser.add_argument("--loop-hz", type=int, default=50, help="Controller polling rate, 10..200 Hz.")
    parser.add_argument("--heartbeat-ms", type=int, default=100, help="Serial safety heartbeat interval; 50..250 ms.")
    parser.add_argument("--settle", type=float, default=2.0, help="Wait after opening Serial before sending commands.")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--list-controllers", action="store_true")
    parser.add_argument("--probe-controllers", action="store_true", help="Show live axes/buttons/hats without opening Serial.")
    parser.add_argument("--self-test", action="store_true", help="Test pure mapping and byte protocol without hardware.")
    return parser


def _open_pygame():
    try:
        import pygame
    except ImportError as exc:
        print(f"pygame is missing; install scripts/requirements.txt ({exc})", file=sys.stderr)
        return None
    pygame.init()
    pygame.joystick.init()
    return pygame


def list_ports() -> int:
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        print(f"pyserial is missing; install scripts/requirements.txt ({exc})", file=sys.stderr)
        return 2
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports detected.")
        return 0
    for port in ports:
        print(f"{port.device}: {port.description}")
    return 0


def list_controllers() -> int:
    pygame = _open_pygame()
    if pygame is None:
        return 2
    try:
        count = pygame.joystick.get_count()
        if count == 0:
            print("No controllers detected.")
        for index in range(count):
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
            print(
                f"[{index}] {joystick.get_name()} | axes={joystick.get_numaxes()} "
                f"buttons={joystick.get_numbuttons()} hats={joystick.get_numhats()}"
            )
            joystick.quit()
        return 0
    finally:
        pygame.quit()


def probe_controllers(index: int, loop_hz: int) -> int:
    pygame = _open_pygame()
    if pygame is None:
        return 2
    try:
        if index < 0 or index >= pygame.joystick.get_count():
            print("No selected controller. Run --list-controllers first.", file=sys.stderr)
            return 2
        joystick = pygame.joystick.Joystick(index)
        joystick.init()
        print(f"Probing {joystick.get_name()} — move one control at a time; Ctrl+C stops. No Serial port is opened.")
        clock = pygame.time.Clock()
        previous = None
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            pygame.event.pump()
            axes = tuple(round(joystick.get_axis(i), 2) for i in range(joystick.get_numaxes()))
            buttons = tuple(i for i in range(joystick.get_numbuttons()) if joystick.get_button(i))
            hats = tuple(joystick.get_hat(i) for i in range(joystick.get_numhats()))
            state = (axes, buttons, hats)
            if state != previous:
                print(f"axes={axes} buttons={buttons} hats={hats}", flush=True)
                previous = state
            clock.tick(loop_hz)
        joystick.quit()
        return 0
    except KeyboardInterrupt:
        print("\nProbe stopped.")
        return 0
    finally:
        pygame.quit()


def _key_movement(pygame, keys) -> Optional[str]:
    if keys[pygame.K_UP]:
        return "F"
    if keys[pygame.K_DOWN]:
        return "B"
    if keys[pygame.K_LEFT] and keys[pygame.K_RIGHT]:
        return "S"
    if keys[pygame.K_LEFT]:
        return "C"
    if keys[pygame.K_RIGHT]:
        return "c"
    if keys[pygame.K_a] and keys[pygame.K_d]:
        return "S"
    if keys[pygame.K_a]:
        return "L"
    if keys[pygame.K_d]:
        return "R"
    if keys[pygame.K_q] and keys[pygame.K_e]:
        return "S"
    if keys[pygame.K_q]:
        return "C"
    if keys[pygame.K_e]:
        return "c"
    return None


def _validate_mappings(args: argparse.Namespace, bindings: dict[int, list[str]]) -> None:
    if not 0.05 <= args.deadzone <= 0.8:
        raise ValueError("--deadzone must be between 0.05 and 0.8.")
    if not 10 <= args.loop_hz <= 200:
        raise ValueError("--loop-hz must be between 10 and 200.")
    if not 50 <= args.heartbeat_ms <= 250:
        raise ValueError("--heartbeat-ms must be between 50 and 250.")
    if args.settle < 0:
        raise ValueError("--settle must not be negative.")
    triggers = [index for index in (args.forward_trigger_button, args.reverse_trigger_button) if index >= 0]
    if len(triggers) != len(set(triggers)):
        raise ValueError("R2 and L2 cannot use the same button index.")
    held_actions = [index for index in (
        args.spin_modifier_button, args.left_bumper_button, args.right_bumper_button
    ) if index >= 0]
    if len(held_actions) != len(set(held_actions)):
        raise ValueError("Y modifier, L1 and R1 must use different button indexes.")
    action_indices = set(triggers) | set(held_actions)
    conflicts = action_indices & set(bindings)
    if conflicts:
        raise ValueError(f"A controller button is assigned to conflicting actions: {sorted(conflicts)}")


def run_controller(args: argparse.Namespace) -> int:
    if not args.port:
        print("Choose --port after --list-ports; for wireless mode, use the paired Bluetooth SPP COM/tty port.", file=sys.stderr)
        return 2
    try:
        bindings = _button_bindings(args)
        _validate_mappings(args, bindings)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    pygame = _open_pygame()
    if pygame is None:
        return 2
    try:
        import serial
    except ImportError as exc:
        print(f"pyserial is missing; install scripts/requirements.txt ({exc})", file=sys.stderr)
        pygame.quit()
        return 2

    if args.joystick < 0 or args.joystick >= pygame.joystick.get_count():
        print("No selected joystick. Run --list-controllers or --probe-controllers first.", file=sys.stderr)
        pygame.quit()
        return 2

    joystick = pygame.joystick.Joystick(args.joystick)
    joystick.init()
    instance_id = joystick.get_instance_id()
    configured = set(bindings) | set(index for index in (
        args.forward_trigger_button, args.reverse_trigger_button, args.spin_modifier_button,
        args.left_bumper_button, args.right_bumper_button,
    ) if index >= 0)
    for button in sorted(configured):
        if button >= joystick.get_numbuttons():
            print(f"Warning: configured button {button} is outside this controller's range.", file=sys.stderr)

    serial_port = None
    try:
        serial_port = serial.Serial(args.port, args.baud, timeout=0, write_timeout=0.5)
        time.sleep(args.settle)
        serial_port.reset_input_buffer()
        sender = CommandSender(serial_port)
        status_reader = SerialStatusReader()
        sender.send("S", force=True)
        sender.heartbeat()

        pygame.display.set_mode((800, 230))
        pygame.display.set_caption("Robot controller bridge — Space requests Stop")
        font = pygame.font.Font(None, 22)
        clock = pygame.time.Clock()
        previous_buttons: set[int] = set()
        previous_hat = (0, 0)
        previous_tone: Optional[str] = None
        speed_status = "waiting for Arduino speed command"
        focused = True
        last_heartbeat_at = time.monotonic()
        timed_action_until = 0.0

        print(f"Controller: {joystick.get_name()} | Serial/BT COM: {args.port} @ {args.baud}")
        print("Left stick: F/B/L/R. R2: forward; L2: reverse; Y+R2/L2: spin. L1/R1: one wheel.")
        print("D-pad up/down: ^/V pulses; left/right: </> timed turns. A/X: speed +2/-2.")
        print("Right stick: four buzzer patterns; R3: H. Verify every index with --probe-controllers first.")
        print("Bridge sends Z heartbeats; firmware stops motors if they cease. Keep the physical power cutoff accessible.")

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
                        if command in PULSE_COMMANDS:
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

            keys = pygame.key.get_pressed()
            movement = "S"
            selected_tone = None
            space_stop = space_stop_event or bool(keys[pygame.K_SPACE])
            if focused and not space_stop:
                keyboard_movement = _key_movement(pygame, keys)
                if keyboard_movement is not None:
                    movement = keyboard_movement
                else:
                    spin = spin_from_modifier(
                        _safe_button(joystick, args.spin_modifier_button),
                        _safe_button(joystick, args.forward_trigger_button),
                        _safe_button(joystick, args.reverse_trigger_button),
                    )
                    if spin is not None:
                        movement = spin
                    else:
                        trigger_movement = movement_from_triggers(
                            _safe_button(joystick, args.forward_trigger_button),
                            _safe_button(joystick, args.reverse_trigger_button),
                        )
                        if trigger_movement is not None:
                            movement = trigger_movement
                        else:
                            bumper = movement_from_bumpers(
                                _safe_button(joystick, args.left_bumper_button),
                                _safe_button(joystick, args.right_bumper_button),
                            )
                            if bumper is not None:
                                movement = bumper
                            else:
                                movement = movement_from_axes(
                                    _safe_axis(joystick, args.left_x),
                                    _safe_axis(joystick, args.left_y),
                                    args.deadzone,
                                )
                    selected_tone = tone_from_axes(
                        _safe_axis(joystick, args.right_x),
                        _safe_axis(joystick, args.right_y),
                        args.deadzone,
                    )

            currently_pressed = {
                button for button in bindings if focused and _safe_button(joystick, button)
            }
            button_pulses = []
            for button in sorted(currently_pressed - previous_buttons):
                button_pulses.extend(bindings[button])
            previous_buttons = currently_pressed

            hat = (0, 0)
            if focused and 0 <= args.hat < joystick.get_numhats():
                hat = joystick.get_hat(args.hat)
            hat_command = dpad_pulse(hat, previous_hat)
            previous_hat = hat

            pulses = key_pulses + button_pulses
            if hat_command is not None:
                pulses.append(hat_command)
            if selected_tone is not None and selected_tone != previous_tone:
                pulses.append(selected_tone)
            previous_tone = selected_tone

            if space_stop or not focused:
                sender.send("S", force=True)
                timed_action_until = 0.0
            elif pulses:
                for command in pulses:
                    sender.send(command, force=True)
                    if command in TIMED_ACTIONS:
                        timed_action_until = max(
                            timed_action_until,
                            now + (DEFAULT_PULSE_MS[command] + 80) / 1000.0,
                        )
            elif now >= timed_action_until:
                sender.send(movement)

            if now - last_heartbeat_at >= args.heartbeat_ms / 1000.0:
                sender.heartbeat()
                last_heartbeat_at = now

            for line in status_reader.poll(serial_port):
                print(f"[Arduino] {line}")
                if line.startswith("SPEED_LEVEL="):
                    speed_status = line

            screen = pygame.display.get_surface()
            screen.fill((24, 28, 35))
            text_lines = [
                f"Controller: {joystick.get_name()}",
                f"Movement command: {movement if focused else 'S (window not focused)'}",
                f"Arduino feedback: {speed_status}",
                "Space = Stop | close window / Ctrl+C = request S",
            "Left stick = movement | R2 = forward | L2 = reverse | Y+R2/L2 = spin",
                "A/X = speed | R1/L1 = one wheel | right stick/R3 = buzzer",
            ]
            for row, text in enumerate(text_lines):
                screen.blit(font.render(text, True, (235, 239, 244)), (16, 14 + row * 31))
            pygame.display.flip()
            clock.tick(args.loop_hz)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted; requesting S before closing.")
        return 0
    except Exception as exc:
        try:
            import serial
            if isinstance(exc, serial.SerialException):
                print(f"Serial error: {exc}", file=sys.stderr)
                return 3
        except ImportError:
            pass
        print(f"Bridge error: {exc}", file=sys.stderr)
        return 3
    finally:
        if serial_port is not None:
            try:
                serial_port.write(b"S")
                serial_port.flush()
                serial_port.close()
            except Exception:
                pass
        joystick.quit()
        pygame.quit()


def self_test() -> None:
    assert normalize_command("v") == "V"
    assert normalize_command("c") == "c"
    assert movement_from_axes(0.0, -0.8, 0.22) == "F"
    assert movement_from_axes(0.0, 0.8, 0.22) == "B"
    assert movement_from_axes(-0.8, 0.0, 0.22) == "L"
    assert movement_from_axes(0.0, 0.0, 0.22) == "S"
    assert spin_from_modifier(True, True, False) == "C"
    assert spin_from_modifier(True, False, True) == "c"
    assert spin_from_modifier(True, True, True) == "S"
    assert spin_from_modifier(False, True, False) is None
    assert movement_from_triggers(True, False) == "F"
    assert movement_from_triggers(False, True) == "B"
    assert movement_from_triggers(True, True) == "S"
    assert movement_from_triggers(False, False) is None
    assert movement_from_bumpers(True, False) == "L"
    assert movement_from_bumpers(False, True) == "R"
    assert movement_from_bumpers(True, True) == "S"
    assert dpad_pulse((0, 1), (0, 0)) == "^"
    assert dpad_pulse((0, -1), (0, 0)) == "V"
    assert dpad_pulse((-1, 0), (0, 0)) == "<"
    assert dpad_pulse((1, 0), (0, 0)) == ">"
    assert dpad_pulse((1, 0), (1, 0)) is None
    assert dpad_pulse((0, 0), (1, 0)) is None
    assert tone_from_axes(0.0, -0.8, 0.22) == "1"
    assert tone_from_axes(0.8, 0.0, 0.22) == "2"
    assert tone_from_axes(0.0, 0.8, 0.22) == "3"
    assert tone_from_axes(-0.8, 0.0, 0.22) == "4"

    class FakeSerial:
        def __init__(self):
            self.data = bytearray()

        def write(self, payload):
            self.data.extend(payload)
            return len(payload)

    fake = FakeSerial()
    sender = CommandSender(fake)
    assert sender.send("F") is True
    assert sender.send("F") is False
    assert sender.send("F", force=True) is True
    sender.heartbeat()
    assert bytes(fake.data) == b"FFZ"
    assert b"\n" not in fake.data and b"\r" not in fake.data
    print("Bridge self-test passed: mappings, one-shot D-pad, speed-independent controls, and raw Serial heartbeat.")


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.list_ports:
        return list_ports()
    if args.list_controllers:
        return list_controllers()
    if args.probe_controllers:
        if not 10 <= args.loop_hz <= 200:
            print("--loop-hz must be between 10 and 200", file=sys.stderr)
            return 2
        return probe_controllers(args.joystick, args.loop_hz)
    if args.port is None:
        print("Use --port COMx or --port /dev/tty...; inspect available ports with --list-ports.", file=sys.stderr)
        return 2
    return run_controller(args)


if __name__ == "__main__":
    raise SystemExit(main())

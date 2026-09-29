# Controller Mapping / خريطة التحكم

The Python bridge reads a wired PS1-style controller exposed to pygame as a joystick and sends one ASCII byte at a time to the Uno at **9600 baud**. Default raw pygame mapping is conventional but controller-dependent; inspect your device with `python scripts/bridge.py --list-controllers` and adjust command-line indices if needed.

## Default physical mapping

| Input | Character sent | Firmware action |
|---|---|---|
| Left stick up | `F` | Drive both motors forward at `currentPWM`, unless the front-distance condition blocks it |
| Left stick down | `B` | Drive both motors backward |
| Left stick left | `L` | Run only the left motor; this is not differential steering |
| Left stick right | `R` | Run only the right motor; this is not differential steering |
| Left stick neutral | `S` | Stop both motor channels |
| D-pad left / right | `C` / lowercase `c` | Continuous counter-clockwise / clockwise spin |
| Right stick up / right / down / left | `1` / `2` / `3` / `4` | Play the associated tone sequence; vertical wins on diagonal inputs |
| R3 / right-stick button (default button index 9) | `H` | 1 kHz, 150 ms horn tone |
| Left / right bumper (default indices 4 / 5) | `<` / `>` | Counter-clockwise / clockwise spin for a fixed 200 ms, then stop; this is not a calibrated 45° turn |
| Optional `--bind COMMAND=BUTTON` | Selected one-shot character | Bind `^`, `V`, `J`, `+`, `-`, `*`, `/`, or another one-shot action to a local button index |

Stick axes default to left X/Y = 0/1 and right X/Y = 2/3, with a 0.22 deadzone. Change them with `--left-x`, `--left-y`, `--right-x`, and `--right-y`. Default D-pad hat index is 0. The bridge favors vertical direction on diagonals. It releases movement by sending `S` when the stick/keys return to neutral.

Example optional bindings (button indexes vary by controller):

```bash
python scripts/bridge.py --port COM3 \\
  --bind=^=6 --bind=V=7 --bind=J=8 \\
  --bind=+=0 --bind=-=1 --bind='*=2' --bind=/=3
```

Keyboard fallback when the pygame window is focused: arrow keys send movement, Space sends `S`, Q/E hold `C`/`c`, number keys 1–4 and `h` trigger tones, and `+`, `-`, `*`, `/`, `^`, `v`, `j`, `<`, `>` trigger one-shot commands. A one-shot request is bracketed by stop bytes; due to the firmware’s blocking delays and lack of acknowledgements, exact timing cannot be guaranteed.

## Firmware character table

| Character | Firmware action |
|---|---|
| `F` | `driveForward()`; blocked only when distance is below 15 cm |
| `B` | `driveBackward()` |
| `L` | Energize left motor only |
| `R` | Energize right motor only |
| `S` | Stop both motors |
| `C` | Continuous counter-clockwise spin |
| `c` | Continuous clockwise spin on USB serial |
| `<` / `>` | Counter-clockwise / clockwise spin for 200 ms, then stop |
| `^` | If smoothed pitch value is above +15, drive forward at PWM 255 for 150 ms; ignored otherwise. The HC‑SR04 cutoff also applies to this command. |
| `V` | If smoothed pitch value is below -15, drive backward at PWM 255 for 150 ms |
| `J` | Set PWM to 100 and drive forward; stopped by the distance check below 15 cm |
| `H` | 1 kHz horn, 150 ms |
| `1` | Two-note 500/650 Hz tone |
| `2` | Short repeated notes followed by 698/880 Hz notes |
| `3` | 200 Hz tone, 400 ms |
| `4` | Three alternating 800/1200 Hz siren cycles |
| `+` / `-` | Adjust speed level by +2 / -2, bounded 1–10 |
| `*` / `/` | Set speed level to 10 / decrement by 1 |

The speed adjustment function runs each time the main loop processes the stored command. The bridge emits these as short pulses, but there is no firmware acknowledgement; do not hold a speed command expecting a single increment.

## Exact case behavior

- **USB Serial (Uno path):** CR and LF are ignored. Lowercase `c` is preserved as clockwise spin; other characters pass through `toupper()`, so `h`→`H`, `v`→`V`, and lowercase letters such as `f`→`F`.
- **ESP32 Bluetooth path in the source:** every non-newline byte is uppercased. Therefore lowercase `c` becomes `C` and cannot select the USB path’s clockwise `c` behavior. This optional path is not built or validated here.
- The source recognizes a one-character command, not a framed/checksummed protocol. It has no acknowledgement, sequence number, or firmware-side timeout.

# Arduino Robot Controller / متحكم الروبوت بأردوينو

![C++](https://img.shields.io/badge/C%2B%2B-Arduino-00599C?logo=cplusplus&logoColor=white) ![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white) ![PlatformIO](https://img.shields.io/badge/PlatformIO-Uno%20build-orange?logo=platformio&logoColor=white) ![Version](https://img.shields.io/badge/version-pre--release-blue) ![License](https://img.shields.io/badge/license-not%20specified-lightgrey)

> **Important / مهم:** The supplied firmware is a prototype, not a certified safety system. It has a basic forward-distance cutoff, but an ultrasonic timeout is treated as “clear”; it has no firmware command watchdog, and it does not implement PID self-balancing. Test only in a controlled, supervised setup with the wheels raised and a physical power cutoff available. / البرنامج نموذج أولي وليس نظام أمان معتمدًا: عند فشل قراءة HC‑SR04 تُعامل المسافة على أنها خالية، ولا توجد مهلة مراقبة لأوامر الاتصال ولا يوجد اتزان PID.

## Contents / المحتويات

- [Project scope](#project-scope--نطاق-المشروع)
- [Current features](#current-firmware--القدرات-الحالية)
- [Hardware](#hardware--المكونات)
- [Architecture](#architecture--البنية)
- [Quick start](#quick-start--البدء-السريع)
- [Serial protocol](#serial-protocol--بروتوكول-serial)
- [Safety and limitations](#safety-and-limitations--السلامة-والقيود)
- [Future roadmap](#future-roadmap--خارطة-المستقبل)
- [Repository layout](#repository-layout--هيكل-المستودع)
- [License](#license)

## Project scope / نطاق المشروع

A small four-wheel chassis (two driven DC motors and two caster wheels) is controlled by an Arduino Uno through an L298N motor driver. A wired PlayStation-style controller, exposed to the PC as an Xbox-compatible joystick, is read by a Python `pygame` bridge; the bridge sends one-character commands over USB serial at **9600 baud**. The firmware also supports an ESP32 Bluetooth code path behind `#ifdef ESP32`, but this repository builds only for the Uno because the supplied pin definitions are Uno-specific.

يتحكم Arduino Uno بهيكل رباعي العجلات: محركان دافِعان وعجلتا caster. يقرأ برنامج Python ذراع التحكم عبر `pygame` ويرسل أحرفًا منفردة عبر USB Serial بسرعة **9600 baud**. توجد وصلة Bluetooth مشروطة لـESP32 في المصدر، لكن إعداد البناء الحالي خاص بـUno فقط لأن توزيع الأرجل المرفق خاص به.

## Current firmware / القدرات الحالية

- Manual motor commands: forward/backward, one-motor-only left/right commands, and continuous clockwise/counter-clockwise spin.
- MPU6050: reads two acceleration bytes, applies a simple exponential smoothing step, and uses the result for tilt-triggered actions. **This is not a continuous balance controller or a validated pitch-angle calculation.**
- HC‑SR04: measures front distance; a reading below 15 cm stops motors for forward, `J`, or `^` commands. This is a narrow cutoff, not full obstacle avoidance. A timed-out echo becomes 999 cm, so sensor failure is fail-open.
- Passive buzzer: command `H` and tones `1`–`4`.
- Speed-level controls `+`, `-`, `*`, `/`; four LED pins are initialized, while current firmware switches LED1 and LED4 at high speed.
- Serial input is read in a `while (Serial.available() > 0)` loop. USB input is uppercased except lowercase `c`, which is preserved for clockwise spin.

القدرات الحالية موصوفة كما ينفذها المصدر فعلًا؛ لا يُدّعى وجود اتزان ذاتي أو منع اصطدام شامل. راجع [خريطة الأوامر](docs/CONTROLLER_MAPPING.md) و[قيود السلامة](docs/SAFETY_AND_TESTING.md).

## Hardware / المكونات

The intended build uses Arduino Uno R3, an L298N, two DC motors, two caster wheels, MPU6050, HC‑SR04, a passive buzzer, four red LEDs, a 3-cell 18650 pack, power switch, and a wired controller connected to a PC. The listed IR receiver is only configured as an input pin; there is no IR protocol decoder yet. See [WIRING_AND_HARDWARE.md](docs/WIRING_AND_HARDWARE.md) for the current pin table and components awaiting software integration.

## Architecture / البنية

```text
PS1-style controller → pygame on PC → USB serial (9600 baud) → Arduino Uno
                                                           ├─ L298N → two DC motors
                                                           ├─ MPU6050 (I²C)
                                                           ├─ HC-SR04 (basic forward cutoff)
                                                           ├─ passive buzzer
                                                           └─ status LEDs
```

The firmware is the source of truth for command behavior. The PC bridge requests `S` when controls return to neutral, when the controller disconnects, and on exit. Because the firmware has no serial timeout, an unplugged bridge cannot guarantee that a previously received movement command will stop.

## Quick start / البدء السريع

### 1. Build and upload the Uno firmware

Install [PlatformIO Core](https://platformio.org/install/cli) or the PlatformIO IDE, then from the repository root:

```bash
pio run -e uno
pio run -e uno -t upload
pio device monitor -e uno
```

The monitor is set to 9600 baud and includes `send_on_enter`; the firmware ignores CR/LF and accepts command characters. Close the monitor before opening the same serial port from Python.

### 2. Install the controller bridge

Use Python 3.10 or newer:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r scripts/requirements.txt
python scripts/bridge.py --list-ports
python scripts/bridge.py --list-controllers
python scripts/bridge.py --port /dev/ttyACM0  # Linux example
# Windows example: python scripts/bridge.py --port COM3
```

The bridge defaults to 9600 baud, left-stick axes 0/1, right-stick axes 2/3, D-pad hat 0, R3/button 9 for `H`, and bumpers 4/5 for momentary `<`/`>`. Controller button numbering varies; use `--list-controllers` and change the options as needed. Commands without a specified physical button can be bound with repeatable `--bind COMMAND=BUTTON`, for example `--bind=^=6 --bind=V=7 --bind=+=0`.

Run the no-hardware mapping checks with:

```bash
python scripts/bridge.py --self-test
```

## Serial protocol / بروتوكول Serial

The bridge writes a single ASCII byte, not a JSON packet. The Uno firmware starts Serial at 9600. Commands include `F`, `B`, `L`, `R`, `S`, `C`, lowercase `c`, `<`, `>`, `^`, `V`, `J`, `H`, digits `1`–`4`, and speed controls `+`, `-`, `*`, `/`. Exact behavior and the USB/Bluetooth case distinction are documented in [CONTROLLER_MAPPING.md](docs/CONTROLLER_MAPPING.md).

## Safety and limitations / السلامة والقيود

- The distance cutoff is not a safety-rated collision-avoidance system: it is front-only, limited to selected forward commands, and treats an echo timeout as clear space.
- The firmware contains blocking `delay()` calls for tones, turns, and tilt actions. While blocked, it cannot process fresh serial commands.
- There is no firmware command timeout or acknowledgement. The bridge’s `S` request is best effort and cannot be delivered after a broken link.
- The MPU6050 code does not implement continuous PID balancing. Do not claim or expect self-balancing.
- A four-cell/three-cell battery pack and L298N wiring must be checked against the actual modules, current draw, and regulator ratings. Disconnect motor power while rewiring.
- Physical verification has not been performed by this repository workflow. See [SAFETY_AND_TESTING.md](docs/SAFETY_AND_TESTING.md).

## Future roadmap / خارطة المستقبل

1. Add an IR decoder only after choosing and validating the receiver/library and remote codes.
2. Replace the simple tilt estimate with a calibrated, validated angle estimator and a properly tuned balancing controller; this is not currently present.
3. Improve HC‑SR04 safety to fail closed on sensor errors, cover relevant motion directions, and test stopping distance. The current `<15 cm` check is only a basic forward cutoff.
4. Remove blocking work from the motor-control loop and add a firmware-side communication watchdog plus an independent emergency stop.
5. Port to a specific ESP32 board only after publishing and electrically verifying a board-specific pin map and 3.3 V protection.

## Repository layout / هيكل المستودع

```text
src/main.cpp                         # latest user-supplied firmware; whitespace-only cleanup
scripts/bridge.py                    # pygame controller → USB serial
scripts/requirements.txt             # Python dependencies
platformio.ini                       # Arduino Uno environment only
docs/WIRING_AND_HARDWARE.md          # wiring, power, and future components
docs/CONTROLLER_MAPPING.md           # input/character/action table
docs/SAFETY_AND_TESTING.md           # limits and bench checklist
CHANGELOG.md
.github/ISSUE_TEMPLATE/              # bug report and feature request
```

## License

No license has been selected or included. Until the owner adds one, reuse and redistribution permissions are not specified. The badge above deliberately says “not specified.”

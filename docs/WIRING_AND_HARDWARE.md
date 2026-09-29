# Wiring and Hardware / التوصيلات والمكونات

This document separates **connections referenced by the current source** from components reserved for later integration. Pin names are for an **Arduino Uno R3 only**; do not reuse this table for an ESP32.

## Current Arduino Uno pin map

| Function | Arduino Uno pin | Firmware use | Notes |
|---|---:|---|---|
| L298N ENA | D5 | `analogWrite()` left-channel PWM | PWM output |
| L298N IN1 / IN2 | D6 / D7 | Left motor direction | Direction truth table is in the source |
| L298N IN3 / IN4 | D8 / D9 | Right motor direction | Direction is reversed in `driveForward()` to align wheel rotation |
| L298N ENB | D10 | `analogWrite()` right-channel PWM | PWM output |
| LED 1 / 2 / 3 / 4 | D11 / D12 / D13 / D4 | Outputs initialized; current `flashLEDs()` toggles LED1 and LED4 only | Use a suitable series resistor, e.g. 220–330 Ω, for each LED |
| Passive buzzer | A0 | `tone()` output | The source sets `BUZZER_PIN` to A0 |
| HC‑SR04 TRIG / ECHO | D2 / D3 | `pulseIn()` distance measurement | Echo timeout is 25 ms; Uno input is 5 V tolerant |
| MPU6050 SDA / SCL | A4 / A5 | I²C, address `0x68` | Uno hardware I²C pins; INT is not used |
| IR receiver output | A1 | `pinMode(INPUT)` only | No decoder, command mapping, or validated signal level yet |
| USB serial | D0/D1 via board USB | `Serial.begin(9600)` | Connect PC through the Uno USB interface; close serial monitor before bridge |

### Motor direction reference

| Firmware action | Left motor IN1/IN2 | Right motor IN3/IN4 | PWM |
|---|---|---|---|
| Forward | HIGH / LOW | LOW / HIGH | `currentPWM` on both channels |
| Backward | LOW / HIGH | HIGH / LOW | `currentPWM` on both channels |
| Clockwise spin | HIGH / LOW | HIGH / LOW | `currentPWM` on both channels |
| Counter-clockwise spin | LOW / HIGH | LOW / HIGH | `currentPWM` on both channels |
| Stop | LOW / LOW | LOW / LOW | 0 on both channels |
| `L` / `R` | One channel energized | Other channel stopped | `currentPWM` on one channel |

Verify motor orientation with the wheels raised before placing the chassis on the floor. The words “left” and “right” describe the firmware channels; wiring orientation may differ on a physical chassis.

## Chassis and parts

The stated chassis is four-wheeled: two DC motors drive the chassis and two passive caster wheels support it. The stated parts also include Arduino Uno R3, an ESP32 DevKit for a future transition, MPU6050, HC‑SR04, L298N dual H-bridge, passive buzzer, four red LEDs, an IR receiver, a three-cell 18650 battery pack, holder, and main power switch. Only the elements in the pin table are currently used as described by firmware; an IR receiver is initialized but not decoded.

## Power and electrical safety

- A 3-cell lithium-ion pack in series is nominally about 11.1 V and reaches 12.6 V when fully charged. Use a protected, correctly assembled/charged pack and a suitable charger; verify the exact cell and BMS ratings.
- Power the motors through the L298N motor-supply input, using a supply within the exact module and motor ratings. Do not assume the L298N’s onboard regulator can safely power the Uno, ESP32, or sensors.
- Use a regulated logic supply appropriate for the Uno and sensor breakout boards. Join grounds where required, but keep motor current paths away from sensitive sensor wiring.
- Do not connect the raw battery pack to the Uno 5 V pin, MPU6050, or ESP32. Disconnect motor/battery power before changing wires.
- Verify the MPU6050 breakout’s voltage and logic-level limits from its own documentation; breakout boards differ.
- The Uno can accept a 5 V HC‑SR04 Echo signal. If an ESP32 is later used, its GPIO is not 5 V tolerant: add a correctly calculated divider/level shifter before Echo and check every other signal direction.
- Use an accessible physical power switch/emergency cutoff. Software stop requests are not a substitute.

## Future components / خارطة مكونات المرحلة التالية

- **HC‑SR04:** this is now read by the supplied firmware on D2/D3 and stops selected forward commands below 15 cm. It is not full obstacle avoidance; a timed-out echo is assigned 999 cm (treated as clear), reverse/turning paths are not protected, and stopping distance depends on the chassis.
- **IR receiver:** A1 is configured as input, but the source does not decode IR pulses or map remote buttons. Do not expect IR control yet.
- **MPU6050/PID:** I²C is initialized and two acceleration bytes are smoothed into a rough value used by tilt actions. There is no continuous PID self-balancing controller or validated calibration routine.
- **Mode switch:** no mode switch pin or mode-selection behavior appears in the source.

## ESP32 transition — not supported by this pin map

The source’s pin macros (`D5`–`D13`, `A0`, `A1`, `D2`, `D3`) are Uno-specific. The optional `#ifdef ESP32` block starts a Bluetooth serial name, but this does not provide a validated ESP32 pin assignment or a separate tested PlatformIO environment. Several GPIOs numbered 6–11 are flash-connected on common ESP32 modules, and `A0` is not generally a suitable buzzer output. **Do not wire or power an ESP32 using the Uno table.** Select the exact board, create a separate verified pin map, account for 3.3 V logic, then test it as a separate port.

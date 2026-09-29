# Safety and Testing / السلامة والاختبار

## Status

This is an experimental motor-control project, **not a safety-rated robot**. The current source has a limited front-distance stop but does not guarantee collision avoidance. It does not implement a continuous PID balancing controller. No physical hardware was available for this repository update, so none of the checks below are represented as hardware tests.

## Known technical limitations

1. **HC‑SR04 is fail-open on timeout.** `updateDistance()` assigns 999 cm if `pulseIn()` times out. The stop condition is only `globalDistanceCM < 15` while the current command is `F`, `J`, or `^`. A disconnected/miswired sensor or an unmeasured/angled surface can therefore look clear. Reverse, single-motor, and spin commands are not checked by that condition. This is a basic forward cutoff, not reliable all-direction obstacle protection.
2. **Blocking work delays commands.** The main loop has a 20 ms delay; `pulseIn()` may wait up to 25 ms; tone patterns, `>`/`<`, and `^`/`V` use additional `delay()` calls. During those waits the firmware cannot fetch a fresh stop command.
3. **No communications watchdog.** The last value remains in `globalCommand` until another serial/Bluetooth character arrives. If a link is unplugged after a motion command, the firmware does not automatically stop. The bridge sends `S` on neutral, window focus loss, controller disconnect, and exit only when the serial link is still usable; this is best effort, not a failsafe.
4. **No PID balance loop.** MPU6050 reads two bytes and linearly scales one accelerometer axis to a rough value with smoothing. There is no gyro fusion, calibration validation, or continuous feedback controller. The `^`/`V` commands are threshold-triggered short movements, not balancing.
5. **IR is not decoded.** `IR_PIN` is configured as an input only. No library, protocol, remote-code capture, or IR command path is implemented.
6. **ESP32 pins are not ported.** The shared pin macros and A0 buzzer definition are Uno-specific. Do not use the Uno wiring table on an ESP32.
7. **Command semantics persist.** The firmware stores `globalCommand`; one-shot actions depend on serial command ordering, and there is no acknowledgement. Speed updates may repeat if the corresponding character remains the stored command.

## Bench checklist

Perform these checks only with an experienced operator, a clear test area, and a physical power cutoff reachable. Keep hands, loose clothing, cables, and objects away from wheels and gears. **Start with motor power disconnected and wheels raised.**

1. Verify the board is an Arduino Uno R3 and check every wire against `WIRING_AND_HARDWARE.md`; do not infer ESP32 wiring from it.
2. Check polarity, common ground, L298N/motor voltage and current ratings, battery protection, and regulated logic power. Keep the battery disconnected while wiring.
3. With motor power still disconnected, build with `pio run -e uno` and upload the firmware. Open the serial monitor at 9600 baud and test one command at a time.
4. With wheels raised and low-risk power available, test `S`, then each motor channel briefly. Confirm the physical forward/backward direction before any floor test.
5. Verify HC‑SR04 readings through test instrumentation or a safe fixture. Test an obstacle under 15 cm, then disconnect or obstruct Echo and confirm that the current source reports/assumes 999 cm; document that this latter case is **not safe** and must not be treated as a successful safety test.
6. Confirm the bridge mapping with `python scripts/bridge.py --self-test`; then connect a controller, check the displayed axis/button counts, and test `S` before each movement command.
7. Verify a physical emergency power cutoff independently of software. Do not test near people, pets, fragile objects, stairs, traffic, or an unattended area.
8. Do not proceed to unrestrained movement or payload operation until the sensor failure mode, serial-loss behavior, stopping distance, and motor-control loop have been redesigned and validated on the actual chassis.

## Release claims

Until those limitations are addressed and verified, describe this as a **manually controlled prototype with a limited forward distance cutoff**. Do not advertise it as self-balancing, autonomous, collision-proof, or safe for unsupervised movement. Software tests and a successful compile cannot establish the mechanical or electrical safety of the assembled robot.

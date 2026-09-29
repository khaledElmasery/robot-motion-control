# Changelog

All notable repository changes are recorded here. This project has not yet published a tagged release.

## Unreleased — repository modernization

- Replaced the prior imported project tree in the active repository with a clean Arduino Uno/PlatformIO layout; the earlier Git commit remains in history for recovery.
- Added the **latest** user-provided firmware as `src/main.cpp`; only trailing whitespace was removed, with no logic, pin, hardware, or control-character changes. The earlier firmware snapshot is not used.
- Added the pygame/pyserial USB bridge and documented its default axis/button assumptions and configurable bindings.
- Added Uno wiring, controller mapping, safety/testing, setup, and roadmap documentation.
- Clarified the implemented but limited HC‑SR04 cutoff, the unimplemented IR decoder and PID balance controller, serial-loss behavior, and Uno-only pin map.
- Added PlatformIO monitor configuration, Python dependency pins, `.gitignore`, and GitHub issue templates.
- No hardware validation or release tag was created as part of this update.

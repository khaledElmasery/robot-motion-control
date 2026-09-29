---
name: Bug report
about: Report a reproducible firmware, bridge, build, or documentation problem
title: "[Bug]: "
labels: bug
assignees: ""
---

## Summary
Describe the problem clearly.

## Environment
- Firmware commit/version:
- Board (exact model):
- Operating system:
- Python version:
- PlatformIO version:
- Controller model / pygame button and axis counts:
- Wiring changes from `docs/WIRING_AND_HARDWARE.md`:

## Reproduction steps
1.
2.
3.

## Expected behavior
What did you expect?

## Actual behavior
What happened? Include relevant serial output or logs, with secrets removed.

## Safety impact
- Did a motor move unexpectedly? If yes, state which command and test setup.
- Was the chassis restrained and the wheels raised?
- Was the physical power cutoff available?
- Did HC-SR04 report a valid distance, or did its Echo time out?

> Do not include API tokens, Wi-Fi passwords, personal information, or unredacted device credentials. Do not reproduce a hazardous behavior around people or property.

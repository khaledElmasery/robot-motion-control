#!/usr/bin/env python3
"""Build the Uno firmware and run Wokwi CI scenarios without persisting secrets."""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parents[1]
BASE_DIAGRAM = PROJECT_DIR / "diagram.json"


def require_tools() -> None:
    missing = [name for name in ("pio", "wokwi-cli") if shutil.which(name) is None]
    if missing:
        raise SystemExit("Required command(s) not found: " + ", ".join(missing))
    if not os.environ.get("WOKWI_CLI_TOKEN"):
        raise SystemExit(
            "WOKWI_CLI_TOKEN is not set. Configure it securely in the current shell; "
            "do not place it in this repository or paste it into chat."
        )


def make_variant(source: dict, path: Path, *, distance: str, disconnect_echo: bool = False) -> None:
    diagram = copy.deepcopy(source)
    sonar = next(part for part in diagram["parts"] if part["id"] == "sonar")
    sonar.setdefault("attrs", {})["distance"] = distance
    if disconnect_echo:
        diagram["connections"] = [
            connection
            for connection in diagram["connections"]
            if not ({"sonar:ECHO", "uno:3"} <= set(connection[:2]))
        ]
    path.write_text(json.dumps(diagram, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    require_tools()
    print("Building Uno firmware with PlatformIO...")
    subprocess.run(["pio", "run", "-e", "uno"], cwd=REPO_ROOT, check=True)

    source = json.loads(BASE_DIAGRAM.read_text(encoding="utf-8"))
    tests = [
        ("forward_clear.yaml", "40", False),
        ("obstacle_blocked.yaml", "10", False),
        ("echo_invalid.yaml", "40", True),
        ("speed_and_stop.yaml", "40", False),
        ("watchdog_stop.yaml", "40", False),
        ("tilt_pulse.yaml", "40", False),
    ]

    with tempfile.TemporaryDirectory(prefix=".wokwi-run-", dir=PROJECT_DIR) as tmp:
        temp_root = Path(tmp)
        for index, (scenario_name, distance, disconnect_echo) in enumerate(tests, start=1):
            diagram_path = temp_root / f"diagram_{index}.json"
            make_variant(
                source,
                diagram_path,
                distance=distance,
                disconnect_echo=disconnect_echo,
            )
            args = [
                "wokwi-cli",
                ".",
                "--diagram-file",
                diagram_path.relative_to(PROJECT_DIR).as_posix(),
                "--scenario",
                f"scenarios/{scenario_name}",
                "--timeout",
                "8000",
            ]
            print(f"\n[{index}/{len(tests)}] {scenario_name}", flush=True)
            subprocess.run(args, cwd=PROJECT_DIR, check=True)

    print("\nAll Wokwi scenarios completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(f"Simulation/build failed with exit code {error.returncode}.", file=sys.stderr)
        raise SystemExit(error.returncode)

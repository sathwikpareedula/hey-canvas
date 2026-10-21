"""Run the 100-student generic matrix via frontend vitest (sanitized stdout)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


def main() -> int:
    cmd = [
        "npm",
        "run",
        "test",
        "--",
        "--run",
        "src/lib/acceptance/student-profile-matrix.test.ts",
        "src/lib/acceptance/tenancy-isolation.test.ts",
    ]
    proc = subprocess.run(cmd, cwd=FRONTEND, check=False)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())

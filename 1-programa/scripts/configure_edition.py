from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara Lankdea Local para Buildozer.")
    parser.add_argument("--edition", choices=("local",), default="local")
    parser.parse_args()
    shutil.copy2(ROOT / "buildozer.local.spec", ROOT / "buildozer.spec")
    print("Lankdea Local preparada. Sin servicios nube.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

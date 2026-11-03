#!/usr/bin/env python3
"""What the recogniser's separate environment actually resolved to, recorded from the venv itself.

A rate measured with a model is a rate measured with a particular build of it. The setup script
beside this one states the pins; this records what they resolved to on the machine that ran the
measurement, so the two can be compared rather than assumed equal.

    python scripts/typed_edit/record_ocsr_environment.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _provenance import record_inputs, stamp  # noqa: E402

VENV = Path.home() / "grail-ocsr" / "venv"
SETUP = ROOT / "scripts" / "setup_ocsr_venv.sh"
OUT = ROOT / "revision" / "ocsr_calibration" / "environment.json"
# The packages whose versions decide whether the thing runs at all, as opposed to the hundred
# that come along. Each of these moved during the install and had to be put back.
LOAD_BEARING = ("torch", "numpy", "opencv-python", "molscribe", "timm", "albumentations",
                "rdkit-pypi", "OpenNMT-py", "torchvision", "SmilesPE")


def _key(name: str) -> str:
    """A distribution name as PEP 503 compares them: case and separators do not count.

    Written after looking the packages up by the name this file spells them with, which reported
    MolScribe itself absent from the environment it had just been installed into.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def freeze() -> dict:
    if not (VENV / "bin" / "pip").exists():
        raise SystemExit(f"REFUSING: no environment at {VENV}; build it with "
                         f"{SETUP.relative_to(ROOT)}")
    out = subprocess.run([str(VENV / "bin" / "pip"), "freeze"],
                         capture_output=True, text=True, check=True).stdout
    got = {}
    for line in out.splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            got[name] = version
    return got


def main() -> int:
    resolved = freeze()
    version = subprocess.run([str(VENV / "bin" / "python"), "-V"],
                             capture_output=True, text=True, check=True).stdout.strip()
    index = {_key(name): version for name, version in resolved.items()}
    missing = [p for p in LOAD_BEARING if _key(p) not in index]
    blob = {
        "provenance": stamp(__file__),
        "inputs": record_inputs([SETUP]),
        "what_this_is": "the resolved versions of the separate environment the image recogniser "
                        "runs in, recorded from the environment that produced the measurement",
        "python": version,
        # Recorded relative to the home directory: an absolute path says who ran it and
        # on which machine, and seven tracked files here already carry one.
        "venv": "~/" + str(VENV.relative_to(Path.home())),
        "load_bearing": {p: index.get(_key(p)) for p in LOAD_BEARING},
        "absent_though_load_bearing": missing,
        "n_packages": len(resolved),
        "packages": dict(sorted(resolved.items())),
        "reading": "torch below 2 is MolScribe's pin, numpy below 2 is torch 1.13's, and OpenCV "
                   "below 5 is numpy's: installing MolScribe raises the last two and the setup "
                   "script puts them back. A rate measured here belongs to these versions.",
    }
    OUT.write_text(json.dumps(blob, indent=1))
    print(f"{version}, {len(resolved)} packages")
    for p in LOAD_BEARING:
        print(f"  {p:<20} {index.get(_key(p)) or 'ABSENT'}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

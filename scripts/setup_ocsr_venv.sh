#!/usr/bin/env bash
# The separate environment the image recogniser needs, and the order it has to be built in.
#
# MolScribe pins torch below 2. Torch 1.13 was built against numpy 1, and the project's own stack
# pins numpy below 2 as well, for an unrelated reason: nothing else is shared between them, so
# they are kept in separate interpreters and only a CSV passes between.
#
# The order below is not cosmetic. Installing molscribe pulls transitive dependencies that raise
# numpy to 2 and OpenCV to 5, and OpenCV 5 requires numpy 2, so the last two lines put both back
# and are what makes torch able to convert a tensor to an array at all. Nothing here is a guess:
# every pin was arrived at by installing, watching what moved, and exercising the boundary.
#
# Python 3.10 is required and not a preference: torch 1.13 publishes no macOS arm64 wheel for 3.11.
set -euo pipefail

HOME_DIR="${OCSR_HOME:-$HOME/grail-ocsr}"
PYTHON="${OCSR_PYTHON:-python3.10}"

"$PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 10), sys.version' \
  || { echo "REFUSING: $PYTHON is not 3.10, and torch 1.13 has no wheel for anything else"; exit 1; }

mkdir -p "$HOME_DIR/weights"
"$PYTHON" -m venv "$HOME_DIR/venv"
PIP="$HOME_DIR/venv/bin/pip"

"$PIP" install --upgrade pip wheel setuptools
"$PIP" install "torch==1.13.1" "torchvision==0.14.1"
"$PIP" install molscribe huggingface_hub
"$PIP" install "opencv-python<5" "opencv-python-headless<5"
"$PIP" install "numpy<2"

"$HOME_DIR/venv/bin/python" - <<'PY'
# Exercising the boundary, not importing across it: an import succeeds under a numpy the library
# cannot actually use.
import numpy as np, cv2, torch, albumentations as A
img = (np.random.default_rng(0).random((64, 64, 3)) * 255).astype(np.uint8)
assert cv2.resize(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), (32, 32)).shape == (32, 32)
assert abs(float(torch.from_numpy(img.astype(np.float32)).numpy().mean()) - img.mean()) < 1e-3
assert A.Compose([A.Resize(16, 16)])(image=img)["image"].shape == (16, 16, 3)
from molscribe import MolScribe  # noqa: F401
print(f"ready: numpy {np.__version__}, cv2 {cv2.__version__}, torch {torch.__version__}")
PY

echo "venv at $HOME_DIR/venv; the checkpoint downloads on first use into $HOME_DIR/weights"

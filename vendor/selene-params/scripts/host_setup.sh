#!/bin/bash
# Build host setup for the Selene runs with Quantinuum's published emulator parameters.
#   bash host_setup.sh SCRATCH
# SCRATCH holds: env/corpus-requirements.lock (open-standards wai/quantum-cross-simulator lock: selene-sim 0.3.8,
# guppylang 1.2.1, every wheel hash-pinned) and env/package-venv-freeze.txt (the package's venv as the vendor checks ran it).
# Two virtual environments, both under SCRATCH, none in $HOME:
#   venv-selene : CPython 3.12.16 + the corpus lock, --require-hashes --only-binary (Selene runs, scoring)
#   venv-pkg    : CPython 3.13 + the package's pinned versions (build_circuits.py, the package's own circuit builder)
set -euo pipefail
S=$1
UV=${UV:-uv}
export UV_CACHE_DIR=$S/uv-cache UV_PYTHON_INSTALL_DIR=$S/python ZIG_GLOBAL_CACHE_DIR=$S/zig-cache
"$UV" --version
if [ ! -f $S/venv-selene/.complete ]; then
  rm -rf $S/venv-selene
  timeout 600 "$UV" venv --quiet --python 3.12.16 --python-preference only-managed $S/venv-selene
  timeout 1200 "$UV" pip install --quiet --python $S/venv-selene/bin/python --require-hashes --only-binary :all: -r $S/env/corpus-requirements.lock
  touch $S/venv-selene/.complete
fi
if [ ! -f $S/venv-pkg/.complete ]; then
  rm -rf $S/venv-pkg
  grep -v '^Python' $S/env/package-venv-freeze.txt > $S/env/package-pins.txt
  timeout 600 "$UV" venv --quiet --python 3.13 --python-preference only-managed $S/venv-pkg
  timeout 1200 "$UV" pip install --quiet --python $S/venv-pkg/bin/python --only-binary :all: -r $S/env/package-pins.txt
  touch $S/venv-pkg/.complete
fi
$S/venv-selene/bin/python -c "import sys, importlib.metadata as m; print(sys.version); print({p: m.version(p) for p in ('selene-sim','selene-core','guppylang','numpy','selene-hugr-qis-compiler','tket')})"
$S/venv-pkg/bin/python -c "import sys, importlib.metadata as m; print(sys.version); print({p: m.version(p) for p in ('qiskit','pyscf','ffsim','numpy','selene-sim')})"
$S/venv-selene/bin/python -m pip freeze 2>/dev/null > $S/env/venv-selene-freeze.txt || "$UV" pip freeze --python $S/venv-selene/bin/python > $S/env/venv-selene-freeze.txt
"$UV" pip freeze --python $S/venv-pkg/bin/python > $S/env/venv-pkg-freeze.txt
echo SETUP_OK

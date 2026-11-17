#!/bin/bash
# Build host setup for the 2025 rerun (Selene with Quantinuum's documented default emulator parameters).
#   bash scripts/host_setup.sh WORK        (run from the staged checkout; WORK is a new folder on the external volume)
# Copies the checkout (builder/, params/, plugin/, scripts/, env/, controls/) into WORK, then under WORK only:
#   venv-selene     CPython 3.12.16 + the corpus lock (selene-sim 0.3.8, guppylang 1.2.1), --require-hashes --only-binary
#   plugin-target/  the docs-noise plugin built against selene-core 0.3.4 (selene-sim-v0.3.8 tag, plugin/vendor)
set -euo pipefail
W=$1
UV=${UV:-uv}
mkdir -p "$W"
for d in builder params plugin scripts env controls; do rm -rf "$W/$d"; cp -R "$d" "$W/$d"; done
export UV_CACHE_DIR=$W/uv-cache UV_PYTHON_INSTALL_DIR=$W/python
"$UV" --version
if [ ! -f "$W/venv-selene/.complete" ]; then
  rm -rf "$W/venv-selene"
  timeout 600 "$UV" venv --quiet --python 3.12.16 --python-preference only-managed "$W/venv-selene"
  timeout 1200 "$UV" pip install --quiet --python "$W/venv-selene/bin/python" --require-hashes --only-binary :all: -r "$W/env/corpus-requirements.lock"
  touch "$W/venv-selene/.complete"
fi
"$W/venv-selene/bin/python" -I -c "import sys, importlib.metadata as m; print(sys.version); print({p: m.version(p) for p in ('selene-sim','selene-core','guppylang','numpy','selene-hugr-qis-compiler')})"
"$UV" pip freeze --python "$W/venv-selene/bin/python" > "$W/env/venv-selene-freeze.txt"
(cd "$W/plugin/vendor/selene-core" && shasum -a 256 -c ../selene-core-0.3.8-tag.sha256 | tail -3)
export CARGO_TARGET_DIR=$W/plugin-target
(cd "$W/plugin" && timeout 1200 cargo build --release --locked 2>&1 | tail -5)
shasum -a 256 "$W/plugin-target/release/libqcup_docs_noise_plugin.dylib" | sed "s#$W/##" > "$W/plugin/built-dylib.sha256"
cat "$W/plugin/built-dylib.sha256"
echo SETUP_OK

#!/bin/bash
# Run every prediction job on the build host, at most 8 at once, each under memguard. Usage: run_predict.sh (from the scratch root)
cd "$(dirname "$0")/.."
LIGHT=$(venv/bin/python -I -c "import json;print(','.join(c['id'] for c in json.load(open('out/design.json'))['circuits'] if c['kind']!='aim1'))")
{
for b in ibm_marrakesh ibm_kingston ibm_fez; do for m in generic cal_idle cal_noidle; do echo "$b $m a1-b20-p1-warm a20"; done; done
for b in ibm_marrakesh ibm_kingston ibm_fez; do for m in generic cal_idle cal_noidle; do echo "$b $m a1-b16-p2-warm,a1-b16-p3-warm a16"; echo "$b $m a1-b12-p1-warm,a1-r12-p2-cold,a1-d12-p2-warm a12"; echo "$b $m $LIGHT light"; done; done
} | AER_THREADS=4 xargs -P 8 -L 1 sh -c '/Volumes/macos_4TB_external_1/wai-build/bin/memguard --max-gb 12 -- venv/bin/python -I work/predict.py out cal $0 $1 $2 pred/$0-$1-$3.json > logs/pred-$0-$1-$3.log 2>&1; echo "$(date -u +%H:%M:%S) $0 $1 $3 exit $?"'
echo ALLDONE

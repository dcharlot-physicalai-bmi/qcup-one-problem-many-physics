#!/bin/bash
# The remaining marrakesh prediction jobs (the backend chosen at the final design check); writes ALLDONE-M when every
# marrakesh prediction process has exited. Usage: work/run_rest.sh (from the scratch root)
cd "$(dirname "$0")/.."
LIGHT=$(venv/bin/python -I -c "import json;print(','.join(c['id'] for c in json.load(open('out/design.json'))['circuits'] if c['kind']!='aim1'))")
MG=/Volumes/macos_4TB_external_1/wai-build/bin/memguard
run() { AER_THREADS=4 $MG --max-gb 12 -- venv/bin/python -I work/predict.py out cal ibm_marrakesh $1 $2 pred/ibm_marrakesh-$1-$3.json > logs/pred-ibm_marrakesh-$1-$3.log 2>&1; echo "$(date -u +%H:%M:%S) ibm_marrakesh $1 $3 exit $?" >> logs/run_predict.log; }
run cal_noidle a1-b16-p2-warm,a1-b16-p3-warm,a1-b12-p1-warm,a1-r12-p2-cold,a1-d12-p2-warm a16a12 &
run cal_noidle "$LIGHT" light &
wait
while pgrep -f "predict.py out cal ibm_marrakesh" > /dev/null; do sleep 20; done
echo ALLDONE-M >> logs/run_predict.log

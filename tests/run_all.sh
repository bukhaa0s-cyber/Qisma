#!/usr/bin/env bash
# يشغّل كل اختبارات قِسمة على qisma.html (بدون إنترنت، بيانات تجريبية فقط — ما يلمس بياناتك)
# المتطلبات: python3 + playwright (pip install playwright && playwright install chromium)
set -u -o pipefail
cd "$(dirname "$0")"
APP="$(cd .. && pwd)/qisma.html"
FX="$(pwd)/fixtures"
fail=0
python3 test_core.py "$APP"                       || fail=1
python3 test_status_and_closed_month.py "$APP"    || fail=1
python3 test_airbnb_paste.py "$APP" "$FX"         || fail=1
for s in 3 7 11 23; do python3 fuzz.py "$APP" $s | tail -1 || fail=1; done
python3 - "$APP" <<'PY' || fail=1
import re, subprocess, sys, tempfile, os
h = open(sys.argv[1], encoding='utf-8').read()
bad = 0
for i, p in enumerate(re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>', h, re.S)):
    f = tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8'); f.write(p); f.close()
    r = subprocess.run(['node', '--check', f.name], capture_output=True, text=True); os.unlink(f.name)
    print('syntax block', i, 'OK' if r.returncode == 0 else r.stderr[:300]); bad |= r.returncode != 0
sys.exit(1 if bad else 0)
PY
[ $fail = 0 ] && echo "ALL GREEN" || { echo "SOMETHING FAILED"; exit 1; }

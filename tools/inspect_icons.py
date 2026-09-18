#!/usr/bin/env python3
"""Проверка иконок через сам браузер (headless Chrome).

Кладёт в корень проекта страницу-зонд probe.html: она грузит РЕАЛЬНУЮ страницу
/divn/index.html в iframe (same-origin) и читает getComputedStyle у настоящих
отрендеренных карточек — background-image (какой спрайт), background-position,
width/height. Дальше --dump-dom отдаёт результат, скрипт его печатает.

Так проверяется то, что реально видит браузер: класс -> правило CSS -> спрайт,
включая отдачу статики сервисом.

Запуск: .venv/bin/python .work/inspect_icons.py <base_url>
"""
import os
import re
import shutil
import tempfile
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8090'
PROBE = os.path.join(ROOT, 'probe.html')

PROBE_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>icon probe</title></head>
<body style="margin:0">
<iframe id="f" src="/divn/index.html" style="width:1500px;height:1200px;border:0"></iframe>
<pre id="probe">pending</pre>
<script>
var frames = 0;
document.getElementById('f').addEventListener('load', function () {
  var fr = this;
  var tick = setInterval(function () {
    frames++;
    var doc = fr.contentDocument;
    var items = doc.querySelectorAll('.item');
    if (items.length < 100 && frames < 40) return;   // ждём, пока Vue отрисует и fetch'и завершатся
    clearInterval(tick);
    var win = fr.contentWindow;
    var rows = [];
    var groups = [
      ['weapon', '.weapon-type'],
      ['slot',   '.gear-icon'],
      ['set',    '.set-icon'],
      ['mod',    '.weapon-mod-icon'],
      ['modifier', '.icon-stat'],
      ['currency', '.icon-cur']
    ];
    groups.forEach(function (g) {
      var els = doc.querySelectorAll(g[1]);
      var seen = {};
      for (var i = 0; i < els.length; i++) {
        var cn = els[i].className;
        if (seen[cn]) continue;
        seen[cn] = 1;
        var cs = win.getComputedStyle(els[i]);
        rows.push([g[0], cn, cs.backgroundImage, cs.backgroundPosition,
                   cs.width, cs.height, cs.display].join(' | '));
      }
    });
    document.getElementById('probe').textContent =
      'ITEMS=' + items.length + '\\n' + rows.sort().join('\\n');
  }, 250);
});
</script>
</body></html>
"""
open(PROBE, 'w', encoding='utf-8').write(PROBE_HTML)
try:
    profile = tempfile.mkdtemp(prefix='d1probe-')      # временный профиль, не мусорим в проекте
    try:
        out = subprocess.run(
            ['google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
             '--disable-dev-shm-usage', f'--user-data-dir={profile}',
             '--virtual-time-budget=20000', '--window-size=1500,1300', '--dump-dom',
             f'{BASE}/divn/probe.html'],
            capture_output=True, text=True, timeout=180).stdout
    finally:
        shutil.rmtree(profile, ignore_errors=True)
finally:
    os.remove(PROBE)

m = re.search(r'<pre id="probe">(.*?)</pre>', out, re.S)
if not m:
    print('НЕ УДАЛОСЬ прочитать probe из DOM — дамп:')
    print(out[:2000])
    sys.exit(1)

text = m.group(1).replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
items_line = lines[0] if lines else ''
rows = [ln.split(' | ') for ln in lines[1:]]

print(items_line)
print(f'{"группа":9} {"классы":30} {"спрайт":26} {"pos":>14} {"размер":>10}  вердикт')
problems = []
for r in rows:
    if len(r) < 7:
        continue
    group, cls, bg, pos, w, h, disp = r[:7]
    sprite = os.path.basename(bg.replace('url(', '').replace(')', '').strip('"\'')) or '—'
    wv = float(w.replace('px', '')) if w.endswith('px') else 0
    hv = float(h.replace('px', '')) if h.endswith('px') else 0
    ok = sprite != '—' and wv > 0 and hv > 0 and disp != 'none'
    if not ok:
        problems.append(f'{cls}: sprite={sprite} w={w} h={h} display={disp}')
    print(f'{group:9} {cls:30} {sprite:26} {pos:>14} {w + "x" + h:>10}  {"ok" if ok else "ПРОБЛЕМА"}')

print()
if problems:
    print(f'ПРОБЛЕМЫ ({len(problems)}):')
    for p in problems:
        print('  -', p)
    sys.exit(1)
print(f'OK: все {len(rows)} классов иконок на реальной странице имеют спрайт и ненулевой размер')

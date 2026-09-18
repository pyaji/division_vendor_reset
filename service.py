#!/usr/bin/env python3
"""
Division 1 Vendor Reset — data service + front end host.

Syncs the published Google Sheet "The Last Wave Division 1 Vendor Reset",
writes data/*.json (page item model) and data/raw/*.json (sheet-native dump),
and serves both the JSON API and the static front end. Stdlib only — runs
directly in .venv.

    .venv/bin/python service.py                 # sync now + serve on :8090, re-sync every week
    .venv/bin/python service.py --sync-only     # one-off sync, no server
    .venv/bin/python service.py --port 9000 --interval 604800

HTTP:
    GET  /divn/index.html   front end (css/js/images/fonts/fetch('data/...') are relative to it)
    GET  /divn/<path>       any project file except dot-dirs and the service's own sources
    GET  /                  JSON index of the endpoints below
    GET  /status            sync state + per-sheet rows
    GET  /data/<name>.json  page item model per sheet (+ meta)
    GET  /data/raw/<name>.json  sheet-native dump
    POST /sync              force re-sync

The front end lives under /divn/ because css/*.css reference assets with the
absolute /divn/ prefix (deployment path) — see AI_CONTEXT §4.7.

Published sheets (gid, slug -> data/<slug>.json; blueprints is skipped):
    Weapons(139561767) weapon-mods Weapon Mods(649177174) gear Gear(324697283)
    gear-mods Gear Mods(1060549195) welcome(1350791782)

Row schema (data/raw/*.json, one array per sheet):
    {"_row": <sheet row number>,
     "_top": <top-level section>, "_section": <innermost section>,
     "_header": [<columns of this block>], "_recommended": <bool>,
     <header cell name>..., <c<i> for unnamed columns>}
Header names are slugified, duplicates get _2/_3 suffix; unnamed columns
are c<i> by 0-based data-column index. Every category block has its own
header row (column count differs per block), and each row records the
header it was parsed with in _header. Section rows = exactly one non-empty
cell whose CSS style is not a "note" style (border/vertical-align); top-level
sections are the ones with black background. If a sheet has no top-level
section at all, _top mirrors _section.
"""

import argparse
import html as htmllib
import json
import logging
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SOURCE_URL = ('https://docs.google.com/spreadsheets/d/e/'
              '2PACX-1vQp0q6ctg-4HP2HsrKt2EGHRoApXLJlC-6QF2A4F0Ixf6UrD9-Thull7I34mnA9vMKgflM4nyVdViMV/pubhtml')
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, 'data')
META_FILE = os.path.join(DATA_DIR, 'meta.json')
WEEK_SECONDS = 7 * 24 * 3600
FAIL_RETRY_SECONDS = 15 * 60
HTTP_TIMEOUT = 30
DEFAULT_PORT = 8090
USER_AGENT = 'd1-vendor-reset-data-service/1.0'
SKIP_SHEETS = {'blueprints'}  # not used by the front end — not synced

# static front end: served under /divn/ because css/*.css point at absolute
# /divn/... asset urls (HARD RULE in AI_CONTEXT §4.7) — the prefix cannot change
STATIC_PREFIX = '/divn'
INDEX_FILE = 'index.html'
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.vue': 'application/javascript; charset=utf-8',  # plain JS loaded via <script src>
    '.json': 'application/json; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
    '.map': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
}
NO_CACHE_SUFFIXES = ('.html', '.json')  # data refreshes weekly — never serve stale

log = logging.getLogger('d1sync')


def utcnow_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def http_get(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        if resp.status != 200:
            raise IOError(f'HTTP {resp.status} for {url}')
        return resp.read().decode('utf-8', 'replace')


# ---------------------------------------------------------------- HTML table

class SheetTableParser(HTMLParser):
    """Extracts rows from the single <table> of a published sheet page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_table = 0
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.in_table += 1
        elif tag == 'tr' and self.in_table:
            self._row = []
        elif tag in ('td', 'th') and self.in_table and self._row is not None:
            try:
                colspan = max(1, int(a.get('colspan', '1')))
            except ValueError:
                colspan = 1
            self._cell = {'tag': tag, 'cls': a.get('class', ''), 'span': colspan, 'text': ''}

    def handle_endtag(self, tag):
        if tag == 'table' and self.in_table:
            self.in_table -= 1
        elif tag in ('td', 'th') and self._cell is not None:
            self._row.append(self._cell)
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell['text'] += data


def extract_table(html_text):
    p = SheetTableParser()
    p.feed(html_text)
    parsed_rows = p.rows
    # expand colspan into repeated cells
    rows = []
    for row in parsed_rows:
        cells, i = [], 1
        for c in row:
            # 1-based sheet column; th first cell is the row-number shim
            for _ in range(c['span']):
                cells.append({'tag': c['tag'], 'cls': c['cls'], 'text': c['text'].strip() if _ == 0 else ''})
            i += 1
        rows.append(cells)
    return rows


def parse_css_map(html_text):
    """class -> full CSS rule text from the inline <style> block."""
    m = {}
    css = re.search(r'<style[^>]*>(.*?)</style>', html_text, re.S)
    if not css:
        return m
    for mm in re.finditer(r'\.(s\d+)\s*\{([^}]*)\}', css.group(1)):
        m[mm.group(1)] = mm.group(2).strip().lower()
    return m


def is_black_bg(cls, cssmap):
    rule = cssmap.get(cls, '')
    return bool(re.search(r'background-color:\s*(#000000|#000|black|rgb\(0,\s*0,\s*0\))', rule))


def is_note_style(cls, cssmap):
    """Note/disclaimer cells carry borders and vertical-align; sections don't."""
    rule = cssmap.get(cls, '')
    return 'border' in rule or 'vertical-align' in rule


# "Recommended Items are highlighted with this shade of orange" (Welcome sheet).
# The class number differs per sheet, so match the colour, not the class.
RECOMMEND_BG = '#ffbb7f'

def is_recommend(cls, cssmap):
    rule = cssmap.get(cls, '')
    return RECOMMEND_BG in rule


# ------------------------------------------------------------------- blocks

def field_names(cells):
    names, seen = [], {}
    for i, cell in enumerate(cells):
        base = slug(cell['text']) or f'c{i}'
        if base in seen:
            seen[base] += 1
            names.append(f'{base}_{seen[base]}')
        else:
            seen[base] = 1
            names.append(base)
    return names


def slug(value):
    value = value.strip().lower()
    value = re.sub(r'\s+', '_', value)
    value = re.sub(r'[^a-z0-9_]+', '', value)
    return value or None


def is_header(cells):
    low = [c['text'].strip().lower() for c in cells]
    if 'name' in low:
        return True
    if any(v.startswith('attribute') for v in low):
        return True
    return 'type' in low and 'stat value' in low


def parse_sheet_html(html_text):
    cssmap = parse_css_map(html_text)
    raw_rows = extract_table(html_text)
    items = []
    header_names = None
    top, sub, has_black_top = '', '', False
    for raw in raw_rows:
        # drop the th row-number shim (col 1)
        if raw and raw[0]['tag'] == 'th':
            rownum, cells = raw[0]['text'].strip(), raw[1:]
        else:
            rownum, cells = None, raw
        nonempty = [c for c in cells if c['text']]
        if not nonempty:
            continue
        if is_header(cells):
            # у каждого блока (категории) своя шапка — фиксируем её позиционно
            header_names = field_names(cells)
            continue
        # section row: exactly one non-empty cell, in a non-note style
        # (gear-mods sections sit in col 2 — position in the row is not required)
        if len(nonempty) == 1:
            c = nonempty[0]
            if c['cls'] and c['cls'] in cssmap and not is_note_style(c['cls'], cssmap):
                text = c['text']
                if is_black_bg(c['cls'], cssmap):
                    top, sub, has_black_top = text, '', True
                elif not has_black_top and sub == '':
                    top = text  # sheet without black top rows: each section is top
                else:
                    sub = text
                continue
        if header_names is None:
            continue  # disclaimer/note rows before any header
        row = {}
        for idx, name in enumerate(header_names):
            row[name] = cells[idx]['text'] if idx < len(cells) else ''
        for idx in range(len(header_names), len(cells)):  # extra columns
            row[f'c{idx}'] = cells[idx]['text']
        row['_row'] = int(rownum) if rownum and rownum.isdigit() else None
        row['_top'] = top
        row['_section'] = sub or top
        # шапка этого блока (позиционный список колонок): у каждой категории она своя,
        # число колонок-атрибутов разное (напр. Muzzle — до Attribute 4, Holster — только Attribute 1)
        row['_header'] = list(header_names)
        # whole row of a recommended item carries the orange highlight
        row['_recommended'] = is_recommend(nonempty[0]['cls'], cssmap)
        items.append(row)
    return items, cssmap


def sheet_slug(display_name):
    return re.sub(r'[^a-z0-9]+', '-', display_name.lower()).strip('-')


def atomic_write(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------- sheet -> page model
# Адаптер строки листа в item-модель страницы (AI_CONTEXT §3) с дефолтами:
# в таблице нет цен/bonus/dmg и др. — подставляем значения, которые компоненты
# читают без падений:
#   price="$0"        — vendor-item.vue делает price.split('$')
#   fire/stam/elec="-"— gear.vue: "-" рендерится как 205
#   bonus="-"         — weapon.vue: "-" = bonus отсутствует
#   attributes/stat   — строки (компоненты делают .split / .replace)
# Честный dump листа сохраняется отдельно в data/raw/<slug>.json.

# ------------------------------------------------------------------ иконки
# Страница строит css-класс иконки из item-поля: weapon.vue/gear.vue/weapon-mod.vue
# предпочитают готовый item.category, а свои регэкспы по имени оставлены фолбэком.
# Ключи ниже — ровно css-классы: .weapon-type-<k>, .gear-icon.<k>, .weapon-mod-icon.<k>
# (css/style.css, css/gear.css). Источник — раздел листа (_section): единственное
# место, где класс/слот указан явно (имена в листе — это имена предметов/сетов).

WEAPON_CLASSES = {          # _section -> .weapon-type-<k>
    'pistol': 'pistol',
    'smg': 'smg',
    'assault rifle': 'ar',
    'shotgun': 'shotgun',
    'marksman rifle': 'marksman',
    'lmg': 'lmg',
}
# У экзотики в листе класса нет (только таланты) — таблица вручную, по имени.
# Дополнять при появлении новых экзотиков в листе.
EXOTIC_CLASSES = {
    'cassidy': 'shotgun',
    'centurion': 'pistol',
    'historian': 'marksman',
    'liberator': 'ar',
    'pakhan': 'lmg',
}
GEAR_SLOTS = {              # _section -> .gear-icon.<k>
    'chest': 'chest',
    'mask': 'mask',
    'knee pads': 'kneepads',
    'backpack': 'backpack',
    'gloves': 'gloves',
    'holster': 'holster',
}
MOD_CLASSES = {             # _section -> .weapon-mod-icon.<k>
    'magazine': 'magazine',
    'muzzle': 'suppressor',
    'underbarrel': 'grip',
    'sight': 'scope',
}
GEAR_SET_RARITY = 'header-gs'  # css-класс "это gear set" (шаблон #gear и name_color)

# Броня в листе не указана (в колонке Main Stat лежит основной атрибут, а не armour):
# по договорённости показываем стандартное число.
GEAR_ARMOR = '1248'
STAT_FIELDS = {'FA': 'fire', 'ST': 'stam', 'EL': 'elec'}   # FA->fire, ST->stam, EL->elec

def _gear_stats(main_stat):
    """Основной атрибут -> блоки FA/ST/EL карточки (gear.vue: fire/stam/elec).

    Обычный слот: "1218 ST"  -> stam=1218 (FA/EL остаются "-", компонент рисует 205).
    Кобура:       "1125|1244|1115" -> fire=1125, stam=1244, elec=1115 (порядок листа FA|ST|EL).
    """
    out = {'fire': '-', 'stam': '-', 'elec': '-'}
    s = (main_stat or '').strip()
    if not s:
        return out
    if '|' in s:                      # кобура: три значения по порядку FA|ST|EL
        for key, val in zip(('fire', 'stam', 'elec'), (p.strip() for p in s.split('|'))):
            if val:
                out[key] = val
        return out
    m = re.match(r'^(.*?)\s*(FA|ST|EL)$', s)
    if m and m.group(1).strip():
        out[STAT_FIELDS[m.group(2)]] = m.group(1).strip()
    return out

def _category(r, table, exotics=False):
    key = table.get((r.get('_section') or '').strip().lower())
    if not key and exotics:
        key = EXOTIC_CLASSES.get((r.get('name') or '').strip().lower())
    return key or ''

def _raw_refs(r):
    d = {'_row': r.get('_row'), '_top': r.get('_top'), '_section': r.get('_section')}
    d['recommended'] = 'Yes' if r.get('_recommended') else ''
    return d

def _header(r):
    """Позиционный список колонок блока (своя шапка у каждой категории)."""
    h = r.get('_header')
    if isinstance(h, list) and h:
        return h
    return [k for k in r if not k.startswith('_')]  # фолбэк для старых данных

def _cols(r, prefix):
    """Непустые значения колонок блока, чья шапка начинается с prefix, в порядке колонок."""
    return [r.get(name) or '' for name in _header(r) if name.startswith(prefix)]

def _attr_pairs(r):
    """Пары (колонка-значение, колонка-атрибут) по раскладке шапки блока.

    В листе модов оружия значение стоит СЛЕВА от своего атрибута:
    ['Name','','Attribute 1','','Attribute 2',...] + значения в безымянных колонках.
    Число атрибутов у блоков разное (Muzzle — 4), поэтому идём по шапке, а не по номерам.
    """
    header = _header(r)
    pairs = []
    for j, name in enumerate(header):
        if name.startswith('attribute_') and j > 0:
            pairs.append((header[j - 1], name))
    return pairs

def _pair_lines(r, pairs=None):
    """[(value_key, attr_key)] → строки "значение атрибут" через <br/>."""
    lines = []
    for vk, ak in (pairs if pairs is not None else _attr_pairs(r)):
        val, attr = r.get(vk) or '', r.get(ak) or ''
        if val or attr:
            lines.append(f'{val} {attr}'.strip())
    return '<br/>'.join(lines)

def adapt_weapons(rows):
    items = []
    for r in rows:
        it = {
            'type': 'exotic' if r.get('_top') == 'Exotic' else 'weapon',
            'name': r.get('name') or '',
            'vendor': r.get('vendor') or '',
            'price': '$0',
            'category': _category(r, WEAPON_CLASSES, exotics=True),  # класс для иконки
            'bonus': '-', 'dmg': '', 'rpm': '', 'mag': '',
        }
        # талантов у блока может быть 2 (Pistol) или 3 (остальные) — идём по шапке
        for i, talent in enumerate([t for t in _cols(r, 'talent') if t], 1):
            it[f'talent{i}'] = talent
        it.update(_raw_refs(r))
        items.append(it)
    return items

def adapt_gear(rows):
    items = []
    for r in rows:
        attrs = [a for a in _cols(r, 'attribute') if a]
        slot = (r.get('_section') or '').strip()
        stats = _gear_stats(r.get('main_stat'))
        it = {
            'type': 'gear',
            # в имени дописываем слот: "D3-FNC" -> "D3-FNC Chest"
            'name': ' '.join(x for x in (r.get('name') or '', slot) if x),
            'vendor': r.get('vendor') or '',
            'price': '$0',
            'category': _category(r, GEAR_SLOTS),          # слот для иконки (.gear-icon.*)
            'rarity': GEAR_SET_RARITY if r.get('_top') == 'Gear Set' else '',
            'armor': GEAR_ARMOR,                 # стандартное число: брони в листе нет
            'fire': stats['fire'], 'stam': stats['stam'], 'elec': stats['elec'],
            'major': attrs[0] if attrs else '',
            'minor': '<br/>'.join(attrs[1:]),
        }
        it.update(_raw_refs(r))
        items.append(it)
    return items

def adapt_weapon_mods(rows):
    items = []
    for r in rows:
        it = {
            'type': 'weapon-mod',
            'name': r.get('name') or '',
            'vendor': r.get('vendor') or '',
            'price': '$0',
            'category': _category(r, MOD_CLASSES),   # иконка мода
            'attributes': _pair_lines(r) or '-',
        }
        it.update(_raw_refs(r))
        items.append(it)
    return items

def adapt_gear_mods(rows):
    items = []
    for r in rows:
        attr = r.get('attribute') or ''
        it = {
            'type': 'purple-mod' if r.get('_top') == 'High End' else 'gear-mod',
            'name': attr or r.get('type') or '?',  # в листе нет колонки name
            'vendor': r.get('vendor') or '',
            'price': '$0',
            'stat': r.get('stat_value') or '-',    # напр. "245"; у performance-модов "-"
            'attribute': f'{r["c3"]} {attr}'.strip() if (r.get('c3') and attr) else attr,
        }
        it.update(_raw_refs(r))
        items.append(it)
    return items

ADAPTERS = {
    'weapons': adapt_weapons,
    'gear': adapt_gear,
    'weapon-mods': adapt_weapon_mods,
    'gear-mods': adapt_gear_mods,
}

# --------------------------------------------------------------------- sync

class Syncer:
    def __init__(self):
        self.lock = threading.Lock()
        self.started_at = utcnow_iso()
        self.last_sync_at = None
        self.last_sync_error = None
        self.last_error_at = None

    def fetch_sheet_index(self):
        page = http_get(SOURCE_URL)
        pairs = re.findall(
            r'name:\s*"([^"]+)"[^}]*?gid:\s*"(\d+)"', page)
        if not pairs:
            raise IOError('could not find sheet list on source page')
        return [(name, gid) for name, gid in pairs]

    def sync(self):
        """Fetch all sheets and rewrite data/*.json + meta.json. Raises on failure."""
        with self.lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            sheets_meta, welcome_update = {}, None
            index = self.fetch_sheet_index()
            for name, gid in index:
                slug = sheet_slug(name)
                if slug in SKIP_SHEETS:
                    log.info('%s: skipped', name)
                    continue
                url = f'{SOURCE_URL}/sheet?headers=false&gid={gid}'
                html_text = http_get(url)
                if slug == 'welcome':
                    # notes sheet: no header block — keep raw text rows
                    lines = []
                    for row in extract_table(html_text):
                        if row and row[0]['tag'] == 'th':
                            row = row[1:]
                        line = ' '.join(c['text'] for c in row if c['text'])
                        if line:
                            lines.append(line)
                            if line.startswith('Last Update'):
                                welcome_update = line
                    items = lines
                else:
                    raw, _ = parse_sheet_html(html_text)
                    items = ADAPTERS[slug](raw) if slug in ADAPTERS else raw
                    # честный dump — в data/raw/, чтобы адаптер можно было дорабатывать
                    raw_dir = os.path.join(DATA_DIR, 'raw')
                    os.makedirs(raw_dir, exist_ok=True)
                    atomic_write(os.path.join(raw_dir, f'{slug}.json'),
                                 json.dumps(raw, ensure_ascii=False, indent=2) + '\n')
                atomic_write(os.path.join(DATA_DIR, f'{slug}.json'),
                             json.dumps(items, ensure_ascii=False, indent=2) + '\n')
                log.info('%s: %d rows', slug, len(items))
                sheets_meta[slug] = {
                    'sheet': name, 'gid': gid, 'url': url,
                    'rows': len(items), 'file': f'{slug}.json',
                    'raw': f'raw/{slug}.json' if slug in ADAPTERS else None,
                    'fetched_at': utcnow_iso(),
                }
            meta = self._load_meta()
            meta.update({
                'source': SOURCE_URL,
                'synced_at': utcnow_iso(),
                'sheet_last_update': welcome_update,
                'sheets': sheets_meta,
            })
            hist = meta.get('history', []) + [{'synced_at': meta['synced_at'],
                                               'rows': {k: v['rows'] for k, v in sheets_meta.items()}}]
            meta['history'] = hist[-16:]
            atomic_write(META_FILE, json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
            self.last_sync_at = meta['synced_at']
            self.last_sync_error = None
            self.last_error_at = None
            return meta

    def _load_meta(self):
        try:
            with open(META_FILE, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def status(self):
        meta = self._load_meta()
        return {
            'service': 'd1-vendor-reset-data',
            'started_at': self.started_at,
            'last_sync_at': self.last_sync_at,
            'last_sync_error': self.last_sync_error,
            'sheets': meta.get('sheets', {}),
            'sheet_last_update': meta.get('sheet_last_update'),
            'data_dir': DATA_DIR,
        }

    def schedule(self, interval_seconds):
        next_at = None
        while True:
            try:
                self.sync()
                next_at = time.time() + interval_seconds
            except Exception as e:
                self.last_sync_error = repr(e)
                self.last_error_at = utcnow_iso()
                log.error('sync failed, retry in %ds: %s', FAIL_RETRY_SECONDS, e)
                time.sleep(FAIL_RETRY_SECONDS)
                continue
            log.info('next sync in %ds (%s)', interval_seconds,
                     datetime.fromtimestamp(next_at, timezone.utc).strftime('%Y-%m-%d %H:%MZ UTC'))
            time.sleep(max(0, next_at - time.time()))


# --------------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    syncer: Syncer = None
    interval: int = WEEK_SECONDS

    def _json(self, code, obj, body=True):
        payload = json.dumps(obj, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if body:
            self.wfile.write(payload)

    def do_GET(self):
        return self._route(get_body=True)

    def do_HEAD(self):
        return self._route(get_body=False)

    def _route(self, get_body):
        raw_path = self.path.split('?', 1)[0]
        path = raw_path.rstrip('/') or '/'
        if path in ('/', ''):
            self._json(200, {
                'service': 'd1-vendor-reset-data',
                'app': f'{STATIC_PREFIX}/{INDEX_FILE}',
                'endpoints': {
                    f'GET  {STATIC_PREFIX}/': 'front end (index.html + css/js/images/fonts + data/)',
                    'GET  /status': 'sync state + per-sheet rows',
                    'GET  /data/<name>.json': 'weapons weapon-mods gear gear-mods welcome meta (+ any <slug>.json in data/)',
                    'GET  /data/raw/<name>.json': 'sheet-native dump (per-block _header etc.)',
                    'POST /sync': 'force re-sync now',
                },
                'interval_seconds': self.interval,
            }, body=get_body)
        elif path == '/status':
            st = self.syncer.status()
            st['next_sync_at'] = (datetime.fromtimestamp(time.time() + self.interval, timezone.utc)
                                  .strftime('%Y-%m-%dT%H:%M:%SZ'))
            return self._json(200, st, body=get_body)
        elif path.startswith('/data/'):
            return self._serve_data(path[len('/data/'):], body=get_body)
        elif raw_path == STATIC_PREFIX:  # /divn -> /divn/
            self.send_response(301)
            self.send_header('Location', STATIC_PREFIX + '/')
            self.send_header('Content-Length', '0')
            self.end_headers()
        elif raw_path.startswith(STATIC_PREFIX + '/'):
            return self._serve_static(raw_path[len(STATIC_PREFIX) + 1:], body=get_body)
        else:
            self._json(404, {'error': 'not found', 'app': f'{STATIC_PREFIX}/{INDEX_FILE}'}, body=get_body)

    def _serve_data(self, name, body=True):
        if not re.fullmatch(r'(?:raw/)?[a-z0-9_-]+\.json', name):
            return self._json(400, {'error': 'bad name, expected <slug>.json or raw/<slug>.json'}, body=body)
        fp = os.path.realpath(os.path.join(DATA_DIR, name))
        if not fp.startswith(os.path.realpath(DATA_DIR) + os.sep) or not os.path.isfile(fp):
            return self._json(404, {'error': f'{name} not available (run POST /sync first)'}, body=body)
        self._send_file(fp, body=body)

    def _serve_static(self, rel, body=True):
        """Отдаёт файлы проекта под /divn/ — страница, css/js/шрифты/картинки и data/."""
        rel = urllib.parse.unquote(rel)
        if rel.endswith('/') or rel == '':
            rel += INDEX_FILE
        target = os.path.realpath(os.path.join(ROOT, rel))
        root = os.path.realpath(ROOT)
        if not target.startswith(root + os.sep):
            return self._json(403, {'error': 'forbidden path'}, body=body)
        # не отдаём служебное: .git/.venv/.work/.codegraph, собственные скрипты и кэш
        parts = os.path.relpath(target, root).split(os.sep)
        if any(p.startswith('.') or p == '__pycache__' for p in parts):
            return self._json(404, {'error': 'not found'}, body=body)
        if parts[-1] in ('service.py', 'demo-server.js'):
            return self._json(404, {'error': 'not found'}, body=body)
        if os.path.isdir(target):
            target = os.path.join(target, INDEX_FILE)
        if not os.path.isfile(target):
            return self._json(404, {'error': f'not found: {rel}', 'app': f'{STATIC_PREFIX}/{INDEX_FILE}'}, body=body)
        self._send_file(target, body=body)

    def _send_file(self, fp, body=True):
        ext = os.path.splitext(fp)[1].lower()
        # файлы без расширения (css/talentslist) — текстовые, а не бинарь
        ctype = MIME_TYPES.get(ext) or ('text/plain; charset=utf-8' if not ext else 'application/octet-stream')
        with open(fp, 'rb') as f:
            payload = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(payload)))
        if fp.endswith(NO_CACHE_SUFFIXES):
            self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        if body:
            self.wfile.write(payload)

    def do_POST(self):
        path = self.path.split('?', 1)[0].rstrip('/') or '/'
        if path == '/sync':
            try:
                self.syncer.sync()
                return self._json(200, self.syncer.status())
            except Exception as e:
                return self._json(502, {'error': f'sync failed: {e}'})
        self._json(404, {'error': 'not found'})

    def log_message(self, fmt, *args):  # quieter access log
        log.debug('http %s', fmt % args)


def main():
    ap = argparse.ArgumentParser(description='D1 vendor reset data service')
    ap.add_argument('--sync-only', action='store_true', help='sync once and exit')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--interval', type=int, default=WEEK_SECONDS,
                    help='sync period in seconds (default: 604800 = 1 week)')
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    syncer = Syncer()
    if args.sync_only:
        syncer.sync()
        log.info('done')
        return

    Handler.syncer = syncer
    Handler.interval = args.interval
    t = threading.Thread(target=syncer.schedule, args=(args.interval,), daemon=True)
    t.start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    log.info('serving on http://%s:%d', args.host, args.port)
    log.info('front end:  http://%s:%d%s/%s', args.host, args.port, STATIC_PREFIX, INDEX_FILE)
    log.info('json api:   http://%s:%d/status  /data/<slug>.json  /data/raw/<slug>.json', args.host, args.port)
    server.serve_forever()


if __name__ == '__main__':
    main()

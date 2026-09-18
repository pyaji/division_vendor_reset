# AI_CONTEXT — division1_vendor_reset

Инструкция для AI-агентов. Проект: статическое веб-приложение, **нет build-системы, нет package.json**, всё запускается как plain HTML/JS. Git: один коммит `init`, ветка `master`, remote не задан.

## 1. Глобальная цель

Каталог товаров веноу (vendor reset inventory) для **The Division 1**: оружие, моды оружия, броня (gear), моды брони (gear-mods / purple-mods). Приложение загружает JSON-дамп с внешнего сайта, отрисовывает карточки с иконками/статами/ценами и позволяет фильтровать по regexp. Целевая аудитория — игроки, планирующие сброс веноу на мобильных/десктопных браузерах.

**Источник данных — Google Sheet** "[PUBLIC] The Last Wave Division 1 Vendor Reset" (published-to-web endpoint). Сервис **`service.py`** (Python, stdlib-only, `.venv/bin/python`) раз в неделю скачивает листы, парсит таблицы и пишет **`data/<slug>.json`** в item-модель страницы (`weapons`, `weapon-mods`, `gear`, `gear-mods`, плюс `welcome` и `meta.json`), а честный dump листов — в `data/raw/<slug>.json`. Лист `Blueprints` не синкронизируется — не используется. Схемы: item-модель страницы — раздел 3, sheet-native dump — раздел 3.1. Первый источник (`rubenalamina.mx` через `cors.io`, затем 52 демо-item'а в `data/`) мёртв/заменён; `url` в `js/index.js` = `'data/'`.

> **Адаптер с дефолтами уже есть** (`ADAPTERS` в `service.py`): сервис пишет `data/<slug>.json` в **item-модель страницы** (раздел 3) — страница с ними рендерится. Для полей, которых нет в таблице, выставляются дефолты: `price="$0"`, `bonus="-"`, `fire/stam/elec="-"` (=205 на карточке), пустые `dmg/rpm/mag`. А вот `recommended`, `category` (класс/слот для иконок) и `rarity` (gear set) — **не дефолты, а реальные данные** листа: рекомендованное = оранжевая подсветка `#ffbb7f`, класс/слот = раздел блока (`_section`), gear set = верхний раздел `Gear Set`. Единственное исключение — таблица экзотики (`EXOTIC_CLASSES` в `service.py`): у экзотиков в листе класса нет, 5 имён размаплены вручную.

**Запуск (один процесс — и данные, и страница):**
```
.venv/bin/python service.py            # sync + HTTP-сервер :8090, повторный sync каждые 7 дней
.venv/bin/python service.py --sync-only# только sync (без сервера)
# страница:  http://127.0.0.1:8090/divn/index.html     (или /divn/ -> index.html)
# JSON API:  /  /status  /data/<slug>.json  /data/raw/<slug>.json  POST /sync
```
Статика отдаётся **под префиксом `/divn/`**, потому что ассеты в CSS прописаны абсолютно (`/divn/css/...`, `/divn/fonts/...` — HARD RULE §4.7); префикс менять нельзя. Страница грузит данные относительным `fetch('data/...')` → попадает в `/divn/data/*.json` (те же файлы, что и JSON API).
`demo-server.js` — прежний отдельный статик-сервер (`:8791`), **больше не нужен**: его роль выполняет `service.py`. Файл оставлен как запасной вариант.

## 2. Технологический стек

- **JS (ES5-стиль, `var`, без модулей)**, выполняется через `<script>` тэги из `index.html` в явном порядке подключения.
- **Vue 2** (global build, `js/vue.js`, v~2.x) — SPA на одном инстансе `new Vue({ el: '#app' })`.
- **Axios** (`js/axios.min.js`) — подключён, но **НЕ используется**; для данных используется нативный `fetch`.
- **Lodash** (`js/lodash.min.js`) — используется фактически только как глобальная зависимость; вызовы `_.debounce(...)` в `js/index.js` **битые** (результат не привязан к обработчикам — мёртвый код).
- **CSS** — vanilla, без препроцессора. Шрифт **Borda** (ttf в `fonts/Borda/`).
- **Данные** — JSON из `data/`, генерируются `service.py` из published Google Sheet (см. раздел 1). Схемы — раздел 3 и 3.1.
- **Иконки** — PNG-спрайты + `background-position` (CSS-атласы в `css/gear.css`, `css/talents.css`, `css/style.css`).

## 3. Структура проекта

```
index.html          # Единственный вход: <template>'ы Vue + разметка #app + порядок <script>
js/index.js         # Глобальное состояние (app_data), fetch данных, filter, Vue-инстанс, 3D-tilt по deviceorientation
js/weapon.vue       # Компонент Weapon (props: item) — template: '#weapon'
js/weapon-mod.vue   # Компонент WeaponMod
js/gear.vue         # Компонент Gear
js/gear-mod.vue     # Компонент GearMod
js/vendor-item.vue  # Vue.component('vendor-item', ...) — обёртка: маппит item.type → внутренний компонент
js/vue.js, axios.min.js, lodash.min.js  # vendor'нутые библиотеки
service.py          # Python-сервис (stdlib-only): sync Google Sheet → data/*.json (+ raw/), HTTP: JSON API + статика страницы под /divn/, порт 8090
demo-server.js      # ПРЕЖНИЙ статик-сервер (/divn/* → корень проекта, :8791) — заменён service.py, оставлен как запасной
.venv/              # Python 3.12.2, ТОЛЬКО pip (без requests/bs4) — сервис работает на stdlib
data/*.json         # ГЕНЕРИРУЕМЫЕ service.py (weapons / weapon-mods / gear / gear-mods / welcome / meta.json) — руками не править
css/style.css       # База: grid-контейнер, карточки .item, currency, responsive
css/gear.css        # Спрайт-иконки gear по слоту (chest/mask/...) + редкости
css/talents.css     # Спрайт-иконки talents (talent.<name>)
css/fonts.css       # @font-face Borda (пути с префиксом /divn/ — см. правило 5)
css/talentslist      # текстовый файл: список имён talents (по одному в строку) — справочник для css-классов `css/talents.css`
fonts/Borda/        # ttf-шрифты Borda всех весов
images/             # Спрайты: talents.png, weapons.png, stats.png, sets.png; images/items/*.png — иконки слотов gear
.codegraph/         # Индекс codegraph (не часть приложения, .gitignore внутри)
tools/              # проверки: smoke_page.js (логика компонентов по data/*.json), inspect_icons.py (иконки через headless Chrome)
.work/              # служебное, НЕ в git: снапшоты листов Google (sheet_*.html, d1pub.html)
```

**Item-модель** (поля зависят от `type`; все значения должны быть строками, где указано):
- общее: `type` (строка-тег компонента), `name`, `vendor`, `price` (строка вида `"$1,234"` или `"123 К"`/`"123 С"`), `recommended` (`"Yes"`/нет).
- **`category` — класс для иконки** (необязательное, но именно оно даёт верные иконки): у оружия `pistol|smg|ar|shotgun|marksman|lmg` (→ `.weapon-type-<k>`), у брони `chest|mask|kneepads|backpack|gloves|holster` (→ `.gear-icon.<k>`), у модов оружия `magazine|grip|scope|suppressor` (→ `.weapon-mod-icon.<k>`). Компоненты берут `item.category`, если он есть, иначе падают на старые регэкспы по `name`/`bonus` (так работают демо-данные прежнего формата).
- `weapon` / `exotic`: `bonus` (текст; `"-"` = нет), `dmg`, `rpm`, `mag`, `talent1..talentN` (`"-"` = unset).
- `weapon-mod`: `type`-категория, `attributes` (строка, разделитель `<br/>`).
- `gear`: `name` — **имя + слот** ("D3-FNC" → `"D3-FNC Chest"`; слот из `_section`, так же работает regex-фолбэк слота в `gear.vue`); `rarity` (css-класс: `header-gs` = **gear set** — включает значок сета `v-if='item.rarity == "header-gs"'` и цвет имени `gs`); `armor` — **константа `"1248"`** (брони в листе нет, см. ниже); `fire`/`stam`/`elec` — основной атрибут из листа, разложенный по типу (`FA→fire`, `ST→stam`, `EL→elec`): у обычного слота `"1218 ST"` → `stam="1218"` (остальные `"-"` → компонент рисует **205**), у кобуры `"1125|1244|1115"` → `fire/stam/elec` по порядку листа `FA|ST|EL`; `major` = первый `attribute_*`, `minor` = остальные (строки `<br/>`; разделение major/minor — наше, в листе его нет). Название сета (`set`-иконка) вычисляется регэкспом по `name`: имена сетов в листе (`D3-FNC`, `Striker`, `Hunter's Faith`, …) совпадают с `sets_list` в `js/gear.vue` — все 14 матчатся.
- `gear-mod` / `purple-mod`: `stat` — `"-"` (без %/букв) = performance-мод, `"30%"` и т.п. = мод со стафом (рендерит `[stat, attribute]`), `attribute` — текст стафа.

**(исторически)** в `data/` лежали 52 демо-item'а; сейчас `data/<slug>.json` генерирует `service.py` **по этой item-модели** (через `ADAPTERS`), а чистый dump листа — в `data/raw/<slug>.json` (схема — ниже, 3.1).

**Критически:** `item.type` — это **имя Vue-компонента**. `vendor-item.vue` маппит: `weapon`, `exotic` → `Weapon`; `weapon-mod` → `WeaponMod`; `gear` → `Gear`; `gear-mod`, `purple-mod` → `GearMod`. Динамический рендер: `<component :is='item.type'>` в шаблоне `#vendor-item`.

### 3.1 Исходные листы Google Sheet (схема честного dump'а в `data/raw/*.json`)

**Структура листов — блочная** (важно для парсера): лист состоит из повторяющихся блоков
`заголовок категории (чёрный фон)` → `подкатегория` → **своя шапка таблицы** → строки данных → пустая строка → следующий. Пустая строка — разделитель блоков; шапка у **каждого блока своя**, и число колонок в ней разное. Фактически:
- `weapons`: `Exotic` → шапка `Name|Talent 1|Talent 2|Talent 3|Location|Vendor` (10 строк); `High End` → 6 подкатегорий (Pistol, SMG, Assault Rifle, Shotgun, Marksman Rifle, LMG), у **Pistol талантов только 2** (шапка `Name|Talent 1|Talent 2||Location|Vendor`), у остальных 3.
- `gear`: `Gear Set` и `High End` → 6 слотов каждый; шапка слота своя: Chest/Gloves `Attribute 1..3`, Mask/Backpack `Attribute 1..2`, Knee Pads `Attribute 1..4`, Holster только `Attribute 1`.
- `weapon-mods`: `Magazine|Muzzle|Underbarrel|Sight` (одноуровневые — подкатегории нет, `_top` = `_section`); шапка `Name | (значение) | Attribute 1 | (значение) | Attribute 2 | …`, **значение стоит СЛЕВА от своего атрибута**; у Muzzle до `Attribute 4`.
- `gear-mods`: `High End|Superior`, шапка одна; колонки `name` нет (первая пустая).

Поэтому адаптеры **не хардкодят номера колонок**, а идут по шапке своего блока: в каждой строке raw-dump лежит `_header` — позиционный список колонок этого блока (см. ниже).

`service.py` пишет **два формата**:
- `data/<slug>.json` — **item-модель страницы** (раздел 3), то, что грузит `js/index.js`; строится адаптерами `ADAPTERS` (см. ниже про дефолты).
- `data/raw/<slug>.json` — **честный sheet-native dump** (массив объектов-строк на лист), из которого строится адаптер. Поля = имена шапки блока (slug-ified; дубликаты → `_2`; безымянные колонки → `c<i>`), плюс:
  - `_row` — номер строки в листе; `_top` — верхний раздел (чёрный фон); `_section` — ближайший (у одноуровневых листов = `_top`); `_header` — **шапка этого блока** (позиционный список колонок, включая `c<i>` для безымянных): по ней адаптеры и раскладывают значения, т.к. у каждой категории шапка своя; `_recommended` — оранжевая подсветка (см. ниже).
  - `weapons`: `name, talent_1..N, location, vendor` (N зависит от блока: 2 у Pistol, 3 у остальных) — разделы: `Exotic`; `High End`→`Pistol|SMG|Assault Rifle|Shotgun|Marksman Rifle|LMG`.
  - `gear`: `name, main_stat` (напр. `"1218 ST"`, `"1139 FA"`), `attribute_1..N` (напр. `"4 All Resistances"`), `location, vendor` — разделы: `Gear Set`/`High End`→`Chest|Mask|Knee Pads|Backpack|Gloves|Holster`; N = 3 (Chest/Gloves), 2 (Mask/Backpack), 4 (Knee Pads), 1 (Holster).
  - `weapon-mods`: `name`, пары `cN` (значение) + `attribute_N` (имя), `location, vendor` — разделы: `Magazine|Muzzle|Underbarrel|Sight`; **значение стоит в колонке слева от своего атрибута** (`c1↔attribute_1`, `c3↔attribute_2`, `c5↔attribute_3`, `c7↔attribute_4` у Muzzle). Отдельного `attribute_4` в других блоках нет.
  - `gear-mods`: `c0` (пусто — колонки name нет), `type` (`Firearms|Armor|Electronics|Performance|Stamina Mod`), `stat_value` (`"245"`, `"-"`), `c3` (число-значение бонуса), `attribute`, `location, vendor` — разделы: `High End|Superior`.
- `welcome.json` — строки-заметки листа Welcome; строка `Last Update: ...` дублируется в `meta.json: sheet_last_update`.
- `meta.json`: `source`, `synced_at`, `sheets` (gid/url/rows/file/raw per sheet), `history` (последние 16 sync'ов).
- **Blueprints** (gid 1313121930) не синкронизируется (`SKIP_SHEETS` в `service.py`) — лист не используется (решение от 18.09.2026).

**Адаптеры с дефолтами** (`ADAPTERS` в `service.py`): `data/<slug>.json` → item-модель, **раскладка берётся из `_header` блока** (никаких хардкодных номеров колонок — иначе теряются данные: так терялась 4-я пара Muzzle `c7↔attribute_4`). Правила: `type`-тег компонента из `_top`/`_section` (Exotic→`exotic`, gear-мод High End→`purple-mod`, Superior→`gear-mod`); **`category`** — класс иконки из `_section` по таблицам `WEAPON_CLASSES`/`GEAR_SLOTS`/`MOD_CLASSES` (+ `EXOTIC_CLASSES` для экзотики — в листе класса нет); **`rarity='header-gs'`** для строк верхнего раздела `Gear Set` (включает значок сета и цвет имени `gs`); `price="$0"`; `bonus="-"`; gear `armor` = константа `GEAR_ARMOR="1248"`, `fire/stam/elec` = `main_stat` по типу (`_gear_stats`: `"1218 ST"` → stam, кобура `"1125|1244|1115"` → fire/stam/elec), `name` = имя + слот; talents — все `talent_*` блока по порядку (2 или 3); gear `armor=main_stat`, `major=первый attribute_*`, `minor=` остальные (1..3 шт. по слоту); weapon-mod `attributes` = все пары `значение атрибут` через `<br/>`; gear-mod `stat=stat_value`, `attribute="c3 attribute"`. Служебные `_row/_top/_section` переносятся в item (страница их игнорирует, а поиск/отладка удобнее). Сверка «raw ↔ item» после правок адаптера: **0 расхождений** по числу талантов/атрибутов/пар.

**`recommended` — не дефолт, а реальные данные**: в листе рекомендованные позиции подсвечены оранжевым (заметка в Welcome: "Recommended Items are highlighted with this shade of orange"), цвет `#ffbb7f`. Парсер помечает строку `_recommended: true` (сравнение **по цвету**, не по номеру класса — в разных листах это `sN` с разными N), адаптер отдаёт `recommended: "Yes"` (страница: класс `req` + `recommended == 'Yes'`). На 18.09.2026: weapons 3, gear 4, weapon-mods 3, gear-mods 3.

**Чего в листе нет** (и что страница поэтому не покажет): `dmg/rpm/mag` у оружия, цены, **броня** — вместо неё показывается стандартное `1248` (`GEAR_ARMOR` в `service.py`); колонка `Main Stat` листа — это **основной атрибут** (`1218 ST`, у кобуры `1125|1244|1115`), он уходит в блоки FA/ST/EL, а не в ARMOR. Отдельно: **иконки слотов** страница выводит regex'ом по `name` (`weapon.vue` — по `bonus`, `gear.vue` — по `name`, см. 4.5/4.6), а имена из листа ("Enduring", "D3-FNC", "Extended Magazine") под эти regexp не подходят — карточка рендерится, но иконка может остаться дефолтной (`pistol`/`none`). Настоящий класс/слот есть в `_section` листа — если нужны верные иконки, это правка фронтенда (пробрасывать `_section` в computed), а не дефолт.

## 4. Ключевые паттерны и правила разработки

### 4.1 Порядок подключения скриптов (HARD RULE)
`index.html` подключает скрипты в фиксированном порядке: сначала библиотеки, затем `weapon.vue` → `weapon-mod.vue` → `gear-mod.vue` → `gear.vue` → `vendor-item.vue` → `index.js`. Файлы `.vue` — **обычный JS**, задающий глобальные константы (`Weapon = {...}` БЕЗ `function`/`var` — имплицитный global, работает только в non-strict). `vendor-item.vue` ссылается на них; нарушить порядок нельзя. `index.js` —последним.

### 4.2 Шаблоны живут в `index.html`
Каждый компонент — `template: '#id'`, шаблон в `<template id='...'>` в `<head>`/`<body>` `index.html`. Новый компонент = новый `<template>` в `index.html` + файл-компонент + `Vue.component(...)` (или глобальная константа + регистрация в `vendor-item.vue`).

### 4.3 Добавление нового типа item — чек-лист
1. Новый тип в JSON-источнике (внешний).
2. `js/<type>.vue` с компонентом (glob const, `props: ['item']`, `template: '#<type>'`).
3. `<template id='<type>'>` в `index.html`.
4. `<script src='js/<type>.vue'>` в `index.html` **до** `js/vendor-item.vue`.
5. Запись в `components` объекта `vendor-item.vue`.
6. **Запись в `fields2look` в `js/index.js`** — без неё filter **падает** (`fields2look[item.type].forEach` на undefined → TypeError).
7. CSS-классы: `.<type>` для имени, иконки, редкости.

### 4.4 Глобальное состояние — один объект + Vue reactivity
`app_data` (global `var`) — источник правды: `items`, `filter`, `filtered_items`. Данные грузятся в `created:` через `updateItems()` (4 параллельных `fetch`). Filter — `watch: filter` → regexp `'i'` по конкатенации полей из `fields2look`. Метод `update` экспортирован наружу (можно вызвать `app.methods.update()` из консоли).
Правило: новые реактивные поля добавлять в `app_data` **до** создания `Vue`-инстанса (иначе не будут реактивными).

### 4.5 Классификация: сначала данные, потом регулярки
Класс иконки берётся из `item.category`, если он есть (**так приходят данные из листа**, см. 3.1) — это точный класс из раздела таблицы. Регэкспы по `name`/`bonus` (`types_list` в `js/gear.vue`, `js/weapon.vue`, `js/weapon-mod.vue`) остались **фолбэком** для данных без `category`. Сеты брони (`sets_list` в `js/gear.vue`) по-прежнему определяются регэкспом по `name` — имена сетов в листе совпадают с этим списком; новая категория/сет = правка соответствующего списка в компоненте + (для классов из листа) таблица в `service.py` (`WEAPON_CLASSES`/`GEAR_SLOTS`/`MOD_CLASSES`/`EXOTIC_CLASSES`).

### 4.6 Иконки — CSS-спрайты, не HTML-имиджи
Класс = категория (`.gear-icon.holster`, `.talent.accurate`, `.weapon-type-ar`). Класс строится на лету: `talent.toLowerCase().replace(/[- ]*/g,'')` — имя talent из JSON должно совпадать с css-классом. Новый talent/mode/slot = новая строка в css-спрайте + класс в `css/gear.css`/`css/talents.css`/`css/style.css`. Проверка «иконка реально рисуется» — `tools/inspect_icons.py` (см. 4.11).

### 4.7 Пути ассетов — префикс `/divn/` (HARD RULE)
Все `url(...)` в CSS и `@font-face` используют **абсолютные** пути с префиксом `/divn/` (напр. `/divn/fonts/Borda/Borda.ttf`, `/divn/images/talents.png`) — приложение деплойится под корнем сайта `/divn/`. Локально из корня файла стили/шрифты/иконки **не загрузятся**. Новая ссылка на ассет в CSS **обязана** использовать `/divn/`. Это осознанный production-path, не опечатка.

### 4.8 Обработка ошибок — примитивная, не ломать fetch-цикл
`fetch().then(r => r.status==200 ? r.json() : undefined).then(json => json.forEach(...))` — при 4xx/5xx `json` = `undefined` → **TypeError в then** (не перехвачен). Каждый из 4 endpoint-ов независим; сбой одного не блокирует остальные, но рвёт пайплайн (unhandled rejection). При доработке: не переходно заменять `fetch` на `axios` (axios подключён, но не используется) — только если меняется весь подход.

### 4.9 3D-tilt / deviceorientation
`deviceorientation.gamma → rotate3d` на контейнере `.container` (transform в `css/style.css` + `UpdateContainer()` в `js/index.js`). Дебаунс **сломан** (см. ниже). На десктопе наклон держит значение по умолчанию из CSS. Не трогать без запроса.

### 4.10 Responsive
Grid `.container` в `css/style.css`: 5 колонок → 4 → 3 → 2 → 1 по breakpoint'ам 1849/1479/1109/739px. Карточка `.item` — фиксированная 3-колоночная grid с `grid-template-areas`.

### 4.11 Сервис `service.py` — правила
- Stdlib-only (`.venv` пустой: только pip). Запуск: `.venv/bin/python service.py [--port 8090] [--interval сек] | --sync-only`.
- Cycle: sync on start, затем раз в `--interval` (по умолчанию 604800 сек = неделя); при сбое sync — retry раз в 15 минут, старые `data/*.json` сохраняются (write атомарный: `.tmp` + `os.replace`).
- API: `GET /` (JSON index, поле `app` = путь к странице), `GET /status` (meta + `next_sync_at`), `GET /data/<slug>.json` (item-модель), `GET /data/raw/<slug>.json` (честный dump), `POST /sync`.
- **Статика и страница — тем же процессом**: `GET /divn/` (→ `index.html`), `GET /divn/<path>` — любой файл проекта, кроме dot-каталогов (`.git`, `.venv`, `.work`, `.codegraph`) и собственных исходников сервиса (`service.py`, `demo-server.js`); `GET /divn` → 301 на `/divn/`; есть `HEAD`. Обход каталога (`/divn/../`, `%2e%2e`) блокируется (403/404). MIME по расширению (`.vue` отдаётся как `application/javascript`, файлы без расширения — `text/plain`), для `.html`/`.json` — `Cache-Control: no-cache` (данные обновляются раз в неделю).
- Парсинг: `html.parser` (не bs4) по статичным subpage-листам `{SOURCE}/sheet?headers=false&gid={gid}`; список листов (name→gid) парсится из pubhtml-страницы regex'ом `name: "..." ... gid: "..."`.
- Section-логика: строка = секция, если ровно одна непустая ячейка и её CSS-стиль — не "note" (border/vertical-align); top-секция = чёрный фон. Если в листе черных нет — каждая секция считается top (`_top` = `_section`). «Рекомендовано» = оранжевый фон `#ffbb7f` (сравнение по цвету, не по номеру класса). Всё это завязано на CSS published-страницы: если владелец листа перестилизует таблицу — прогнать `--sync-only` и сверить секции/`_recommended` с `data/raw/*.json`.
- `data/*.json` — артефакты sync'а: не править руками, не коммитить изменения от руки; при необходимости пересчитать — `POST /sync` или `--sync-only`.
- **Проверка после правки парсера/адаптера**: `node tools/smoke_page.js` — прогоняет реальные `computed` компонентов из `js/*.vue` по `data/*.json` и ловит падения вида `undefined.split(...)` + отсутствующие css-классы иконок (сейчас: 247 items, OK). Плюс `--sync-only` и сверка числа строк/секций с `data/raw/*.json`.
- **Проверка иконок в браузере**: `.venv/bin/python tools/inspect_icons.py [url]` — кладёт в корень `probe.html`, грузит реальную страницу в iframe через headless Chrome и печатает `getComputedStyle` каждой иконки (спрайт, background-position, размер). Так проверяется связка «класс → правило CSS → спрайт» на настоящем рендере (сейчас: 34 класса, все с ненулевым размером). Прогонять после правок CSS-спрайтов или логики `category`.
- Частота запросов к Google — 1 раз в неделю (по просьбе владельца данных; на листе есть anti-scraping заметка — частых fetch'ей не делать).

## 5. Известные дефекты (не чинить без запроса, но знать)

1. **`_.debounce` мёртвый код** (`js/index.js:57-58`): результат не используется; `handleOrientation` вызывается на каждое событие.
2. **`var pos = document.getElementById('pos')`** (`js/index.js:41`) — элемента `#pos` нет, `pos === null`, неиспользуется.
3. **Filter падает на неизвестном `item.type`** (`js/index.js:83`): `fields2look[item.type].forEach` → TypeError.
4. **`weapon.vue` → `type` computed**: `this.item.bonus.match(...)` — если `bonus` не строка/`undefined`, TypeError. Данные из внешнего JSON в норме это содержат, но fragile.
5. **`vendor-item.vue` → `cur` computed**: `price.replace(...)`/`split` без проверок — падает на пустой `price`; `'$'`-ветка не учитывает локальную валюту с пробелом.
6. **`gear.vue` → `fire/stam/elec`**: `.replace(/^[\s-]*$/, 205)` — `Number` vs `String` replacement mismatch; работает из-за String-семантики, но хрупко.
7. **`index.html` — bootstrap-стrokes** (строки 5-6, 8) — закомментирован, но остаётся.
8. **`css/talentslist`** — txt-список имён talents; не подключён ни к HTML, ни к JS (референтный артефакт, вероятно служил для создания `css/talents.css`).
9. **`.vue`-расширение без SFC-синтаксиса** — не путать с Single File Components; это просто JS-объекты. Переименовывать только если меняем весь конвейер.

## 6. Что НЕ делать

- Не вводить npm/build/vite: проект статический, деплойится целиком как директория `/divn/`.
- Не переключать `fetch` на `axios` точечно —axios не используется, `fetch` работает.
- Не менять префикс `/divn/` в CSS без изменения деплоя.
- Не нарушать порядок `<script>` в `index.html`.
- Не переключать `url` на внешние источники — первоисточник мёртв; страница берёт `data/*.json` (их генерирует `service.py`).
- Не править `data/*.json` руками и не увеличивать частоту sync'а выше раза в неделю (волонтёрские данные, на листе anti-scraping заметка).
- Не ставить зависимости в `.venv` без необходимости: `service.py` осознанно stdlib-only.
- Не переписывать ES5-стиль (`var`, callbacks) в ES6/модули точечно — без смены всего конвейера это только усложнит diff.

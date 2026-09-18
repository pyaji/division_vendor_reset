# AI_CONTEXT — division1_vendor_reset

Инструкция для AI-агентов. Проект: статическое веб-приложение, **нет build-системы, нет package.json**, всё запускается как plain HTML/JS. Git: один коммит `init`, ветка `master`, remote не задан.

## 1. Глобальная цель

Каталог товаров веноу (vendor reset inventory) для **The Division 1**: оружие, моды оружия, броня (gear), моды брони (gear-mods / purple-mods). Приложение загружает JSON-дамп с внешнего сайта, отрисовывает карточки с иконками/статами/ценами и позволяет фильтровать по regexp. Целевая аудитория — игроки, планирующие сброс веноу на мобильных/десктопных браузерах.

Данные лежат в **`data/*.json`** (4 файла: `weapons.json`, `weapon-mods.json`, `gear.json`, `gear-mods.json`). Первоисточник `rubenalamina.mx/division/*.json` через `cors.io` **недоступен**, `url` в `js/index.js` переключён на `'data/'` (старое значение оставлено комментарием). Схемы см. раздел 3.

**Запуск для демо:** fetch работает только по http(s), а ассеты в CSS идут с абсолютным префиксом `/divn/` — сервер должен отдавать проект как `/divn/`. Минимальный вариант (node, без зависимостей):

```
node /tmp/d1server.js   # маппинг /divn/* → корень проекта, порт 8791
# открыть http://127.0.0.1:8791/divn/index.html
```

## 2. Технологический стек

- **JS (ES5-стиль, `var`, без модулей)**, выполняется через `<script>` тэги из `index.html` в явном порядке подключения.
- **Vue 2** (global build, `js/vue.js`, v~2.x) — SPA на одном инстансе `new Vue({ el: '#app' })`.
- **Axios** (`js/axios.min.js`) — подключён, но **НЕ используется**; для данных используется нативный `fetch`.
- **Lodash** (`js/lodash.min.js`) — используется фактически только как глобальная зависимость; вызовы `_.debounce(...)` в `js/index.js` **битые** (результат не привязан к обработчикам — мёртвый код).
- **CSS** — vanilla, без препроцессора. Шрифт **Borda** (ttf в `fonts/Borda/`).
- **Данные** — JSON с внешнего endpoint (см. выше). Схемы см. раздел 3.
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
data/*.json         # демо-данные: weapons / weapon-mods / gear / gear-mods (схемы ниже)
css/style.css       # База: grid-контейнер, карточки .item, currency, responsive
css/gear.css        # Спрайт-иконки gear по слоту (chest/mask/...) + редкости
css/talents.css     # Спрайт-иконки talents (talent.<name>)
css/fonts.css       # @font-face Borda (пути с префиксом /divn/ — см. правило 5)
css/talentslist      # текстовый файл: список имён talents (по одному в строку) — справочник для css-классов `css/talents.css`
fonts/Borda/        # ttf-шрифты Borda всех весов
images/             # Спрайты: talents.png, weapons.png, stats.png, sets.png; images/items/*.png — иконки слотов gear
.codegraph/         # Индекс codegraph (не часть приложения, .gitignore внутри)
```

**Item-модель** (поля зависят от `type`; все значения должны быть строками, где указано):
- общее: `type` (строка-тег компонента), `name`, `vendor`, `price` (строка вида `"$1,234"` или `"123 К"`/`"123 С"`), `recommended` (`"Yes"`/нет).
- `weapon` / `exotic`: `bonus` (текст; `"-"` = нет), `dmg`, `rpm`, `mag`, `talent1..talentN` (`"-"` = unset).
- `weapon-mod`: `type`-категория, `attributes` (строка, разделитель `<br/>`).
- `gear`: `rarity` (css-класс, напр. `header-gs` = GS), `armor`, `fire`, `stam`, `elec` (`"-"` → рендерится как 205), `minor`, `major` (строки `<br/>`).
- `gear-mod` / `purple-mod`: `stat` — `"-"` (без %/букв) = performance-мод, `"30%"` и т.п. = мод со стафом (рендерит `[stat, attribute]`), `attribute` — текст стафа.

В `data/` лежат 52 демо-item'а, уже прогоненные по логике страницы (regex-типы, парсинг цен, slots/sets) — использовать как эталон при добавлении данных.

**Критически:** `item.type` — это **имя Vue-компонента**. `vendor-item.vue` маппит: `weapon`, `exotic` → `Weapon`; `weapon-mod` → `WeaponMod`; `gear` → `Gear`; `gear-mod`, `purple-mod` → `GearMod`. Динамический рендер: `<component :is='item.type'>` в шаблоне `#vendor-item`.

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

### 4.5 Классификация по регуляркам, а не по данным
Типы/категории/сеты определяются регэксп по `name`/`bonus` (см. `types_list`, `sets_list` в `js/gear.vue`, `js/weapon.vue`, `js/weapon-mod.vue`), а не полями из JSON. Это **хрупкая** логика: новые названия/модификации в игре → новый тип молча становится `'none'`/`'pistol'`/`false`. Новые категории добавлять только в эти списки.

### 4.6 Иконки — CSS-спрайты, не HTML-имиджи
Класс = категория (`.gear-icon.holster`, `.talent.accurate`, `.weapon-type-ar`). Класс строится на лету: `talent.toLowerCase().replace(/[- ]*/g,'')` — имя talent из JSON должно совпадать с css-классом. Новый talent/mode/slot = новая строка в css-спрайте + класс в `css/gear.css`/`css/talents.css`/`css/style.css`.

### 4.7 Пути ассетов — префикс `/divn/` (HARD RULE)
Все `url(...)` в CSS и `@font-face` используют **абсолютные** пути с префиксом `/divn/` (напр. `/divn/fonts/Borda/Borda.ttf`, `/divn/images/talents.png`) — приложение деплойится под корнем сайта `/divn/`. Локально из корня файла стили/шрифты/иконки **не загрузятся**. Новая ссылка на ассет в CSS **обязана** использовать `/divn/`. Это осознанный production-path, не опечатка.

### 4.8 Обработка ошибок — примитивная, не ломать fetch-цикл
`fetch().then(r => r.status==200 ? r.json() : undefined).then(json => json.forEach(...))` — при 4xx/5xx `json` = `undefined` → **TypeError в then** (не перехвачен). Каждый из 4 endpoint-ов независим; сбой одного не блокирует остальные, но рвёт пайплайн (unhandled rejection). При доработке: не переходно заменять `fetch` на `axios` (axios подключён, но не используется) — только если меняется весь подход.

### 4.9 3D-tilt / deviceorientation
`deviceorientation.gamma → rotate3d` на контейнере `.container` (transform в `css/style.css` + `UpdateContainer()` в `js/index.js`). Дебаунс **сломан** (см. ниже). На десктопе наклон держит значение по умолчанию из CSS. Не трогать без запроса.

### 4.10 Responsive
Grid `.container` в `css/style.css`: 5 колонок → 4 → 3 → 2 → 1 по breakpoint'ам 1849/1479/1109/739px. Карточка `.item` — фиксированная 3-колоночная grid с `grid-template-areas`.

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
- Не переключать `url` на внешние источники — первоисточник мёртв; всё демо — на `data/*.json`.
- Не переписывать ES5-стиль (`var`, callbacks) в ES6/модули точечно — без смены всего конвейера это только усложнит diff.

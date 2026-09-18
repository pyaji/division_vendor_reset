// Smoke-test: прогоняет РЕАЛЬНЫЕ computed-функции компонентов страницы
// (js/*.vue, они же обычный JS) по сгенерированным data/*.json.
// Ловит два класса проблем:
//   1) падения вида "undefined.split(...)" до открытия браузера;
//   2) несуществующие css-классы иконок (тип оружия / слот брони / сет / мод).
// Запуск: node .work/smoke_page.js   (из корня проекта)
const fs = require('fs')
const vm = require('vm')
const path = require('path')

const root = path.resolve(__dirname, '..')
const components = {}
const sandbox = {
  Vue: { component: (name, opts) => { components[name] = opts } },
  console,
}
vm.createContext(sandbox)
for (const f of ['weapon.vue', 'weapon-mod.vue', 'gear-mod.vue', 'gear.vue', 'vendor-item.vue']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'js', f), 'utf8'), sandbox, { filename: f })
}
const vendorItem = components['vendor-item']
if (!vendorItem) throw new Error('vendor-item.vue did not register via Vue.component')
const byTag = vendorItem.components

// все классы и составные селекторы (.gear-icon.chest) из css/*.css
const cssClasses = new Set()
const cssPairs = new Set()
for (const f of fs.readdirSync(path.join(root, 'css'))) {
  const text = fs.readFileSync(path.join(root, 'css', f), 'utf8')
  for (const m of text.matchAll(/\.([a-zA-Z][\w-]*)/g)) cssClasses.add(m[1])
  for (const m of text.matchAll(/\.([a-zA-Z][\w-]*)\.([a-zA-Z][\w-]*)/g)) cssPairs.add(`${m[1]}.${m[2]}`)
}
const icons = (pair, key) => cssPairs.has(`${pair}.${key}`)

const files = ['weapons', 'weapon-mods', 'gear', 'gear-mods']
const fields2look = {
  weapon: ['name', 'type'], exotic: ['name', 'type'], gear: ['name'],
  'gear-mod': ['type', 'attribute', 'stat'], 'weapon-mod': ['type', 'attributes'],
  'purple-mod': ['type', 'attribute'],
}

let checked = 0
const problems = []
const iconStats = { weapon: {}, slot: {}, set: {}, mod: {} }
const bump = (bucket, key) => { iconStats[bucket][key] = (iconStats[bucket][key] || 0) + 1 }
// шаблоны index.html: оружие -> 'weapon-type-'+type; gear/mod -> два класса [base, type]
const checkClass = (cls, where) => {
  if (!cls || cls === 'none' || cls === 'false') problems.push(`${where}: icon class "${cls}"`)
  else if (!cssClasses.has(cls)) problems.push(`${where}: css class .${cls} does not exist`)
}
const checkIcon = (base, key, where) => {
  if (!key || key === 'none' || key === 'false') problems.push(`${where}: icon key "${key}"`)
  else if (!icons(base, key)) problems.push(`${where}: no css rule .${base}.${key}`)
}

for (const file of files) {
  const items = JSON.parse(fs.readFileSync(path.join(root, 'data', file + '.json'), 'utf8'))
  for (const item of items) {
    const ctx = { item }
    const run = (label, fn) => {
      try { return fn() } catch (e) { problems.push(`${file}: ${item.name} -> ${label}: ${e.message}`) }
    }
    run('vendor-item.recommended', () => vendorItem.computed.recommended.call(ctx))
    run('vendor-item.price', () => vendorItem.computed.price.call(ctx))
    run('vendor-item.cur', () => vendorItem.computed.cur.call(ctx))
    run('vendor-item.name_color', () => vendorItem.computed.name_color.call(ctx))
    run('index.js filter', () => {
      const keys = fields2look[item.type]
      if (!keys) throw new Error(`no fields2look entry for type "${item.type}"`)
      keys.forEach(k => { if (item[k] === undefined) throw new Error(`missing field ${k}`) })
    })

    const comp = byTag[item.type]
    if (!comp) { problems.push(`${file}: no component mapped for type "${item.type}"`); continue }
    const computed = {}
    for (const [name, fn] of Object.entries(comp.computed || {})) {
      computed[name] = run(`${item.type}.${name}`, () => fn.call(ctx))
      if (['talents', 'attributes', 'stat'].includes(name)) {
        run(`${item.type}.${name}[]`, () =>
          (computed[name] || []).forEach(v => String(v).toLowerCase().replace(/[- ]*/g, '')))
      }
    }

    // иконки: ровно те классы, что подставляет шаблон index.html
    if (item.type === 'weapon' || item.type === 'exotic') {
      const t = computed.type
      checkClass('weapon-type-' + t, `${file}: ${item.name}`)
      bump('weapon', t)
    } else if (item.type === 'gear') {
      checkIcon('gear-icon', computed.type, `${file}: ${item.name} (slot)`)
      bump('slot', computed.type)
      if (item.rarity === 'header-gs') {           // шаблон: v-if='item.rarity == "header-gs"'
        checkIcon('set-icon', computed.set, `${file}: ${item.name} (set)`)
        bump('set', computed.set)
      }
    } else if (item.type === 'weapon-mod') {
      checkIcon('weapon-mod-icon', computed.type, `${file}: ${item.name}`)
      bump('mod', computed.type)
    }
    checked++
  }
}

const flat = (o) => Object.entries(o).sort().map(([k, v]) => `${k}:${v}`).join('  ')
console.log(`checked items: ${checked}`)
console.log(`weapon icons:     ${flat(iconStats.weapon)}`)
console.log(`gear slots:       ${flat(iconStats.slot)}`)
console.log(`gear sets:        ${flat(iconStats.set)}`)
console.log(`weapon-mod icons: ${flat(iconStats.mod)}`)
if (problems.length) {
  console.log(`PROBLEMS (${problems.length}):`)
  problems.slice(0, 20).forEach(p => console.log('  - ' + p))
  process.exit(1)
}
console.log('OK: no exceptions, no missing css classes')

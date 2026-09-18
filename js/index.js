var gear_types = [
  'weapons',
  'weapon-mods',
  'gear',
  'gear-mods'
]
var url = 'https://cors.io/?http://rubenalamina.mx/division/'
var app_data = {
  items: [],
  message: new Date(),
  filter: '',
  filtered_items: [],
}


function updateItems() {
  app_data.items = []
  gear_types.forEach(function(item) {
    var i = url + item + '.json'
    // console.warn(i)
    fetch(i).then(function(response) {
      if (response.status == 200) {
        return response.json()
      }
    }).then(function(json) {
      json.forEach(function(item) {
        app_data.items.push(item)
      })
    })
  })
}

var SupportOrientation = window['deviceorientation'] ? true : false
function UpdateContainer(d) {
  d = d ? d : -1;
  var container = document.getElementById('vender_reset')
  var h = container.scrollHeight
  container.style.transform = "perspective(" + h + "px) rotate3d(0, 5, 0, " + d + "deg)"
  console.warn(h)
}
var pos = document.getElementById('pos')
function handleOrientation(event) {
  // var x = event.beta;  // In degree in the range [-180,180]
  var x = event.gamma 
  var y = event.beta
  var z = event.alpha
  x = x / -5
  x = x - 2
  if (x >  7) { x =  7};
  if (x < -7) { x = -7};
  UpdateContainer(x)
}
function MoveHandler(event) {
  console.warn(event)
}

_.debounce(handleOrientation, 400)
_.debounce(MoveHandler, 400)


window.addEventListener('deviceorientation', handleOrientation);

var app = new Vue({
  el: '#app',
  data: app_data,
  created: function () {
    updateItems()
    this.filtered_items = this.items
  },
  watch: {
    filter: function(val) {
      var filter = new RegExp(val, 'i')
      var fields2look = {
        weapon: ['name', 'type'],
        exotic: ['name', 'type'],
        gear: ['name'],
        'gear-mod': ['type', 'attribute', 'stat'],
        'weapon-mod': ['type', 'attributes'],
        'purple-mod': ['type', 'attribute']
      }
      this.filtered_items = this.items.filter(function(item) {
        var fields_string = ' '
        fields2look[item.type].forEach(function(i) {
          fields_string += item[i]
        })
        return ! val || (val && fields_string.match(filter))
      })
      setTimeout(UpdateContainer, 200)
    },
    filtered_items: {
      handler: UpdateContainer,
      immediate: true
    }
  },
  methods: {
    update: updateItems,
  }
});
 
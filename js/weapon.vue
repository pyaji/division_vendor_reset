Weapon = {
    props: ['item'],
    template: '#weapon',
    computed: {
        talents: function() {
            var t = Object.keys(this.item).filter(function(item) {return item.startsWith('talent')})
            ret = []
            wpn = this
            t.forEach(function(element) {
                if(wpn.item[element] !== '-') {
                    ret.push(wpn.item[element])
                }
            })
            return ret
        },
        type: function() {
            // класс из данных (service.py: раздел листа Pistol/SMG/AR/...) — он точный
            if (this.item.category) {
                return this.item.category
            }
            ret = 'pistol'
            types_list = {
                'lmg': /out of cover/i,
                'smg': /critical hit/i,
                'ar': /Armor Damage/i,
                'marksman': /headshot/i,
                'shotgun': /stagger/i
            }
            var wpn = this
            Object.keys(types_list).forEach(function(key) {
                value = types_list[key]
                if(wpn.item.bonus.match(value)) {
                    ret = key
                    return key
                }
            })
            return ret
        }
    }
}
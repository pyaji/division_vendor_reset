Vue.component('vendor-item', {
    props: ['item'],
    components: {
        'weapon': Weapon, 
        'exotic': Weapon, 
        'weapon-mod': WeaponMod,
        'gear': Gear,
        'gear-mod': GearMod,
        'purple-mod': GearMod
    },
    computed: {
        recommended: function() {
            return this.item.recommended == 'Yes'
        },
        price: function() {
            price = this.item.price.split(' ')[1]
            if (! price) {
                price = this.item.price.split('$')[1]
            }
            return price.replace(',', ', ')
        },
        cur: function() {
            ret = this.item.price.startsWith('$') ? 'dol' : price = this.item.price.split(' ')[0]
            return ret.toLowerCase()
        },
        name_color: function() {
            ret = 'standart'
            if (this.item.type == 'exotic') {
                ret = 'exotic'
            } else if (this.item.type == 'purple-mod') {
                ret = 'purple'
            } else if (this.item.type == 'gear', this.item.rarity == 'header-gs') {
                ret = 'gs'
            }
            return ret
        }
    },
    template: '#vendor-item'
})

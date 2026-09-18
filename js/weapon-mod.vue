WeaponMod = {
    props: ['item'],
    template: '#weapon-mod',
    computed: {
        attributes: function() {
            return this.item.attributes.split('<br/>')
        },
        type: function() {
            types_list = {
                'magazine': /magazine/i,
                'grip': /grip|pointer|hand|PEQ-15/i,
                'scope': /sight|scope/i,
                'suppressor': /Suppressor|Flash Hider|muzzle|Compensator/i
            }
            ret = false
            gmod = this.item.name
            Object.keys(types_list).forEach(function(key) {
                if (gmod.match(types_list[key])) {
                    ret = key
                    return
                }
            })
            return ret
        }
    }
}
Gear = {
    props: ['item'],
    template: '#gear',
    computed: {
        type: function() {
            // слот из данных (service.py: раздел листа Chest/Mask/...) — он точный
            if (this.item.category) {
                return this.item.category
            }
            types_list = {
                'chest': /chest/i,
                'mask': /mask/i,
                'backpack': /backpack/i,
                'gloves': /gloves/i,
                'kneepads': /knee[\s]?pads/i,
                'holster': /holster/i
            }
            ret = 'none'
            gear = this
            Object.keys(types_list).forEach(function(item) {
                if(gear.item.name.match(types_list[item])) {
                    ret = item
                    return
                }
            })
            return ret
        },
        set: function() {
            sets_list = {
                'striker': /striker/i,
                'hunters': /hunter/i,
                'sentry': /sentry/i,
                'd3-fnc': /d3-fnc/i,
                'predator': /predator/i,
                'nomad': /nomad/i,
                'reclaimer': /reclaimer/i,
                'firecrest': /firecrest/i,
                'tactician': /tactician/i,
                'alphabridge': /alphabridge/i,
                'banshee': /banshee/i,
                'deadeye': /DeadEYE/i,
                'finalmeasure': /final Measure/i,
                'lonestar': /Lone Star/i
            }
            ret = 'none'
            gear = this.item.name
            Object.keys(sets_list).forEach(function(item) {
                if(gear.match(sets_list[item])) {
                    ret = item
                    return
                }
            })
            return ret
        },
        major: function() {
            ret = this.item.major.split('<br/>').filter(function(item) {
                return ! item.match(/^[-\s]*$/)
            })
            return ret.length ? ret : false
        },
        minor: function() {
            ret = this.item.minor.split('<br/>').filter(function(item) {
                return ! item.match(/^[-\s]*$/)
            })
            return ret.length ? ret : false
        },
        fire: function() {
            return this.item.fire.replace(/^[\s-]*$/, 205)
        },
        stam: function() {
            return this.item.stam.replace(/^[\s-]*$/, 205)
        },
        elec: function() {
            return this.item.elec.replace(/^[\s-]*$/, 205)
        }
    }
}
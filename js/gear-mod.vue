GearMod = {
    props: ['item'],
    template: '#gear-mod',
    computed: {
        has_stat: function() {
            ret =  this.item.stat.replace(/[-\s\d]*/i, '').toLowerCase()
            return ret
        },
        stat: function() {
            return this.has_stat ? [this.item.stat, this.item.attribute] : [this.item.attribute]
        }
    }
}
odoo.define('l10n_cl_fe.upgrade_widgets', function (require) {
"use strict";

/**
 *  The upgrade widgets are intended to be used in config settings.
 *  When checked, an upgrade popup is showed to the user.
 */

var AbstractField = require('web.AbstractField');
var basic_fields = require('web.basic_fields');
var core = require('web.core');
var Dialog = require('web.Dialog');
var field_registry = require('web.field_registry');
var framework = require('web.framework');
var relational_fields = require('web.relational_fields');

var _t = core._t;
var QWeb = core.qweb;

var FieldBoolean = basic_fields.FieldBoolean;
var FieldRadio = relational_fields.FieldRadio;

var AbstractFieldUpgrade = {
    _confirmUpgrade: function () {
        return this._rpc({
                model: 'res.users',
                method: 'search_count',
                args: [[["share", "=", false]]],
            })
            .then(function (data) {
                framework.redirect("https://odoocoop.cl/upgrade?num_users=" + data);
            });
    },
    _insertEnterpriseLabel: function ($enterpriseLabel) {},

    _openDialog: function () {
        var message = $(QWeb.render('ProUpgrade'));

        var buttons = [
            {
                text: _t("Be a Pro now"),
                classes: 'btn-primary',
                close: true,
                click: this._confirmUpgrade.bind(this),
            },
            {
                text: _t("Cancel"),
                close: true,
            },
        ];

        return new Dialog(this, {
            size: 'medium',
            buttons: buttons,
            $content: $('<div>', {
                html: message,
            }),
            title: _t("Be a Pro with OdooCoop"),
        }).open();
    },
    _render: function () {
        this._super.apply(this, arguments);
        this._insertEnterpriseLabel($("<span>", {
            text: "Pro",
            'class': "label label-primary oe_inline o_enterprise_label"
        }));
    },

    _resetValue: function () {},

    _onInputClicked: function (event) {
        if ($(event.currentTarget).prop("checked")) {
            this._openDialog().on('closed', this, this._resetValue.bind(this));
        }
    },

};

var UpgradeBoolean = FieldBoolean.extend(AbstractFieldUpgrade, {
    supportedFieldTypes: [],
    events: _.extend({}, AbstractField.prototype.events, {
        'click input': '_onInputClicked',
    }),
    renderWithLabel: function ($label) {
        this.$label = $label;
        this._render();
    },

    _insertEnterpriseLabel: function ($enterpriseLabel) {
        var $el = this.$label || this.$el;
        $el.append('&nbsp;').append($enterpriseLabel);
    },
    _resetValue: function () {
        this.$input.prop("checked", false).change();
    },
});

var UpgradeRadio = FieldRadio.extend(AbstractFieldUpgrade, {
    supportedFieldTypes: [],
    events: _.extend({}, FieldRadio.prototype.events, {
        'click input:last': '_onInputClicked',
    }),

    isSet: function () {
        return true;
    },

    _insertEnterpriseLabel: function ($enterpriseLabel) {
        this.$('label').last().append('&nbsp;').append($enterpriseLabel);
    },

    _resetValue: function () {
        this.$('input').first().prop("checked", true).click();
    },
});

field_registry
    .add('upgrade_odoocoop_boolean', UpgradeBoolean)
    .add('upgrade_odoocoop_radio', UpgradeRadio);

});

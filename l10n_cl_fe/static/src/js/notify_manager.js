odoo.define('l10n_cl_fe.notify_manager', function (require) {
"use strict";

    var bus = require('bus.bus').bus;
    var BasicModel = require('web.BasicModel');
    var field_registry = require('web.field_registry');
    var Notification = require('web.notification').Notification;
    var WebClient = require('web.WebClient');

    var DTENotification = Notification.extend({
        template: "DTENotification",

        init: function(parent, title, text, sticky, url) {
            this._super(parent, title, text, sticky);
            this.url = url;
            console.log(url);
            this.events = _.extend(this.events || {}, {
                'click .link2config': function() {
                    var self = this;

                    this._rpc({
                            route: '/web/action/load',
                            params: {
                                action_id: 'l10n_cl_fe.action_dte_config',
                            },
                        })
                        .then(function(r) {
                            return self.do_action(r);
                        });
                },

                'click .link2recall': function() {
                    this.destroy(true);
                    this._rpc({route: url.uri});
                },

                'click .link2showed': function() {
                    this.destroy(true);
                }
            });
        },
    });

    WebClient.include({
        display_dte_notif: function(notifications) {
            var self = this;
            var last_notif_timer = 0;

            // Clear previously set timeouts and destroy currently displayed dte notifications
            clearTimeout(this.get_next_dte_notif_timeout);
            _.each(this.dte_notif_timeouts, clearTimeout);
            _.each(this.dte_notif, function(notif) {
                if (!notif.isDestroyed()) {
                    notif.destroy();
                }
            });
            this.dte_notif_timeouts = {};
            this.dte_notif = {};

            // For each notification, set a timeout to display it
            _.each(notifications, function(notif) {
                self.dte_notif_timeouts[notif.id] = setTimeout(function() {
                    var sticky =  true;
                    if (notif.hasOwnProperty('sticky')){
                        sticky = notif.sticky;
                    }
                    var notification = new DTENotification(self.notification_manager, notif.title, notif.message, sticky, notif.url);
                    self.notification_manager.display(notification);
                    self.dte_notif[notif.id] = notification;
                }, notif.timer * 1000);
            });

            // Set a timeout to get the next notifications when the last one has been displayed
            if (last_notif_timer > 0) {
                this.get_next_dte_notif_timeout = setTimeout(this.get_next_dte_notif.bind(this), last_notif_timer * 1000);
            }
        },
        show_application: function() {
            // An event is triggered on the bus each time a dte event with alarm
            // in which the current user is involved is created, edited or deleted
            this.dte_notif_timeouts = {};
            this.dte_notif = {};
            bus.on('notification', this, function (notifications) {
                _.each(notifications, (function (notification) {
                    if (notification[1].type === 'dte_notif') {
                        this.display_dte_notif([notification[1]]);
                    }
                }).bind(this));
            });
            return this._super.apply(this, arguments);
        },
    });
})

require([
    "aps/load",
    "aps/xhr",
    "dojo/promise/all",
    "aps/Memory",
    "aps/Output",
    "dijit/registry",
    "aps/Button",
    "aps/Container",
    "aps/ready!cbcext/services/hub/aps_package/src/ui/js"
], function (load, xhr, all, Memory, Output, registry, Button, Container) {
    var page = [];
    all([
        xhr.post("/aps/2/navigation?bw_id=" + aps.context._sessionId, {
            data: JSON.stringify({
                "placeholder": "http://www.odin.com/products/services-selector/placeholder",
                "context": [],
                "parameters": {},
                "locale": "en_US"
            })
        }),
        xhr.get("/aps/2/resources?implementing(http://aps-standard.org/types/core/subscription/1.0),select(account,services),eq(account.aps.id," + aps.context.vars.admin.aps.id + ")").otherwise(function () {
            return [];
        }),
        xhr.get("/aps/2/resources?implementing(http://idsync.com/tenant/2.1),select(account,subscription),eq(account.aps.id," + aps.context.vars.admin.aps.id + ")").otherwise(function () {
            return [];
        }),
        xhr.get("/aps/2/resources?implementing(http://acronis.com/aps/cloud-backup-v1/tenant/9.0),select(account,subscription),eq(account.aps.id," + aps.context.vars.admin.aps.id + "),eq(type,RESELLER)").otherwise(function () {
            return [];
        }),
        xhr.get("/aps/2/resources?implementing(http://www.mozy.com/mozyProAPS2/mozyProAccount/1.8),select(account,subscription),eq(account.aps.id," + aps.context.vars.admin.aps.id + "),eq(accountType,R)").otherwise(function () {
            return [];
        })
    ]).then(function (results) {
        var navigations = results[0].items;
        var subscriptions = results[1];
        var idSync = results[2];
        var acronis = results[3];
        var mozy = results[4];
        var dataMemory = [];
        var i = 0;
        var j = 0;
        for (i = 0; i < subscriptions.length; i++) {
            var subscription = subscriptions[i];
            for (var k = 0; k < subscription.services.length; k++) {
                var service = subscription.services[k];
                if (service.aps.type.indexOf('tenant') !== -1) {
                    //Found a tenant
                    var tenantType = service.aps.type.split("/tenant", 1);
                    for (j = 0; j < navigations.length; j++) {
                        if (navigations[j].id.indexOf(tenantType) !== -1) {
                            dataMemory.push({
                                viewId: navigations[j].id + "1-main",
                                resource: service.aps.id,
                                subscription: service.aps.subscription,
                                subscriptionName: subscription.name,
                                subscriptionId: subscription.subscriptionId,
                                serviceStatus: service.aps.status,
                                subscriptionStatus: subscription.aps.status,
                                isTrial: subscription.trial,
                                isAcronis: false,
                                isMozy: false
                            });
                        }
                    }
                }
            }
        }
        if (idSync.length > 0) {
            xhr.post("/aps/2/navigation?bw_id=" + aps.context._sessionId, {
                sync: true,
                data: JSON.stringify({
                    "placeholder": "http://www.aps-standard.org/ui/service",
                    "context": [],
                    "parameters": {},
                    "locale": "en_US"
                })
            }).then(function (data) {
                if (!data) return;
                var onlyIDSync = data.items.filter(function (f) {
                    return f.id === 'http://www.idsync.com/aps/2.0#ccp';
                });
                for (var nav in onlyIDSync) {
                    console.log(nav);
                    navigations.push({
                        viewId: 'http://www.idsync.com/aps/2.0#ccp',
                        label: 'IDSync'
                    });
                }
            });
            for (i = 0; i < idSync.length; i++) {
                for (j = 0; j < navigations.length; j++) {
                    if (navigations[j].viewId == "http://www.idsync.com/aps/2.0#ccp") {
                        dataMemory.push({
                            viewId: 'http://www.idsync.com/aps/2.0#ad-cloud',
                            resource: idSync[i].aps.id,
                            subscription: idSync[i].aps.subscription,
                            subscriptionName: idSync[i].subscription.name,
                            subscriptionId: idSync[i].subscription.subscriptionId,
                            serviceStatus: idSync[i].aps.status,
                            subscriptionStatus: idSync[i].subscription.aps.status,
                            isTrial: idSync[i].subscription.trial,
                            isAcronis: false,
                            isMozy: false
                        });
                    }
                }
            }
        }
        for (i = 0; i < acronis.length; i++) {
            dataMemory.push({
                viewId: "http://www.acronis.com/aps/cloud-backup-v1#ccp--reseller-administrator--list",
                resource: acronis[i].aps.id,
                subscription: acronis[i].aps.subscription,
                subscriptionName: acronis[i].subscription.name,
                subscriptionId: acronis[i].subscription.subscriptionId,
                serviceStatus: acronis[i].aps.status,
                subscriptionStatus: acronis[i].subscription.aps.status,
                isTrial: acronis[i].subscription.trial,
                isAcronis: true,
                isMozy: false
            });
        }
        for (i = 0; i < mozy.length; i++) {
            dataMemory.push({
                viewId: "http://www.mozy.com/mozyProAPS2#mozyProReseller",
                resource: mozy[i].aps.id,
                subscription: mozy[i].aps.subscription,
                subscriptionName: mozy[i].subscription.name,
                subscriptionId: mozy[i].subscription.subscriptionId,
                serviceStatus: mozy[i].aps.status,
                subscriptionStatus: mozy[i].subscription.aps.status,
                isTrial: mozy[i].subscription.trial,
                isAcronis: false,
                isMozy: true
            });
        }
        var memory = new Memory({
            data: dataMemory,
            idProperty: "resource"
        });
        page = ["aps/PageContainer", {
            id: "page"
        },
            [
                ["aps/Output", {
                    type: "info",
                    value: _("Here you can manage services from subscriptions assigned to your account directly."),
                    closeable: false
                }],
                ["aps/Grid", {
                    id: 'servicesGrid',
                    store: memory,
                    noDataText: _("You do not have services that require management yet."),
                    noEntriesFoundText: _("No services available matching your search criteria"),
                    filters: {
                        serviceStatus: "Ready"
                    },
                    columns: [{
                        name: _("Subscription Id"),
                        field: "subscriptionId",
                        filter: true,
                        renderCell: function (row) {
                            return new Output({
                                id: row.subscriptionId,
                                escapeHtml: false,
                                innerHTML: "<a href='javascript:void(0)'>" + row.subscriptionId + "</a>",
                                type: "link",
                                subscription: row.subscription,
                                onClick: function () {
                                    aps.apsc.gotoView("http://parallels.com/aps/types/pa/poa/1.0#subscription", this.subscription);
                                }
                            });
                        }
                    },
                        {
                            name: _("Subscription Name"),
                            field: "subscriptionName",
                            filter: true

                        },
                        {
                            name: _("Subscription Status"),
                            field: "serviceStatus",
                            filter: true,
                            renderCell: function (row) {
                                switch (row.serviceStatus) {
                                    case "aps:ready":
                                        if (row.isTrial === false) {
                                            return new Output({
                                                content: '<img src="/pem/images/icons/alert_green_16x16.gif" alt=""> ' + _('Ready'),
                                                scapeHTML: false
                                            });
                                        } else {
                                            return new Output({
                                                content: '<img src="/pem/images/icons/alert_yellow_16x16.gif" alt=""> ' + _('Trial'),
                                                scapeHTML: false
                                            });
                                        }
                                        break;
                                    case "aps:provisioning":
                                        return new Output({
                                            content: '<img src="/pem/images/icons/alert_grey_16x16.gif" alt=""> ' + _('Provisioning'),
                                            scapeHTML: false
                                        });
                                    case "aps:unprovisioning":
                                        return new Output({
                                            content: '<img src="/pem/images/icons/alert_red_16x16.gif" alt=""> ' + _('Unprovisioning'),
                                            scapeHTML: false
                                        });
                                    default:
                                        var internalStatus = row.serviceStatus.substring(4, row.serviceStatus.length);
                                        return new Output({
                                            content: '<img src="/pem/images/icons/alert_unknown_16x16.gif" alt=""> ' + internalStatus.charAt(0).toUpperCase() + internalStatus.slice(1)
                                        });
                                }
                            }
                        },
                        {
                            field: "viewId",
                            name: _('Actions'),
                            renderCell: function (row) {
                                if (row.isAcronis === false && row.isMozy === false) {
                                    return new Button({
                                        id: "button_" + row.resource,
                                        label: _('Manage'),
                                        viewId: row.viewId,
                                        resource: row.resource,
                                        disabled: (row.serviceStatus === 'aps:ready' ? false : true),
                                        onClick: function () {
                                            aps.apsc.gotoView(this.viewId, this.resource);
                                        }
                                    });
                                } else if (row.isAcronis === true && row.isMozy === false) {
                                    var rowContainer = new Container({
                                        id: "container_" + row.resource
                                    });
                                    rowContainer.addChild(new Button({
                                        id: "button_" + row.resource,
                                        label: _('Manage Backup'),
                                        viewId: row.viewId,
                                        resource: row.resource,
                                        disabled: (row.serviceStatus === 'aps:ready' ? false : true),
                                        onClick: function () {
                                            aps.apsc.gotoView(this.viewId, this.resource);
                                        }
                                    }));
                                    rowContainer.addChild(new Button({
                                        id: "button2_" + row.resource,
                                        label: _('Manage Cloud Storage'),
                                        viewId: "http://www.acronis.com/aps/cloud-backup-v1#ccp--reseller-service-plan2--list",
                                        resource: row.resource,
                                        disabled: (row.serviceStatus === 'aps:ready' ? false : true),
                                        onClick: function () {
                                            aps.apsc.gotoView(this.viewId, this.resource);
                                        }
                                    }));
                                    return rowContainer;
                                } else if (row.isAcronis === false && row.isMozy === true) {
                                    var rowContainer2 = new Container({
                                        id: "container_" + row.resource
                                    });
                                    rowContainer2.addChild(new Button({
                                        id: "button_" + row.resource,
                                        label: _('Mozy Reseller'),
                                        viewId: row.viewId,
                                        resource: row.resource,
                                        disabled: (row.serviceStatus === 'aps:ready' ? false : true),
                                        onClick: function () {
                                            aps.apsc.gotoView(this.viewId, this.resource);
                                        }
                                    }));
                                    rowContainer2.addChild(new Button({
                                        id: "button2_" + row.resource,
                                        label: _('Mozy Account'),
                                        viewId: "http://www.mozy.com/mozyProAPS2#mozyProAccount2",
                                        resource: row.resource,
                                        disabled: (row.serviceStatus === 'aps:ready' ? false : true),
                                        onClick: function () {
                                            aps.apsc.gotoView(this.viewId, this.resource);
                                        }
                                    }));
                                    return rowContainer2;
                                }
                            }
                        }
                    ]
                }]
            ]
        ];
        load(page);
    });
});

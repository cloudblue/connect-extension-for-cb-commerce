require([
    "aps/load",
    "aps/xhr",
    "aps/Store",
    "aps/Output",
    "aps/Button",
    "dojo/when",
    "aps/ready!cbcext/services/hub/aps_package/src/ui/js"
], function (load, xhr, Store, Output, Button, when) {
    var store = new Store({
        target: "/aps/2/resources/" + aps.context.vars.servicesglobals.aps.id + "/getTierConfigs",
        idProperty: "id"
    });
    var page = ["aps/PageContainer", {
        id: "page"
    },
        [
            ["aps/Output", {
                type: "info",
                value: _("Manage settings of the products in your account here."),
                closeable: false
            }],
            ["aps/Grid", {
                id: 'configs',
                store: store,
                noDataText: _("You do not have products that require management."),
                noEntriesFoundText: _("No services available matching your search criteria"),
                pageSizeOptions: [10, 25, 100],
                filters: {
                    "product.id": "PRD"
                },
                columns: [
                    {
                        name: _('Product ID'),
                        field: "product.id",
                        filter: true,
                        "sortable": false
                    },
                    {
                        name: _('Product Name'),
                        field: "product.name",
                        filter: true,
                        "sortable": true
                    },
                    {
                        name: _('Configuration ID'),
                        field: "id",
                        filter: true,
                        "sortable": false
                    },
                    {
                        name: _('Status'),
                        field: 'status',
                        filter: {
                            "options": [
                                {
                                    value: 'active',
                                    label: _('Ready')
                                },
                                {
                                    value: 'pending',
                                    label: _('Updating')
                                }
                            ],
                            "title": "Status"
                        },
                        "sortable": true,
                        renderCell: function (row) {
                            switch (row.status) {
                                case 'active':
                                    return new Output({
                                        content: '<img src="/pem/images/icons/alert_green_16x16.gif" alt=""> ' + _('Ready'),
                                        scapeHTML: false
                                    });
                                case 'pending':
                                    return new Output({
                                        content: '<img src="/pem/images/icons/alert_yellow_16x16.gif" alt=""> ' + _('Updating'),
                                        scapeHTML: false
                                    });
                                case 'inquiring':
                                    return new Output({
                                        content: '<img src="/pem/images/icons/alert_yellow_16x16.gif" alt=""> ' + _('Inquiring'),
                                        scapeHTML: false
                                    });
                                case 'tiers_setup':
                                    return new Output({
                                        content: '<img src="/pem/images/icons/alert_yellow_16x16.gif" alt=""> ' + _('Processing'),
                                        scapeHTML: false
                                    });
                            }
                        }
                    },
                    {
                        field: 'id',
                        name: _('Actions'),
                        renderCell: function (row) {
                            if (row.activation &&
                                row.activation.link.length > 0) {
                                return new Button(
                                    {
                                        id: "activate_" + row.id,
                                        "targetLink": row.activation.link,
                                        label: _('Requires attention'),
                                        autoBusy: false,
                                        onClick: function () {
                                            window.open(this.targetLink, '_blank');
                                        }
                                    }
                                );
                            } else {
                                return new Button({
                                    id: 'manage_' + row.id,
                                    label: _('Manage'),
                                    disabled: (row.template.representation === null ? true : false),
                                    manageObject: row,
                                    onClick: function () {
                                        var managedAPP = locate_app_from_environment(this.manageObject.product.id);
                                        var productName = this.manageObject.product.name;
                                        if (managedAPP) {
                                            when(get_service_data(managedAPP), function (tcInfo) {
                                                if (tcInfo) {
                                                    aps.apsc.gotoView("viewconfig", null, tcInfo);
                                                } else {
                                                    aps.apsc.displayMessage({
                                                        "description": _("Managing of product ") + productName + " " +_("is not available now, please try again later."),
                                                        "type": "warning"
                                                    });
                                                    this.cancel();
                                                }
                                            });

                                        } else {
                                            aps.apsc.displayMessage({
                                                "description": _("Managing of product ") + productName + " " + _("is not available now, please try again later."),
                                                "type": "warning"
                                            });
                                            this.cancel();
                                        }
                                    }
                                });
                            }
                        }
                    }
                ]
            }]
        ]
    ];

    function locate_app_from_environment(product) {
        for (var i = 0; i < aps.context.vars.tierconfigapps.length; i++) {
            var type = aps.context.vars.tierconfigapps[i].aps.type;
            if (type.indexOf(product) !== -1) {
                return aps.context.vars.tierconfigapps[i].aps.id;
            }
        }
        return undefined;
    }

    function get_service_data(appglobals) {
        var activation=[];
        return xhr.get("/aps/2/resources/" + appglobals + "/tier/config",
            {timeout: 60000}
        ).then(function(data) {
            var tierConfigReturn = {};
            if (data.length === 0) {
                return {};
            }
            if (data.length === 1) {
                tierConfigReturn = data[0];
            } else {
                tierConfigReturn = data.filter(function (tierConfigRequest) {
                    return tierConfigRequest.status === 'approved';
                })[0];
                activation = data.filter(function (tierConfigRequest) {
                    if (tierConfigRequest.activation && tierConfigRequest.activation.link && tierConfigRequest.activation.link.length > 0) {
                        return tierConfigRequest;
                    }
                });
            }
            var pending = data.filter(function (tierConfigRequest) {
                return tierConfigRequest.status === 'pending';
            });
            if (activation && activation.length > 0 && activation[0].activation && activation[0].activation.link && activation[0].activation.link.length > 0) {
                tierConfigReturn.activation = {};
                tierConfigReturn.activation.link = data.activation[0].activation.link;
                tierConfigReturn.status = 'inquiring';
            } else if (pending.length > 0) {
                if (tierConfigReturn.id === "") {
                    tierConfigReturn = pending[0];
                }
                tierConfigReturn.status = 'pending';
            }
            tierConfigReturn.aps = appglobals;
            return tierConfigReturn;
        }).otherwise(function () {
            return undefined;
        });
    }

    load(page);
});
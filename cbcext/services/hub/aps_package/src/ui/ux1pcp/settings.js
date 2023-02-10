define([
    "dojo/_base/declare",
    "aps/xhr",
    "dojo/promise/all",
    "aps/Store",
    "aps/Output",
    "dijit/registry",
    "aps/Button",
    "dojo/when",
    "aps/Status",
    "aps/confirm",
    "aps/_View"
], function (declare, xhr, all, Store, Output, registry, Button, when, Status, confirm, _View) {
    return declare(_View, {
        init: function () {
            var self = this;
            return [
                ["aps/Tiles", {
                    id: self.genId("connect_system_tiles"),
                    description: _("Centralized management of integration from the CloudBlue Connect to the CloudBlue Commerce.")
                }, [
                    ["aps/Tile", {
                        id: self.genId("connect_system_main_tile"),
                        title: _("CloudBlue Connect Extension"),
                        gridSize: "md-6 xs-12",
                        info: new Status({
                            gridSize: 'md-12',
                            id: self.genId('systemstatus'),
                            statusInfo: {
                                'updating': {
                                    "label": _('Updating Status'),
                                    "type": "muted",
                                    isLoad: true,
                                    icon: "fa-spinner"
                                },
                                'fail': {
                                    "label": _('Error'),
                                    "type": "danger",
                                    icon: "fa-bolt"
                                },
                                'upgrade': {
                                    "label": _('Upgrade Available'),
                                    "type": "warning",
                                    icon: "fa-exclamation"
                                },
                                "upgrading": {
                                    "label": _('Upgrading'),
                                    "type": "warning",
                                    icon: "fa-exclamation",
                                    isLoad: true
                                },
                                "ready": {
                                    "label": _('Ready'),
                                    "type": "success",
                                    icon: "fa-check"
                                }
                            }
                        })
                    }, [
                        ["aps/Container", {
                            class: "row",
                            id: self.genId("system-tile-container")
                        }, [
                            ["aps/FieldSet", {
                                gridSize: "md-12 xs-12",
                                description: _('This extension is configured with the following settings:')
                            }, [
                                ["aps/Output", {
                                    gridSize: "md-6 xs-12",
                                    id: self.genId("AccountName"),
                                    label: _("Account Name")
                                }],
                                ["aps/Output", {
                                    gridSize: "md-6 xs-12",
                                    id: self.genId("AccountId"),
                                    label: _('Account ID')
                                }],
                                ["aps/Output", {
                                    gridSize: "md-6 xs-12",
                                    id: self.genId("HubInstanceId"),
                                    label: _('Hub Instance ID')
                                }],
                                ["aps/Output", {
                                    gridSize: "md-6 xs-12",
                                    id: self.genId("HubId"),
                                    label: _('Hub ID')
                                }]
                            ]
                            ]
                        ]]
                    ]]]],
                ["aps/Output", {
                    id: 'products_intro',
                    escapeHTML: false,
                    value: _('Please refer to the list below to manage products available to you through the Provider Portal of the CloudBlue Connect. To learn more about this extension, please refer to ') + "<a href='https://connect.cloudblue.com/documentation/extensions/cloudblue-commerce/' target='_blank'>" + _("our documentation") + "</a>"
                }],
                ["aps/Hr"],
                ["aps/Grid", {
                    id: self.genId("products"),
                    pageSizeOptions: [10, 25, 50],
                    noDataText: _("There are no products available, please check your products on provider portal."),
                    noEntriesFoundText: _("No services available matching your search criteria")
                }]
            ];
        },
        onContext: function () {
            var self = this;
            self.byId("systemstatus").set({
                status: "updating"
            });
            self.byId("AccountName").set({
                content: aps.context.vars.globalSettings.account_name
            });
            self.byId("AccountId").set({
                content: aps.context.vars.globalSettings.account_id
            });
            self.byId("HubId").set({
                content: aps.context.vars.globalSettings.hub_id
            });
            self.byId("HubInstanceId").set({
                content: aps.context.vars.globalSettings.hub_uuid
            });
            if (self.byId("upgradeButton") !== undefined) {
                self.byId("upgradeButton").set({
                    visible: false
                });
            }
            if (aps.context.vars.openapiadapter === undefined) {
                aps.apsc.displayMessage({
                    "description": _("Product Management operations are disabled due lack of CloudBlue Connect openapi adapter installed on this hub"),
                    "type": "warning"
                });
            }
            xhr.get("/aps/2/resources/" + aps.context.vars.globalSettings.aps.id + "/healthCheck").then(function (healthcheck) {
                switch (healthcheck.status) {
                    case "fail":
                        self.byId("systemstatus").set({
                            status: "fail"
                        });
                        aps.apsc.displayMessage({
                            "description": _("Health check error:") + healthcheck.message,
                            "type": "error"
                        });
                        break;
                    case "upgrade":
                        self.byId("systemstatus").set({
                            status: "upgrade"
                        });
                        if (self.byId('upgradeButton') === undefined) {
                            self.byId('connect_system_main_tile').set({
                                buttons: [
                                    {
                                        id: self.genId('upgradeButton'),
                                        title: _('Upgrade'),
                                        autoBusy: false,
                                        visible: true,
                                        disabled: (aps.context.vars.openapiadapter !== undefined ? false:true),
                                        onClick: function () {
                                            confirm({
                                                title: _('Upgrade Extension'),
                                                submitLabel: _('Yes'),
                                                cancelLabel: _('No'),
                                                description: _('Do you want to upgrade the CloudBlue Connect Extension Now?')
                                            }).then(function (response) {
                                                if (response === true) {
                                                    aps.apsc.showLoading();
                                                    var task = {
                                                        "aps": {
                                                            "type": "http://odin.com/app/productInitTask/1.1"
                                                        },
                                                        "productId": "extension",
                                                        "includeEoS": "false",
                                                        "globals": {
                                                            "aps": {
                                                                "id": aps.context.vars.globalSettings.aps.id
                                                            }
                                                        },
                                                        "operation": "upgrade"
                                                    };
                                                    xhr.post(
                                                        "/aps/2/resources/",
                                                        {
                                                            headers: {"Content-Type": "application/json"},
                                                            data: JSON.stringify(task)
                                                        }
                                                    ).then(function () {
                                                        self.byId("systemstatus").set({
                                                            status: "upgrading"
                                                        });
                                                        self.byId("upgradeButton").set({
                                                            disabled: true
                                                        });
                                                        aps.apsc.displayMessage({
                                                            "description": _('Upgrade of CloudBlue Connect extension initiated'),
                                                            "type": "info"
                                                        });
                                                    }).otherwise(function (error) {
                                                        aps.apsc.displayMessage({
                                                            "description": _('Error while scheduling upgrade task:') + error.message,
                                                            "type": "error"
                                                        });
                                                    }).always(function () {
                                                        aps.apsc.hideLoading();
                                                    });
                                                }
                                            });
                                        }
                                    }
                                ]
                            });
                        } else {
                            self.byId("upgradeButton").set({
                                visible: true,
                                disabled: (aps.context.vars.openapiadapter !== undefined ? false:true)
                            });
                        }
                        break;
                    default:
                        self.byId("systemstatus").set({
                            status: "ready"
                        });
                        break;
                }
            }).otherwise(function (error) {
                self.byId("systemstatus").set({
                    status: "fail"
                });
                aps.apsc.displayMessage({
                    "description": _("Error while performing system health check:") + error,
                    "type": "error"
                });
            });
            var store = new Store({
                target: "/aps/2/resources/" + aps.context.vars.globalSettings.aps.id + "/products",
                idProperty: "id"
            });
            var columns = [
                {
                    name: _('Product Name'),
                    field: "name",
                    filter: true,
                    "sortable": true
                },
                {
                    name: _('Created'),
                    field: "events.created.at",
                    "sortable": true,
                    type: "datetime"
                },
                {
                    name: _('Last version'),
                    field: "version",
                    "sortable": false,
                    type: "integer"
                },
                {
                    name: _('Product ID'),
                    field: "id",
                    filter: true,
                    "sortable": false
                },
                {
                    name: _('Vendor Name'),
                    field: "owner.name",
                    filter: true,
                    "sortable": false
                },
                {
                    name: _('Vendor ID'),
                    field: "owner.id",
                    filter: false,
                    "sortable": false
                },
                {
                    name: _('Actions'),
                    field: 'product.id',
                    filter: false,
                    "sortable": false,
                    renderCell: function (row) {
                        return new Button({
                            id: 'button_' + row.id,
                            label: _('Manage'),
                            disabled: (aps.context.vars.openapiadapter === undefined),
                            autoBusy: false,
                            product: row.id,
                            onClick: function () {
                                aps.apsc.gotoView("productmanagementux1", null, {
                                    "product": this.product
                                });
                            }
                        });
                    }
                }
            ];
            self.byId('products').set({
                store: store,
                columns: columns,
                rowsPerPage: 10,
                sort:
                    {
                        attribute: "name",
                        descending: false
                    }
            });
            aps.apsc.hideLoading();
        }
    });
});
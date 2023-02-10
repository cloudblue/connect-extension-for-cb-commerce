require([
    "aps/load",
    "aps/xhr",
    "aps/Output",
    "dijit/registry",
    "aps/Store",
    "aps/Button",
    "aps/ToolbarButton",
    "aps/ready!cbcext/services/hub/aps_package/src/ui/js"
], function (load, xhr, Output, registry, Store, Button, ToolbarButton) {
    var page = [];
    if (aps.context.vars.globalSettings.length === 0) {
        aps.apsc.displayMessage({
            "description": _("Connect Cloudblue Commerce extension is not properly installed"),
            "type": "warning"
        });
        page = ["aps/PageContainer", {
            id: "page"
        }];
        load(page);
    } else {
        var store = new Store({
            target: "/aps/2/resources/" + aps.context.vars.globalSettings.aps.id + "/products",
            idProperty: "id"
        });
        page = ["aps/PageContainer", {
            id: "page"
        }, [
            ["aps/ActiveList", [
                ["aps/ActiveItem", {
                    id: "status",
                    iconName: "./images/Connect.png",
                    title: _("CloudBlue Connect Extension"),
                    collapsible: false,
                    collapsed: false,
                    description: [new Output({
                        content: _("Centralized management of integration from the CloudBlue Connect to the CloudBlue Commerce.")
                    })],
                    info: new Output({
                        innerHTML: _("Updating Status"),
                        "class": "summary-item",
                        "style": "color: #FFF; background-color: #BDBDBD; float: right; padding: 4px 7px; " +
                            "margin-top: 3px; margin-right: 5px;"
                    })
                }, [
                    ["aps/Container", {
                        id: "infoContainer"
                    }, [
                        ["aps/FieldSet", {
                            title: "This extension is configured with the following settings:",
                            id: "hub_fieldset"
                        }, [
                            ["aps/Output", {
                                label: "Account Name",
                                content: aps.context.vars.globalSettings.account_name
                            }],
                            ["aps/Output", {
                                label: "Account ID",
                                content: aps.context.vars.globalSettings.account_id
                            }],
                            ["aps/Output", {
                                label: "Hub ID",
                                content: aps.context.vars.globalSettings.hub_id
                            }],
                            ["aps/Output", {
                                label: "Hub Instance ID",
                                content: aps.context.vars.globalSettings.hub_uuid
                            }]
                        ]]
                    ]
                    ]
                ]
                ]
            ]],
            ["aps/Output", {
                id: 'products_intro',
                escapeHTML: false,
                value: _('Please refer to the list below to manage products available to you through the Provider Portal of the CloudBlue Connect. To learn more about this extension, please refer to ') + "<a href='https://connect.cloudblue.com/documentation/extensions/cloudblue-commerce/' target='_blank'>" + _("our documentation") + "</a>"
            }],
            ["aps/Hr"],
            ["aps/Grid", {
                id: 'productsGrid',
                store: store,
                descending: false,
                noDataText: _("There are no products available, please check your products on provider portal."),
                pageSizeOptions: [10, 25, 50],
                filters: {
                    "id": "PRD"
                },
                columns: [
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
                                    aps.apsc.gotoView("productmanagement", null, {
                                        "product": this.product
                                    });
                                }
                            });
                        }
                    }
                ]
            }]
        ]
        ];
        load(page).then(function () {
            if (aps.context.vars.openapiadapter === undefined) {
                aps.apsc.displayMessage({
                    "description": _("Product Management operations are disabled due lack of CloudBlue Connect openapi adapter installed on this hub"),
                    "type": "warning"
                });
            }
            xhr.get("/aps/2/resources/" + aps.context.vars.globalSettings.aps.id + "/healthCheck").then(function (healthcheck) {
                switch (healthcheck.status) {
                    case "fail":
                        registry.byId("status").set({
                            info: new Output({
                                innerHTML: _("Status: Error"),
                                "class": "summary-item",
                                "style": "color: #FFF; background-color: #FF3333; float: right; padding: 4px 7px; " +
                                    "margin-top: 3px; margin-right: 5px;"
                            })
                        });
                        aps.apsc.displayMessage({
                            "description": _("Health check error:") + healthcheck.message,
                            "type": "error"
                        });
                        break;
                    case 'upgrade':
                        registry.byId("status").set({
                            info: new Output({
                                innerHTML: _("Status: Upgrade Available"),
                                "class": "summary-item",
                                "style": "color: #FFF; background-color: #F7E4A2; float: right; padding: 4px 7px; " +
                                    "margin-top: 3px; margin-right: 5px;"
                            })
                        });
                        var upgradeButton = new ToolbarButton({
                            id: "upgrade_ext",
                            label: _('Upgrade Now'),
                            iconName: "/pem/images/icons/env_migration_16x16.gif",
                            autoBusy: false,
                            disabled: (aps.context.vars.openapiadapter === undefined),
                            onClick: function () {
                                var confirm = window.confirm("Are you sure you want to upgrade now?");
                                if (confirm === true) {
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
                                        registry.byId("upgrade_ext").set({
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
                                    });
                                }
                            }
                        });
                        registry.byId('status').addChild(upgradeButton);
                        aps.apsc.displayMessage({
                            "description": healthcheck.message,
                            "type": "warning"
                        });
                        registry.byId("status").set({
                            info: new Output({
                                innerHTML: _("Status: OK"),
                                "class": "summary-item",
                                "style": "color: #FFF; background-color: #00C051; float: right; padding: 4px 7px; " +
                                    "margin-top: 3px; margin-right: 5px;"
                            })
                        });
                        break;
                    default:
                        registry.byId("status").set({
                            info: new Output({
                                innerHTML: _("Status: OK"),
                                "class": "summary-item",
                                "style": "color: #FFF; background-color: #00C051; float: right; padding: 4px 7px; " +
                                    "margin-top: 3px; margin-right: 5px;"
                            })
                        });
                        break;
                }
            }).otherwise(function (error) {
                registry.byId("status").set({
                    info: new Output({
                        innerHTML: _("Status: Error"),
                        "class": "summary-item",
                        "style": "color: #FFF; background-color: #FF3333; float: right; padding: 4px 7px; " +
                            "margin-top: 3px; margin-right: 5px;"
                    })
                });
                aps.apsc.displayMessage({
                    "description": _("Error while passing healthcheck:") + error,
                    "type": "error"
                });
            });
        });
    }
});
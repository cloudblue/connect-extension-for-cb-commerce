require([
    "aps/load",
    "aps/xhr",
    "dojo/promise/all",
    "aps/Memory",
    "aps/Output",
    "dijit/registry",
    "aps/Button",
    "aps/Container",
    "./lib/marked.min.js",
    "aps/ToolbarButton",
    "aps/Store",
    "aps/ready!cbcext/services/hub/aps_package/src/ui/js"
], function (load, xhr, all, Memory, Output, registry, Button, Container, marked, ToolbarButton,Store) {
    var page = ["aps/PageContainer", {
        id: "page"
    }];
    var endpoint = "/aps/2/resources/";
    function runTask(operation, includeEos, productId){
        var confirm = window.confirm("Are you sure you want to continue?");
        if (confirm === true) {
            var task = {
                "aps": {
                    "type": "http://odin.com/app/productInitTask/1.1"
                },
                "productId": productId,
                "includeEoS": includeEos,
                "globals": {
                    "aps": {
                        "id": aps.context.vars.globalSettings.aps.id
                    }
                },
                "operation": operation
            };
            xhr.post(
                endpoint,
                {
                    headers: {"Content-Type": "application/json"},
                    data: JSON.stringify(task)
                }
            ).then(
                function () {
                    aps.apsc.displayMessage({
                        "description": _('Installation process initiated'),
                        "type": "info"
                    });
                    aps.apsc.gotoView("productmanagement", null, {
                        "product": productId
                    });
                }).otherwise(
                function (error) {
                    aps.apsc.displayMessage(error.message);

                }
            );
        }
    }
    function runningTask(){
        if (aps.context.vars.productInitTasks === undefined || aps.context.vars.productInitTasks.length === 0){
            return false;
        }
        for (var i=0; i < aps.context.vars.productInitTasks.length; i++){
            if(aps.context.vars.productInitTasks[i].productId === aps.context.params.product){
                if(aps.context.vars.productInitTasks[i].step.toLowerCase() !== "completed"){
                    return true;
                }
            }
        }
        return false;
    }
    all([
        xhr.post("/aps/2/resources/" + aps.context.vars.globalSettings.aps.id + "/productInfo", {
            headers: {"Content-Type": "application/json"},
            data: JSON.stringify({"product": aps.context.params.product})
        }),
        xhr.post("/aps/2/resources/" + aps.context.vars.globalSettings.aps.id + "/connectionsInfo", {
            headers: {"Content-Type": "application/json"},
            data: JSON.stringify({"product": aps.context.params.product})
        }),
        xhr.get(
            "/aps/2/resources/" + aps.context.vars.globalSettings.aps.id + "/availableOperations?product_id=" + aps.context.params.product
        ).then(function (result) {
            return result;
        }).otherwise(function (error) {
            aps.apsc.displayMessage({
                "description": (error.response !== undefined && error.response.data !== undefined && error.response.data.message !== undefined) ? error.response.data.message : error.message,
                "type": (error.response !== undefined && error.response.data !== undefined && error.response.data.type !== undefined ? error.response.data.type : "error")
            });
        }),
        xhr.get(
            "/aps/2/resources/" + aps.context.vars.globalSettings.aps.id + "/getStaticContentUrl"
        ).then(function(result){
            if(result.url.charAt( result.url.length -1 ) === "/") {
                result.url = result.rul.slice(0, -1)
            }
            return result;
        }).otherwise(function(){
            return {"url": "https://api.connect.cloudblue.com"};
        })
    ]).then(function (pageData) {
        var productInfo = pageData[0];
        var connectionInfo = pageData[1];
        var operations = pageData[2];
        var staticContentUrl = pageData[3].url;
        var existsRunningTask = runningTask();
        var actionLog = new Store({
            idProperty: "aps.id",
            target: "/aps/2/resources",
            baseQuery: "implementing(http://odin.com/app/productInitTask/1.1),eq(productId," + aps.context.params.product +")"
        });

        page = ["aps/PageContainer", {
            id: "page"
        }, [
            ["aps/ActiveList", [
                ["aps/ActiveItem", {
                    iconName: staticContentUrl.replace(/\/$/, '') + productInfo.icon,
                    title: productInfo.name,
                    id: 'activeItem_' + productInfo.id,
                    collapsible: true,
                    collapsed: true,
                    description: [
                        new Output({
                            escapeHTML: false,
                            content: _("Product ID") + ": " + productInfo.id + "<br>"
                        }),
                        new Output({
                            escapeHTML: false,
                            content: _("Connection ID") + ": " + (
                                connectionInfo.id !== undefined ?
                                    connectionInfo.id :
                                    "<a target='_blank' href=" + staticContentUrl.replace('api', 'provider') + "/products/" + productInfo.id + "/connections?account=" + aps.context.vars.globalSettings.account_id + ">" + _("No Connection available") + "</a>"
                            )
                        }),
                        new Output({
                            escapeHTML: false,
                            content: "<br>" + _("Vendor ID") + ": " + productInfo.owner.id + "<br>"
                        }),
                        new Output({
                            escapeHTML: false,
                            content: _("Vendor Name") + ": " + productInfo.owner.name + "<br>"
                        })
                    ]
                }, [
                    ["aps/Output", {
                        escapeHTML: false,
                        value: marked(productInfo.detailed_description)
                    }]
                ]
                ]
            ]],
            ["aps/Output",{
                id: "actionLogIntro",
                escapeHTML: false,
                value: _("Here you can find the list of actions performed to this product. To learn more about this extension, please refer to ") + "<a href='https://connect.cloudblue.com/documentation/extensions/cloudblue-commerce/' target='_blank'>" + _("our documentation") + "</a>"
            }],
            ["aps/Hr"],
            ["aps/Grid",{
                id: "actionLog",
                store: actionLog,
                noDataText: _("No actions performed to this product"),
                pageSizeOptions: [10, 25, 50],
                columns: [
                    {
                        name: _('Executed'),
                        field: "aps.modified",
                        filter: true,
                        "sortable": true,
                        renderCell: function(row){
                            var executedTimeStamp = row.aps.modified;
                            executedTimeStamp = executedTimeStamp.replace("Z", "");
                            executedTimeStamp = executedTimeStamp.replace("T", " ");
                            return executedTimeStamp;
                        }
                    },
                    {
                        name: _('Operation'),
                        field: "operation",
                        filter: true,
                        "sortable": true
                    },
                    {
                        name: _('Created RT #'),
                        field: "rts",
                        filter: false,
                        "sortable": false,
                        renderCell: function(row){
                            return (row.rts !== undefined ? row.rts.length: "-");
                        }
                    },
                    {
                        name: _("Created ST ID"),
                        field: "stid",
                        filter: false,
                        "sortable": false,
                        renderCell: function(row){
                            return (row.stid !== undefined ? row.stid: "-");
                        }
                    },
                    {
                        name: _("Status"),
                        field: "step",
                        filter: false,
                        "sortable": false,
                        renderCell: function(row){
                            var step = row.step.toLowerCase();
                            switch(step) {
                                case "create_instance":
                                    return _("Creating application instance");
                                case "create_core_rts":
                                    return _("Creating system RTs");
                                case "create_rts":
                                    return _("Creating item RTs");
                                case "create_st":
                                    return _("Creating ST");
                                case "apply_st_limits":
                                    return _("Applying ST limits");
                                case "upgrade_instance":
                                    return _("Upgrading application instance");
                                case "wait_upgrade_complete":
                                    return _("Waiting for application upgrade completion");
                                case "completed":
                                    return _("Completed");
                                case "import":
                                    return _("Importing application");
                                default:
                                    return row.step;
                            }
                        }
                    },
                    {
                        name: _('Details'),
                        field: "aps.id",
                        filter: false,
                        "sortable": false,
                        renderCell: function (row) {
                        return new Button({
                            id: 'details' + row.aps.id,
                            label: _('Details'),
                            autoBusy: false,
                            product: row.productId,
                            taskid: row.aps.id,
                            onClick: function () {
                                aps.apsc.gotoView("taskDetails", null, {
                                    "product": this.product,
                                    "taskId": this.taskid
                                });
                            }
                        });
                    }
                    }
                ]
            }]
        ]];
        load(page).then(function () {
            if (connectionInfo.id === undefined) {
                registry.byId('activeItem_' + productInfo.id).set({
                    info: new Output({
                        innerHTML: _('Missing Connection'),
                        "class": "summary-item",
                        "style": "color: #FFF; background-color: #FF0000; float: right; padding: 4px 7px; " +
                            "margin-top: 3px; margin-right: 5px;"
                    })
                });
            } else if (operations !== undefined) {
                switch (operations.operation) {
                    case "install":
                        registry.byId('activeItem_' + productInfo.id).addChild(
                            new ToolbarButton({
                                id: "install",
                                label: "Install",
                                disabled: existsRunningTask,
                                iconName: "/pem/images/icons/env_new_16x16.gif",
                                autoBusy: false,
                                onClick: function () {
                                    runTask("install", false, productInfo.id);
                                }
                            })
                        );
                        registry.byId('activeItem_' + productInfo.id).addChild(
                            new ToolbarButton({
                                id: "install_eol",
                                label: "Install including End of Sale items",
                                iconName: "/pem/images/icons/env_new_16x16.gif",
                                disabled: existsRunningTask,
                                autoBusy: false,
                                onClick: function () {
                                    runTask("install", true, productInfo.id);
                                }
                            })
                        );
                        if(existsRunningTask){
                            registry.byId('activeItem_' + productInfo.id).set({
                                info: new Output({
                                    innerHTML: _('Operation in progress'),
                                    "class": "summary-item",
                                    "style": "color: #FFF; background-color: #FFCC00; float: right; padding: 4px 7px; " +
                                        "margin-top: 3px; margin-right: 5px;"
                                })
                            });
                        }
                        break;
                    case "upgrade":
                        registry.byId('activeItem_' + productInfo.id).addChild(
                            new ToolbarButton({
                                id: "upgrade",
                                label: "Upgrade",
                                iconName: "/pem/images/icons/env_migration_16x16.gif",
                                disabled: existsRunningTask,
                                autoBusy: false,
                                onClick: function () {
                                    runTask("upgrade", false, productInfo.id);
                                }
                            })
                        );
                        registry.byId('activeItem_' + productInfo.id).addChild(
                            new ToolbarButton({
                                id: "upgrade_eol",
                                label: "Upgrade including End of Sale items",
                                iconName: "/pem/images/icons/env_migration_16x16.gif",
                                disabled: existsRunningTask,
                                autoBusy: false,
                                onClick: function () {
                                    runTask("upgrade", true, productInfo.id);
                                }
                            })
                        );
                        if(existsRunningTask){
                            registry.byId('activeItem_' + productInfo.id).set({
                                info: new Output({
                                    innerHTML: _('Operation in progress'),
                                    "class": "summary-item",
                                    "style": "color: #FFF; background-color: #FFCC00; float: right; padding: 4px 7px; " +
                                        "margin-top: 3px; margin-right: 5px;"
                                })
                            });
                        }
                        else{
                            registry.byId('activeItem_' + productInfo.id).set({
                                info: new Output({
                                    innerHTML: _('Version __version__ available', {"version": operations.to}),
                                    "class": "summary-item",
                                    "style": "color: #FFF; background-color: #FFCC00; float: right; padding: 4px 7px; " +
                                        "margin-top: 3px; margin-right: 5px;"
                                })
                            });
                        }
                        break;
                    default:
                        registry.byId('activeItem_' + productInfo.id).set({
                            info: new Output({
                                innerHTML: _('Up to Date'),
                                "class": "summary-item",
                                "style": "color: #FFF; background-color: #00C051; float: right; padding: 4px 7px; " +
                                    "margin-top: 3px; margin-right: 5px;"
                            })
                        });
                        break;
                }
            }
        });
    }).otherwise(function (error) {
        console.log("Detailed Error",error);
        aps.apsc.displayMessage({
            "description": _("We are sorry, an error has happened, please try again later"),
            "type": "error"
        });
        load(page);
    });
});
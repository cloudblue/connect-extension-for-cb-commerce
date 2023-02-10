define([
    "dojo/_base/declare",
    "aps/xhr",
    "dojo/promise/all",
    "aps/Memory",
    "aps/Output",
    "aps/Button",
    "aps/Container",
    "dojox/mvc/at",
    "dojox/mvc/getStateful",
    "aps/Store",
    "aps/Status",
    "aps/ToolbarButton",
    "aps/confirm",
    "aps/alert",
    "aps/_View"
], function (declare, xhr, all, Memory, Output, Button, Container, at, getStateful, Store, Status, ToolBarButton, confirm, alert, _View) {
    function createHiddenInput(name, value) {
        const input = document.createElement('input');
        input.setAttribute('type', 'hidden');
        input.setAttribute('name', name);
        input.setAttribute('value', value);
        return input;
    }

    const createForm = (url, newTabId, additionalOptions) => {
        const form = document.createElement('form');
        form.setAttribute('method', 'get');
        form.setAttribute('action', url);
        form.setAttribute('target', newTabId);
        additionalOptions && additionalOptions.forEach(opt => {
            const optInput = createHiddenInput(opt.key, opt.value);
            form.appendChild(optInput);
        });

        document.body.appendChild(form);

        form.submit();
        document.body.removeChild(form);
    };

    function waitHtml() {
        var string = '\
		<html>\
			<head>\
				<title>' + _('Loading') + '</title>\
				<style>\
					body {\
						background-color: #fafcfd;\
					}\
					div.loader {\
						width: 100%;\
						height: 100%;\
						position: fixed;\
						top: 0;\
						left: 0;\
						display: flex;\
						align-items: center;\
						align-content: center; \
						justify-content: center; \
						overflow: auto;\
					}\
					div.content {\
						display: flex;\
						justify-content: center;\
						flex-direction: column;\
						align-items: center;\
					}\
					\
					.spinner svg {\
						fill: #1894FC;\
						animation: rotate 1.2s linear infinite;\
					}\
					.spinner, .spinner svg {\
						width: 42px;\
						height: 42px;\
					}\
					.message {\
						font-family: "Graphik", Arial, sans-serif;\
						font-size: 24px;\
						color: #47485A;\
					}\
					.spinner, .message {\
						text-align: center;\
					}\
					@keyframes rotate {\
						0% {\
							transform: rotate(0deg);\
							-ms-transform: rotate(0deg);\
							-webkit-transform: rotate(0deg);\
							-moz-transform: rotate(0deg);\
							-o-transform: rotate(0deg);\
						}\
						50% {\
							transform: rotate(360deg);\
							-ms-transform: rotate(360deg);\
							-webkit-transform: rotate(360deg);\
							-moz-transform: rotate(360deg);\
							-o-transform: rotate(360deg);\
						}\
						100% {\
							transform: rotate(720deg);\
							-ms-transform: rotate(720deg);\
							-webkit-transform: rotate(720deg);\
							-moz-transform: rotate(720deg);\
							-o-transform: rotate(720deg);\
						}\
					}\
				</style>\
			</head>\
			<body>\
				<div class="loader">\
					<div class="content">\
						<div class="spinner">\
							<svg viewBox="0 0 512 512">\
								<path d="M288 39.056v16.659c0 10.804 7.281 20.159 17.686 23.066C383.204 100.434 440 \
								171.518 440 256c0 101.689-82.295 184-184 184-101.689 0-184-82.295-184-184 0-84.47 \
								56.786-155.564 134.312-177.219C216.719 75.874 224 66.517 224 \
								55.712V39.064c0-15.709-14.834-27.153-30.046-23.234C86.603 43.482 7.394 141.206 8.003 \
								257.332c.72 137.052 111.477 246.956 248.531 246.667C393.255 503.711 504 392.788 504 \
								256c0-115.633-79.14-212.779-186.211-240.236C302.678 11.889 288 23.456 288 39.056z"/>\
							</svg>\
						</div>\
						<div class="message"><br/>' + _('Please wait while you are being redirected to Provider Portal...') + '</div>\
					</div>\
				</div>\
			</body>\
		</html>\
	';
        return string;
    }

    return declare(_View, {
        init: function () {
            var self = this;
            return [
                ["aps/Tiles", {
                    id: self.genId("tiles"),
                    visible: true
                }, [
                    ["aps/Tile", {
                        id: self.genId("product"),
                        gridSize: "md-6 xs-12",
                        info: new Status({
                            gridSize: 'md-12',
                            id: self.genId('productStatus'),
                            statusInfo: {
                                'noConnection': {
                                    "label": _('Missing Connection'),
                                    "type": "error",
                                    icon: "fa-bolt"
                                },
                                'inProgress': {
                                    "label": _('Operation in progress'),
                                    "type": "warning",
                                    icon: "fa-exclamation",
                                    isLoad: true
                                },
                                'upgrade': {
                                    "label": _('New Version available'),
                                    "type": "warning",
                                    icon: "fa-exclamation"
                                },
                                'up2date': {
                                    "label": _('Up to Date'),
                                    "type": "success",
                                    icon: "fa-check"
                                },
                                'install': {
                                    "label": _('Ready for install'),
                                    "type": "success"
                                }
                            }
                        })
                    }, [
                        ["aps/Container", {
                            class: "row"
                        }, [
                            ["aps/FieldSet", {
                                gridSize: "md-3 xs-12"
                            }, [
                                ["aps/Output", {
                                    id: self.genId('productIcon'),
                                    class: "col-md-12 col-xs-12"
                                }
                                ]
                            ]],
                            ["aps/Container", {
                                gridSize: "md-9 xs-12"
                            }, [
                                ["aps/FieldSet", {
                                    id: self.genId("fieldsetSystem"),
                                    gridSize: "md-12 xs-12"
                                }, [
                                    ["aps/Output", {
                                        gridSize: "md-6 xs-12",
                                        label: _('Product ID'),
                                        id: self.genId("productId")
                                    }],
                                    ["aps/Output", {
                                        gridSize: "md-6 xs-12",
                                        label: _('Connection ID'),
                                        id: self.genId("connectionId")
                                    }],
                                    ["aps/Output", {
                                        gridSize: "md-6 xs-12",
                                        label: _('Vendor Name'),
                                        id: self.genId("vendorName")
                                    }],
                                    ["aps/Output", {
                                        gridSize: "md-6 xs-12",
                                        label: _('Vendor ID'),
                                        id: self.genId("vendorId")
                                    }]
                                ]]]]
                        ]]
                    ]]
                ]],
                ["aps/Output", {
                    id: self.genId("actionLogIntro"),
                    visible: true,
                    gridSize: 'md-12 xs-12',
                    escapeHTML: false,
                    value: _("Here you can find the list of actions performed to this product. To learn more about this extension, please refer to ") + "<a href='https://connect.cloudblue.com/documentation/extensions/cloudblue-commerce/' target='_blank'>" + _("our documentation") + "</a>"
                }],
                ["aps/Hr"],
                ["aps/Grid", {
                    id: self.genId("actionLog"),
                    visible: true,
                    gridSize: 'md-12 xs-12',
                    noDataText: _("No actions performed to this product"),
                    pageSizeOptions: [10, 25, 50]
                }]
            ];
        },
        onContext: function () {
            var self = this;
            var endpoint = "/aps/2/resources/";

            function runTask(operation, includeEos, productId) {
                confirm({
                    title: _('__operation__ Extension', {"operation": operation.charAt(0).toUpperCase() + operation.slice(1)}),
                    description: _('Do you want to __operation__ this product now?', {"operation": operation}),
                    submitLabel: _('Yes'),
                    cancelLabel: _('No')
                }).then(function (response) {
                    if (response === true) {
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
                                aps.apsc.gotoView("productmanagementux1", null, {
                                    "product": productId
                                });
                            }).otherwise(
                            function (error) {
                                aps.apsc.displayMessage(error.message);

                            }
                        );
                    }
                });
            }

            function runningTask() {
                if (aps.context.vars.productInitTasks === undefined || aps.context.vars.productInitTasks.length === 0) {
                    return false;
                }
                for (var i = 0; i < aps.context.vars.productInitTasks.length; i++) {
                    if (aps.context.vars.productInitTasks[i].productId === aps.context.params.product) {
                        if (aps.context.vars.productInitTasks[i].step.toLowerCase() !== "completed") {
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
                ).then(function (result) {
                    if(result.url.charAt( result.url.length -1 ) === "/") {
                        result.url = result.rul.slice(0, -1)
                    }
                    return result;
                }).otherwise(function () {
                    return {"url": "https://api.connect.cloudblue.com"};
                })
            ]).then(function (pageData) {
                self.byId("tiles").set({visible: true});
                self.byId("actionLog").set({visible: true});
                if (self.byId("createConnectionConnect")) {
                    self.byId("createConnectionConnect").destroy();
                }
                var productInfo = pageData[0];
                var connectionInfo = pageData[1];
                var operations = pageData[2];
                var staticContentUrl = pageData[3].url;
                var existsRunningTask = runningTask();
                var actionLog = new Store({
                    idProperty: "aps.id",
                    target: "/aps/2/resources",
                    baseQuery: "implementing(http://odin.com/app/productInitTask/1.1),eq(productId," + aps.context.params.product + ")"
                });
                self.byId("actionLog").set({
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
                            renderCell: function (row) {
                                return (row.rts !== undefined ? row.rts.length : "-");
                            }
                        },
                        {
                            name: _("Created ST ID"),
                            field: "stid",
                            filter: false,
                            "sortable": false,
                            renderCell: function (row) {
                                return (row.stid !== undefined ? row.stid : "-");
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
                                        xhr.get(
                                            "/aps/2/resources/" + row.aps.id
                                        ).then(function (details) {
                                            alert({
                                                title: _("Task details"),
                                                description: JSON.stringify(details, null, 2)
                                            });
                                        }).otherwise(function (error) {
                                            console.log("Detailed error:",error);
                                            aps.apsc.displayMessage({
                                                "description": _("We are sorry, an error has happened, please try again later"),
                                                "type": "error"
                                            });
                                        });
                                    }
                                });
                            }
                        }
                    ],
                    store: actionLog
                });
                self.byId('productIcon').set({
                    "content": '<span class="media"><img class="media-object" src="' + staticContentUrl.replace(/\/$/, '') + productInfo.icon + '"></span>'
                });
                self.byId('product').set({title: productInfo.name});
                self.byId("productId").set({content: productInfo.id});
                self.byId("vendorId").set({content: productInfo.owner.id});
                self.byId("vendorName").set({content: productInfo.owner.name});
                if (connectionInfo.id === undefined) {
                    if (existsRunningTask) {
                        self.byId('productStatus').set({status: 'inProgress'});
                    } else {
                        self.byId('productStatus').set({status: 'noConnection'});
                    }
                    self.byId('connectionId').set({
                        visible: false
                    });
                    self.byId('fieldsetSystem').addChild(
                        new Button({
                            label: _('Create Connection'),
                            id: self.genId('createConnectionConnect'),
                            autoBusy: false,
                            onClick: function () {
                                var newTabId = Date.now();
                                var newTab = window.open('', newTabId);
                                if (!newTab) {
                                    throw new Error('Window \'newTabId\' could not be opened.');
                                }
                                newTab.opener = null;
                                newTab.document.write(waitHtml());

                                createForm(staticContentUrl.replace('api', 'provider') + "/products/" + productInfo.id + "/connections?account=" + aps.context.vars.globalSettings.account_id, newTabId);
                            }
                        })
                    );
                } else {
                    self.byId('connectionId').set({content: connectionInfo.id});
                    if (operations !== undefined) {
                        switch (operations.operation) {
                            case "install":
                                if (existsRunningTask) {
                                    self.byId('productStatus').set({status: 'inProgress'});
                                } else {
                                    self.byId('productStatus').set({status: 'install'});
                                }
                                self.byId('product').set({
                                    buttons: [{
                                        title: _('Actions'),
                                        items: [{
                                            label: "Install",
                                            disabled: existsRunningTask,
                                            autoBusy: false,
                                            onClick: function () {
                                                runTask("install", false, productInfo.id);
                                            }
                                        }, {
                                            label: "Install including End of Sale items",
                                            disabled: existsRunningTask,
                                            autoBusy: false,
                                            onClick: function () {
                                                runTask("install", true, productInfo.id);
                                            }
                                        }]
                                    }]
                                });
                                break;
                            case "upgrade":
                                if (existsRunningTask) {
                                    self.byId('productStatus').set({status: 'inProgress'});
                                } else {
                                    self.byId('productStatus').set({
                                        status: 'upgrade'
                                    });
                                }
                                self.byId('product').set({
                                    buttons: [{
                                        title: _('Actions'),
                                        items: [{
                                            label: "Upgrade",
                                            disabled: existsRunningTask,
                                            autoBusy: false,
                                            onClick: function () {
                                                runTask("upgrade", false, productInfo.id);
                                            }
                                        }, {
                                            label: "Upgrade including End of Sale items",
                                            disabled: existsRunningTask,
                                            autoBusy: false,
                                            onClick: function () {
                                                runTask("upgrade", true, productInfo.id);
                                            }
                                        }]
                                    }]
                                });
                                break;
                            default:
                                self.byId('product').set({
                                    buttons: []
                                });
                                if (existsRunningTask) {
                                    self.byId('productStatus').set({status: 'inProgress'});
                                } else {
                                    self.byId('productStatus').set({status: 'up2date'});
                                }
                                break;
                        }
                    }
                }
                aps.apsc.hideLoading();
            }).otherwise(function (error) {
                self.byId("tiles").set({visible: false});
                self.byId("actionLog").set({visible: false});
                console.log("Error happened", error);
                aps.apsc.displayMessage({
                    "description": _("We are sorry, an error has happened, please try again later"),
                    "type": "error"
                });
                aps.apsc.hideLoading();
            });
        }
    })
        ;
})
;
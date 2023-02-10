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
    "./lib/marked.min.js",
    "aps/Status",
    "aps/ToolbarButton",
    "aps/_View",
    "./tools/helpers/parameters.js"
], function (declare, xhr, all, Memory, Output, Button, Container, at, getStateful, marked, Status, ToolBarButton, _View, parameters) {
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

    function waitHtml(){
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
						<div class="message"><br/>' +_('Please wait while you are being redirected...')  +'</div>\
					</div>\
				</div>\
			</body>\
		</html>\
	';
        return string;
    }
    function packageLocalize(locale, string) {
        if (locale && locale[string]) {
            return locale[string];
        }
        return string;
    }

    return declare(_View, {
        init: function () {
            var self = this;
            return [
                ["aps/Tiles", {
                    id: self.genId("tiles")
                }, [
                    ["aps/Tile", {
                        id: self.genId("product"),
                        gridSize: "md-6 xs-12",
                        info: new Status({
                            gridSize: 'md-12',
                            id: self.genId('statusTCR'),
                            statusInfo: {
                                'approved': {
                                    "label": _('Ready'),
                                    "type": "success"
                                },
                                'pending': {
                                    "label": _('Updating'),
                                    "type": "warning"
                                },
                                'inquiring': {
                                    "label": _('Inquiring'),
                                    "type": "muted",
                                    isLoad: true
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
                                ["aps/FieldSet", {gridSize: "md-12 xs-12"}, [
                                    ["aps/Output", {
                                        gridSize: "md-12 xs-12",
                                        id: self.genId("productDescription")
                                    }],
                                    ["aps/Output", {
                                        gridSize: "md-6 xs-12",
                                        id: self.genId("TcID"),
                                        label: _("Configuration ID")
                                    }],
                                    ["aps/Output", {
                                        gridSize: "md-6 xs-12",
                                        id: self.genId("PRID"),
                                        label: _("Product ID")
                                    }]
                                ]]]]
                        ]]
                    ]],
                    ["aps/Tile", {
                        id: self.genId("parametersTile"),
                        gridSize: "md-6 xs-12",
                        title: _('Parameters'),
                        buttons: [{
                          label: _('Edit'),
                          type: "success",
                          id: self.genId("editbutton"),
                          autoBusy: false
                        }]
                    }, [
                        ["aps/Grid", {
                            gridSize: "md-12 xs-12",
                            id: self.genId("parametersGrid"),
                            noDataText: _("This product has no parameters"),
                            noEntriesFoundText: _("No parameters available matching your search criteria")
                        }]
                    ]]
                ]
                ],
                ["aps/Toolbar", {
                    id: self.genId("actionsToolBar")
                }],
                ["aps/Tiles", {
                    id: self.genId("tilesMarkup")
                },[
                    ["aps/Tile", {
                        id: self.genId("markupContentTile"),
                        gridSize: 'md-12 xs-12'
                    },[
                        ["aps/Output",{
                            escapeHTML: false,
                            id: self.genId("markupContent")
                        }]
                    ]]
                ]]
            ];
        },
        onContext: function () {
            var self=this;
            self.byId("actionsToolBar").removeAll();
            xhr.get("/aps/2/resources/" + aps.context.params.aps).then(function (apsResource) {
                var localeDictionary = {};
                xhr.get(apsResource.aps.package.href + "/i18n/" + aps.context._locale + ".json").then(function (locale) {
                    localeDictionary = locale;
                }).otherwise(function () {
                    localeDictionary = {};
                }).always(function () {
                    self.byId('product').set({
                        title: packageLocalize(localeDictionary, aps.context.params.configuration.product.name)
                    });
                    self.byId('statusTCR').set({
                        status: aps.context.params.status
                    });
                    self.byId('editbutton').set({
                        disabled: (aps.context.params.status == "approved" && aps.context.params.params.length > 0 ? false : true),
                        onClick: function () {
                            var params = aps.context.params;
                            params.localeDictionary = localeDictionary;
                            aps.apsc.showPopup({
                                viewId: 'editparams',
                                params: params,
                                modal: false
                            }).then(function(popupData){
                                if(popupData.btnType === "submit"){
                                    aps.apsc.displayMessage({
                                        "description": "Your request to update settings is being processed",
                                        "type": "info"
                                    });
                                    self.byId('editbutton').set({
                                        disabled: true
                                    });
                                    self.byId('statusTCR').set({
                                        status: 'pending'
                                    });

                                }
                            });
                        }
                    });
                    self.byId('productIcon').set({
                        "content": '<span class="media"><img class="media-object" src="' + apsResource.aps.package.href + "/images/logo.png" + '"></span>'
                    });
                    xhr.get(apsResource.aps.package.href + "/APP-META.xml", {
                        handleAs: 'xml'
                    }).then(function (AppMeta) {
                        self.byId('productDescription').set({
                            "content": packageLocalize(localeDictionary,AppMeta.getElementsByTagName('description')[0].childNodes[0].nodeValue)
                        });
                    }).otherwise(function () {
                        console.log("Error obtaining APP-META");
                    });
                    self.byId('TcID').set({
                        value: aps.context.params.configuration.id
                    });
                    self.byId('PRID').set({
                        value: aps.context.params.configuration.product.id
                    });
                    if(aps.context.params.configuration.template) {
                        var title = "";
                        var content = aps.context.params.configuration.template.representation;
                        if(aps.context.params.configuration.template.representation.slice(0, 2) === "# ") {
                            title = aps.context.params.configuration.template.representation.split('\n')[0].replace("# ", "");
                            content = content.split('\n');
                            content.splice(0,1);
                            content = content.join('\n');
                            content.replace("# ", "### ");
                            content.replace("## ", "### ");
                        }
                        self.byId('markupContentTile').set({
                           "title": title
                        });
                        self.byId('markupContent').set({
                            "content": marked(content)
                        });
                        /* Working with Parameters */
                        if (aps.context.params.configuration.params.length > 0) {
                            self.byId("parametersTile").set({
                                visible: true
                            });
                            parameters.setLocaleDictionary(localeDictionary);
                            parameters.populateParamsGrid(self, "parametersGrid", aps.context.params.configuration.params);
                        }
                        /* ACTIONS */
                        aps.context.params.configuration.actions.forEach(function (action) {
                            self.byId("actionsToolBar").addChild(
                              new ToolBarButton({
                                  label: packageLocalize(localeDictionary, action.title),
                                  autoBusy: false,
                                  onClick: function onClick() {
                                      aps.apsc.showLoading();
                                      var newTabId = Date.now();
                                      var newTab = window.open('', newTabId);

                                      if (!newTab) {
                                          throw new Error('Window \'newTabId\' could not be opened.');
                                      }
                                      newTab.opener = null;
                                      newTab.document.write(waitHtml());

                                      xhr.post("/aps/2/resources/" + aps.context.params.aps + "/tier/action/", {
                                          headers: {
                                              'Content-Type': 'application/json'
                                          },
                                          data: JSON.stringify({
                                              "action_id": action.id,
                                              "tier_config_id": aps.context.params.configuration.id
                                          })
                                      }).then(function (data) {
                                          var token = data.url.split("jwt=");
                                          createForm(data.url, newTabId, [{key: 'jwt', value: token[1]}]);
                                          aps.apsc.hideLoading();

                                      });
                                  }
                              })
                            );
                        });
                    }
                    else{
                        self.byId("parametersTile").set({
                            visible: false
                        });
                        xhr.get('/aps/2/resources/' + aps.context.user.organization.aps.id).then(function(account){
                            self.byId('markupContentTile').set({
                                title: _('Please wait while we get things ready')
                            });
                            self.byId('markupContent').set({
                                content: _(
                                  "The vendor is currently processing information provided by you and no additional input is required at the moment."
                                  ) + "<br>" +
                                  _('In case of additional questions, an email will be sent to __CONTACT__ (__EMAIL__),  the technical contact of the __COMPANY__ account.',
                                    {
                                        COMPANY: account.companyName,
                                        CONTACT: account.techContact.givenName + " " + account.techContact.familyName,
                                        EMAIL: account.techContact.email
                                    })
                            });
                        });
                    }
                    aps.apsc.hideLoading();
                });
            }).otherwise(function () {
                aps.apsc.displayMessage("An error has occurred, please try again later");
                aps.apsc.hideLoading();
            });
        }
    });
});
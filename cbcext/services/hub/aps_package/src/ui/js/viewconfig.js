require([
  "aps/load",
  "aps/xhr",
  "dojo/promise/all",
  "aps/Memory",
  "aps/Output",
  "dijit/registry",
  "aps/Button",
  "aps/Container",
  "dojox/mvc/at",
  "dojox/mvc/getStateful",
  "./lib/marked.min.js",
  './tools/helpers/parameters.js',
  'aps/query',
  "aps/ready!cbcext/services/hub/aps_package/src/ui/js"
], function (load, xhr, all, Memory, Output, registry, Button, Container, at, getStateful, marked, parameters, query) {

  var newWinLoadingHtml = void 0;

  function searchForCSSHref(filePart) {
    var sheets = document.styleSheets;
    var href = void 0;
    for (var i = 0; i < sheets.length; i++) {
      var sheet = sheets[i];
      if (sheet.href) {
        if (sheet.href.indexOf(filePart) > -1) return sheet.href;
      } else if (sheet.cssRules) {
        for (var j = 0; j < sheet.cssRules.length; j++) {
          var cssRule = sheet.cssRules[j];
          if (!cssRule.styleSheet) continue;
          var styleSheet = cssRule.styleSheet;
          if (styleSheet && styleSheet.href && styleSheet.href.indexOf(filePart) > -1) {
            return styleSheet.href;
          }
        }
      }
    }

    return href;
  }

  function getNewWindowLoadingHtml() {
    if (newWinLoadingHtml) return newWinLoadingHtml;

    var isCCPv2 = aps.context.bs;
    var filePart = isCCPv2 ? 'bootstrap' : 'style';
    var cssHref = searchForCSSHref(filePart);
    newWinLoadingHtml = isCCPv2 ? '<html class="ccp-frame"><head>\n    <link rel="stylesheet" type="text/css" href="' + cssHref + '">\n        </head>\n        <body class="ccp-frame  ccp-md"><div id="loading-spinner" class="in">\n        <i class="fa fa-cog fa-spin fa-5x text-muted"></i></div></body></html>' : '<html class="ccp-frame"><head>\n      <link rel="stylesheet" type="text/css" href="' + cssHref + '">\n      </head>\n      <div class="page-loading">Please wait</div></html>';

    return newWinLoadingHtml;
  }

  function openNewWindow(promise) {
    var html = getNewWindowLoadingHtml();
    var win = window.open('', '_blank');
    win.document.open().write(html);

    return promise.then(function (url) {
      if (url) win.location.replace(url);
    });
  }

  function packageLocalize(locale, string) {
    if (locale && locale[string]) {
      return locale[string];
    }
    return string;
  }

  function findEvenTheNestedWidgets(innitialNode){
    return query("[widgetid]", innitialNode)
      .map(dijit.byNode)
      .filter(function(wid){ return wid;});
  }

  xhr.get("/aps/2/resources/" + aps.context.params.aps).then(function (apsResource) {
    var localeDictionary = {};
    xhr.get(apsResource.aps.package.href + "/i18n/" + aps.context._locale + ".json").then(function (locale) {
      localeDictionary = locale;
    }).otherwise(function () {
      localeDictionary = {};
    }).always(function () {
      var activeItemContent = [];
      var initEdit = {
        'view': true,
        'edit': false,
        'button': (aps.context.params.status === 'pending' ? false : true),
        'status': (aps.context.params.status === 'pending' ? true : false)
      };
      var isvisible = getStateful(initEdit);
      aps.context.params.configuration.actions.forEach(function (action) {
        activeItemContent.push(
          ["aps/ToolbarButton", {
            label: packageLocalize(localeDictionary, action.title),
            iconName: "/pem/images/icons/action_16x16.gif",
            autoBusy: false,
            onClick: function onClick() {
              return openNewWindow(xhr.post("/aps/2/resources/" + aps.context.params.aps + "/tier/action/", {
                headers: {
                  'Content-Type': 'application/json'
                },
                data: JSON.stringify({
                  "action_id": action.id,
                  "tier_config_id": aps.context.params.configuration.id
                })
              }).then(function (data) {
                return data.url;
              }));
            }
          }]
        );
      });
      var parametersInfoBoard = [];
      var parametersUpdate = [];
      var parametersUpdateId = [];
      var update = false;
      if (aps.context.params.configuration.params.length > 0) {
        aps.context.params.configuration.params.forEach(function (parameter) {
          if (parameter.phase === "ordering" && parameter.value !== "") {
            update = true;
            parametersInfoBoard.push(["aps/Output", {
              label: packageLocalize(localeDictionary, parameter.title),
              value: parameter.value
            }]);
            parametersUpdateId.push(parameter.id);
            if (parameter.type === "text") {
              parametersUpdate.push(["aps/TextBox", {
                label: packageLocalize(localeDictionary, parameter.title),
                value: parameter.value,
                description: _(parameter.description),
                required: parameter.constraints.required,
                missingMessage: _('Please provide value'),
                id: "forupdate_" + parameter.id,
                visible: (((parameter.value) || (parameter.constraints.hidden === false)) ? true : false)
              }]);
            } else if (parameter.type === 'dropdown') {
              var options = [];
              for (var i = 0; i < parameter.constraints.choices.length; i++) {
                options.push({
                  "value": parameter.constraints.choices[i].value,
                  "label": packageLocalize(localeDictionary, parameter.constraints.choices[i].label),
                  "selected": (parameter.value === parameter.constraints.choices[i].value ? true : false)
                });
              }
              parametersUpdate.push(["aps/Select", {
                label: packageLocalize(localeDictionary, parameter.title),
                options: options,
                description: _(parameter.description),
                required: parameter.constraints.required,
                missingMessage: _('Please provide value'),
                id: "forupdate_" + parameter.id,
                visible: (((parameter.value) || (parameter.constraints.hidden === false)) ? true : false)
              }]);
            }
          }
        });
      }
      if (update === true) {
        activeItemContent.push(
          ["aps/ToolbarButton", {
            label: _("Update Information"),
            iconName: "/pem/images/icons/action_16x16.gif",
            autoBusy: false,
            visible: at(isvisible, 'button'),
            onClick: function () {
              var widgets = findEvenTheNestedWidgets('viewFieldset');
              widgets.forEach(function (widget) {
                registry.byId(widget.id).set({
                  disabled: false
                });
              });
              isvisible.set({'view': false, 'edit': true, 'button': false});
            }
          }]);
        activeItemContent.push(
          ["aps/ToolbarButton", {
            id: 'Update',
            label: _('Save'),
            iconName: "/pem/images/icons/action_16x16.gif",
            visible: at(isvisible, 'edit'),
            onClick: function () {
              if (registry.byId('viewFieldset').validate()) {
                var params = parameters.getParamValues(registry, aps.context.params.configuration.params.filter(
                    function(param){
                        return param.phase==="ordering" && (param.constraints.hidden && param.value || !param.constraints.hidden);
                    }
                    ), 'id');
                xhr.post("/aps/2/resources/" + aps.context.params.aps + "/tier/config",
                  {
                    headers: {
                      'Content-Type': 'application/json'
                    },
                    data: JSON.stringify({
                      "configuration": {
                        "id": aps.context.params.configuration.id
                      },
                      "params": params
                    })
                  }).then(function () {
                  var widgets = findEvenTheNestedWidgets('viewFieldset');
                  widgets.forEach(function (widget) {
                    registry.byId(widget.id).set({
                      disabled: true
                    });
                  });
                  isvisible.set({'edit': false, 'view': true, 'button': false, 'status': true});
                }).otherwise(function () {
                  aps.apsc.displayMessage(_("Error updating configuration, try again later"));
                }).always(function () {
                  registry.byId('Update').cancel();
                });
              }
            }
          }]);
        activeItemContent.push(
          ["aps/ToolbarButton", {
            id: 'Cancel',
            label: _('Cancel'),
            iconName: "/pem/images/icons/action_16x16.gif",
            visible: at(isvisible, 'edit'),
            autoBusy: false,
            onClick: function () {
              var widgets = findEvenTheNestedWidgets('viewFieldset');
              widgets.forEach(function (widget) {
                registry.byId(widget.id).set({
                  disabled: true
                });
              });
              isvisible.set({'edit': false, 'view': true, 'button': true, 'status': false});
            }
          }]);
      }
      if (parametersInfoBoard.length > 0) {
        activeItemContent.push(
          ["aps/InfoBoard", {
            cols: 1
          }, [
            ["aps/FieldSet", {
              id: "viewFieldset",
              title: _('Information provided to vendor')
            }]
          ]]
        );
      }
      if (aps.context.params.configuration.template && aps.context.params.configuration.template.representation && aps.context.params.configuration.template.representation.length > 0) {
        activeItemContent.push(["aps/Container", [
          ["aps/Output", {
            escapeHTML: false,
            value: marked(aps.context.params.configuration.template.representation)
          }]
        ]
        ]);
      }
      var page = ["aps/PageContainer", {
        id: "page"
      }, [
        ["aps/ActiveList", [
          ["aps/ActiveItem", {
            iconName: apsResource.aps.package.href + "/images/logo.png",
            title: packageLocalize(localeDictionary, aps.context.params.configuration.product.name),
            collapsible: true,
            collapsed: false,
            info: new Output({
              visible: at(isvisible, 'status'),
              innerHTML: _('Updating'),
              "class": "summary-item",
              "style": "color: #FFF; background-color: #FE9A2E; float: right; padding: 4px 7px; " +
                "margin-top: 3px; margin-right: 5px;"
            })
          }, activeItemContent
          ]]]]];
      load(page).then(function() {
        if (parametersInfoBoard.length > 0) {
          parameters.setLocaleDictionary(localeDictionary);
          registry.genId = function(id) {
            return id;
          };
          parameters.addParameters(registry, aps.context.params.configuration.params.filter(function(param){return param.phase==="ordering";}), "viewFieldset");
          var widgets = findEvenTheNestedWidgets('viewFieldset');
          widgets.forEach(function (widget) {
            registry.byId(widget.id).set({
              disabled: true
            });
          });
        }
      });
    });
  }).otherwise(function () {
    aps.apsc.displayMessage("An error has occurred, please try again later");
    var page = ["aps/PageContainer", {
      id: "page"
    }];
    load(page);
  });
});
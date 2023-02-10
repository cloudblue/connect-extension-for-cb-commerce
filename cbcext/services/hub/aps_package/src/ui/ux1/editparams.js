define([
    "dojo/_base/declare",
    "aps/_PopupView",
    "dojo/Deferred",
    "aps/TextBox",
    "aps/Select",
    "aps/xhr",
    "./tools/helpers/parameters.js"
], function (
    declare,
    _PopupView,
    Deferred,
    TextBox,
    Select,
    xhr,
    parameters
) {
    var parametersUpdateId = [];

    return declare(_PopupView, {
        size: "md",
        init: function () {
            var self = this;
            return [
                "aps/Panel", {
                    id: self.genId('editParametersPanel')
                }, [
                    ["aps/FieldSet", {
                        id: self.genId("fieldsetOutputParameters"),
                        gridSize: "xs-12 md-12",
                        type: 'widgets'
                    }]
                ]
            ];

        },
        onContext: function() {
            var self = this;
            parametersUpdateId = [];
            var localeDictionary = aps.context.params.localeDictionary;
            parameters.setLocaleDictionary(localeDictionary);
            parameters.addParameters(self, aps.context.params.configuration.params.filter(function(param){return param.phase==="ordering";}), "fieldsetOutputParameters");
            aps.apsc.hideLoading();
        },
        onCancel: function () {
            this.cancel();
        },
        onSubmit: function(){
            var self = this;
            if (this.byId('fieldsetOutputParameters').validate()) {
                var params = parameters.getParamValues(self, aps.context.params.configuration.params.filter(
                    function(param){
                        return param.phase==="ordering" && (param.constraints.hidden && param.value || !param.constraints.hidden);
                    }
                    ), "id");
                aps.apsc.showLoading();
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
                    aps.apsc.hideLoading();
                    self.submit();
                }).otherwise(function () {
                    aps.apsc.hideLoading();
                    aps.apsc.displayMessage(_("Error updating configuration, try again later"));
                });
            }
            else{
                aps.apsc.cancelProcessing();
            }
        },
        onHide: function() {
            var self = this;
            self.byId('fieldsetOutputParameters').removeAll();
        }
    });
});
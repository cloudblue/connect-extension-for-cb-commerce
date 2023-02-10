require([
    "aps/load",
    "aps/xhr",
    "aps/ready!cbcext/services/hub/aps_package/src/ui/js"
], function (load, xhr) {
    xhr.get(
        "/aps/2/resources/" + aps.context.params.taskId
    ).then(function (task) {
        var page = ["aps/PageContainer", {
            id: "page"
        }, [
            ["aps/Output", {
                id: "taskDetailsIntro",
                content: _("Raw operation execution details")
            }],
            ["aps/Hr"],
            ["aps/Output", {
                id: "rawDetails",
                escapeHTML: false,
                content: JSON.stringify(task, null, 2)
            }],
            ["aps/Hr"],
            ["aps/Button", {
                id: "back",
                autoBusy: false,
                label: _("Back"),
                onClick: function () {
                    aps.apsc.gotoView("productmanagement", null, {
                        "product": aps.context.params.product
                    });
                }
            }]
        ]];
        load(page);
    }).otherwise(function (error) {
        var page = ["aps/PageContainer", {
            id: "page"
        }];
        load(page);
        aps.apsc.displayMessage(error.message());
    });
});
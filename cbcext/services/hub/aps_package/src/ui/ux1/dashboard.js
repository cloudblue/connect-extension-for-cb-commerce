define([
  'dojo/_base/declare',
  'aps/nav/ViewPlugin',
  'aps/common',
  'dojox/mvc/getStateful',
  'aps/i18n',
  'aps/xhr',
  'module',
  "aps/tiles/UsageInfoTile"
], function (
  declare,
  ViewPlugin,
  common,
  getStateful,
  i18n,
  xhr,
  apsModule,
  UsageInfoTile
) {
  /* UTILITIES */
  var _ = i18n.bindToPackage(common.getPackageId(apsModule));

  // DECLARATION
  return declare(ViewPlugin, {
    init: function (mediator) {
      var self = this;
      var tcrTile = new UsageInfoTile({
        id: self.genId('tcrTile'),
        gridSize: "md-4 xs-12",
        title: _('Reseller Authorization'),
        iconName: self.buildStaticURL('ui/images/fa-handshake.svg'),
        showPie: false,
        visible: true,
        showNumber: false,
        description: _("Product requires your attention"),
        usageHint: _("out of 0 being configured"),
        value: 0,
        onClick: function () {
          aps.apsc.gotoView("http://odin.com/servicesSelector#tierconfigsux1");
        }
      });

      mediator.getWidget = function () {
        return tcrTile;
      };
    },
    onContext: function (context) {
      var self = this;
      xhr.get(
        '/aps/2/resources/' + context.vars.extension.aps.id + '/getTierConfigs?eq(status,processing)',
        {'sync': false}
      ).then(function (tcrs) {
          var pending = 0;
          var inquiring = 0;
          tcrs.forEach(function(tc){
            if (tc.status === "pending"){
              pending++;
            }
            if(tc.status === "inquiring"){
              inquiring++;
            }
          });
          self.byId("tcrTile").set({
            visible: true,
            description: ( pending < 2 ? _('Product requires your attention') : _('Products require your attention')),
            usageHint: _("out of __PENDING__ being configured", { "PENDING": pending + inquiring}),
            value: inquiring
          });
        });
    }
  });
});
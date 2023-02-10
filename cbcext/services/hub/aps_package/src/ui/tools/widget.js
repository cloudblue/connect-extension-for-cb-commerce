define([], function() {
  return function(widget, settings) {
    var opt = settings || {};
    return function(children) {
      return children ? [widget, opt, children] : [widget, opt];
    };
  };
});

define([
], function() {
  var VALID_CHARS = 'QWERTYUIOPASDFGHJKLZXCVBNMqwertyuiopasdfghjklzxcvbnm1234567890!@#$%^&*()-_+=';
  var newWinLoadingHtml;

  function searchForCSSHref(filePart) {
    var sheets = document.styleSheets;
    var href = '';

    for (var i = 0; i < sheets.length; i++) {
      var sheet = sheets[i];

      if (sheet.href) {
        if (sheet.href.indexOf(filePart) > -1) {
          return sheet.href;
        }
      } else if (sheet.cssRules) {
        for (var j = 0; j < sheet.cssRules.length; j++) {
          var cssRule = sheet.cssRules[j];

          if (!cssRule.styleSheet) {
            continue;
          }

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
    newWinLoadingHtml = isCCPv2 ?
        '<html class="ccp-frame">' +
        '<head>' +
        '<link rel="stylesheet" type="text/css" href="' + cssHref + '">' +
        '</head>' +
        '<body class="ccp-frame  ccp-md">' +
           '<div id="loading-spinner" class="in">' +
              '<i class="fa fa-cog fa-spin fa-5x text-muted"></i>' +
           '</div>' +
        '</body>' +
        '</html>' :
        '<html class="ccp-frame">' +
        '<head>' +
          '<link rel="stylesheet" type="text/css" href="' + cssHref + '">' +
        '</head>' +
        '<div class="page-loading">Please wait</div>' +
        '</html>';

    return newWinLoadingHtml;
  }

  // HELPERS FOR RESOURCE INFO
  function getLimit(_counter, _tenant) {
    return _tenant[_counter.position].limit;
  }

  function isLimited(_counter, _tenant) {
    return getLimit(_counter, _tenant) >= 0;
  }

  function decorateAsLimited(_counter, _tenant) {
    return _counter.title + ':' + getLimit(_counter, _tenant) + ' ' + _counter.units;
  }

  function decorateAsUnlimited(_counter) {
    return _counter.title + ': unlimited';
  }

  function decorateCounter(_counter, _tenant) {
    if (isLimited(_counter, _tenant)) {
      return decorateAsLimited(_counter, _tenant);
    } else {
      return decorateAsUnlimited(_counter);
    }
  }

  function pth(object, path) {
    if(object === undefined || object === null){
      return undefined;
    }
    return path.length ? object[path[0]] ? pth(object[path.shift()], path) : undefined : object;
  }


  return {
    // >>> Reusable functional tools
    openNewWindow: function (promise) {
      var html = getNewWindowLoadingHtml();
      var win = window.open('', '_blank');
      win.document.open().write(html);

      return promise.then(function(url) {
        if (url) {
          win.location.replace(url);
        }
      });
    },

    // Returns formatted string with limits for all counters with non-zero limits
    getResourcesInfo: function(tenant, appInfo) {
      return appInfo.allCounters.reduce(function(result, counter) {
        if (tenant[counter.position].limit !== 0) {
          if (result.length > 0) result += ', ';

          result += decorateCounter(counter, tenant);
        }

        return result;
      }, '');
    },

    isUnlimited: function(resource, t, f) {
      return resource.limit === -1 ? t : f;
    },

    fill: function (array) {
      return array.reduce(function (accum, item) {
        if (Array.isArray(item)) {
          accum.push(item);
        } else if (typeof item === 'function') {
          var r = item();

          if (!!r) {
            accum.push(r);
          }
        }

        return accum;
      }, []);
    },

    poll: function (callback, marker, timeout) {
      function Polling(pollCallback, pollMarker) {
        var self = this;
        self._polling = null;

        this.start = function() {
          if (pollMarker) pollMarker();

          if (!self._polling) {
            self._polling = setInterval(pollCallback, timeout);
          }
        };

        this.stop = function() {
          clearInterval(self._polling);
          self._polling = null;
        };
      }

      return new Polling(callback, marker);
    },

    generatePassword: function(len) {
      var res = '';
      while(res.length <= len) {
        res += VALID_CHARS[Math.floor(Math.random() * VALID_CHARS.length)];
      }

      return res;
    },

    // >>> Small lodash-like helpers
    noop: function() {},

    not: function(v) {
      return !v;
    },

    snakeCase: function(str) {
      return str.toLowerCase().replace(/ +/g, '_');
    },

    serialize: function(obj, space) {
      return JSON.stringify(obj, null, space || 2);
    },

    getCurrentDate: function() {
      return (new Date()).toLocaleDateString();
    },

    path: pth,

    merge: function(to, from) {
      Object.keys(from).forEach(function (key) { to[key] = from[key]; });

      return to;
    },

    flatten: function flatten(arr) {
      return arr.reduce(function (accum, elem) {
        return accum.concat(Array.isArray(elem) ? flatten(elem) : [elem]);
      }, []);
    },

    unnest: function (arr) {
      return arr.reduce(function (accum, elem) {
        if (Array.isArray(elem)) {
          return accum.concat(elem);
        }

        return accum.concat([elem]);
      }, []);
    },

    template: function (tpl, src) {
      var res = {};

      for (var key in tpl) {
        if (tpl.hasOwnProperty(key)) {
          if (Array.isArray(tpl[key])) {
            res[key] = pth(src, tpl[key]);
          } else {
            res[key] = tpl[key];
          }
        }
      }

      return res;
    },

    safeArray: function(data) {
      return Array.isArray(data) ? data : [data];
    },

    always: function(v) {
      return function() {
        return v;
      };
    }
  };
});

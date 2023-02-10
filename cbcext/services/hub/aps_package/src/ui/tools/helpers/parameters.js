define([
    "aps/Output",
    "aps/Button",
    "aps/Container",
    "aps/Status",
    "aps/ToolbarButton",
    'aps/TextBox',
    'aps/Select',
    'aps/Password',
    'aps/CheckBox',
    'aps/RadioButton',
    'aps/validate/web',
    "aps/Memory",
    "aps/Switch",
    "aps/FieldSet",
    './tools/utils.js',
    './tools/helpers/countries.js',
    './lib/libphonenumber.js'
  ], function (
  Output,
  Button,
  Container,
  Status,
  ToolbarButton,
  TextBox,
  Select,
  Password,
  CheckBox,
  RadioButton,
  web,
  Memory,
  Switch,
  FieldSet,
  utils,
  countries,
  libphonenumber
  ) {
    var generatePassword = utils.generatePassword;
    var path = utils.path;
    var merge = utils.merge;
    var complexParameterTypes = ['address', 'subdomain', 'checkbox', 'radiobutton', 'choice', 'phone', 'object'];
    var localeDictionary = {};

    function packageLocalize(string) {
      if (localeDictionary[string]) {
        return localeDictionary[string];
      }
      return _('__STRING__', {"STRING": string});
    }

    function constraint(param, name) {
      return param.constraints[name] ? param.constraints[name] : false;
    }

    function setWidgetsState(page, state, parameters) {
      function disableWidgets(arr) {
        arr.forEach(function (w) {
          if (page.byId(w).visible) {
            page.byId(w).set({
              disabled: !state
            });
          }
        });
      }

      parameters.forEach(function (param) {
        if (complexParameterTypes.indexOf(param.type) > -1) {
          switch (param.type) {
            case 'phone':
              disableWidgets(['param-' + param.id + '-input']);
              break;
            case 'checkbox':
              disableWidgets((path(param, ['constraints', 'choices']) || []).map(function (choice) {
                return 'param-' + param.id + '-input-' + choice.value;
              }));
              break;
            case 'subdomain':
              disableWidgets(['param-' + param.id + '-input', 'param-' + param.id + '-input-select']);
              break;
            case 'choice':
              disableWidgets((path(param, ['constraints', 'choices']) || []).map(function (choice) {
                return 'param-' + param.id + '-input-' + choice.value;
              }));
              break;
            case 'address':
              disableWidgets([
                'param-' + param.id + '-address1',
                'param-' + param.id + '-address2',
                'param-' + param.id + '-city',
                'param-' + param.id + '-country',
                'param-' + param.id + '-region',
                'param-' + param.id + '-postalcode'
              ]);
              break;
            case 'object':
              return true;
            default:
              return true;
          }
        } else {
          disableWidgets(['param-' + param.id + '-input']);
          return true;
        }
      });
    }

    return {
      setLocaleDictionary: function (dictionary) {
        localeDictionary = dictionary;
      },
      addParameters: function addParameters(page, parameters, location, contact) {
        if (typeof contact === "undefined") {
          contact = {
            "streetAddress": "",
            "extendedAddress": "",
            "locality": "",
            "countryName": "",
            "region": "",
            "postalCode": "",
            "phoneNumber": ""
          };
        }
        parameters.forEach(function (param) {
          if (param.type === 'object') {
            return;
          }
          if(param.type !== 'address') {
            var widget = new Container({
              id: page.genId('param-' + param.id + '-input-container'),
              gridSize: 'md-12 xs-12',
              visible: (param.value || !(constraint(param, 'hidden'))),
              label: packageLocalize(param.title)
            });
          }
          var defaultOptions = {
            id: page.genId('param-' + param.id + '-input'),
            gridSize: 'md-12 xs-12',
            required: constraint(param, 'required'),
            visible: (param.value || !(constraint(param, 'hidden'))),
            description: packageLocalize(param.hint),
            placeholder: (param.placeholder || ""),
            value: (param.value || "")
          };
          var additionalOptions = {};
          switch (param.type) {
            case 'text':
              widget.addChild(new TextBox(defaultOptions));
              break;
            case 'phone':
              additionalOptions = {
                extraValidator: function (inputNumber) {
                  try {
                    return libphonenumber.parsePhoneNumberFromString(inputNumber).isValid();
                  } catch (_) {
                    return false;
                  }
                },
                value: (param.value ? param.value : contact.phoneNumber)
              };
              widget.addChild(new TextBox(merge(defaultOptions, additionalOptions)));
              break;
            case 'dropdown':
              var existsDefault = false;
              var defaultValue = "";
              defaultOptions.options = (path(param, ['constraints', 'choices']) || []).map(function (item) {
                if (item.default) {
                  existsDefault = true;
                  defaultValue = item.value;
                }
                return {
                  label: item.label,
                  value: item.value,
                  selected: (param.value && param.value === item.value || item.default)
                };
              });
              if (param.constraints.required !== true) {
                defaultOptions.options.unshift(
                  {
                    label: _('-- please select --'),
                    value: "",
                    selected: !existsDefault
                  }
                );
              }
              widget.addChild(new Select(defaultOptions));
              // Workarround for CCPv1 dropdown that does not get value after creation
              page.byId('param-' + param.id + '-input').set({
                'value': defaultValue
              });
              break;
            case 'password':
              additionalOptions = {
                confirmation: false,
                constraints: {
                  minimumLength: constraint(param, 'min_length'),
                  maximumLength: constraint(param, 'max_length')
                },
                showGenerateButton: true,
                showStrengthIndicator: false,
                value: ((!param.value || param.value === "") ?
                  generatePassword((!constraint(param, 'min_length') ? 8 : constraint(param, 'min_length'))) : param.value)
              };
              widget.addChild(new Password(merge(defaultOptions, additionalOptions)));
              break;
            case 'email':
              additionalOptions = {
                extraValidator: web.isEmailAddress,
                invalidMessage: _('Invalid e-mail address')
              };
              widget.addChild(new TextBox(merge(defaultOptions, additionalOptions)));
              break;
            case 'checkbox':
              widget.set({
                label: packageLocalize(param.title),
                visible: !(constraint(param, 'hidden'))
              });
              ((path(param, ['constraints', 'choices']) || []).forEach(function (choice) {
                widget.addChild(new CheckBox({
                  description: packageLocalize(choice.label),
                  gridSize: 'md-12 xs-12',
                  value: choice.value,
                  id: page.genId('param-' + param.id + '-input-' + choice.value),
                  checked: param.default
                }));
              }));
              break;
            case 'subdomain':
              widget.set({
                label: param.title,
                visible: (param.value || !(constraint(param, 'hidden')))
              });
              var values = [];
              if (param.value && param.value !== "") {
                values = param.value.replace(/\./, '&').split('&');
              }
              widget.addChild(new TextBox({
                id: page.genId('param-' + param.id + '-input'),
                required: constraint(param, 'required'),
                gridSize: 'md-6 xs-6',
                extraValidator: function (value) {
                  var re = new RegExp(/^([A-Za-z]|[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])$/);
                  return value.match(re);
                },
                value: (values[0] ? values[0] : "")
              }));
              widget.addChild(new Select({
                id: page.genId('param-' + param.id + '-input-select'),
                gridSize: 'md-6 xs-6',
                options: (path(param, ['constraints', 'choices']) || []).map(function (item) {
                  return {
                    label: "." + item.label,
                    value: item.value,
                    selected: ((values[1] && values[1] === item.value) || item.default)
                  };
                })
              }));
              break;
            case 'domain':
              additionalOptions = {
                extraValidator: function (domain) {
                  var re = new RegExp(/^([a-zA-Z0-9_][-_a-zA-Z0-9]{0,62}\.)+([a-zA-Z0-9]{1,10})$/);
                  return domain.match(re);
                }
              };
              widget.addChild(new TextBox(merge(defaultOptions, additionalOptions)));
              break;
            case 'url':
              additionalOptions = {
                extraValidator: function (url) {
                  try {
                    new URL(url);
                  } catch (_) {
                    return false;
                  }
                  return true;
                }
              };
              widget.addChild(new TextBox(merge(defaultOptions, additionalOptions)));
              break;
            case 'choice':
              widget.set({
                label: packageLocalize(param.title),
                visible: !(constraint(param, 'hidden'))
              });
              var first = true;
              var valueSelected = "";
              ((path(param, ['constraints', 'choices']) || []).forEach(function (choice) {
                if (first || param.default) {
                  valueSelected = choice.value;
                }
                widget.addChild(new RadioButton({
                  description: packageLocalize(choice.label),
                  name: 'param-' + param.id + '-input',
                  gridSize: 'md-12 xs-12',
                  value: packageLocalize(choice.value),
                  id: page.genId('param-' + param.id + '-input-' + choice.value),
                  checked: (param.default ? param.default : first),
                  onClick: function () {
                    page.byId('param-' + param.id + '-input-container').set({
                      'valueSelected': choice.value
                    });
                  }
                }));
                first = false;
              }));
              widget.valueSelected = valueSelected;
              break;
            case 'address':
              page.byId(location).addChild(new Output({
                id: page.genId('param-' + param.id + '-input-error'),
                visible: false,
                gridSize: 'md-12 xs-12'
              }));
              page.byId(location).addChild(new Output({
                id: page.genId('param-' + param.id + '-input-description'),
                label: packageLocalize(param.title),
                content: packageLocalize(param.description),
                gridSize: 'md-12 xs-12',
                visible: (param.structured_value && param.structured_value.address_line1 || !(constraint(param, 'hidden')))
              }));
              page.byId(location).addChild(new TextBox({
                id: page.genId('param-' + param.id + '-address1'),
                required: constraint(param, 'required'),
                gridSize: 'md-6 xs-12',
                label: _('Address line 1'),
                value: (param.structured_value && param.structured_value.address_line1 ? param.structured_value.address_line1 : contact.streetAddress),
                visible: (param.structured_value && param.structured_value.address_line1 || !(constraint(param, 'hidden')))
              }));
              page.byId(location).addChild(new TextBox({
                id: page.genId('param-' + param.id + '-address2'),
                required: false,
                gridSize: 'md-6 xs-12',
                label: _('Address line 2'),
                value: (param.structured_value && param.structured_value.address_line2 ? param.structured_value.address_line2 : contact.extendedAddress),
                visible: (param.structured_value && param.structured_value.address_line1 || !(constraint(param, 'hidden')))
              }));
              page.byId(location).addChild(new TextBox({
                id: page.genId('param-' + param.id + '-city'),
                required: false,
                gridSize: 'md-6 xs-12',
                label: _('City'),
                value: (param.structured_value && param.structured_value.city ? param.structured_value.city : contact.locality),
                visible: (param.structured_value && param.structured_value.address_line1 || !(constraint(param, 'hidden')))
              }));
              page.byId(location).addChild(new TextBox({
                id: page.genId('param-' + param.id + '-region'),
                required: constraint(param, 'required'),
                gridSize: 'md-6 xs-12',
                label: _('Region'),
                pattern: "[a-zA-Z0-9_()'!\\s\\-\\.&\\u00C0-\\uFFFD]{1,64}$",
                placeHolder: _("e.g.: Alaska"),
                value: (param.structured_value && param.structured_value.state ? param.structured_value.state : contact.region),
                visible: (param.structured_value && param.structured_value.address_line1 || !(constraint(param, 'hidden')))
              }));
              page.byId(location).addChild(new TextBox({
                id: page.genId('param-' + param.id + '-postalcode'),
                required: constraint(param, 'required'),
                gridSize: 'md-6 xs-12',
                label: _('ZIP'),
                placeHolder: _("e.g.: 12345"),
                pattern: "^(.){0,10}$",
                value: (param.structured_value && param.structured_value.postal_code ? param.structured_value.postal_code : contact.postalCode),
                visible: (param.structured_value && param.structured_value.address_line1 || !(constraint(param, 'hidden')))
              }));
              if (contact.countryName) {
                countries.forEach(function (country, index) {
                  if (country['value'] === contact.countryName.toUpperCase()) {
                    countries[index]['selected'] = true;
                  }
                });
              } else if (param.structured_value && param.structured_value.country) {
                countries.forEach(function (country, index) {
                  if (country['value'] === param.structured_value.country.toUpperCase()) {
                    countries[index]['selected'] = true;
                  }
                });
              }
              page.byId(location).addChild(new Select({
                id: page.genId('param-' + param.id + '-country'),
                required: constraint(param, 'required'),
                gridSize: 'md-6 xs-12',
                label: _('Country'),
                placeHolder: _("Choose Country"),
                options: countries,
                visible: (param.structured_value && param.structured_value.address_line1 || !(constraint(param, 'hidden')))
              }));
              break;
          }
          if(param.type !== "address") {
            widget.addChild(new Output({
              id: page.genId('param-' + param.id + '-input-error'),
              visible: false,
              value: "error placeholder",
              gridSize: 'md-12 xs-12',
              "style": "margin-top:-8px"
            }));
            page.byId(location).addChild(widget);
          }
        });
      },
      getParamValues: function getParamValues(page, parametersList, key) {
        if (parametersList == undefined) {
          return [];
        }
        return parametersList.reduce(function (accum, param) {
          var processedParam = {};
          var value = "";
          if (complexParameterTypes.indexOf(param.type) > -1) {
            var structured_value = {};
            switch (param.type) {
              case 'phone':
                processedParam[key] = param.id;
                if (page.byId('param-' + param.id + '-input').value !== "") {
                  var phone = libphonenumber.parsePhoneNumberFromString(page.byId('param-' + param.id + '-input').value);
                  structured_value['country_code'] = (phone.countryCallingCode ? "+" + phone.countryCallingCode : "");
                  structured_value['area_code'] = (phone.area_code ? phone.area_code : "");
                  structured_value['phone_number'] = (phone.nationalNumber ? phone.nationalNumber : "");
                  processedParam["structured_value"] = structured_value;
                }
                accum.push(processedParam);
                break;
              case 'checkbox':
                (path(param, ['constraints', 'choices']) || []).forEach(function (choice) {
                  structured_value[choice.value] = !!(page.byId('param-' + param.id + '-input-' + choice.value).get('checked'));
                });
                processedParam[key] = param.id;
                processedParam["structured_value"] = structured_value;
                accum.push(processedParam);
                break;
              case 'subdomain':
                processedParam[key] = param.id;
                //CCPV1-RCPv1 workarround
                if (page.byId('param-' + param.id + '-input-select').value === "") {
                  value = page.byId('param-' + param.id + '-input-select').options[0].value;
                } else {
                  value = page.byId('param-' + param.id + '-input-select').value;
                }
                processedParam["value"] = page.byId('param-' + param.id + '-input').value + '.' + value;
                accum.push(processedParam);
                break;
              case 'choice':
                processedParam[key] = param.id;
                processedParam["value"] = page.byId('param-' + param.id + '-input-container').get('valueSelected');
                accum.push(processedParam);
                break;
              case 'address':
                processedParam[key] = param.id;
                processedParam["structured_value"] = {
                  "address_line1": page.byId('param-' + param.id + '-address1').value,
                  "address_line2": page.byId('param-' + param.id + '-address2').value,
                  "city": page.byId('param-' + param.id + '-city').value,
                  "state": page.byId('param-' + param.id + '-region').value,
                  "postal_code": page.byId('param-' + param.id + '-postalcode').value,
                  "country": page.byId('param-' + param.id + '-country').value
                };
                accum.push(processedParam);
                break;
              default:
                break;
            }
          } else {
            processedParam[key] = param.id;
            //RCP and CCPv1 workarround
            if (param.type == 'dropdown' && page.byId('param-' + param.id + '-input').value === "") {
              processedParam["value"] = page.byId('param-' + param.id + '-input').options[0].value;
            } else {
              processedParam["value"] = page.byId('param-' + param.id + '-input').value;
            }
            accum.push(processedParam);
          }
          return accum;
        }, []);
      },
      anyVisible: function anyVisible(parameters) {
        return parameters.some(function (parameter) {
          return !parameter.constraints.hidden;
        });
      },
      populateParamsGrid: function populateParamsGrid(page, gridName, params) {
        // Only applicable by logic to ordering ones, is expected that fulfillment ones to be seen by actor are on some template
        var paramsData = [];
        if (params.length > 0) {
          params.forEach(function (parameter) {
            if (parameter.phase === "ordering" && parameter.value && parameter.value !== "" && parameter.type !== 'object') {
              paramsData.push({
                name: _('__TITLE__', {"TITLE": parameter.title}),
                value: parameter.value,
                type: parameter.type,
                id: "param_" + parameter.id
              });
            }
          });
        }
        var paramsMemory = new Memory({
          data: paramsData,
          idProperty: "id"
        });
        page.byId("parametersGrid").set({
          store: paramsMemory,
          columns: [
            {
              name: "type",
              field: "type",
              visible: false
            },
            {
              name: _('Parameter'),
              field: "name",
              renderCell: function (row) {
                return packageLocalize(row.name);
              }
            },
            {
              name: _('Value'),
              field: "value",
              renderCell: function (row) {
                if (row.type === 'password') {
                  return "*******";
                }
                return row.value;
              }
            }
          ],
          showPaging: true,
          rowsPerPage: 4
        });
      },
      disabledByResellerWidget: function disabledByReseller(page, location, params, name) {
        if (!page.byId('params-disabled-by-reseller')) {
          page.byId(location).addChild(new CheckBox({
            id: 'params-disabled-by-reseller',
            hint: _("Allowed because of the ordering on behalf of the customer"),
            description: _('Send email to ask for this information directly to the end-customer __NAME__', {
              "NAME": name
            }),
            onClick: function () {
              if (this.get('checked')) {
                setWidgetsState(page, false, params);
              } else {
                setWidgetsState(page, true, params);
              }
            }
          }));
        }
      },
      disabledByResellerWidgetUX1: function disabledByResellerWidgetUX1(page, location, params, name, email) {
        if (!page.byId('params-disabled-by-reseller-reseller-provides')) {
          page.byId(location).addChild(new RadioButton({
            id: page.genId('params-disabled-by-reseller-reseller-provides'),
            name: 'whoselector',
            description: _('Provide information yourself (default)'),
            checked: true,
            onClick: function () {
              setWidgetsState(page, true, params);
              page.byId('params-disabled-by-reseller').set({
                checked: false
              });
            }
          }));
        }
        else {
          page.byId('params-disabled-by-reseller-reseller-provides').set({
            checked: true
          });
          page.byId('params-disabled-by-reseller').set({
            checked: false
          });
        }
        if (!page.byId('params-disabled-by-reseller-customer-provides')) {
          page.byId(location).addChild(new RadioButton({
            id: page.genId('params-disabled-by-reseller-customer-provides'),
            name: 'whoselector',
            description: _('Send email to ask for this information directly to the end-customer __NAME__ (__EMAIL__)', {
              "NAME": name,
              "EMAIL": email
            }),
            checked: false,
            onClick: function () {
              setWidgetsState(page, false, params);
              page.byId('params-disabled-by-reseller').set({
                checked: true
              });
            }
          }));
        }
        else {
          page.byId('params-disabled-by-reseller-customer-provides').set({
            value: _('Send email to ask for this information directly to the end-customer __NAME__ (__EMAIL__)', {
              "NAME": name,
              "EMAIL": email
            })
          });
        }
      },
      validateDraftRequest: function validateDraftRequest(page, draftRequest) {
        var errorFields = draftRequest.activationParams.filter(function (v) {
          return !!v.valueError;
        });
        // Reset previous errors and apply received values
        var complexParameterTypes = ['subdomain', 'checkbox', 'choice'];
        var isOkToFinish = true;
        // Reset previous errors and apply received values
        draftRequest.activationParams.forEach(function (field) {
          if (page.byId('param-' + field.key + '-input') !== undefined) {
            if (complexParameterTypes.indexOf(field.type) > -1) {
              if (field.type === "subdomain") {
                page.byId('param-' + field.key + '-input').set({
                  value: (field.value.length > 0 ? field.value.split(".")[0] : "")
                });
              } else if (field.type === "checkbox" || field.type === "choice") {
                Object.keys(field.structured_value).forEach(function (key) {
                  if (page.byId('param-' + field.key + '-input-' + key)) {
                    page.byId('param-' + field.key + '-input-' + key).set({
                      checked: field['structured_value'][key]
                    });
                  }
                });
              }
            } else {
              page.byId('param-' + field.key + '-input').set({
                value: field.value,
                invalidMessage: null
              });
            }
          }
          if (page.byId('param-' + field.key + '-input-error') !== undefined) {
            page.byId('param-' + field.key + '-input-error').set({
              visible: false,
              content: ""
            });
          }
        });

        // Add new errors if there are any and set hidden items among them to visible
        if (errorFields.length > 0) {
          isOkToFinish = false;
          var allEqual = errorFields.length > 1 && !errorFields.some(function (item, i, a) {
            return i > 0 && item.valueError !== a[i - 1].valueError;
          });
          if (allEqual) {
            aps.apsc.displayMessage({
              "description": errorFields[0]['valueError'],
              "type": "error"
            });
          }
          errorFields.forEach(function (field) {
            if(page.byId('param-' + field.key + '-input-container') !== undefined) {
              page.byId('param-' + field.key + '-input-container').set({
                visible: true
              });
            }
            if (page.byId('param-' + field.key + '-input') !== undefined) {
              var options = {
                visible: true,
                lastValue: field.value,
                wasOptional: function () {
                  return page.byId('param-' + field.key + '-input').required !== true;
                },
                lastTime: new Date().getTime()
              };
              var no_extra_validator = ['phone', 'email', 'domain', 'url', 'subdomain'];
              if (no_extra_validator.indexOf(field.type) === -1) {
                if(!allEqual) {
                  options.invalidMessage = _("Please review this information");
                }
                options['required'] = true;
                options['extraValidator'] = function (newValue) {
                  if (this.lastValue === newValue && this.lastTime + 5000 > new Date().getTime()) {
                    if (this.wasOptional === true) {
                      page.byId('param-' + field.key + '-input').set({
                        required: false
                      });
                    }
                    return false;
                  }
                  return true;
                };
              }
              page.byId('param-' + field.key + '-input').set(options);
            }
            if (page.byId('param-' + field.key + '-input-error')) {
              page.byId('param-' + field.key + '-input-error').set({
                visible: true,
                content: (!allEqual ? "<p style='color:#ff0000'> " + field.valueError + "</p>" : ""),
                escapeHTML: true
              });
            }
          });
        }
        return isOkToFinish;
      }
    };
  }
);
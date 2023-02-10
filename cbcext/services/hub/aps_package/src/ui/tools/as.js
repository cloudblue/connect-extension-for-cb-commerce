define(['dojox/mvc/at'], function (at) {
  function _as(direction){
    return function(object, property, transform) {
      var binding = at(object, property);

      if (direction !== 'both') {
        binding = binding.direction(at[direction]);
      }

      if (typeof transform === 'function') {
        binding = binding.transform({ format: transform });
      }

      return binding;
    };
  }

  // as('from', obj, 'prop', callback) === at(obj, 'prop').direction(at.from).transform({ format: callback });
  var as = function(direction, object, property, transform) {
    return _as(direction)(object, property, transform);
  };

  // as.from(obj, 'prop', callback) === at(obj, 'prop').direction(at.from).transform({ format: callback });
  as.from = _as('from');
  // as.to(obj, 'prop', callback) === at(obj, 'prop').direction(at.to).transform({ format: callback });
  as.to = _as('to');
  // as.both(obj, 'prop', callback) === at(obj, 'prop').transform({ format: callback });
  as.both = _as('both');

  return as;
});

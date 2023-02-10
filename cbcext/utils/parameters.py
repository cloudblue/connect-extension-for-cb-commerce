OA_CACHE_LIFETIME = 30  # seconds


def extract_activation_params(params):
    parameters = {}
    for item in params:
        if "key" in item:
            value, structured_value = item.get("value"), item.get("structured_value")
            if value is None and structured_value is None:
                continue
            value_dict = _get_parameters({}, item)
            if value_dict:
                parameters[item["key"]] = value_dict

    params_list = []

    for key, value in parameters.items():
        value_dict = _get_parameters({"id": key}, value)
        params_list.append(value_dict)

    return parameters, params_list


def _get_parameters(initial_dictionary, initial_values_dict):
    """
    Formats the parameters coming from APS to operate internally
    and to be according with public api
    :param initial_dictionary: dict
    :param initial_values_dict: dict
    :return: dict
    """

    if "value" in initial_values_dict:
        initial_dictionary.update(
            {
                "value": str(
                    initial_values_dict.get(
                        "value",
                    ),
                ),
            },
        )
    if "structured_value" in initial_values_dict:
        initial_dictionary.update(
            {
                "structured_value": initial_values_dict.get(
                    "structured_value",
                ),
            },
        )
    return initial_dictionary

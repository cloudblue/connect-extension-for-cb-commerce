import re

from starlette_context import context as g


def from_aps_rql_to_client_rql(rql_params):
    match = re.match(r'limit\((\d+),(\d+)\)', rql_params)
    match2 = re.match(r'limit\((\d+)\)', rql_params)
    if match:
        limit = int(match.groups()[1])
        offset = int(match.groups()[0])
    elif match2:
        limit = int(match.groups()[0])
        offset = 0
    else:
        limit = g.client.default_limit
        offset = 0

    raw_query_string = re.sub(r'[,]?limit\((\d+),(\d+)\)', '', rql_params)
    raw_query_string = re.sub(r'[,]?limit\((\d+)\)', '', raw_query_string)
    raw_query_string = re.sub(r'\*\*', r'\*', raw_query_string)
    raw_query_string = re.sub(r'like\(', r'ilike(', raw_query_string)
    raw_query_string = re.sub(r'sort\(', r'ordering(', raw_query_string)
    if raw_query_string.startswith('and(') and len(raw_query_string[4:-1].split('),(')) == 1:
        raw_query_string = raw_query_string[4:-1]
    return raw_query_string or '', limit, offset


def serialize_for_get_tier_configs(tier_config, tier_config_request=None):
    """
    Prepares output for get on GetTierConfigs with exact information needed to draw the grid
    on CB Side
    :param tier_config:
    :param tier_config_request:
    :return: dict
    """
    output = {
        k: v for k, v in tier_config.items() if k in (
            'id',
            'product',
            'status',
            'template',
            'params',
            'marketplace',
        )
    }

    if tier_config_request:
        output['status'] = tier_config_request.get('status', output['status'])

        if 'activation' in tier_config_request:
            output['activation'] = tier_config_request['activation']

    return output


def get_resclass_name(unit):
    resclass_name = {
        'Kbit/sec': 'rc.saas.resource.kbps',
        'kb': 'rc.saas.resource',
        'mb-h': 'rc.saas.resource.mbh',
        'mhz': 'rc.saas.resource.mhz',
        'mhzh': 'rc.saas.resource.mhzh',
        'unit': 'rc.saas.resource.unit',
        'unit-h': 'rc.saas.resource.unith',
    }.get(unit)

    return resclass_name or 'rc.saas.resource.unit'


def make_aps_headers_reschedule(delay, message, transaction_id):
    """
    Creates headers to return to APS controller to reschedule a task
    :param delay: int
    :param message: str
    :param transaction_id: str
    :return:
    """
    return {
        'aps-retry-timeout': str(delay),
        'aps-info': message,
        'Aps-Transaction-Id': transaction_id,
    }


def split_in_chunks(items, n):
    """
    Simple support function to divide a list in chunks
    :param items: list
    :param n: int
    :return: list of list
    """
    for i in range(0, len(items), n):
        yield items[i:i + n]


def get_st_representation(product_name):
    """
    Returns the model of a service template
    :param product_name: string
    :return: dict
    """
    return {
        "aps": {
            "type": "http://parallels.com/aps/types/pa/serviceTemplate/1.2",
        },
        "name": product_name,
        "description": product_name,
        "autoprovisioning": True,
    }

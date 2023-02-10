from fastapi.responses import JSONResponse
from connect.client import ClientError
from starlette_context import context as g

statuses_to_track = [
    'failed',
    'pending',
    'approved',
    'inquiring',
    'tiers_setup',
    'scheduled',
    'revoking',
    'revoked',
]


def get_actions(product_id, scope):
    """
    :param product_id: str
    :param scope: enum ('asset', 'tier1', 'tier2')
    :return: list of dict
    """
    actions = list(
        g.client.products[product_id].actions.filter(f'scope={scope}'),
    )
    return actions


def get_action_id_by_action_local_id(product_id, scope, action_local_id):
    """
    returns product action id from connect given the local_id known by OA
    Action ID like 'ACT-XXX-XXX-XXX-XXX'
    :param product_id: str
    :param scope: enum ('asset', 'tier1', 'tier2')
    :param action_local_id: str
    :return: str
    """
    product_actions = get_actions(product_id, scope)
    action_id = _filter_actions_by_local_id(action_local_id, product_actions)
    return action_id


def _filter_actions_by_local_id(action_id, action_list):
    """
    Filters action response from connect based on a concrete action id
    :param action_id: str
    :param action_list: list of dicts
    :return: str || none
    """
    for action in action_list:
        if action['action'] == action_id:
            return action['id']
    return None


def get_asset_by_uuid(asset_external_uid):
    """
    Returns asset id (AS-XXX-XXX-XXX) given it's uuid.
    uuid matches APS resource and stored in connect as external_uid
    :param asset_external_uid:
    :return:
    """
    return g.client.assets.filter(f'external_uid={asset_external_uid}').first()


def get_action_link(product_id, action, scope, identifier):
    """
    Provides action link to redirect user to operate given action on top a concrete asset
    :param product_id: str
    :param action: str
    :param scope: str
    :param identifier: str
    :return: dict
    """
    filter_params = {
        '{scope}'.format(scope='asset_id' if scope == 'asset' else 'tier_config_id'): identifier,
    }
    resp = g.client.products[product_id].actions[action].action("actionLink").get(
        params=filter_params,
    )
    return resp


def get_tier_config_by_id(tier_config_id):
    """
    Provides connect tier configuration given it's ID
    :param tier_config_id: str
    :return: dict
    """
    return g.client.ns('tier').collection('configs').resource(tier_config_id).get()


def get_last_request_by_tenant_id(tenant_id, operation=None):
    """
    Returns last request for a given asset, identified by external_id and optional a given operation
    :param tenant_id: str
    :param operation: str
    :return:
    """

    if operation:
        url_filter = (
            f'and('
            f'eq(asset.external_uid,{tenant_id}),'
            f'eq(type,{operation}),'
            f'in(status,({",".join(statuses_to_track)})))'
        )
    else:
        url_filter = (
            f'and('
            f'eq(asset.external_uid,{tenant_id}),'
            f'in(status,({",".join(statuses_to_track)})))'
        )
    return g.client.requests.filter(
        url_filter,
    ).select(
        '-asset.configuration',
    ).order_by(
        '-created',
    ).first()


def get_request_by_id(request_id):
    """
    Returns a concrete request given it's id
    :param request_id: str
    :return: dict or none
    """
    try:
        request = g.client.requests[request_id].get()
    except ClientError:
        return None
    return request


def approve_due_max_retries(tenant_id, operation, limit=None):
    """
    This function contains the logic when we mark in OA a task as approved even when the
    last request failed. For that we check if last amount of requests in scope
    of given operation has failed, if last amount of requests is like the limit we will return
    OK to CBC.
    """
    limit = limit or 5

    url_filter = (
        f'and('
        f'eq(asset.external_uid,{tenant_id}),'
        f'in(status,({",".join(statuses_to_track)})))'
    )
    requests = g.client.requests.filter(url_filter).select(
        '-asset.configuration', '-asset.tiers', '-asset.items',
        '-asset.params', '-activation_key', '-template',
    ).limit(limit).order_by('-created').all()

    return len(
        list(
            filter(
                lambda r: r['type'] == operation and r['status'] == 'failed', requests,
            ),
        ),
    ) == limit if requests.count() == limit else False


def get_tcr_link_by_external_id_and_product(external_id, product_id):
    url_filter = (
        f'and('
        f'eq(configuration.product.id,{product_id}),'
        f'eq(configuration.account.external_uid,{external_id}),'
        f'in(status,(pending,inquiring,approved)))'
    )

    request = g.client.ns(
        'tier',
    ).collection(
        'config-requests',
    ).filter(
        url_filter,
    ).ordering(
        '-created',
    ).first()
    if request and request['status'] == 'inquiring' and 'activation' in request:
        return request['activation']['link']


def product_capability_parameters_change(product_id):
    connect_product = g.client.products[product_id].get()
    if 'subscription' in connect_product['capabilities']:
        capabilities = connect_product['capabilities']['subscription']
        if 'change' in capabilities and 'editable_ordering_parameters' in capabilities['change']:
            return capabilities['change']['editable_ordering_parameters']
    return False


def not_supported_schedule():
    return JSONResponse(
        content={
            "message": "An scheduled operation has been requested and is not supported yet",
        },
        status_code=400,
    )


def template_by_tenant(tenant_id, locale):
    asset = get_asset_by_uuid(tenant_id)
    if asset:
        template = g.client.assets[asset['id']].action(
            'render',
        ).get(headers={
            'Connect-Localization': locale,
        })
        return JSONResponse(
            content={
                'data': template.decode(),
            },
            status_code=200,
        )
    return JSONResponse(
        content={},
        status_code=400,
    )

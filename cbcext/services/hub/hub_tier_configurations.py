from fastapi.responses import JSONResponse
from starlette_context import context as g

from cbcext.models.fulfillment_models import Reseller
from cbcext.services.hub.utils import from_aps_rql_to_client_rql, serialize_for_get_tier_configs
from cbcext.services.locales import LOCALES

from connect.client import ClientError


def handle_tier_configs_from_aps(app_id):
    initiator_id = g.source_request.headers.get("aps-identity-id")
    locale = g.source_request.headers.get("aps-locale", "EN")
    locale = LOCALES.get(locale.upper(), LOCALES.get(locale.split("_")[0].upper()))
    rql_params = g.source_request.query_string
    raw_query_string, limit, offset = from_aps_rql_to_client_rql(rql_params)

    reseller_uuid = Reseller.get_oss_uid(initiator_id, app_id)
    rql = f'account.external_uid={reseller_uuid}'
    if len(raw_query_string) > 0:
        rql = rql + f'&{raw_query_string}'
    tier_configs_all_data = list(
        g.client.ns('tier').collection('configs').filter(rql)[offset:offset + limit],
    )
    content_range = g.client.response.headers['content-range']
    body = []
    for tier_config in tier_configs_all_data:
        open_request = None
        if 'open_request' in tier_config:
            # In case that checking open requests fails, let's silently skip the error
            # reason behind is that we don't want to block OSA, further more data returned
            # is just used to populate grid

            try:
                open_request = g.client.ns(
                    'tier',
                ).collection(
                    'config-requests',
                ).resource(
                    tier_config['open_request']['id'],
                ).get()
            except ClientError:
                pass
        # Draft TC and TCR must be skiped, new one to be created
        if open_request and _check_if_skip_tc_or_request(open_request, tier_config):
            continue
        output = serialize_for_get_tier_configs(tier_config, open_request)
        # localization if not inquiring due in inquiring we don't have template
        if not open_request or open_request.get('status') != 'inquiring':
            object_type, resource = _get_object_type_and_id(tier_config, open_request)
            output = _localize_tc_or_tcr(object_type, resource, locale, output)
        body.append(output)
    return JSONResponse(
        content=body,
        headers={
            'Content-Range': content_range,
        },
    )


def _localize_tc_or_tcr(object_type, resource, locale, temp_output):
    try:
        representation = g.client.ns(
            'tier',
        ).collection(
            object_type,
        ).resource(
            resource,
        ).action(
            'render',
        ).get(headers={
            'Connect-Localization': locale,
        })
        temp_output['template']['representation'] = representation.decode('utf-8')

    except (ClientError, KeyError):
        # Localization Failed
        pass

    return temp_output


def _get_object_type_and_id(tier_config, tier_config_request):
    object_type = 'configs'
    query_id = tier_config['id']
    if tier_config_request and 'activation' in tier_config_request:
        object_type = 'config-requests'
        query_id = tier_config_request['id']
    return object_type, query_id


def _check_if_skip_tc_or_request(open_request, tier_config):
    if open_request and 'status' in open_request and open_request['status'] == 'draft':
        return True
    if tier_config.get('status') == 'processing' and not open_request:
        return True
    return False

from fastapi.responses import JSONResponse

from cbcext.services.fulfillment.request_tracker_utils import update_tenant_with_request
from cbcext.services.utils import (
    get_last_request_by_tenant_id,
    get_tcr_link_by_external_id_and_product,
)


def handle_last_request_status(tenant_id, request):
    last_request = get_last_request_by_tenant_id(tenant_id)
    if not last_request:
        return {}
    else:
        output = {
            "status": last_request['status'],
            "type": last_request['type'],
        }
        external_uid = request.headers.get('Aps-Actor-Id', '')
        request_tier1 = last_request['asset']['tiers']['tier1']['external_uid']
        product_id = last_request['asset']['product']['id']
        if last_request['status'] == 'tiers_setup' and external_uid == request_tier1:
            link = get_tcr_link_by_external_id_and_product(request_tier1, product_id)
            if link:
                output['link'] = link
        elif last_request['status'] == 'inquiring' and 'params_form_url' in last_request:
            output['link'] = last_request['params_form_url']
        elif last_request['status'] == 'failed' and 'reason' in last_request:
            output['reason'] = last_request['reason']

        if last_request['type'] == 'adjustment' and last_request['status'] == 'approved':
            output['activation_key'] = last_request['activation_key']
            update_tenant_with_request(tenant_id, last_request)
        return JSONResponse(content=output)

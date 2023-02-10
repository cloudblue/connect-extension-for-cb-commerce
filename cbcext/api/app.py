import uuid

from connect.eaas.core.decorators import guest
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from starlette_context import context as g

from cbcext.models.fulfillment_models import TierConfigRequest
from cbcext.services.client.apsconnectclient.response import PublicApiError
from cbcext.services.fulfillment import ValidateDraftRequest
from cbcext.services.fulfillment.request_tracker_utils import get_product_parameters
from cbcext.services.hub.services import fetch_hub_uuid_from_oa
from cbcext.services.tier_configurations import (
    get_last_requests_by_type,
    get_tier_requests,
    TierConfigurationRequest,
)
from cbcext.services.utils import get_action_link, get_tier_config_by_id
from cbcext.utils.dependencies import convert_request
from cbcext.utils.generic import property_parser
from cbcext.utils.security import authentication_required

app_auth_router = APIRouter(
    dependencies=[Depends(authentication_required)],
)


@guest()
@app_auth_router.post('/app')
def create_app_instance(aps: dict):
    return JSONResponse(
        content={
            "aps": {"type": aps['type'], "id": aps['id']},
            "appId": str(uuid.uuid4()),
            "hubId": fetch_hub_uuid_from_oa(aps['id']),
        },
        status_code=201,
    )


@guest()
@app_auth_router.delete('/app/{app_id}')
def delete_app_instance():
    return JSONResponse(
        content={},
        status_code=204,
    )


@guest()
@app_auth_router.put('/app/{app_id}')
def update_app_instance(app_id, body: dict):
    body['hubId'] = fetch_hub_uuid_from_oa(app_id=app_id)
    return JSONResponse(
        content=body,
        status_code=200,
    )


@guest()
@app_auth_router.get('/app/{app_id}/getInitWizardConfig')
def get_init_wizard_config(app_id):
    return JSONResponse(
        content={},
        status_code=200,
    )


@guest()
@app_auth_router.get('/app/{app_id}/testConnection')
def test_connection(app_id):
    return JSONResponse(
        content={},
        status_code=200,
    )


@guest()
@app_auth_router.get('/app/{app_id}/validateInitWizardData')
def get_validate_init_wizard(app_id):
    return JSONResponse(
        content={},
        status_code=200,
    )


@guest()
@app_auth_router.post('/app/{app_id}/ItemProfileNew')
def post_new_item_profile(app_id):
    return JSONResponse(
        content={},
        status_code=200,
    )


@guest()
@app_auth_router.post('/app/{app_id}/tenants')
def post_new_tenant(app_id):
    return JSONResponse(
        content={},
        status_code=200,
    )


@guest()
@app_auth_router.delete('/app/{app_id}/tenants/{tenant_id}')
def delete_tenant(app_id, tenant_id):
    return JSONResponse(
        content={},
        status_code=204,
    )


@guest()
@app_auth_router.post('/app/{app_id}/upgrade')
def upgrade_application(app_id):
    return JSONResponse(
        content={},
        status_code=200,
    )


@guest()
@app_auth_router.get('/app/{app_id}/tier/config')
def get_tier_config(
    app_id,
):
    try:
        tier_requests = get_tier_requests(app_id=app_id)
        tier_requests = get_last_requests_by_type(tier_requests)
        tier_config = [TierConfigRequest(t_req).serialize for t_req in tier_requests]

        return JSONResponse(
            content=tier_config,
            status_code=200,
        )
    except PublicApiError as error:
        return JSONResponse(
            content=error.dict,
            status_code=error.status_code,
        )


@guest()
@app_auth_router.post('/app/{app_id}/tier/config')
def create_tier_config(
    app_id,
    request: Request = Depends(convert_request),
):
    try:
        data_format = request.json
        parse = property_parser(data_format)
        parse("configuration.id", required=True)
    except Exception:
        return JSONResponse(status_code=400, content={})
    tier_request = g.client.ns('tier').collection('config-requests').create(payload=request.json)
    tier_config = TierConfigRequest(tier_request).serialize

    return JSONResponse(
        content=tier_config,
        status_code=200,
    ) if tier_config else {}


@guest()
@app_auth_router.post('/app/{app_id}/tier/action')
def action_on_tier_config(
    app_id,
    request: Request = Depends(convert_request),
):
    data = request.json
    required_field = ("tier_config_id", "action_id")
    if not all(data.get(key) for key in required_field):
        return JSONResponse(status_code=400, content="required fields is empty in request data")
    tier_config_id = data.get('tier_config_id')
    requested_action = data.get('action_id')
    try:
        tier_config = get_tier_config_by_id(tier_config_id)
        link = get_action_link(
            product_id=tier_config['product']['id'],
            action=requested_action,
            scope='tier' + str(tier_config['tier_level']),
            identifier=tier_config_id,
        )
        return JSONResponse(
            content={
                'url': link['link'],
            },
            status_code=200,
        )
    except PublicApiError:
        pass
    return JSONResponse(
        content={
            "error": "Is not possible to process your request, try again later",
        },
        status_code=400,
    )


@guest()
@app_auth_router.post('/app/{app_id}/tier/config-requests')
def create_tier_config_request(
    app_id,
    request: Request = Depends(convert_request),
):
    input_data = request.json
    required_field = (
        "type",
        "configuration",
        "params",
    )
    if not all(input_data.get(key) for key in required_field):
        return JSONResponse(status_code=400, content="required fields missing")
    tier_config = TierConfigurationRequest()
    if not input_data['id']:
        return tier_config.create_request(input_data, app_id)
    return tier_config.validate_draft(input_data)


@guest()
@app_auth_router.post('/app/{app_id}/validate')
def validate_draft_request_app(
    app_id,
    request: Request = Depends(convert_request),
):
    if 'X-OSA-End-Customer' in request.headers:
        customer = request.headers.get('X-OSA-End-Customer')
    else:
        customer = request.headers.get('Aps-Account-Hierarchy', None)
        if customer is not None:
            customer = customer.split(",")
            customer = customer[-1]
    return ValidateDraftRequest(
        app_id=app_id,
        data=request.json,
        customer=customer,
    ).validate()


@guest()
@app_auth_router.get('/app/{app_id}/parameters')
def get_product_paramters_via_app(
    app_id,
):
    activation, fulfillment, tier = get_product_parameters(g.product_id)

    return JSONResponse(
        content={
            "activationParameters": activation,
            "fulfillmentParameters": fulfillment,
            "tier1Parameters": tier,
        },
        status_code=200,
    )

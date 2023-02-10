from connect.eaas.core.decorators import guest
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from cbcext.services.asset_actions import handle_actions
from cbcext.services.client.apsconnectclient.response import MissingAssetError
from cbcext.services.exceptions import InvalidPhoneException
from cbcext.services.fulfillment import (
    BillingRequest,
    CancelRequest,
    ChangeRequest,
    PurchaseRequest,
    ResumeRequest,
    SuspendRequest,
    ValidateDraftRequest,
)
from cbcext.services.fulfillment.request_tracker import RequestTracker
from cbcext.services.fulfillment.request_tracker_scheduled_actions import ScheduledChangesTracker
from cbcext.services.fulfillment.simple_tracker import SimpleRequestTracker
from cbcext.services.last_request_status import handle_last_request_status
from cbcext.services.locales import LOCALES
from cbcext.services.usage import build_usage
from cbcext.services.utils import not_supported_schedule, template_by_tenant
from cbcext.utils.dependencies import convert_request
from cbcext.utils.security import authentication_required

tenant_auth_router = APIRouter(
    dependencies=[Depends(authentication_required)],
)


scheduled_header = 'APS-Scheduled-On-Date'
phase_header = 'aps-request-phase'


@guest()
@tenant_auth_router.get('/tenant')
def get_tenant():
    return JSONResponse(
        content={"message": "Listing tenants is not allowed"},
        status_code=405,
    )


@guest()
@tenant_auth_router.post('/tenant')
def post_tenant(
    request: Request = Depends(convert_request),
):
    # Scheduled actions not supported by CBC yet, even that supported in connect
    # better to avoid such case till we test properly end to end)
    if request.headers.get(scheduled_header):
        return not_supported_schedule()
    phase = request.headers.get(phase_header, "sync")
    if phase == "sync":
        try:
            return PurchaseRequest(tenant_data=request.json).create
        except InvalidPhoneException as e:
            return JSONResponse(
                content={"message": str(e)},
                status_code=409,
            )
    return RequestTracker(tenant_data=request.json).track("purchase")


@guest()
@tenant_auth_router.get('/tenant/{tenant_id}')
def get_tenant_usage(tenant_id):
    return build_usage(tenant_id)


@guest()
@tenant_auth_router.put('/tenant/{tenant_id}')
def update_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    phase = request.headers.get(phase_header, "sync")
    planned_date = request.headers.get(scheduled_header, None)
    if phase == "sync":
        change_request = ChangeRequest(
            tenant_data=request.json,
            planned_date=planned_date,
        )
        # Let's check that package supports scheduled changes, otherwise let's refuse since
        # tracking on events coming from CBC will be impossible due no relation between orders
        # and requests

        if planned_date and change_request.tenant.legacy_planned_date_not_supported:
            return JSONResponse(
                content={
                    "error": "NotSupported",
                    "message": "Scheduled actions are not supported by installed product, "
                               "please contact support to upgrade it",
                },
                status_code=400,
            )
        else:
            return change_request.create

    return RequestTracker(
        tenant_data=request.json,
        planned_date=planned_date,
    ).track("change")


@guest()
@tenant_auth_router.delete('/tenant/{tenant_id}')
def delete_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    if request.headers.get(scheduled_header):
        return not_supported_schedule()

    phase = request.headers.get(phase_header, "sync")
    if phase == "sync":
        try:
            return CancelRequest(tenant_id=tenant_id).create
        except MissingAssetError:
            return JSONResponse(
                content={},
                status_code=204,
            )
    return SimpleRequestTracker(tenant_id=tenant_id).track(
        operation="cancel",
    )


@guest()
@tenant_auth_router.put('/tenant/{tenant_id}/disable')
def suspend_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    if request.headers.get(scheduled_header):
        return not_supported_schedule()

    phase = request.headers.get(phase_header, "sync")
    if phase == "sync":
        try:
            return SuspendRequest(tenant_id=tenant_id).create
        except MissingAssetError:
            return JSONResponse(content={}, status_code=204)
    return SimpleRequestTracker(tenant_id=tenant_id).track(
        operation="suspend",
    )


@guest()
@tenant_auth_router.put('/tenant/{tenant_id}/enable')
def enable_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    if request.headers.get(scheduled_header):
        return not_supported_schedule()

    phase = request.headers.get(phase_header, "sync")
    if phase == "sync":
        try:
            return ResumeRequest(tenant_id=tenant_id).create
        except MissingAssetError:
            return JSONResponse(content={}, status_code=204)
    return SimpleRequestTracker(tenant_id=tenant_id).track(
        operation="resume",
    )


@guest()
@tenant_auth_router.post('/tenant/{tenant_id}/billing')
def bill_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    return BillingRequest(
        tenant_id=tenant_id,
        data=request.json,
    ).create


@guest()
@tenant_auth_router.post('/tenant/{tenant_id}/renew')
def renew_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    return BillingRequest(
        tenant_id=tenant_id,
        data=request.json,
    ).create


@guest()
@tenant_auth_router.post('/tenant/{tenant_id}/action/{action_id}')
def execute_action_on_tenant(
    tenant_id,
    action_id,
):
    return handle_actions(tenant_id=tenant_id, action_id=action_id)


@guest()
@tenant_auth_router.get('/tenant/{tenant_id}/lastRequestStatus')
def get_tenant_last_request_status(
    tenant_id,
    request: Request = Depends(convert_request),
):
    return handle_last_request_status(tenant_id=tenant_id, request=request)


@guest()
@tenant_auth_router.post('/tenant/{tenant_id}/migrationPreCheck')
def migration_pre_check_tenant(
    tenant_id,
):
    # This is dummy operation that allows OA to move assets between accounts
    # Had been agreed that we will support it even that we will change NOTHING
    # on our side. We may expect business issues if operator moves between MKP
    # but has been decided that when that happens we will sit down and talk
    return JSONResponse(
        content={
            "canMigrate": True,
        },
        status_code=200,
    )


@guest()
@tenant_auth_router.post('/tenant/{tenant_id}/account')
def account_relink(
    tenant_id,
):
    # This is dummy operation that allows OA to move assets between accounts
    # Please note that maybe day of tomorrow we will use this to know that has
    # been executed the migration
    return JSONResponse(content={}, status_code=204)


@guest()
@tenant_auth_router.post('/tenant/{tenant_id}/validate')
def validate_change_operation_existing_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    customer = request.headers.get('X-OSA-End-Customer', None)
    return ValidateDraftRequest(
        tenant_id=tenant_id,
        data=request.json,
        customer=customer,
    ).validate()


@guest()
@tenant_auth_router.post('/tenant/{tenant_id}/onActivateScheduledChanges')
def activate_scheduled_changes_on_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    planned_date = request.headers.get(scheduled_header, None)
    return ScheduledChangesTracker(
        tenant_id=tenant_id,
        planned_date=planned_date,
        operation='activate',
    ).track()


@guest()
@tenant_auth_router.post('/tenant/{tenant_id}/onCancelScheduledChanges')
def cancel_scheduled_changes_on_tenant(
    tenant_id,
    request: Request = Depends(convert_request),
):
    planned_date = request.headers.get(scheduled_header, None)
    return ScheduledChangesTracker(
        tenant_id=tenant_id,
        planned_date=planned_date,
        operation="cancel",
    ).track()


@guest()
@tenant_auth_router.get('/tenant/{tenant_id}/render')
def render_localized_template(
    tenant_id,
    locale: str | None = None,
):
    if locale:
        locale = LOCALES.get(locale.upper(), LOCALES.get(locale.split("_")[0].upper(), 'EN'))
    return template_by_tenant(tenant_id, locale)

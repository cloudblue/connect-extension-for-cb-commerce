from random import randrange

from fastapi.responses import JSONResponse

from cbcext.models.fulfillment_models import Tenant
from cbcext.services.client.oaclient import OA, OACommunicationException

from starlette_context import context as g
from connect.client import ClientError


APS_RETRY_TIMEOUT = 60
UTC_OFFSET = '+00:00'


def randomize_aps_retry_timeout():
    # This simple function is used to randomize the retries on CBC side
    # goal is to ensure that task manager don't ends up with a lot of tasks to be executed at same
    # second
    return str(APS_RETRY_TIMEOUT + randrange(APS_RETRY_TIMEOUT))


def aps_retry_header_obtain_request_error(message=None):
    if not message:
        message = "Waiting vendor to process request"
    return {
        "aps-retry-timeout": randomize_aps_retry_timeout(),
        "aps-info": message,
    }


def aps_no_retry_header():
    return {
        'aps-transient-error': False,
    }


def aps_retry_header(
        asset_id,
        request_id,
        vendor_name=None,
        vendor_id=None,
        request_status=None,
        scheduled_date=None,
):
    if vendor_id and vendor_name:
        vendor_string = f"{vendor_name} ({vendor_id}) "
    else:
        vendor_string = ""
    if request_status and request_status == 'tiers_setup':
        message = (f"Waiting vendor {vendor_string}to complete related tier requests "
                   f"for request {request_id} on asset {asset_id}")
    else:
        message = (f"Waiting vendor {vendor_string}to complete request "
                   f"{request_id} on asset {asset_id}")

    if scheduled_date and request_status == "scheduled":
        scheduled_date = scheduled_date.replace('T', ' at ')
        scheduled_date = scheduled_date.replace(UTC_OFFSET, ' UTC')
        message += f'. Vendor has scheduled the request to be processed on {scheduled_date}'

    if scheduled_date and request_status == "revoking":
        message += ('. Request has been requested to be revoked by provider '
                    'but vendor did not process it yet.')
    return {
        "aps-retry-timeout": randomize_aps_retry_timeout(),
        "aps-info": message,
    }


def aps_inquire_header(
        asset_id,
        request_id,
        tech_contact,
        email,
        form_url,
        vendor_name=None,
        vendor_id=None,
):
    if vendor_id and vendor_name:
        vendor_string = f"{vendor_name} ({vendor_id}) "
    else:
        vendor_string = ""
    message = (f"Vendor {vendor_string}has set request {request_id} for asset {asset_id} to "
               f"inquire. Technical Contact {tech_contact} has been notified at email {email} "
               f"to populate form {form_url}")
    return {
        "aps-retry-timeout": randomize_aps_retry_timeout(),
        "aps-info": message,
    }


def aps_approved_header(asset_id, request_id):
    message = f"Vendor has approved request {request_id} for asset {asset_id}"
    return {
        "aps-info": message,
    }


def clear_inquire_properties(answer_data=None):
    if not answer_data:
        answer_data = {}

    answer_data['activationKey'] = ""
    answer_data['paramsFormUrl'] = ""
    return answer_data


def get_request_tech_contact(request: dict):
    contact_info = request['asset']['tiers']['customer']['contact_info']['contact']
    tech_contact = contact_info['first_name'] + " " + contact_info['last_name']
    email = contact_info['email']

    return tech_contact, email


def populate_tenant_common_properties(tenant: Tenant, request: dict, answer_data=None):
    if not answer_data:
        answer_data = {}
    if not tenant.legacy_asset_id:
        answer_data['assetId'] = request['asset']['id']
    if not tenant.legacy_marketplace_id and request['asset']['marketplace']['id']:
        answer_data["marketPlaceId"] = request['asset']['marketplace']['id']
    return answer_data


def populate_tenant_parameters(tenant: Tenant, request: dict, answer_data=None):

    if not answer_data:
        answer_data = {}

    vendor_sub_id, activation_params, fulfillment_params = extract_parameters(request)

    if not tenant.legacy_vendor_subscription_id and vendor_sub_id is not None:
        answer_data["vendorSubscriptionId"] = vendor_sub_id[:4000]
    if not tenant.legacy_external_identifiers:
        answer_data["fulfillmentParameters"] = fulfillment_params
        answer_data["activationParameters"] = activation_params
    return answer_data


def populate_tenant_activation_date(tenant: Tenant, request: dict, answer_data=None):
    if not answer_data:
        answer_data = {}
    if not tenant.legacy_sync_activation_date:
        if 'effective_date' in request:
            answer_data['activationDate'] = request['effective_date'].replace(UTC_OFFSET, 'Z')
        else:
            answer_data['activationDate'] = request['updated'].replace(UTC_OFFSET, 'Z')
    return answer_data


def is_not_shared(param):
    if 'shared' in param['constraints'] and param['constraints']['shared'] == 'none':
        return True
    return False


def is_valid(param_def, phase):
    skip_param = ['object', 'password']
    if param_def and param_def[0]['phase'] == phase and param_def[0]['type'] not in skip_param:
        return True
    return False


def extract_parameters(request):
    vendor_subscription_id = ""
    activation_parameters = []
    fulfillment_parameters = []
    activation, fulfillment, tier = get_product_parameters(
        request['asset']['product']['id'],
    )
    for parameter in request["asset"]["params"]:
        ordering_definition = get_parameter_definition(parameter['id'], activation)
        param_definition = get_parameter_definition(
            parameter['id'],
            fulfillment,
        )
        if parameter.get("reconciliation"):
            vendor_subscription_id = parameter["value"]
        # LITE-14888: in case of vendor marking parameter as not shared with provider
        if is_valid(param_definition, "fulfillment"):
            if is_not_shared(param_definition[0]):
                continue
            fulfilled_parameter = get_parameter_object_for_oa(parameter)
            fulfillment_parameters.append(fulfilled_parameter)
        if is_valid(ordering_definition, "ordering"):
            ordered_parameter = get_parameter_object_for_oa(parameter)
            activation_parameters.append(ordered_parameter)

    return vendor_subscription_id, activation_parameters, fulfillment_parameters


def get_product_parameters(product_id):
    """
    Returns tuple of activation, fulfillment and tier parameters
    """
    try:
        rql_filter = (
            'in(phase,(ordering,fulfillment))'
            '&in(scope,(asset,tier1))'
        )
        product_parameters = g.client.products[product_id].collection('parameters').filter(
            rql_filter,
        ).order_by('position')
        return serialize_params(product_parameters)
    except ClientError:
        return [], [], []


def serialize_params(params):
    """
    Serializes the parameters based on External Identifiers format
    :param params:
    :return:
    """
    activation_parameters = []
    fulfillment_parameters = []
    tier_activation_parameters = []
    for param in params:
        param['id'] = param['name']
        param.pop('name', None)
        param.pop('events', None)
        if param['scope'] == 'asset' and param['phase'] == 'ordering':
            activation_parameters.append(param)
        elif param['scope'] == 'asset' and param['phase'] == 'fulfillment':
            fulfillment_parameters.append(param)
        elif param['scope'] == 'tier1' and param['phase'] == 'ordering':
            tier_activation_parameters.append(param)

    return activation_parameters, fulfillment_parameters, tier_activation_parameters


def get_parameter_definition(parameter_id, parameter_list):
    return list(filter(lambda x: x['id'] == parameter_id, parameter_list))


def get_parameter_object_for_oa(parameter):
    parameter_object = {
        "key": parameter["id"],
        "value": parameter.get("value", ""),
    }
    if parameter.get("structured_value"):
        parameter_object['structured_value'] = parameter.get("structured_value")
    return parameter_object


def handle_no_request(tenant_aps_id):
    return JSONResponse(
        content={
            "status_code": 409,
            "error": "No request for APS tenant with id {resource}".format(resource=tenant_aps_id),
            "message": "We did not found an asset that matches the APS id {resource}".format(
                resource=tenant_aps_id,
            ),
        },
        status_code=409,
        headers=aps_no_retry_header(),
    )


def handle_failed(request):

    error_message = "Vendor has failed request {id} with following reason: {reason}".format(
        id=request['id'],
        reason=request['reason'],
    )
    if request['status'] != 'revoked':
        message = (f"\n\nThe {request['type']} request {request['id']} has not been completed.\n"
                   "The vendor has rejected the request with following reason:\n\n"
                   ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n"
                   f"Message from the Vendor: {request['reason']}"
                   "\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n")
    else:
        message = (f"\n\nThe {request['type']} request {request['id']} has not been completed.\n"
                   "The vendor has accepted revoking the request done by provider with following "
                   "reason:\n\n "
                   ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n"
                   f"Revokation reason: {request['reason']}"
                   "\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n")
    if request['type'] == "purchase":
        message = message + (
            "Important note: submitting again this order will fail due previous reason\n"
            "please create a new purchase request to correct it or contact support"
        )
    return JSONResponse(
        content={
            "status_code": 409,
            "error": error_message,
            "message": message,
        },
        status_code=409,
        headers=aps_no_retry_header(),
    )


def handle_approved(request, answer_data=None, tenant_draft_request_id=None):
    answer_data = clear_inquire_properties(answer_data)
    if 'activation_key' in request:
        answer_data['activationKey'] = request['activation_key']
    else:
        if 'template' in request:
            # Handling possibility of suspend request NOT approved workarround
            answer_data['activationKey'] = request['template']['message']
    # In case that purchase was done using a draft request, let's remove it from OA
    if tenant_draft_request_id:
        answer_data['draftRequestId'] = ""
    # Clear Original order parameters
    answer_data['activationParams'] = []
    return JSONResponse(
        content=answer_data,
        status_code=200,
        headers=aps_approved_header(
            request_id=request['id'],
            asset_id=request['asset']['id'],
        ),
    )


def handle_pending(request, operation, answer_data=None):
    answer_data = answer_data or {}
    if operation == "purchase":
        answer_data = clear_inquire_properties(answer_data)
    else:
        # Only in case that for some reason change/suspend/resume/cancel got inquiring
        answer_data['paramsFormUrl'] = ""
    return JSONResponse(
        content=answer_data,
        status_code=202,
        headers=aps_retry_header(
            asset_id=request['asset']['id'],
            request_id=request['id'],
            vendor_id=request['asset']['connection']['vendor']['id'] or None,
            vendor_name=request['asset']['connection']['vendor']['name'] or None,
            request_status=request['status'] or None,
            scheduled_date=request.get('planned_date', None),
        ),
    )


def revoke_scheduled_request(request_id, message):
    return g.client.requests[request_id].action('revoke').post(
        payload={
            "reason": message,
        },
    )


def update_tenant_with_request(tenant_id, request):
    try:
        tenant = OA.get_resource(
            resource_id=tenant_id,
            impersonate_as=None,
            transaction=False,
            retry_num=1,
        )
        if tenant:  # pragma no branch
            tenant['activationKey'] = request.get('activation_key', '')
            vendor_sub_id, activation_params, fulfillment_params = extract_parameters(
                request,
            )
            tenant["vendorSubscriptionId"] = vendor_sub_id[:4000]
            tenant["fulfillmentParameters"] = fulfillment_params
            tenant["activationParameters"] = activation_params
            # Activation date is optional, and to speed up we check if property is there
            # instead of loading schema, since in case of presence, means is supported
            # We will NOT update in case that request is adjustment, yes for rest just in case
            # If we don't update such date, CBC RDE will calculate effective dates based on
            # previous requests (f.e we are processing a suspend operation here and last one was
            # a change done
            # a year ago...that will cause a disaster)
            if request['type'] != 'adjustment' and 'activationDate' in tenant:
                tenant['activationDate'] = get_effective_date(request)
            OA.send_request(
                method='PUT',
                transaction=False,
                impersonate_as=None,
                retry_num=1,
                path=f'aps/2/application/tenants/{tenant_id}',
                body=tenant,
            )
            # let's return tenant for answer response of operations like suspend,
            # this is good for logging purposes even that will not be used by cbc
            # in most cases. In call of TenantLastRequestStatus, please follow the logic there where
            # is updated in background but processed by ui using navigation

            return tenant

    except OACommunicationException:
        # Is not business critical to update cache on CBC, next time may work, silently pass
        pass

    return {}


def get_effective_date(request):
    if 'effective_date' in request:
        return request['effective_date'].replace(
            UTC_OFFSET, 'Z',
        )
    else:
        return request['updated'].replace(
            UTC_OFFSET, 'Z',
        )

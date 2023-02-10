from fastapi.responses import JSONResponse

from cbcext.models.fulfillment_models import Tenant
from cbcext.services.client.apsconnectclient.response import PublicApiError
from cbcext.services.client.oaclient import OA, OACommunicationException
from cbcext.services.fulfillment.request_tracker_utils import (
    aps_no_retry_header,
    aps_retry_header_obtain_request_error,
    extract_parameters,
    get_effective_date,
    handle_failed,
    revoke_scheduled_request,
)
from cbcext.services.utils import get_request_by_id


class ScheduledChangesTracker:

    def __init__(self, tenant_id, planned_date, operation):
        self.tenant_id = tenant_id
        self.planned_date = planned_date
        self.operation = operation

    def track(self):
        try:
            tenant = Tenant.from_aps_id(self.tenant_id)
            if not tenant.last_planned_request:
                # Smells somebody modified CBC DB or somehow this event is unordered, better to
                # say that all is OK
                return _accept()
            scheduled_request = get_request_by_id(tenant.last_planned_request)
        except OACommunicationException:
            # something happened when obtaining the info from APS bus
            # Most probable a temp error, let's retry later
            message = "Error when obtaining tenant object from APS bus"
            return _retry(message)
        except PublicApiError as error:
            if error.status_code == 404:
                # something strange, probably cbc db changes
                # since we don't find the request, we don't know and better to accept
                return _accept()
            else:
                # something wrong with connect infra most probable, let's reschedule
                return _retry()
        request_status = scheduled_request.get('status')

        handlers = {
            ('failed', 'cancel'): _accept,
            ('failed', 'activate'): _fail,
            ('scheduled', 'cancel'): _revoke,
            ('revoked', 'cancel'): _accept,
            ('approved', 'activate'): _accept,
            ('approved', 'cancel'): _miss_match,
        }

        handler = handlers.get((request_status, self.operation), None)

        if handler and request_status == 'approved':
            self._update_tenant_with_request(self.tenant_id, scheduled_request, self.operation)
        return handler(scheduled_request) if handler else _retry()

    def _update_tenant_with_request(self, tenant_id, last_request, operation):
        try:
            tenant = OA.get_resource(
                resource_id=tenant_id,
                impersonate_as=None,
                transaction=False,
                retry_num=1,
            )
            if tenant:
                tenant['activationKey'] = last_request.get('activation_key', '')
                vendor_sub_id, activation_params, fulfillment_params = extract_parameters(
                    last_request,
                )
                tenant["vendorSubscriptionId"] = vendor_sub_id[:4000]
                tenant["fulfillmentParameters"] = fulfillment_params
                tenant["activationParameters"] = activation_params
                # Careful, in the use case that is cancel, if we will clear last_planned_date
                # brute force will cause a success to CBC since we lost track...this must happen
                # ONLY in the case of activation
                if operation == 'activate':
                    tenant["last_planned_request"] = ""
                    tenant['activationDate'] = get_effective_date(last_request)
                OA.send_request(
                    method='PUT',
                    transaction=False,
                    impersonate_as=None,
                    retry_num=1,
                    path=f'aps/2/application/tenants/{tenant_id}',
                    body=tenant,
                )
        except OACommunicationException:
            # Is not business critical to update cache on CBC, next time may work, silently pass
            pass


def _miss_match(scheduled_request):
    vendor = scheduled_request['asset']['connection']['vendor']['name']
    message = (
        f"Cancellation of request is not possible becouse vendor {vendor} has already processed "
        f"request {scheduled_request['id']}, contact support in case of need further explanation"
    )
    return JSONResponse(
        content={
            "status_code": 409,
            "error": 'CONFLICT',
            "message": message,
        },
        status_code=409,
        headers=aps_no_retry_header(),
    )


def _retry(message=None):
    return JSONResponse(
        content={},
        status_code=202,
        headers=aps_retry_header_obtain_request_error(message),
    )


def _accept():
    return JSONResponse(content={}, status_code=200)


def _revoke(scheduled_request):
    try:
        provider = scheduled_request['asset']['connection']['provider']['name']
        message = f"Distributor {provider} has requested to revoke this request"
        revoke_scheduled_request(scheduled_request.get('id'), message)
    except PublicApiError:
        # Does not matter if was error on connect side (since was scheduling and error can
        # mean only temp error) or was successful and request moved to revoking, in such
        # case we must ask CBC to wait
        pass
    return _retry()


def _fail(scheduled_request):
    return handle_failed(scheduled_request)

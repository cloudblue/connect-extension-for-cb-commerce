from fastapi.responses import JSONResponse
from requests.exceptions import Timeout
from starlette_context import context as g

from cbcext.models.fulfillment_models import Tenant
from cbcext.services.client.apsconnectclient.response import PublicApiError
from cbcext.services.client.oaclient import OACommunicationException
from cbcext.services.fulfillment import ChangeRequest
from cbcext.services.fulfillment.request_tracker_utils import (
    aps_inquire_header,
    aps_retry_header_obtain_request_error,
    get_request_tech_contact,
    handle_approved,
    handle_failed,
    handle_no_request,
    handle_pending,
    populate_tenant_activation_date,
    populate_tenant_common_properties,
    populate_tenant_parameters,
)
from cbcext.services.utils import get_last_request_by_tenant_id


class RequestTracker:

    operation = None

    def __init__(self, tenant_data: dict, planned_date=None):
        self.tenant = Tenant(tenant_data)
        self.planned_date = planned_date

    def track(self, operation):
        self.operation = operation
        try:
            last_request = get_last_request_by_tenant_id(
                tenant_id=self.tenant.aps_id,
                operation=operation,
            )
        except (PublicApiError, Timeout):
            # In case that something wrong with public api, let's reschedule at OA
            return JSONResponse(
                content={},
                status_code=202,
                headers=aps_retry_header_obtain_request_error(),
            )

        if not last_request:
            return handle_no_request(self.tenant.aps_id)

        request_status = last_request['status']

        if request_status == "failed" or request_status == "revoked":
            return handle_failed(last_request)

        # For all other status, response must contain at least following answer data
        answer_data = populate_tenant_parameters(
            tenant=self.tenant,
            request=last_request,
        )
        answer_data = populate_tenant_common_properties(
            tenant=self.tenant,
            request=last_request,
            answer_data=answer_data,
        )

        if request_status == "approved":
            if self.operation == "purchase":
                # Let's try to subscribe to renewal events to get provider billing requests
                try:
                    self.tenant.subscribe_for_renew()
                except OACommunicationException:
                    pass
            answer_data = populate_tenant_activation_date(
                tenant=self.tenant,
                request=last_request,
                answer_data=answer_data,
            )
            if self.operation == "change":
                return self.verify_change_request(last_request, answer_data)
            return handle_approved(last_request, answer_data, self.tenant.draft_request_id)

        if request_status == "inquiring":
            return self.handle_inquiring(last_request, answer_data)

        # Handling use case of scheduled action when requested by provider
        # in case is not requested by provider, CBC will wait till vendor acts.
        # validation that APS supports it happened on sync phase
        if request_status == "scheduled" and self.planned_date:
            return self.handle_scheduled(
                request=last_request,
                answer_data=answer_data,
            )

        # Handling use case pending, tiers_setup, scheduling and revoking
        return handle_pending(
            request=last_request,
            answer_data=answer_data,
            operation=self.operation,
        )

    def handle_scheduled(self, request, answer_data):
        try:
            self.tenant.subscribe_for_delayed_actions()
        except OACommunicationException:
            # Ups something went wrong on subscription, we may expect that is OA communication
            # issue, hence better to return a 202 and retry later
            return handle_pending(
                request=request,
                answer_data=answer_data,
                operation=self.operation,
            )
        answer_data['last_planned_request'] = request['id']
        return JSONResponse(
            content=answer_data,
            status_code=200,
        )

    def handle_inquiring(self, request, answer_data):

        if self.operation == "purchase":
            answer_data['activationKey'] = request['template']['message']
            answer_data['paramsFormUrl'] = request['params_form_url']
        tech_contact, email = get_request_tech_contact(request)
        return JSONResponse(
            content=answer_data,
            status_code=202,
            headers=aps_inquire_header(
                request_id=request['id'],
                asset_id=request['asset']['id'],
                tech_contact=tech_contact,
                email=email,
                form_url=request['params_form_url'],
                vendor_id=request['asset']['connection']['vendor']['id'] or None,
                vendor_name=request['asset']['connection']['vendor']['name'] or None,
            ),
        )

    def verify_change_request(self, request, answer_data):
        # This method handles a weird behaivour of OA, where due failed tasks there is inconsistency
        # between APS resource values when using app counted service references and what was
        # ordered
        # We always had this case where was possible that resubmiting a failed change order
        # values was not matching, with this method we act as before and we resync items
        # We Cover this use case in the use case that request has been approved ONLY, it may
        # happen that order was failed exactly due wrong items, but in such case we can't detect
        # In the use case that this happens on failure, when provider resubmits, new order will be
        # created

        def _c(quantity):
            if isinstance(quantity, str) and quantity.lower() == "unlimited":
                return -1
            return int(quantity)

        try:
            aps_items_unfiltered = self.tenant.items

            # let's skip on comparison any item that has quantity 0 to avoid placing
            # change request in use case that item was removed from subscription in OA
            # for example when removing items from ST

            aps_items = list(
                filter(
                    lambda x: x['quantity'] != 0 and x['id'] not in ['COUNTRY', 'ENVIRONMENT'],
                    aps_items_unfiltered,
                ),
            )

            # and same for ones coming from last approved request. Please note that this has
            # some business implication, use case where asset is not entitled to use, aka
            # resource not present is not controled

            request_items_unfiltered = [
                {'id': v['id'], 'quantity': _c(v['quantity'])} for v in request['asset']['items']
            ]

            request_items = list(filter(lambda x: x['quantity'] != 0, request_items_unfiltered))

            items_difference = [
                x for x in aps_items + request_items if x not in aps_items or x not in request_items
            ]
            if items_difference:
                return ChangeRequest(
                    tenant_data=g.source_request.json,
                ).create

        except Exception:
            g.logger.exception("Exception while firing change request on asset sync")

        return handle_approved(request, answer_data, self.tenant.draft_request_id)

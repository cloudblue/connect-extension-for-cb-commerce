from typing import List

from starlette_context import context as g

from cbcext.models.fulfillment_models import Account
from cbcext.services.client.apsconnectclient import request_statuses, request_types
from cbcext.services.client.apsconnectclient.response import RequestResponse
from cbcext.services.fulfillment.request_tracker_utils import randomize_aps_retry_timeout

from connect.client import ClientError

MAX_RESELLER_LEVEL = 3

NOT_IMPLEMENTED_MESSAGE = "No implement method"


class BaseRequest(object):
    resource = "requests"
    statuses = request_statuses
    types = request_types

    @property
    def request_body(self) -> dict:
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def get_connection_id(self):
        product = g.product_id
        hub_uuid = self.provider.aps_id
        resp = g.client.products[product].connections.filter(
            f'eq(hub.instance.id,{hub_uuid})',
        ).first()
        return resp['id'] if resp else None

    def sanitize_local_items(self):
        return [
            {"id": key, "quantity": val}
            for key, val in self.tenant.resources.items()
            if key not in ('COUNTRY', 'ENVIRONMENT')
        ]

    @property
    def replay_header(self):
        return {
            "aps-retry-timeout": randomize_aps_retry_timeout(),
        }

    def _request_exists_response(self, public_error: ClientError):
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def _create_response_for_oa(self, response: RequestResponse):
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    @staticmethod
    def _handle_400_errors(public_error):
        items_error = "Item limits is not changed in new request."
        items_error_2 = "asset.items: Item quantities are not changed."
        items_error_3 = "asset.items: This list may not be empty."
        marketplace_misconfiguration = "Field 'marketplace.id' is required."
        no_listing = 'There is no Listing for specified Product and Marketplace.'
        # For purchase case, new error introduced in v25
        if public_error.errors and items_error_3 in public_error.errors:
            return RequestResponse(
                status_code=409,
                message="All items purchased has quantity 0, "
                        "at least one item must be purchased",
            )
        # For change requests
        if public_error.errors and (
                items_error in public_error.errors or items_error_2 in public_error.errors
        ):
            return RequestResponse(status_code=200)
        if public_error.errors and marketplace_misconfiguration in public_error.errors:
            return RequestResponse(
                status_code=409,
                message="There is a marketplace misconfiguration that prevents order "
                        "processing. Ensure that one of the involved tiers in this request "
                        "matches a marketplace configured in CloudBlue Connect.",
            )
        # We want to throw 409 in case of errors like
        # asset.tiers.tierX.contact_info.contact.last_name: This field may not be blank or null
        if public_error.errors and (
            no_listing in public_error.errors[0]
            or 'asset.tiers' in public_error.errors[0]
        ):
            return RequestResponse(
                status_code=409,
                message=str(public_error.errors),
            )
        # We raise 500 in order to see case by case what we shall do
        # Specially interesting when we do major Connect upgrades
        raise Exception(str(public_error))

    def _handle_public_error(self, public_error):
        if public_error.status_code != 409:
            return self._handle_400_errors(public_error)
        # Handling of 409, means we may have a dup.
        if not any([
                public_error.additional_info['params'].get("request_status"),
                public_error.additional_info['params'].get("asset_status")]):
            return RequestResponse(status_code=409, message=str(public_error.errors))

        return self._request_exists_response(public_error)

    def _place_request(self) -> RequestResponse:
        try:
            resp = g.client.requests.create(payload=self.request_body)
        except ClientError as public_error:
            return self._handle_public_error(public_error)

        return RequestResponse(
            status_code=202,
            params_form_url=resp.get("params_form_url"),
            template=resp.get("template"),
        )

    @property
    def create(self):
        portal_response = self._place_request()
        return self._create_response_for_oa(portal_response)

    def get_marketplace_from_request(self, request_id: str) -> str:
        if not request_id:
            return ""
        try:
            request = g.requests[request_id].get()
            if request.get('marketplace'):
                return request['marketplace']['id']
            return 'MP-00000'

        except ClientError:
            pass
        return ""


def reseller_chain(account_id: str, app_id: str, first: bool = False) -> List[Account]:
    if not first:
        return [Account.dummy()]

    chain = []

    for _ in range(MAX_RESELLER_LEVEL):
        if account_id is None:
            break
        reseller = Account.from_external_scope(account_id, app_id)
        chain.append(reseller)
        account_id = reseller.parent

    return chain

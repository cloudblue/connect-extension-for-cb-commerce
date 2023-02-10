from copy import deepcopy

from fastapi.responses import JSONResponse
from starlette_context import context as g

from cbcext.models.fulfillment_models import Provider, Subscription, Tenant
from cbcext.services.client.apsconnectclient.response import PublicApiError, RequestResponse
from cbcext.services.utils import get_asset_by_uuid, product_capability_parameters_change
from .base import BaseRequest


class ChangeRequest(BaseRequest):
    def __init__(self, tenant_data: dict, planned_date=None):
        self.tenant = Tenant(tenant_data)
        self.subscription = Subscription.dummy()
        self.provider = Provider.from_app_id(self.tenant.app_id)
        self.draft_request_id = self.tenant.draft_request_id
        self.planned_date = planned_date

    @property
    def request_body(self):
        def _get_asset_id():
            if self.tenant.asset_id:
                return self.tenant.asset_id
            else:
                return get_asset_by_uuid(self.tenant.aps_id)['id']

        data = {
            "asset": {
                "external_uid": self.tenant.aps_id,
                "external_id": self.subscription.oss_id,
                "items": self.sanitize_local_items(),
                "connection": {
                    "id": self.get_connection_id(),
                },
            },
            "type": "change",
        }
        # Due backwards compatibility we have 2 ways to get asset id to send to pub api
        # in some cases is stored in tenant (new connectors since mid 2019), in others
        # we must check in Connect API

        data['asset']['id'] = _get_asset_id()

        # In case that product supports parameters change, we pass order parameters comming from
        # CBC, we must remember that such ones are synced back from time to time

        if product_capability_parameters_change(g.product_id):
            data['asset']['params'] = self._normalize_parameters(self.tenant.activationParameters)

        # Support for planned_date (scheduled actions)
        # Somehow in sandbox CBC sends additional commas, let's remove them too.
        if self.planned_date:
            data['planned_date'] = self.planned_date.replace('Z', '+00:00').replace('"', '')
        return data

    @staticmethod
    def _normalize_parameters(params):
        parameters = []
        for item in params:
            if "key" in item:
                item["id"] = item["key"]
                del item["key"]
                parameters.append(item)
        return parameters

    def _request_exists_response(self, public_error: PublicApiError) -> RequestResponse:
        def _check_items_not_changed(error):
            expected_error = "asset.items: Item quantities are not changed."
            if error.status_code == 400 and error.errors and error.errors[0] == expected_error:
                return True
            return False

        def _check_change_not_done_asset_suspended(error):
            expected_error = "Request type change is not allowed when asset state is suspended"
            if error.errors and error.errors[0] == expected_error:
                return True
            return False

        # Return a 409 in case of failure caused by asset is suspended
        if _check_change_not_done_asset_suspended(public_error):
            error_msg = (
                "Change is not allowed when asset is in suspended state at vendor side, "
                "resume it first"
            )
            return RequestResponse(
                status_code=409,
                error="ProvisioningFailed",
                message=error_msg,
            )

        current_status = public_error.params.get('request_status')

        if current_status == self.statuses.failed or public_error.status_code == 409:
            # In the use case that error is caused by no limits change, let's approve on OA
            # Unfortunately due how OA works it may happen that on Sync of tenant, we receive a PUT
            # but for nothing changed, in such case we shall return 200 silently
            if _check_items_not_changed(public_error):
                return RequestResponse(
                    fulfillment_parameters=None,
                    activation_parameters=None,
                    params_form_url="",
                    status_code=200,
                )
            return RequestResponse(
                status_code=409, error="ProvisioningFailed",
                message=public_error.params.get("fail_message", ', '.join(public_error.errors)),
            )

        return RequestResponse(
            status_code=202,
            template=public_error.params.get("template"),
            params_form_url=public_error.params.get("params_form_url"),
            asset_id=public_error.params.get("asset_id"),
            marketplace_id=self.get_marketplace_from_request(
                public_error.params.get("id"),
            ),
        )

    def _create_response_for_oa(self, response: RequestResponse):

        status_code = 200 if response.status_code == 201 else response.status_code

        answer_data = {}
        headers = {}

        # In theory impossible case, but in case of DB modifications in CBC it may happen
        # if we receive a request to change an asset, but tenant has a request to be tracked
        # we must clear it in general and act properly based on what we have in connect
        if self.tenant.last_planned_request:
            answer_data['last_planned_request'] = ''

        if response.status_code == 202:
            headers = deepcopy(self.replay_header)
            headers["aps-info"] = "Waiting for limits change to be approved"
        elif response.status_code == 409:
            answer_data["error"] = response.error
            answer_data["message"] = response.message

        return JSONResponse(
            content=answer_data,
            status_code=status_code,
            headers=headers,
        )

    def _place_request(self) -> RequestResponse:
        if not self.draft_request_id:
            return super()._place_request()
        request = g.requests[self.draft_request_id].get()
        if request and request['status'] == 'draft':
            try:
                g.requests[self.draft_request_id].update(payload=self.request_body)
                resp = g.requests[self.draft_request_id].action('submit').post(payload={})
            except PublicApiError:
                # In the use case that for whatever reason draft conversion don't works
                # Let's place a regular change request
                return super()._place_request()

            return RequestResponse(
                status_code=202,
                params_form_url=resp.get("params_form_url"),
                template=resp.get("template"),
            )
        # This case shall never happen, but better to have controled
        # in case that draft existed before but somehow was approved and tenant keeps having it
        # place regular change request

        return super()._place_request()

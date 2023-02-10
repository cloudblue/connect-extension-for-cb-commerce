from copy import deepcopy

from fastapi.responses import JSONResponse

from cbcext.models.fulfillment_models import (
    Account,
    Provider,
    Subscription,
    Tenant,
)
from cbcext.services.client.apsconnectclient.response import RequestResponse
from cbcext.services.vat import Vat
from .base import BaseRequest, reseller_chain

from starlette_context import context as g
from connect.client import ClientError


class PurchaseRequest(BaseRequest):

    def __init__(self, tenant_data: dict):
        """
        Creates PurchaseRequest in Connect
        :param tenant_data: representation of Tenant in OA
        Allows us to control how we can extract Tiers data since in such phase we don't have it
        On tenant pobject
        """
        self.tenant = Tenant(tenant_data)
        self.account = Account.from_aps_id(self.tenant.account_id)
        vat = Vat(self.tenant.app_id)
        self.account.tax_id = vat.get_vat_code(aps_account_id=self.account.aps_id)
        self.resellers = reseller_chain(self.account.parent, self.tenant.app_id, True)
        self.provider = Provider.from_app_id(self.tenant.app_id)
        self.subscription = Subscription.from_aps_id(self.tenant.sub_id)
        self.draft_request_id = self.tenant.draft_request_id

    @staticmethod
    def _fill_account_info(account: dict) -> dict:
        contact_info = account["contact_info"]
        contact = contact_info["contact"]
        phone = contact["phone_number"]
        country_code = phone['country_code'] or ""
        country_code = country_code.replace("+", "")
        return {
            "companyName": account.get("name"),
            "addressPostal": {
                "countryName": contact_info.get("country"),
                "extendedAddress": contact_info.get("address_line2"),
                "locality": contact_info.get("city"),
                "postalCode": contact_info.get("postal_code"),
                "region": contact_info.get("state"),
                "streetAddress": contact_info.get("address_line1"),
            },

            "techContact": {
                "email": contact.get("email"),
                "givenName": contact.get("first_name"),
                "familyName": contact.get("last_name"),
                "telVoice": "#".join((country_code, phone['area_code'] or '',
                                      phone['phone_number'] or '', phone['extension'] or '')),
            },
        }

    @property
    def request_body(self) -> dict:
        request_body = {
            "asset": {
                "external_uid": self.tenant.aps_id,
                "external_id": self.subscription.oss_id,
                "params": self.tenant.params,
                "items": self.sanitize_local_items(),
                "tiers": {
                    "customer": self.account.dict,
                    "tier1": self.resellers[0].dict if len(self.resellers) > 0 else {},
                    "tier2": self.resellers[1].dict if len(self.resellers) > 1 else {},
                },
                "connection": {
                    "id": self.get_connection_id(),
                },
            },
            "type": "purchase",
        }
        return request_body

    def _request_exists_response(self, public_error: ClientError) -> RequestResponse:
        current_status = public_error.additional_info['params']['request_status']
        if current_status == self.statuses.failed:
            return RequestResponse(
                status_code=409,
                error="ProvisioningFailed",
                message=public_error.additional_info['params'].get(
                    "fail_message", ', '.join(public_error.errors),
                ),
            )
        return RequestResponse(
            status_code=202,
            template=public_error.additional_info['params'].get("template"),
            params_form_url=public_error.additional_info['params'].get("params_form_url"),
            asset_id=public_error.additional_info['params'].get("asset_id"),
            marketplace_id=self.get_marketplace_from_request(
                public_error.additional_info['params']['request_id'],
            ),
        )

    def _handle_legacy_for_oa_response(self, answer_data, response: RequestResponse):
        # Introduces data on tenant object added on new versions of Connect
        if not self.tenant.legacy_asset_id and response.asset_id:
            answer_data['assetId'] = response.asset_id[:4000]
        if not self.tenant.legacy_marketplace_id and response.marketplace_id:
            answer_data["marketPlaceId"] = response.marketplace_id[:4000]
        return answer_data

    def _create_response_for_oa(self, response: RequestResponse):
        answer_data = self.account.as_tenant_account_info() if response.status_code != 409 else {}
        headers = {}

        if response.status_code == 202:
            headers = deepcopy(self.replay_header)
            headers["aps-info"] = "Waiting for subscription to be activated"
            if response.draft_request_id == "":
                answer_data["draftRequestId"] = ""
        elif response.status_code == 409:
            answer_data["error"] = response.error
            answer_data["message"] = response.message

        # We populate inquiring template
        if response.activation_key:
            answer_data["activationKey"] = response.activation_key[:4000]
        if not self.tenant.legacy_params_form_url:
            answer_data = self.update_answer_data(response, answer_data)
        answer_data = self._handle_legacy_for_oa_response(answer_data, response)
        return JSONResponse(
            content=answer_data,
            status_code=response.status_code,
            headers=headers,
        )

    def _place_request(self) -> RequestResponse:
        if not self.draft_request_id:
            return super()._place_request()
        request = g.client.requests[self.draft_request_id].get()
        if request and request['status'] == 'draft':
            try:
                g.client.requests[self.draft_request_id].update(payload=self.request_body)
                resp = g.client.requests[self.draft_request_id].action('purchase').post(payload={})
            except ClientError as public_error:
                return self._handle_public_error(public_error)

            return RequestResponse(
                status_code=202,
                params_form_url=resp.get("params_form_url"),
                template=resp.get("template"),
            )
        # This means is UX1 purchase and customer placed twice same product in basket

        return super()._place_request()

    @staticmethod
    def update_answer_data(response, answer_data):
        answer_data["paramsFormUrl"] = (
            response.params_form_url[:4000] if response.params_form_url else ""
        )
        if response.params_form_url and response.template:
            answer_data["activationKey"] = response.template["message"][:4000]

        return answer_data

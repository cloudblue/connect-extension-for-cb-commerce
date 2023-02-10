from copy import deepcopy

from fastapi.responses import JSONResponse

from cbcext.services.client.apsconnectclient import ASSET_STATUS_IGNORE_REQUEST_TYPES, request_types
from cbcext.services.client.apsconnectclient.response import (
    MissingAssetError,
    PublicApiError,
    RequestResponse,
)
from cbcext.services.utils import get_asset_by_uuid
from .base import BaseRequest

from starlette_context import context as g


class SimpleRequest(BaseRequest):

    def __init__(self, tenant_id: str, kind: str):
        self.kind = kind
        asset = get_asset_by_uuid(tenant_id)
        if asset is None:
            raise MissingAssetError("No asset found by tenant_id")
        self.asset_id = asset['id']

    @property
    def request_body(self):
        data = {
            "type": self.kind,
            "asset": {
                "id": self.asset_id,
            },
        }

        return data

    def _request_exists_response(self, public_error):
        status = public_error.params.get("request_status")
        asset_status = public_error.params.get("asset_status")
        if status == self.statuses.approved:
            return RequestResponse(status_code=201)
        elif self.kind in ASSET_STATUS_IGNORE_REQUEST_TYPES.get(asset_status, []):
            return RequestResponse(status_code=201)
        elif status == self.statuses.failed:
            return RequestResponse(
                status_code=409,
                message=public_error.params.get('fail_message'),
            )
        else:
            return RequestResponse(status_code=202)

    def _create_response_for_oa(self, response: RequestResponse):
        answer_data, headers = {}, {}
        # Obtaining a response code 200 is impossible unless billing request
        if response.status_code == 409:
            answer_data["message"] = response.message
            status_code = 409
        elif response.status_code == 201:
            status_code = 200 if self.kind in [request_types.suspend, request_types.resume] else 204
        else:
            status_code = 202
            headers = deepcopy(self.replay_header)
            headers["aps-info"] = f"Waiting for subscription {self.kind}"

        return JSONResponse(content=answer_data, status_code=status_code, headers=headers)

    def _place_request(self) -> RequestResponse:
        try:
            resp = g.client.requests.create(payload=self.request_body)
        except PublicApiError as public_error:
            return self._handle_public_error(public_error)

        # In the use case of suspend and resume, on sync phase we may get request failed due
        # product does not support administrative hold capability
        # CBC does not care about it, due it, let's return ok to speedup, in other cases, let's
        # track request status in async way

        if (self.kind == "suspend" or self.kind == "resume") and resp.get('status') == 'failed':

            return RequestResponse(
                status_code=201,
                params_form_url=resp.get("params_form_url"),
                template=resp.get("template"),
            )

        return RequestResponse(
            status_code=202,
            params_form_url=resp.get("params_form_url"),
            template=resp.get("template"),
        )

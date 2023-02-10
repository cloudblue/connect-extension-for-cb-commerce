from typing import Optional

from fastapi.responses import JSONResponse
from starlette_context import context as g

from cbcext.models.fulfillment_models import Account, DraftRequest
from cbcext.services.client.apsconnectclient import request_statuses, request_types
from cbcext.services.client.oaclient import OA
from cbcext.utils.generic import property_parser
from .base import BaseRequest, reseller_chain

from connect.client import ClientError


class ValidateDraftRequest(BaseRequest):
    def __init__(
            self,
            data: dict,
            customer: str,
            app_id: Optional[str] = None,
            tenant_id: Optional[str] = None,
    ):
        self.draft = DraftRequest(data, app_id)
        self.draft_request_id = self.draft.draft_request_id
        if not tenant_id:
            self.draft_customer, self.draft_tiers = self._get_tiers(customer, app_id)
        self.draft_items = self._extract_items(data)
        self.tenant = tenant_id

    @property
    def request_body(self) -> dict:
        body = {
            "type": request_types.new if not self.tenant else request_types.change,
            "status": request_statuses.draft,
            "asset": {
                "params": self.draft.params,
            },
        }
        if self.draft_items:
            body['asset']['items'] = self.draft_items
        if not self.tenant:
            body['asset']['product'] = {
                "id": g.product_id,
            }
            body['asset']['connection'] = {
                "id": self.get_connection_id(),
            }
            if self.draft_customer:
                body['asset']['tiers'] = {}
                body['asset']['tiers']['customer'] = self.draft_customer.dict
                if len(self.draft_tiers) > 0:
                    body['asset']['tiers']['tier1'] = self.draft_tiers[0].dict
                if len(self.draft_tiers) > 1:
                    body['asset']['tiers']['tier2'] = self.draft_tiers[1].dict
        else:
            if not self.draft.assetId:
                return self.validation_not_possible()
            body['asset']['id'] = self.draft.assetId
        return body

    def get_connection_id(self):
        # Only used when validating purchase requests, not on change

        product = g.product_id
        hub_uuid = OA.get_resource(
            resource_id=self.draft.app_id,
            impersonate_as=self.draft.app_id,
        )['hubId']
        resp = g.client.products[product].connections.filter(
            f'eq(hub.instance.id,{hub_uuid})',
        ).first()
        if not resp:
            raise Exception("Connection not found")
        return resp['id']

    def _extract_items(self, data):
        """
        Function used only by CCPv2 right now, it converts items from OA to Connect world
        Items is object like:
        {
            "OA_ID": {
                "limit": int,
                "property": Connect item local_id
            }
        }
        Output for draft request follows item
        """

        parse = property_parser(data, desc="draft")
        oa_items = parse("items", default=None)

        # Workaround to extract Product id, this must be changed when we remove product auth
        # and we move to regular SU/Extension one
        # at this moment on time has been done that way as is the cheaper way

        aps = parse("aps", default={})
        product = None
        if 'type' in aps:
            product = aps['type'].replace("http://aps.odin.com/app/", "")
            product = product.split("/")

        items = []
        if oa_items is not None and product is not None:
            oa_items = {k: v for k, v in oa_items.items() if 'property' in v}
            if not len(oa_items):
                return items

            limits = {v['property']: v['value'] for k, v in oa_items.items()}
            local_ids = [v['property'] for k, v in oa_items.items()]

            product_items = self._get_product_items(product[0], local_ids)
            for product_item in product_items:
                items.append({
                    "global_id": product_item['id'],
                    "quantity": limits[product_item['local_id']],
                })

        return items

    def _get_product_items(self, connect_product, aps_local_ids):
        offset = 0
        connect_items = []
        while True:
            ids_to_send = aps_local_ids[offset:offset + 100]
            if not ids_to_send:
                return connect_items
            ids = ','.join(ids_to_send)
            pd_items = list(
                g.client.products[connect_product].items.filter(f'in(local_id,({ids}))'),
            )
            connect_items.extend(pd_items)
            offset += 100

    def _get_tiers(self, customer, app_id):
        if customer is None:
            return None, []
        account = Account.from_external_scope(customer, app_id)
        oa_tiers = reseller_chain(account.parent, app_id=app_id, first=True)
        return account, oa_tiers

    def _create_response_for_oa(self, validation_result):
        response_data = {
            'draftRequestId': self.draft_request_id,
            'activationParams': [],
        }

        for parameter in validation_result['asset']['params']:
            activation_parameter = {
                'key': parameter['id'],
                'value': parameter['value'],
                'type': parameter['type'],
                'constraints': parameter['constraints'],
            }
            value_error = parameter.get('value_error')
            if value_error:
                activation_parameter['valueError'] = value_error
            if 'structured_value' in parameter:
                activation_parameter['structured_value'] = parameter.get('structured_value')

            response_data['activationParams'].append(activation_parameter)

        return JSONResponse(content=response_data, status_code=200)

    def _create_draft_request(self):

        response = g.client.requests.create(
            payload=self.request_body,
        )
        self.draft_request_id = response['id']

    def _validate_draft_request(self):
        response = g.client.requests[self.draft_request_id].action('validate').post(
            payload=self.request_body,
        )
        return response

    def validate(self):
        """
        Validates draft purchase request. Creates draft request if needed.
        """
        if not self.draft_request_id:
            try:
                self._create_draft_request()
            except Exception:
                # This covers 3 use cases that at the end shall end equally
                # OA Failing
                # Connect API failing
                # No connection
                # reason is that we want not to block any order placement due failure
                return self.validation_not_possible()
        try:
            validation_result = self._validate_draft_request()
        except ClientError:
            # This happens in case that for example endpoint of vendor is down
            # To avoid bad logging on controlled case, let's capture exception and return
            # that is not possible to do validation now, something that will not block the order
            return self.validation_not_possible()

        return self._create_response_for_oa(validation_result)

    @staticmethod
    def validation_not_possible():
        return JSONResponse(
            content={
                "error": "Missing connection from this hub or missing assetId for change requests",
                "message": "Validation can't be performed at this moment on time",
            },
            status_code=409,
        )

from fastapi.responses import JSONResponse
from starlette_context import context as g

from cbcext.models.fulfillment_models import Account
from cbcext.models.fulfillment_models import Reseller
from cbcext.services.client.oaclient import OA, OACommunicationException
from cbcext.services.hub.services import fetch_hub_data_from_connect, fetch_hub_uuid_from_oa

from connect.client import ClientError


TIER_CONFIG_URL = "/tier/config-requests"
RETURN_STATUS = ("pending", "inquiring", "approved")


def get_tier_requests(app_id):
    initiator_id = g.source_request.headers.get("aps-identity-id")
    reseller_uuid = Reseller.get_oss_uid(initiator_id, app_id)
    rql = (
        f'eq(configuration.account.external_uid,{reseller_uuid})&'
        f'eq(configuration.product.id,{g.product_id})&'
        'in(status,(pending,inquiring,approved))'
    )

    return g.client.ns('tier').collection('config-requests').filter(rql).order_by('-created')


def get_last_requests_by_type(tier_requests):
    last_requests = {key: None for key in RETURN_STATUS}
    for tier_request in tier_requests:
        status = tier_request.get("status")
        if status not in last_requests.keys():
            continue

        if not last_requests.get(status):
            last_requests[status] = tier_request

    return [_ for _ in last_requests.values() if _ is not None]


class TierConfigurationRequest:
    def create_request(self, input_data, app_id):
        if 'id' not in input_data['configuration']['product']:
            return JSONResponse(
                content={"error": self.generic_error_message},
                status_code=400,
            )

        connection = self._get_connection(
            app_id=app_id,
            product_id=input_data['configuration']['product']['id'],
        )
        if connection is None:
            # This error only can mean we have hub mess
            return JSONResponse(
                content={"error": "Please contact support, miss-configuration detected"},
                status_code=400,
            )

        input_data['configuration']['connection']['id'] = connection

        if input_data['configuration']['account']['external_id'] != 1:
            try:
                input_data['configuration']['parent_account'] = self._get_parent_account_reference(
                    app_id=app_id,
                    account_id=input_data['configuration']['account']['external_uid'],
                )
                input_data['configuration']['tier_level'] = 1
            except OACommunicationException:
                return JSONResponse(
                    content={
                        "error": "Temporal error, please try again later",
                    },
                    status_code=500,
                )
        try:
            if not input_data['status'] or not input_data['id']:
                if not input_data['status']:
                    input_data['status'] = 'pending'
                setup_request = g.client.ns(
                    'tier',
                ).collection(
                    'config-requests',
                ).create(
                    payload=input_data,
                )
                if setup_request['status'] != 'draft':
                    return setup_request
                input_data['id'] = setup_request['id']
        except ClientError:
            return JSONResponse(
                content={"error": "Error while creating your tier configuration request"},
                status_code=500,
            )

        return self.validate_draft(input_data)

    def validate_draft(self, data):
        try:
            validation_result = g.client.ns(
                'tier',
            ).collection(
                'config-requests',
            ).resource(
                data['id'],
            ).action(
                'validate',
            ).post(payload=data)
        except ClientError:
            # Something went wrong, but we was validating draft, let's convert
            return self._convert_draft_to_pending(data)
        if self._validate_no_value_errors(validation_result['params']):
            return self._convert_draft_to_pending(validation_result)
        # small trick to let CBC rehuse how purchase / change requests are validated
        validation_result['activationParams'] = self._prepare_params_for_oa(
            validation_result['params'],
        )
        validation_result['can_continue'] = False
        return JSONResponse(content=validation_result)

    @staticmethod
    def _prepare_params_for_oa(params):
        activation_params = []
        for parameter in params:
            activation_parameter = {
                'key': parameter['id'],
                'value': parameter['value'],
                'type': parameter['type'],
            }
            value_error = parameter.get('value_error')
            if value_error:
                activation_parameter['valueError'] = value_error
            if 'structured_value' in parameter:
                activation_parameter['structured_value'] = parameter.get('structured_value')

            activation_params.append(activation_parameter)
        return activation_params

    @staticmethod
    def _validate_no_value_errors(params):
        for param in params:
            if 'value_error' in param and param['value_error']:
                return False
        return True

    @staticmethod
    def _convert_draft_to_pending(data):
        try:
            g.client.ns(
                'tier',
            ).collection(
                'config-requests',
            ).resource(
                data['id'],
            ).action(
                'submit',
            ).post(payload={})
        except ClientError as public_error:
            if public_error.status_code and public_error.status_code >= 400:
                return JSONResponse(
                    content={"error": "Error while submitting tier configuration request"},
                    status_code=500,
                )
        # CBC needs the request, to be consistent with purchase request flow
        # and params analysis on CBC side
        data['status'] = 'pending'
        data['can_continue'] = True
        return JSONResponse(content=data, status_code=200)

    @staticmethod
    def _get_parent_account_reference(app_id, account_id):
        """
        Returns account object of the parent of given an account
        :param app_id: aps_id of the app instance
        :param account_id: aps_id of the account we want the parent
        :return: Account
        """

        parent = OA.send_request(
            method='GET',
            impersonate_as=app_id,
            transaction=False,
            path='aps/2/resources/{account_uid}/parent'.format(
                account_uid=account_id,
            ),
        )
        parent_account = Account(parent[0]).dict
        if 'type' in parent_account:  # pragma no branch
            del parent_account['type']
        return parent_account

    @staticmethod
    def _get_connection(app_id, product_id):
        # @TODO: we have similar function in connector/hub/services.py
        # need to merge both functions and leave only one in code
        try:
            hub_uuid = fetch_hub_uuid_from_oa(app_id)
            hub_data = fetch_hub_data_from_connect(hub_uuid)
            connections = g.client.products[product_id].connections.filter('ne(hub.id,null())')
            for connection in connections:
                if connection['hub']['id'] == hub_data['id']:
                    return connection['id']
            return None
        except ClientError:
            # Errors must be generic due tier actor
            return None

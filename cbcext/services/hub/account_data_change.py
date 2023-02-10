from fastapi.responses import JSONResponse
from starlette_context import context as g

from cbcext.services.client.oaclient import OA, OACommunicationException
from cbcext.services.exceptions import InvalidPhoneException
from cbcext.services.hub.services import (
    fetch_account_data_from_oa,
    fetch_tier_account_from_connect,
    send_tier_account_request_to_connect,
)

from connect.client import ClientError


class AccountDataChange:
    """
    Class to handle Tier Account Changes from OA
    """
    TAR_SUBMIT_ERROR = 'TierAccountRequestFailed'

    def handle(self, app_id):
        required_fields = (
            'event',
            'time',
            'serial',
            'subscription',
            'source',
        )
        event_body = g.source_request.json
        if not all(event_body.get(key) for key in required_fields):
            # Silent OK, otherwise OA will continue to send the notification
            return JSONResponse(
                status_code=200,
                content={},
            )
        if not self._validate_event_body(event_body):
            return JSONResponse(content={}, status_code=200)

        if 'changed' in event_body['event']:
            return self._handle_account_change(event_body, app_id)
        return self._handle_create_reseller_relation(event_body, app_id)

    @staticmethod
    def _handle_create_reseller_relation(event_body, app_id):
        try:
            account = fetch_account_data_from_oa(
                account_uuid=event_body['source']['id'],
                app_id=app_id,
            )
            if account.dict['type'] == "RESELLER":
                OA.send_request(
                    method="POST",
                    impersonate_as=app_id,
                    path="aps/2/application/globals/{app_id}/accounts/{account_uid}".format(
                        app_id=app_id,
                        account_uid=event_body['source']['id'],
                    ),
                )
            return JSONResponse(content={}, status_code=200)
        except OACommunicationException:
            return JSONResponse(
                content={"message": "Error while communicating with APS Bus"},
                status_code=409,
            )
        except InvalidPhoneException:
            # Reseller has invalid phone number and we can't create the relation
            return JSONResponse(
                content={},
                status_code=200,
            )

    def _handle_account_change(self, event_body, app_id):
        account_uuid = event_body['source']['id']
        try:
            # Due amount of spam generated in the use case that Proxy is down
            # we silently return 200
            # assumption is that notifying account changes is not business critical in general
            oa_account = fetch_account_data_from_oa(account_uuid, app_id, get_vat=True)
        except OACommunicationException as e:
            if 'OA responded with code 404' in str(e):
                return JSONResponse(content={}, status_code=200)
            else:
                return JSONResponse(
                    content={'message': 'error obtaining account from hub, retry later'},
                    status_code=409,
                )
        except InvalidPhoneException:
            # In the case that OA has an invalid phone number, if we return 409 we will be notified
            # again, better to silently return 200.
            return JSONResponse(content={}, status_code=200)
        # Due fact that we are just notified if we have relation, we must check if account is
        # reseller, in such case we will create relation to know about it's customers
        if oa_account.dict.get('type', None) == "RESELLER":
            # Handling situation where account promoted to reseller, f.e when reseller is
            # created form OA UI
            self._handle_create_reseller_relation(event_body, app_id)

        try:
            connect_tier_acc = fetch_tier_account_from_connect(account_uuid)
        except ClientError:
            return JSONResponse(content={}, status_code=200)

        # In case that Connect don't knows about such account, we silently go away
        if not connect_tier_acc:
            # "Thanks for your assistance, keep us informed."
            return JSONResponse(content={}, status_code=200)

        # we don't catch OA errors to force OA resend us the event and repeat attempt of getting
        # changed account details.

        try:
            send_tier_account_request_to_connect(oa_account, connect_tier_acc)
        except ClientError as pub_err:
            if pub_err.error_code == 'TAR_004':
                """
                No changes in Tier Account has happened
                """
                return JSONResponse(content={}, status_code=200)
            elif pub_err.error_code == 'TAR_003':
                """
                TAR is old and probably test one linked to ACME Marketplace
                """
                return JSONResponse(content={}, status_code=200)

            return self.__tar_submit_error_response(pub_err.status_code, str(pub_err.dict))

        return JSONResponse(content={}, status_code=200)

    @staticmethod
    def _validate_event_body(event_body):
        return (
            not ({'id', 'type'} - event_body['source'].keys())
            and event_body['source']['id'].strip()
        )

    @classmethod
    def __tar_submit_error_response(cls, code, message):
        return JSONResponse(
            content={'error': cls.TAR_SUBMIT_ERROR, 'message': message},
            status_code=code,
        )

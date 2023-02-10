from requests_oauthlib import OAuth1
from starlette_context import context as g

from cbcext.services.client.oaclient import OA, OACommunicationException
from cbcext.services.db_services import fetch_configuration, fetch_hub_uuid_by_app_id
from cbcext.services.hub.services import get_oa_aps_openapi_adapter


class VatGatheringException(Exception):
    """Exception to denote that VAT can't be obtained and due it return nothing"""


class Vat:
    """ Class in charge to extract the VAT Code using Hub Extension and Adapter from OA """

    def __init__(self, app):
        self.app = app

    def get_vat_code(self, aps_account_id):
        """
        provides VAT Code given app (aka APS Product) and aps account id
        :param aps_account_id: str
        :return: str or None
        """
        try:
            """
            First we check if adapter is present just due if not we can save a lot of cycles
            """
            openapi_adapter = get_oa_aps_openapi_adapter(self.app)
            if openapi_adapter is None:
                return None
            impersonate_user_id = self._get_account_admin(aps_account_id)
            vat_identification_number = self._get_vat_using_user_id(
                user_id=impersonate_user_id,
                account_id=aps_account_id,
                openapi_adapter=openapi_adapter,
            )

            return vat_identification_number

        except OACommunicationException:
            """
            In case of any OACommunication exception since VAT is not really possible to be
            extracted, we return None
            """
            return None
        except VatGatheringException:
            """
            If any of the conditions in order to get VAT code is not met, since we consider that
            as not a business blocker, we return None
            """
            return None

    def _get_extension_resource(self):
        """
        Obtains APS Id of Hub Extension in OA
        Only we support that if HUB extension is from Connect v20 or newer, that means
        type id is 2.4 or bigger
        """
        extension_aps_resource = OA.get_resources(
            "aps/2/resources/?implementing({type})".format(
                type="http://odin.com/servicesSelector/globals/2",
            ),
            impersonate_as=self.app,
            transaction=False,
        )

        if not len(extension_aps_resource) == 1:
            raise VatGatheringException("Extension not ok to grab VAT")

        subversion = int(extension_aps_resource[0]['aps']['type'].replace(
            'http://odin.com/servicesSelector/globals/2.', '',
        ))
        if subversion < 4:
            raise VatGatheringException("Extension not ok to grab VAT")
        return extension_aps_resource[0]['aps']['id']

    @staticmethod
    def _get_extension_credentials(extension_aps_id):
        """
        Gets OAUTH1 credentials for a given hub extension instance
        :param extension_aps_id:
        """
        hub_uuid = fetch_hub_uuid_by_app_id(db=g.db, app_id=extension_aps_id)
        extension_credentials = fetch_configuration(
            db=g.db,
            instance_id=hub_uuid,
        )
        oauth_creds = OAuth1(
            client_key=extension_credentials.oauth_key,
            client_secret=extension_credentials.oauth_secret,
        )

        return oauth_creds

    def _get_account_admin(self, oa_account_aps_id):
        """
        Gets first admin user on a given account
        :param oa_account_aps_id: str (UUID)
        """
        users = OA.send_request(
            method='get',
            transaction=False,
            impersonate_as=self.app,
            path='aps/2/resources/{account_resource}/users'.format(
                account_resource=oa_account_aps_id,
            ),
        )
        for user in users:
            if 'isAccountAdmin' in user and user['isAccountAdmin'] is True:
                return user['userId']
        raise VatGatheringException("No admin user in account")

    def _get_vat_using_user_id(self, user_id, account_id, openapi_adapter):
        """
        Gets the VAT using user ID from OA
        :param user_id: int
        :param account_id: string
        :return: string
        """
        user_token = self._get_user_token(user_id, openapi_adapter)
        bss_account = self._get_bss_account(account_id)
        var_code = OA.send_request(
            method='GET',
            transaction=False,
            impersonate_as=None,
            auth='Token',
            headers={
                'APS-Token': user_token['aps_token'],
            },
            path='aps/2/resources/{pba_account_aps_id}/taxRegId'.format(
                pba_account_aps_id=bss_account,
            ),
            binary=True,
        )
        return var_code.text

    def _get_bss_account(self, aps_account_id):
        """
        Gets BSS OA Account given oa_aps_account_id
        """
        bss_account = OA.get_resources(
            transaction=False,
            impersonate_as=self.app,
            rql_request='aps/2/resources?implementing({type}),eq(paAccount.aps.id,{id})'.format(
                type='http://parallels.com/pa/bss-account-info/1.0',
                id=aps_account_id,
            ),
        )
        if len(bss_account) != 1:
            raise VatGatheringException("Error obtaining BSS account")
        return bss_account[0]['aps']['id']

    def _get_user_token(self, user_id, adapter_aps_id):
        """
        Gets user APS token to query VAT
        :param user_id: int
        :param adapter_aps_id: string (UUID)
        :return:
        """
        extension = self._get_extension_resource()
        extension_creds = self._get_extension_credentials(extension)
        token = OA.send_request(
            method='GET',
            transaction=False,
            impersonate_as=extension,
            auth=extension_creds,
            path='aps/2/resources/{adapter}/getToken?user_id={user_id}'.format(
                adapter=adapter_aps_id,
                user_id=user_id,
            ),
        )
        if 'aps_token' not in token:
            raise VatGatheringException("No token obtained")
        return token

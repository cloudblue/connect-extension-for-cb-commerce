from urllib.parse import urlparse

from connect.client import ConnectClient
from connect.eaas.core.inject.common import get_call_context, get_config
from connect.eaas.core.inject.synchronous import get_extension_client
from connect.eaas.core.models import Context
from fastapi import Depends, HTTPException, Request
from oauthlib import oauth1 as oauth
from requests_oauthlib import OAuth1
from sqlalchemy.orm import Session
from starlette_context import context as g

from cbcext.db import get_db
from cbcext.services.db_services import fetch_configuration
from cbcext.utils.generic import get_oauth_key, get_real_url


class RequestValidator(oauth.RequestValidator):
    enforce_ssl = False
    secret = "secret"
    key = "key"
    dummy_client = "dummy"
    dummy_request_token = "dummy"
    dummy_access_token = "dummy"

    def __init__(self, oauth_key, oauth_secret):
        self.endpoint = oauth.SignatureOnlyEndpoint(self)
        self._oauth_key = oauth_key
        self._oauth_secret = oauth_secret
        super(RequestValidator, self).__init__()

    @property
    def nonce_length(self):
        return 16, 50

    def check_client_key(self, client_key):
        return True if client_key else False

    def validate_client_key(self, client_key, request):
        return client_key == self._oauth_key

    def get_client_secret(self, client_key, request):
        if client_key == "dummy":
            return "blah-blah-blah"
        return self._oauth_secret

    def validate_timestamp_and_nonce(
        self,
        client_key,
        timestamp,
        nonce,
        request,
        request_token=None,
        access_token=None,
    ):
        return True  # we don't validate nonce and timestamp

    def validate_signature(self, url, command, body_string, headers):
        headers = dict(headers) if headers else {}
        try:
            result, request = self.endpoint.validate_request(
                url, command, body_string, headers,
            )
            return result
        except ValueError:
            return False

    def get_request(self, url, command, body_string, headers):
        headers = dict(headers) if headers else {}
        result, request = self.endpoint.validate_request(
            url, command, body_string, headers,
        )
        return request


def check_oauth_signature(oauth_key, oauth_secret, request):
    return RequestValidator(oauth_key, oauth_secret).validate_signature(
        get_real_url(request), request.method, request.body, request.headers,
    )


def check_required_aps_headers(request):
    headers = request.headers
    return 'aps-controller-uri' in headers and is_url(headers.get('aps-controller-uri'))


def get_client_key(request):
    oauth_request = RequestValidator().get_request(
        get_real_url(request), request.method, request.body, request.headers,
    )
    return oauth_request.client_key if oauth_request else None


def is_url(url):
    try:
        # Consult urlparse doc for more info if unclear
        result = urlparse(url)
        # Accessing port, if not valid throws ValueError
        result.port
        # If no hostname, urlparse returns none
        if result.hostname is None:
            return False
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def authentication_required(
    request: Request,
    db: Session = Depends(get_db),
    config: dict = Depends(get_config),
    extension_client: ConnectClient = Depends(get_extension_client),
    context: Context = Depends(get_call_context),
):
    oauth_key = get_oauth_key(request)
    configuration = fetch_configuration(db, oauth_key=oauth_key)
    if not configuration or not check_oauth_signature(
            oauth_key,
            configuration.oauth_secret,
            request,
    ):
        raise HTTPException(status_code=401)
    if not check_required_aps_headers(request):
        raise HTTPException(
            status_code=400,
            detail='Instance configuration in CloudBlue Commerce is not set to type proxy',
        )
    g.client = get_installation_client(
        extension_client=extension_client,
        extension_id=context.extension_id,
        installation_id=configuration.installation_id,
    )
    g.product_id = configuration.instance_id
    g.extension_config = config
    g.auth = OAuth1(
        client_key=oauth_key, client_secret=configuration.oauth_secret,
    )
    g.db = db


def get_installation_client(
        extension_client,
        extension_id,
        installation_id,
):
    data = (
        extension_client('devops')
        .services[extension_id]
        .installations[installation_id]
        .action('impersonate')
        .post()
    )

    return ConnectClient(
        data['installation_api_key'],
        endpoint=extension_client.endpoint,
        default_headers=extension_client.default_headers,
        logger=extension_client.logger,
        max_retries=3,
    )

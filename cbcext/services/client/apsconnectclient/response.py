import json
import typing

import attr
from requests import Response


@attr.s
class ErrorResponse(object):
    status_code = attr.ib(default=None)
    text = attr.ib(default="")
    request = attr.ib(default=None)


@attr.s
class RequestResponse(object):
    status_code = attr.ib(default=202)
    activation_key = attr.ib(default=None)
    params_form_url = attr.ib(default=None)
    asset_id = attr.ib(default=None)
    marketplace_id = attr.ib(default=None)
    vendor_subscription_id = attr.ib(default=None)
    tenant_id = attr.ib(default=None)
    message = attr.ib(default=None)
    error = attr.ib(default=None)
    account = attr.ib(default=None)
    template = attr.ib(default=None)
    activation_parameters = attr.ib(default=None)
    fulfillment_parameters = attr.ib(default=None)
    draft_request_id = attr.ib(default=None)


@attr.s
class ActionResponse(object):
    status_code = attr.ib(default=302)
    forward_to = attr.ib(default=None)
    error = attr.ib(default=None)


class MissingAssetError(Exception):
    # This error is thrown in suspend/resume/cancel scenarios in use case that connect
    # don't have Asset for a give uuid
    # This can happen in use case that creation task in CBC was canceled and then
    # provider cancels the subscription that is partially created
    pass


class PublicApiError(Exception):

    def __init__(self, status_code=None, *args, **kwargs):
        self.error_code = kwargs.get("error_code", {})
        self.params = kwargs.get("params", {})
        self.errors = kwargs.get("errors", kwargs.get("error"))
        self.status_code = status_code

    @property
    def dict(self):
        error_dict = {
            "code": self.status_code,
            "error_code": self.error_code,
            "params": self.params,
            "errors": self.errors,
        }
        if not self.params:
            error_dict.pop("params")
        return error_dict


class APSConnectCommunicationException(Exception):

    def __init__(self, resp: typing.Union[ErrorResponse, Response]):
        msg = "Request to APS Connect failed."
        if resp.status_code:
            msg += " APS Connect responded with code {code}".format(code=resp.status_code)
        msg += "\nError message: {text}".format(text=resp.text)
        msg += "\nRequest URL: {url}".format(url=resp.request.url)
        msg += "\nRequest Headers: {headers}".format(
            headers=json.dumps(dict(resp.request.headers.items()), indent=4),
        )
        msg += "\nRequest Body:\n\n{body}".format(body=resp.request.body)
        super(APSConnectCommunicationException, self).__init__(msg)

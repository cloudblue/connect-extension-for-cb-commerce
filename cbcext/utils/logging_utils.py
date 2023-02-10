import json
import logging
from typing import Dict

from requests import PreparedRequest, Response, Session
from requests.adapters import HTTPAdapter
from starlette_context import context as g
from urllib3.util.retry import Retry


def log_outgoing_request(request: PreparedRequest) -> Dict:
    headers = dict(request.headers)
    for k, v in headers.items():
        if isinstance(v, bytes):
            headers[k] = v.decode()
    return {
        "method": request.method,
        "url": request.url,
        "headers": headers,
        "data": request.body,
    }


def log_outgoing_response(response: Response) -> Dict:
    try:
        data = json.loads(response.content)
    except Exception:
        data = response.content.decode()
    headers = dict(response.headers)
    for k, v in headers.items():
        if isinstance(v, bytes):
            headers[k] = v.decode()
    return {"status": response.status_code, "headers": headers, "data": data}


def log_binary(req):
    logging_message = "Outgoing request to {url} not logging content due is an stream".format(
        url=req["url"],
    )
    if g.logger.isEnabledFor(logging.DEBUG):
        g.logger.debug(logging_message)
    else:
        g.logger.error(logging_message)


def log_message(req):
    logging_message = "Outgoing request to {url}\n{response}".format(
        url=req["url"],
        response=json.dumps(req, indent=4),
    )
    if g.logger.isEnabledFor(logging.DEBUG):
        g.logger.debug(logging_message)
    else:
        g.logger.error(logging_message)


def send_and_log(session: Session, request: PreparedRequest, binary=False, **kwargs) -> Response:
    # In case that proxy is not working, let's retry up to 3 times and with a backoff
    retries = Retry(total=3, connect=3, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    resp: Response = session.send(request, **kwargs)

    if g.logger.isEnabledFor(logging.DEBUG) or resp.status_code < 200 or resp.status_code > 299:
        request_dict = log_outgoing_request(request)
        if resp.status_code < 200 or resp.status_code > 299:
            message = (
                f'Flow generated a response with code {resp.status_code}.\n'
                f'Received request from source system: {g.source_request.body}'
            )
            g.logger.error(message)
        if binary:
            log_binary(request_dict)
        else:
            log_message(request_dict)

        response_dict = log_outgoing_response(resp)
        message = "Response from {url}\n{response}".format(
            url=request_dict["url"],
            response=json.dumps(response_dict, indent=4),
        )
        if g.logger.isEnabledFor(logging.DEBUG):
            g.logger.debug(message)
        else:
            g.logger.error(message)
    return resp

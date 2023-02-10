from dataclasses import dataclass
from json.decoder import JSONDecodeError
from logging import LoggerAdapter

from connect.eaas.core.inject.common import get_logger
from fastapi import Depends, Request as FARequest
from starlette.requests import Request as STRequest
from starlette_context import context as g


@dataclass
class Request:
    json: dict = None
    headers: dict = None
    query_params: dict = None
    query_string: str = None


async def convert_request(request: FARequest):
    try:
        body = await request.json()
    except JSONDecodeError:
        body = {}
    headers = request.headers
    query_params = request.query_params
    r = Request(body, headers, query_params, request.url.query)
    return r


def set_globals(
        request: STRequest = Depends(convert_request),
        logger: LoggerAdapter = Depends(get_logger),
):
    g.logger = logger
    g.source_request = request

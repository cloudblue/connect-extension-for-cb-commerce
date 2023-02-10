import re
from functools import reduce

from fastapi import HTTPException

RE_OAUTH_KEY = re.compile(r'oauth_consumer_key="(.+?)",')


def get_real_url(request):
    proto = request.headers['X-Forwarded-Proto']
    host = request.headers['X-Forwarded-Host']
    parameters = request.query_params
    if parameters:
        return f'{proto}://{host}{request.url.path}?{parameters}'
    return f'{proto}://{host}{request.url.path}'


def get_oauth_key(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise HTTPException(status_code=401)
    match = re.search(RE_OAUTH_KEY, auth_header)
    if not match:
        raise HTTPException(status_code=401)

    key = match.groups()[0]
    return key


def property_parser(data, desc="data"):
    def extract_params(args, required=False, default=None):
        try:
            return reduce(lambda dict_, key: dict_[key], args.split("."), data)
        except KeyError:
            if required:
                raise KeyError(f"Missing {args} in {desc}")
        return default

    return extract_params

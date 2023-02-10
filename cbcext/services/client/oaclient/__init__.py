import json
import os
from collections import namedtuple
from urllib.parse import urljoin

import redis
from requests import Request, Session
from requests.exceptions import Timeout
from starlette_context import context as g

from cbcext.utils.logging_utils import send_and_log

ErrorResponse = namedtuple("ErrorResponse", "status_code text request")

OA_TASKS = {
    'Connect healthcheck': {
        'description': "Performs periodic healthcheck between this CloudBlue Commerce hub"
                       " and CloudBlue Connect",
        'path': '/healthCheck',
        'verb': 'GET',
    },
    'Connect Chunk Usage Files retrieval': {
        'description': "Performs periodic retrieval of usage files between this CloudBlue Commerce"
                       " hub and CloudBlue Connect",
        'path': '/processUsageChunkFiles',
        'verb': 'GET',
        'startHour': 23,
        'startMinute': 1,
    },
}


class OACommunicationException(Exception):

    def __init__(self, resp):
        msg = "Request to OA failed."
        if resp.status_code:
            msg += " OA responded with code {status_code}".format(status_code=resp.status_code)
        msg += "\nError message: {message}".format(message=resp.text)
        msg += "\nRequest URL: {url}".format(url=resp.request.url)
        msg += "\nRequest Headers: {headers}".format(headers=str(resp.request.headers))
        msg += "\nRequest Body:\n\n{body}".format(body=resp.request.body)
        super(OACommunicationException, self).__init__(msg)


class ScheduleUnknownTaskException(Exception):
    def __init__(self, task_name):
        msg = "Attempt to schedule unknown task '{task_name}'".format(task_name=task_name)
        super().__init__(msg)


class OA(object):

    @staticmethod
    def subscribe_on(
        resource_id="", event_type="", handler="", relation="", source_type="",
        transaction=True, impersonate_as=None,
    ):
        subscription = {
            "event": event_type,
            "source": {"type": source_type},
            "relation": relation,
            "handler": handler,
        }
        rql_request = "aps/2/resources/{resource}/aps/subscriptions".format(resource=resource_id)
        return OA.send_request("post", rql_request, subscription)

    @staticmethod
    def check_resource_subscribed_to(
        aps_resource,
        event_type,
    ):
        rql_request = f"aps/2/resources/{aps_resource}/aps/subscriptions"
        event_subscriptions = OA.send_request("GET", rql_request)
        for subscription in event_subscriptions:
            if event_type == subscription.get('event'):
                return True
        return False

    @staticmethod
    def schedule_task(task_name, resource_id, period, period_type="SECONDS"):
        if task_name not in OA_TASKS:
            raise ScheduleUnknownTaskException(task_name)

        task_params = OA_TASKS[task_name]

        task = {
            'taskUuid': '',
            'taskName': task_name,
            'taskDescription': task_params['description'],
            'callInfo': {
                'resourceId': resource_id,
                'path': task_params['path'],
                'verb': task_params['verb'],
            },
            'schedule': {
                'period': period,
                'periodType': period_type,
                'startHour': task_params.get('startHour', ''),
                'startMinute': task_params.get('startMinute', ''),
            },
        }
        rql_request = "/aps/2/services/periodic-task-manager/tasks"

        return OA.send_request(
            "post", rql_request, task,
            transaction=False,
            impersonate_as=resource_id,
        )

    @staticmethod
    def get_resource(resource_id, impersonate_as=None, transaction=True, retry_num=10):
        rql_request = "aps/2/resources/{resource_id}".format(resource_id=resource_id)
        return OA.send_request(
            "get",
            rql_request,
            impersonate_as=impersonate_as,
            transaction=transaction,
            retry_num=retry_num,
        )

    @staticmethod
    def put_resource(
        representation, transaction=True, impersonate_as=None, retry_num=10,
    ):
        rql_request = "aps/2/resources"
        return OA.send_request(
            "put",
            rql_request,
            body=representation,
            transaction=transaction,
            impersonate_as=impersonate_as,
            retry_num=retry_num,
        )

    @staticmethod
    def get_resources(rql_request, transaction=True, impersonate_as=None, retry_num=10):
        return OA.send_request(
            "get",
            rql_request,
            transaction=transaction,
            impersonate_as=impersonate_as,
            retry_num=retry_num,
        )

    @staticmethod
    def _create_headers(http_request, headers, impersonate_as, transaction):
        if not headers:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Connect-Extension-CBC",
            }
        if impersonate_as:
            headers["aps-resource-id"] = impersonate_as
        if transaction and http_request.headers.get("aps-transaction-id"):
            headers["aps-transaction-id"] = http_request.headers.get("aps-transaction-id")
        return headers

    @staticmethod
    def _prepare_body(body, binary):
        if not binary:
            data = None if body is None else json.dumps(body)
        else:
            data = body
        return data

    @staticmethod
    def make_prepared_request(method, url, data, headers, auth):
        if 'APS-Token' not in headers:
            prepared = Request(
                method=method, url=url, data=data, headers=headers, auth=auth,
            ).prepare()
        else:
            prepared = Request(
                method=method, url=url, data=data, headers=headers,
            ).prepare()
        return prepared

    @staticmethod
    def make_prepared_auth(auth):
        return auth or g.auth

    @staticmethod
    def send_request(
            method,
            path,
            body=None,
            transaction=True,
            impersonate_as=None,
            retry_num=10,
            headers=None,
            binary=False,
            auth=None,
            timeout=None,
    ):
        oa_uri = g.source_request.headers.get("aps-controller-uri")
        url = urljoin(oa_uri, path)
        headers = OA._create_headers(g.source_request, headers, impersonate_as, transaction)

        data = OA._prepare_body(body, binary)

        retry_num = retry_num if retry_num > 0 else 1

        timeout = timeout if timeout else 300
        with Session() as s:
            auth = OA.make_prepared_auth(auth)
            prepared = OA.make_prepared_request(method, url, data, headers, auth)
            while retry_num > 0:
                retry_num -= 1
                try:
                    resp = send_and_log(
                        s,
                        prepared,
                        timeout=timeout,
                        verify=False,
                        binary=binary,
                    )
                except Timeout:
                    err = ErrorResponse(
                        None,
                        "Request to OA timed out. "
                        "Timeout: {timeout}".format(timeout=timeout),
                        prepared,
                    )
                    raise OACommunicationException(err)
                except Exception as e:
                    err = ErrorResponse(None, str(e), prepared)
                    raise OACommunicationException(err)

                if resp.status_code == 200:
                    return resp if binary else resp.json()
                elif resp.status_code != 400:
                    raise OACommunicationException(resp)

            raise OACommunicationException(resp)

    @staticmethod
    def get_application_schema():
        return OA.send_request("get", "aps/2/application", transaction=False)

    @staticmethod
    def is_application_support_users():
        return True if OA.get_application_schema().get("user") else False

    @staticmethod
    def get_user_schema():
        user_schema = {}
        user_schema_uri = OA.get_application_schema().get("user", {}).get("schema")
        if user_schema_uri:
            user_schema = OA.send_request("get", user_schema_uri, transaction=False)
        return user_schema

    @staticmethod
    def get_tenant_schema(tenant_type=None):
        redis_prefix = 'CBC-EXTENSION'
        r = redis.from_url(
            g.extension_config.get(
                'REDIS_LOCATION',
                os.getenv('REDIS_LOCATION', 'redis://redis:6379/0'),
            ),
        )
        if tenant_type:
            try:
                schema = r.get(f'{redis_prefix}:{tenant_type}')
                if schema:
                    return json.loads(schema)
            except Exception:
                pass
        tenant_schema = {}
        tenant_schema_uri = OA.get_application_schema().get("tenant", {}).get("schema")
        if tenant_schema_uri:
            tenant_schema = OA.send_request("get", tenant_schema_uri, transaction=False)
            tenant_type = tenant_schema['id']
            try:
                r.set(f'{redis_prefix}:{tenant_type}', json.dumps(tenant_schema), nx=True)
            except Exception:
                pass
        return tenant_schema

    @staticmethod
    def get_user_resources():
        return (
            OA.get_user_schema()
            .get("properties", {})
            .get("resource", {})
            .get("enum", [])
        )

    @staticmethod
    def get_counters():
        props = OA.get_tenant_schema().get("properties", {})
        counters = [
            name for name, value in props.items() if "Counter" in value.get("type", "")
        ]
        return counters

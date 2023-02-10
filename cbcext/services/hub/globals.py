import re

from fastapi.responses import JSONResponse
from starlette_context import context as g

from cbcext.services.client.oaclient import OA
from cbcext.services.db_services import save_aps_global_config
from cbcext.services.hub.services import (
    fetch_hub_data_from_connect,
    subscribe_on_account_creation,
    subscribe_on_account_data_changes,
)
from cbcext.services.hub.services import (
    aps_openapi_adapter_get_application_id,
    aps_openapi_adapter_get_instances,
    fetch_hub_uuid_by_app_id,
    fetch_hub_uuid_from_oa,
    fetch_product_connections,
    fetch_product_from_connect,
    fetch_product_item_by_local_id,
    get_oa_aps_openapi_adapter,
    ping_oa,
    schedule_healthcheck_in_oa,
    schedule_usage_chunks_retrival_in_oa,
)
from cbcext.services.hub.utils import from_aps_rql_to_client_rql

from connect.client import ClientError

APS_APP_TYPE = 'http://odin.com/servicesSelector/globals/2.'
REGISTRATION_ERROR = 'AppRegistrationFailed'


def get_account_products(request):
    rql_params = request.query_string
    raw_query_string, limit, offset = from_aps_rql_to_client_rql(rql_params)
    try:

        products = list(g.client.products.filter(raw_query_string)[offset:offset + limit])
        content_range = g.client.response.headers['Content-Range']
        return JSONResponse(
            content=products,
            headers={
                'Content-Range': content_range,
            },
            status_code=200,
        )
    except ClientError as pub_err:
        return JSONResponse(
            content={
                "error": str(pub_err.status_code),
                "error_message": str(pub_err),
            },
            status_code=400,
        )


def get_available_operations(app_id, request):
    if 'product_id' not in request.query_params:
        return JSONResponse(
            content={
                "message": "product_id is required parameter",
                "type": "error",
            },
            status_code=400,
        )
    openapi_adapter = get_oa_aps_openapi_adapter(app_id)
    if not openapi_adapter:
        return_message = {
            "message": "CloudBlue Connect OpenApi adapter not available on the hub",
            "type": "error",
        }

        return JSONResponse(content=return_message, status_code=400)

    oa_app_id = aps_openapi_adapter_get_application_id(
        app_id=app_id,
        openapi_adapter=openapi_adapter,
        product_id=request.query_params['product_id'],
    )

    if oa_app_id is None:
        return JSONResponse(
            content={
                "message": "Error while communicating with hub",
                "type": "error",
            },
            status_code=400,
        )

    if oa_app_id['app_id'] is None:
        return JSONResponse(content={"operation": "install"}, status_code=200)
    oa_app_instances = aps_openapi_adapter_get_instances(
        app_id=app_id,
        openapi_adapter=openapi_adapter,
        oa_app_id=oa_app_id['app_id'],
    )
    if oa_app_instances is None:
        return JSONResponse(
            content={
                "message": "Error while communicating with hub to retrieve app instances",
                "type": "error",
            },
            status_code=400,
        )

    if len(oa_app_instances) == 0:
        return JSONResponse(content={"operation": "install"}, status_code=200)
    elif len(oa_app_instances) > 1:
        return JSONResponse(
            content={
                "message": "Only single instance of product can be operated per hub",
                "type": "error",
            },
            status_code=400,
        )

    aps_app = OA.send_request(
        method='GET',
        path='aps/2/resources/{resource}'.format(
            resource=oa_app_instances[0]['application_resource_id'],
        ),
        impersonate_as=app_id,
    )
    if 'aps' not in aps_app:
        return JSONResponse(content={"operation": "install"}, status_code=200)
    connect_product = fetch_product_from_connect(product_id=request.query_params['product_id'])
    latest = int(connect_product['version'])
    match = re.match(
        r'http://aps.odin.com/app/{product}/app/(?P<major>\d+)\.0'.format(
            product=request.query_params['product_id'],
        ),
        aps_app['aps']['type'],
    )
    if not match:
        return JSONResponse(
            content={
                "message": "Installed version has been modified, automatic operations disabled",
                "type": "error",
            },
            status_code=400,
        )
    major = int(match.groupdict()['major'])
    if int(major) == latest:
        return {"operation": "createRTs"}
    elif int(major) > latest:
        return JSONResponse(
            content={
                "message": "Version of product deployed is greater than available in Connect",
                "type": "error",
            },
            status_code=400,
        )
    return JSONResponse(
        content={
            "operation": "upgrade",
            "from": latest,
            "to": connect_product['version'],
        },
        status_code=200,
    )


def validate_app_data(app_data):
    required_keys = {
        'id',
        'type',
        'status',
    }
    if required_keys - app_data.keys():
        return False, "Attributes 'id', 'type' and 'status' are required for 'aps' object."

    if not app_data['type'].startswith(APS_APP_TYPE):
        return (
            False,
            "Only type '{type}x' is supported for this operation.".format(
                type=APS_APP_TYPE,
            ),
        )

    return True, None


def registration_error_response(code, message):
    return JSONResponse(
        content={'error': REGISTRATION_ERROR, 'message': message},
        status_code=code,
    )


def get_product_information(request):
    if 'product' not in request.json:
        return JSONResponse(
            content={"error_message": "Invalid request"},
            status_code=400,
        )
    try:
        return fetch_product_from_connect(request.json['product'])
    except ClientError:
        return JSONResponse(
            content={"error_message": "Error when retrieving product information"},
            status_code=400,
        )


def get_product_connections_info(app_id, request):
    if 'product' not in request.json:
        return JSONResponse(
            content={"error_message": "Invalid request"},
            status_code=400,
        )
    hub_uuid = fetch_hub_uuid_by_app_id(db=g.db, app_id=app_id)

    try:
        hub_data = fetch_hub_data_from_connect(hub_uuid)
    except ClientError as pub_err:
        return JSONResponse(
            content={"error": pub_err.status_code, "error_message": str(pub_err)},
            status_code=400,
        )

    try:
        return fetch_product_connections(request.json['product'], hub_data['id'])
    except ClientError:
        return JSONResponse(
            content={"error_message": "Error when retrieving connections information"},
            status_code=400,
        )


def get_item_per_product_information():
    if 'product_id' not in g.source_request.json or 'local_id' not in g.source_request.json:
        return JSONResponse(
            content={"error_message": "Invalid request"},
            status_code=400,
        )
    try:
        return fetch_product_item_by_local_id(g.source_request.json['product'],
                                              g.source_request.json['local_id'])
    except ClientError:
        return JSONResponse(
            content={"error_message": "Error when retrieving item information"},
            status_code=400,
        )


class HubGlobals:
    @staticmethod
    def handle_creation(request):
        required_field = ("aps",)
        input_data = request.json
        if not all(input_data.get(key) for key in required_field):
            return JSONResponse(status_code=400, content="required fields missing")
        is_valid, err_msg = validate_app_data(input_data['aps'])
        if not is_valid:
            return registration_error_response(400, err_msg)

        app_id = input_data['aps']['id']
        hub_uuid = fetch_hub_uuid_from_oa(app_id)

        try:
            hub_data = fetch_hub_data_from_connect(hub_uuid=hub_uuid)
        except ClientError as pub_err:
            return registration_error_response(pub_err.status_code, str(pub_err))

        if not hub_data:
            return registration_error_response(
                400,
                "This hub is not registered in Connect.",
            )

        subscribe_on_account_data_changes(app_id)
        subscribe_on_account_creation(app_id)
        healthcheck = schedule_healthcheck_in_oa(app_id)
        processusagechunkfiles = schedule_usage_chunks_retrival_in_oa(app_id)
        save_aps_global_config(
            db=g.db,
            app_id=app_id,
            hub_uuid=hub_uuid,
        )

        resp = {
            'aps': input_data['aps'],
            'hub_id': hub_data['id'],
            'hub_uuid': hub_uuid,
            'account_id': hub_data['company']['id'],
            'account_name': hub_data['company']['name'],
            'healthcheck_task': healthcheck['taskUuid'],
            'processusagechunkfiles_task': processusagechunkfiles['taskUuid'],
        }
        return JSONResponse(
            content=resp,
            status_code=200,
        )

    @staticmethod
    def handle_upgrade(request):
        required_field = ("aps",)
        input_data = request.json
        if not all(input_data.get(key) for key in required_field):
            return JSONResponse(
                status_code=400,
                content={"message": "Invalid input data, not an aps resource"},
            )
        oa_app_id = input_data['aps']['id']
        hub_uuid = fetch_hub_uuid_from_oa(oa_app_id)

        try:
            hub_data = fetch_hub_data_from_connect(hub_uuid)
        except ClientError:
            return {"message": "Temporal error, retry again later"}, 500

        if not hub_data:
            return {"message": "This hub is not registred in Connect."}, 400

        if 'version' in request.query_params:
            version = request.query_params['version']
            match = re.match(r'(?P<major>(.?.))\.(?P<minor>\d+)-', version)
            if match:
                major = int(match.groupdict()['major'])
                minor = int(match.groupdict()['minor'])

                healthcheck_task = None
                processusagechunkfiles_task = None

                if 'healthcheck_task' in input_data:
                    healthcheck_task = input_data['healthcheck_task']
                if 'processusagechunkfiles_task' in input_data:
                    processusagechunkfiles_task = input_data['processusagechunkfiles_task']
                """
                Concrete upgrade tasks depending on source version installed on hub
                """
                if major == 19 and minor < 3:
                    subscribe_on_account_creation(oa_app_id)
                if (major == 19 and minor == 0) or (major < 19 and major > 1):
                    healthcheck = schedule_healthcheck_in_oa(oa_app_id)
                    healthcheck_task = healthcheck['taskUuid']
                    processusagechunkfiles = schedule_usage_chunks_retrival_in_oa(oa_app_id)
                    processusagechunkfiles_task = processusagechunkfiles['taskUuid']
                elif major == 1:
                    return JSONResponse(
                        content={
                            "message": (
                                "Upgrade from version 1.0 is not possible, "
                                "check upgrade instructions available at "
                                "https://connect.cloudblue.com/documentation/extensions/"
                                "cloudblue-commerce/reseller-control-panel/"
                            ),
                        },
                        status_code=400,
                    )

                resp = {
                    'aps': input_data['aps'],
                    'hub_id': hub_data['id'],
                    'hub_uuid': hub_uuid,
                    'account_id': hub_data['company']['id'],
                    'account_name': hub_data['company']['name'],
                    'healthcheck_task': healthcheck_task,
                    'processusagechunkfiles_task': processusagechunkfiles_task,
                }

                return JSONResponse(content=resp, status_code=200)

            else:
                return JSONResponse(
                    content={
                        "message": "Upgrading from unsupported version {version}".format(
                            version=version,
                        ),
                    },
                    status_code=400,
                )

        return JSONResponse(
            content={"message": "Hub did not pass application version"},
            status_code=400,
        )

    @staticmethod
    def hub_healthcheck(app_id):
        is_success, info, update_external_identifiers = ping_oa(app_id)

        if is_success:
            if info is not None:
                return JSONResponse(content={'status': 'upgrade', 'message': info}, status_code=200)
            if update_external_identifiers:
                return JSONResponse(
                    content={
                        'status': 'fail',
                        'message': 'APS Core types requires update, please check '
                                   'https://connect.cloudblue.com/community/extensions/cloudblue'
                                   '-commerce/prerequisites/prerequisite-1-abstract-types/ for '
                                   'additional information ',
                    },
                    status_code=200,
                )
            return JSONResponse(content={'status': 'ok', 'message': info}, status_code=200)
        else:
            return JSONResponse({'status': 'fail', 'message': info}, status_code=409)

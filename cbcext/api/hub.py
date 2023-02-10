from urllib.parse import urlparse

from connect.eaas.core.decorators import guest
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from starlette_context import context as g

from cbcext.services.db_services import remove_aps_global_config
from cbcext.services.hub.account_data_change import AccountDataChange
from cbcext.services.hub.aps_package_download import download_hub_aps_package
from cbcext.services.hub.globals import (
    get_account_products,
    get_available_operations,
    get_item_per_product_information,
    get_product_connections_info,
    get_product_information,
    HubGlobals,
)
from cbcext.services.hub.hub_tier_configurations import handle_tier_configs_from_aps
from cbcext.services.hub.process_chunk_files import ProcessUsageChunkFiles
from cbcext.services.hub.product_lifecycle import InitTask
from cbcext.utils.dependencies import convert_request
from cbcext.utils.security import authentication_required

hub_auth_router = APIRouter(
    dependencies=[Depends(authentication_required)],
)
hub_noauth_router = APIRouter()


@guest()
@hub_auth_router.post('/globals')
def globals(
        request: Request = Depends(convert_request),
):
    return HubGlobals().handle_creation(request)


@guest()
@hub_auth_router.put('/globals/{app_id}')
def update_globals(app_id):
    return JSONResponse(content={}, status_code=200)


@guest()
@hub_auth_router.delete('/globals/{app_id}')
def delete_hub_globals(app_id):
    try:
        remove_aps_global_config(
            db=g.db,
            app_id=app_id,
            impersonator_hub_uuid=g.configuration['instance_id'],
        )
    except TypeError:
        pass
    return JSONResponse(content={}, status_code=204)


@guest()
@hub_auth_router.post('/globals/{app_id}/upgrade')
def upgrade_hub_instance(
        app_id,
        request: Request = Depends(convert_request),
):
    return HubGlobals().handle_upgrade(request)


@guest()
@hub_auth_router.get('/globals/{app_id}/healthCheck')
def hub_healthcheck(app_id):
    return HubGlobals().hub_healthcheck(app_id)


@guest()
@hub_auth_router.get('/globals/{app_id}/products')
def account_products(
    app_id,
    request: Request = Depends(convert_request),
):
    return get_account_products(request)


@guest()
@hub_auth_router.post('/globals/{app_id}/productInfo')
def get_product_info(
        app_id,
        request: Request = Depends(convert_request),
):
    return get_product_information(request)


@guest()
@hub_auth_router.post('/globals/{app_id}/connectionsInfo')
def get_connections_info(
        app_id,
        request: Request = Depends(convert_request),
):
    return get_product_connections_info(app_id, request)


@guest()
@hub_auth_router.get('/globals/{app_id}/availableOperations')
def get_application_available_operations(
        app_id,
        request: Request = Depends(convert_request),
):
    return get_available_operations(app_id, request)


@guest()
@hub_auth_router.get('/globals/{app_id}/getStaticContentUrl')
def get_static_content_url(app_id):
    static_url = urlparse(g.client.endpoint)
    return JSONResponse(
        content={
            "url": f'{static_url.scheme}://{static_url.hostname}',
        },
        status_code=200,
    )


@guest()
@hub_auth_router.post('/globals/{app_id}/itemInfo')
def get_item_information(app_id):
    return get_item_per_product_information()


@guest()
@hub_auth_router.post('/globals/{app_id}/accountDataChange')
def account_data_change(app_id):
    return AccountDataChange().handle(app_id)


@guest()
@hub_auth_router.get('/globals/{app_id}/processUsageChunkFiles')
def process_usage_files(app_id):
    return ProcessUsageChunkFiles().handle(app_id)


@guest()
@hub_auth_router.post('/globals/{app_id}/accounts/{resource_id}')
def handle_create_account_link(app_id, resource_id):
    return JSONResponse(content={}, status_code=200)


@guest()
@hub_auth_router.delete('/globals/{app_id}/accounts/{resource_id}')
def handle_delete_account_link(app_id, resource_id):
    return JSONResponse(content={}, status_code=200)


@guest()
@hub_auth_router.post('/globals/{app_id}/accounts/')
def handle_account_creation(app_id):
    return JSONResponse(content={}, status_code=200)


@guest()
@hub_auth_router.get('/globals/{app_id}/getTierConfigs')
def handle_get_tier_configs(app_id):
    return handle_tier_configs_from_aps(app_id)


@guest()
@hub_auth_router.post('/globals/{app_id}/productInitTasks')
def create_init_task_globals(app_id):
    return JSONResponse(content={}, status_code=200)


@guest()
@hub_auth_router.get('/globals/{app_id}/productInitTasks')
def getinit_task_globals(app_id):
    return JSONResponse(content={}, status_code=200)


@guest()
@hub_auth_router.delete('/globals/{app_id}/productInitTasks/{resource_id}')
def delete_init_task(app_id, resource_id):
    return JSONResponse(content={}, status_code=200)


@guest()
@hub_auth_router.delete('/productInitTask/{resource_id}')
def delete_prod_init_task(resource_id):
    return JSONResponse(content={}, status_code=200)


@guest()
@hub_auth_router.delete('/productInitTask')
def delete_product_init_task():
    return InitTask().handle_delete()


@guest()
@hub_auth_router.post('/productInitTask')
def create_product_init_task():
    return InitTask().handle_create_init_task()


@guest()
@hub_noauth_router.get('/apspackage')
def download_aps_package():
    return download_hub_aps_package()

from fastapi.responses import JSONResponse

from cbcext.services.utils import (
    get_action_id_by_action_local_id,
    get_action_link,
    get_asset_by_uuid,
)

from connect.client import ClientError


def handle_actions(tenant_id, action_id):
    asset = get_asset_by_uuid(asset_external_uid=tenant_id)
    if asset is None:
        return JSONResponse(
            content={
                "error": "Invalid asset",
            },
            status_code=400,
        )
    action_id = get_action_id_by_action_local_id(
        product_id=asset['product']['id'],
        scope='asset',
        action_local_id=action_id,
    )
    if action_id:
        try:
            link = get_action_link(
                product_id=asset['product']['id'],
                action=action_id,
                scope='asset',
                identifier=asset['id'],
            )
            return JSONResponse(
                content={
                    'url': link['link'],
                },
                status_code=200,
            )
        except ClientError:
            pass
    return JSONResponse(
        content={
            "error": "Invalid action",
        },
        status_code=400,
    )

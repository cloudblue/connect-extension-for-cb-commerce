from connect.eaas.core.decorators import guest
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from cbcext.utils.dependencies import convert_request
from cbcext.utils.security import authentication_required

item_auth_router = APIRouter(
    dependencies=[Depends(authentication_required)],
)


@guest()
@item_auth_router.post('/itemProfile')
def create_item_profile():
    return JSONResponse(
        content={},
        status_code=200,
    )


@guest()
@item_auth_router.put('/itemProfile/{item_profile_id}')
def update_item_profile(
    item_profile_id,
    request: Request = Depends(convert_request),
):
    return JSONResponse(
        content=request.json,
        status_code=200,
    )


@guest()
@item_auth_router.delete('/itemProfile/{item_profile_id}')
def delete_item_profile(
    item_profile_id,
):
    return JSONResponse(
        content={},
        status_code=204,
    )

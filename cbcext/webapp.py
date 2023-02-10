# -*- coding: utf-8 -*-
#
# Copyright (c) 2023, CloudBlue an Ingram Micro Company
# All rights reserved.
#

import os

import urllib3
from alembic import command
from alembic.config import Config
from connect.eaas.core.decorators import (
    guest,
    router,
    web_app,
)
from connect.eaas.core.extension import WebApplicationBase
from fastapi import Depends
from starlette_context.middleware import RawContextMiddleware

from cbcext.api.app import app_auth_router
from cbcext.api.hub import hub_auth_router, hub_noauth_router
from cbcext.api.itemprofile import item_auth_router
from cbcext.api.tenant import tenant_auth_router
from cbcext.utils.dependencies import set_globals


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


router.include_router(
    hub_auth_router,
    prefix='/hub',
    dependencies=[Depends(set_globals)],
)
router.include_router(hub_noauth_router, prefix='/hub')
router.include_router(
    tenant_auth_router,
    prefix='/connector',
    dependencies=[Depends(set_globals)],
)
router.include_router(
    app_auth_router,
    prefix='/connector',
    dependencies=[Depends(set_globals)],
)
router.include_router(
    item_auth_router,
    prefix='/connector',
    dependencies=[Depends(set_globals)],
)


@web_app(router)
class CbcWebApplication(WebApplicationBase):

    @guest()
    @router.get('/')
    def healthcheck(self):
        return {"status": "ok", "version": "1.0"}

    @classmethod
    def get_middlewares(cls):
        return [RawContextMiddleware]

    @classmethod
    def on_startup(cls, logger, config):
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', 'cbcext:migrations')
        alembic_cfg.set_main_option(
            'sqlalchemy.url',
            config.get(
                'DATABASE_URL',
                os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:1q2w3e@db/extension_cbc'),
            ),
        )
        logger.info('Running migrations....')
        command.upgrade(alembic_cfg, "head")
        logger.info('Migrations completed')

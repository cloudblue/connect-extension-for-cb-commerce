from datetime import datetime

import sqlalchemy as db

from cbcext.db import Model


class Configuration(Model):
    __tablename__ = 'configuration'
    """
    Product (old term - connector)/Hub  configurations model.
    Configurations are used to get devportal credentials for Odin Automation requests.
    In other words, QS-Connector gets `oauth_key` from OA `Authorization` headers to find `api_key`.

    """
    oauth_key = db.Column(db.String(100), primary_key=True)
    oauth_secret = db.Column(db.String(100))
    instance_id = db.Column('product_id', db.String(100))
    installation_id = db.Column('installation_id', db.String(100), nullable=True)


class GlobalAppConfiguration(Model):
    __tablename__ = 'global_app_configuration'
    """
    Each hub of OA type should have application Connect APS Global installed.

    Binding between instance of Connect APS Global and its Hub is stored here.
    """

    app_instance_id = db.Column(db.String(100), primary_key=True)
    hub_uuid = db.Column(db.String(100))


class HubInstances(Model):
    __tablename__ = 'hub_instances'
    """
    Mechanism in order to have tracking of the aps controller URIs from all connected
    CBC instances, that allows us to initiate connections from our side
    """

    hub_id = db.Column('hub_id', db.String(100), primary_key=True)
    app_instance_id = db.Column('app_instance_id', db.String(100), nullable=True)
    extension_resource_uid = db.Column(db.String(100), nullable=True)
    controller_uri = db.Column('controller_uri', db.String(400), nullable=True)
    last_health_check = db.Column(
        'last_check',
        db.TIMESTAMP(),
        default=datetime.utcnow,
    )

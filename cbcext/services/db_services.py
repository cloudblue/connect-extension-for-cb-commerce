from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from cbcext.models.db_models import Configuration, GlobalAppConfiguration, HubInstances


def fetch_configuration(db: Session, **filter_kw):
    """
    Selects a single configuration from the database using passed filter keywords as conditions.

    :keyword str instance_id:
    :keyword str oauth_key:

    :rtype: connector.configs.Configuration
    :return: first configuration from the result queryset.
    """
    return db.query(Configuration).filter_by(**filter_kw).first()


def fetch_hub_uuid_by_app_id(db: Session, app_id):
    """
    Look ups for app-hub binding in GlobalAppConfiguration.

    :param str app_id: APS Instance ID of Connect APS Global app in OA.

    :rtype: str
    :return: Hub UUID (APS Root Resource ID in OA)
    """

    app2hub = db.query(GlobalAppConfiguration).filter_by(app_instance_id=app_id).first()
    return app2hub.hub_uuid


def update_or_create_hub_instance(db: Session, hub_id, app_instance_id, ext_resource, uri):
    hub = db.query(HubInstances).filter_by(hub_id=hub_id).first()
    if not hub:
        hub = HubInstances(
            hub_id=hub_id,
            app_instance_id=app_instance_id,
            extension_resource_uid=ext_resource,
            controller_uri=uri,
        )
        db.add(hub)
    else:
        db.query(HubInstances).filter_by(hub_id=hub_id).update(
            {
                'hub_id': hub_id,
                'app_instance_id': app_instance_id,
                'extension_resource_uid': ext_resource,
                'controller_uri': uri,
                'last_health_check': datetime.utcnow(),
            },
        )
    db.commit()


def save_aps_global_config(db: Session, app_id, hub_uuid):
    """
    Creates binding APS Instance ID to Hub UUID in QS-connector database.
    """
    app2hub = GlobalAppConfiguration(app_instance_id=app_id, hub_uuid=hub_uuid)
    db.session.add(app2hub)
    db.session.commit()
    return app2hub


def remove_aps_global_config(db: Session, app_id, impersonator_hub_uuid):
    """
    Removes binding between Connect Globals App Id and Hub UUID in QS-connector database.
    """
    app2hub = db.query(GlobalAppConfiguration).filter_by(app_instance_id=app_id).first()
    if app2hub:

        if app2hub.hub_uuid != impersonator_hub_uuid:
            raise HTTPException(status_code=403)

        app2hub.query.delete()
        db.session.commit()

from connect.client.rql import R

from cbcext.models.db_models import Configuration
from cbcext.db import get_engine

from sqlalchemy.orm import Session

from contextlib import contextmanager

from cbcext.db import SessionLocal


@contextmanager
def get_db_for_events(config):
    engine = get_engine(config)
    db = SessionLocal(bind=engine)
    try:
        yield db
    finally:
        db.close()


def get_products(client):
    rql = R().visibility.listing.eq(True)
    rql |= R().visibility.syndication.eq(True)
    return client.products.filter(rql)


def get_oa_connections(client, product_id):
    rql = R().hub.id.ne('null()')
    connections = []
    all_connections = client.products[product_id].connections.filter(rql)
    for connection in all_connections:
        if connection.get('hub', {}).get('instance', {}).get('type', 'API') == 'OA':
            connections.append(connection)
    return connections


def add_product_connections(db: Session, client, installation_id):
    products = get_products(client)
    for product in products:
        connections = get_oa_connections(client, product['id'])
        for connection in connections:
            exists = db.query(Configuration).filter_by(
                oauth_key=connection['oauth_key'],
            ).first()
            if not exists:
                conn = Configuration(
                    oauth_key=connection['oauth_key'],
                    oauth_secret=connection['oauth_secret'],
                    instance_id=product['id'],
                    installation_id=installation_id,
                )
                db.add(conn)
                db.commit()


def add_installation_hubs(db: Session, client, installation_id):
    hubs = client.hubs.filter('eq(instance.type,OA)')
    for hub in hubs:
        exists = db.query(Configuration).filter_by(
            oauth_key=hub['creds']['key'],
        ).first()
        if not exists:
            conn = Configuration(
                oauth_key=hub['creds']['key'],
                oauth_secret=hub['creds']['secret'],
                instance_id=hub['instance']['id'],
                installation_id=installation_id,
            )
            db.add(conn)
            db.commit()

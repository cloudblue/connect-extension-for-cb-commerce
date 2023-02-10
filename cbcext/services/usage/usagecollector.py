from datetime import datetime
from typing import Tuple

from fastapi.responses import JSONResponse
from starlette_context import context as g

from cbcext.services.client.apsconnectclient import request_statuses
from cbcext.services.client.oaclient import OA, OACommunicationException

from connect.client import ClientError

import math


PPU = 'ppu'
RESERVATION = 'reservation'
FETCH_DEFAULT_LIMIT = 1000
USAGE_SCHEMA = 'qt'
RESOURCE_MULTIPLIERS = {
    'integer': 1,
    'decimal(1)': 10,
    'decimal(2)': 100,
    'decimal(4)': 10000,
    'decimal(8)': 100000000,
}


def _get_multiplier_by_precision(data_type):
    """ Fetch multiplier by item precision type """
    return RESOURCE_MULTIPLIERS.get(data_type, RESOURCE_MULTIPLIERS['integer'])


def _bulk_close_usage_records(rec_ids: list) -> Tuple[dict, dict]:
    return g.client.ns('usage').ns('records').collection('close-records').bulk_create(rec_ids)


def _get_usage_aggregate_by_asset_external_uid(asset_external_uid: str) -> dict:
    """ GET Usage Aggregate API call with required parameter - asset external uid"""
    rql = f'asset.external_uid={asset_external_uid}'
    return g.client.ns('usage').collection('aggregates').filter(rql)


def _get_all_usage_records(asset_external_id: str) -> dict:
    rql = (
        f'status={request_statuses.approved}'
        f'&asset.external_uid={asset_external_id}'
        f'&usagefile.schema={USAGE_SCHEMA}'
    )
    return g.client.ns('usage').collection('records').filter(rql)


def _get_item_usage(item_type: str, usage_rec: dict) -> float:
    """ Fetch usage value from usage item aggregate dict """
    if item_type == PPU:
        return float(usage_rec.get('accepted', 0))

    return float(usage_rec.get('consumed', 0))


def _setup_item_with_usage_data(tenant_id: str, tenant_data: dict) -> dict:
    """ Set item usage data from aggregate API for reporting to OA """
    item_usage = {}

    try:
        for usage_rec in _get_usage_aggregate_by_asset_external_uid(tenant_id):
            local_id = usage_rec['item'].get('local_id')
            item_type = usage_rec['item'].get('type', '').lower()

            if local_id in tenant_data and item_type in [PPU, RESERVATION]:
                usage = _get_item_usage(item_type, usage_rec)

                multiplier = float(_get_multiplier_by_precision(usage_rec['item'].get('precision')))
                current_reported = math.floor(usage * multiplier)
                previous_usage = tenant_data[local_id].get('usage', 0)

                # Special case to handle for OA - We shouldn't be reporting less usage value than
                # what has been reported earlier for PPU item
                if previous_usage >= current_reported and item_type == PPU:
                    item_usage[local_id] = previous_usage
                else:
                    item_usage[local_id] = current_reported
    except ClientError:
        return {}

    return item_usage


def _setup_usage_record_to_close(external_uid: str, item_usage: dict) -> list:
    """ List of dict of usage record to be closed """
    records_ids = []
    try:
        for usage_rec in _get_all_usage_records(external_uid):
            local_id = usage_rec['item'].get('local_id')
            if local_id in item_usage:
                records_ids.append({
                    "id": usage_rec['id'],
                    "external_billing_note": "Closed at {time}".format(time=datetime.now()),
                })
    except ClientError:
        return []

    return records_ids


def _setup_tenant_usage_to_report(props: dict, item_usage: dict) -> dict:
    """ Prepare dict of usage to report OA"""
    tenant = {}
    for name, item in props.items():
        if 'Counter' in item.get('type', '') and name in item_usage:
            tenant[name] = {'usage': item_usage.get(name)}

    return tenant


def build_usage(tenant_id: str) -> JSONResponse:
    """
    Report usage to OA on teh basis on asset_external_uid
    :param str tenant_id: asset_external_uid
    :rtype: dict : Dict of item local ID with usage value
    """
    tenant = {}
    if tenant_id:
        try:
            tenant_data = OA.get_resource(tenant_id)
            props = OA.get_tenant_schema(tenant_data['aps']['type']).get('properties', {})
        except OACommunicationException:
            return JSONResponse(
                content={
                    "error": "APSControllerFailure",
                    "message": (
                        "Error while communicating with CloudBlue Commerce,"
                        "please retry later"
                    ),
                },
                status_code=409,
            )

        item_usage = _setup_item_with_usage_data(tenant_id, tenant_data)

        if not item_usage:
            return JSONResponse(content=tenant_data)

        records_ids = _setup_usage_record_to_close(tenant_id, item_usage)

        tenant = _setup_tenant_usage_to_report(props, item_usage)

        if records_ids:
            _bulk_close_usage_records(records_ids)

    return JSONResponse(
        content=tenant,
    )

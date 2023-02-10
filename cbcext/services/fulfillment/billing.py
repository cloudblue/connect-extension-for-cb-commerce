from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from cbcext.models.fulfillment_models import Event, Tenant
from cbcext.services.fulfillment.base import BaseRequest

from connect.client import ClientError
from starlette_context import context as g

DAILY = 'daily'
HOURLY = 'hourly'
MONTHLY = 'monthly'
YEARLY = 'yearly'

UOM_DICT = {
    'Day(s)': DAILY,
    'Hour(s)': HOURLY,
    'Month(s)': MONTHLY,
    'Year(s)': YEARLY,
}


class BillingRequest(BaseRequest):
    resource = "/subscriptions/requests"

    def __init__(self, tenant_id: str, data: dict):
        self.tenant = Tenant.from_aps_id(aps_id=tenant_id)
        self.billing_data = Event(data=data, tenant_id=tenant_id).billing_data

    @property
    def request_body(self):
        data = {
            "type": "provider",
            "asset": {
                "external_uid": self.tenant.aps_id,
            },
            "items": self.items,
            "period": self.renewal_obj,
        }
        return data

    def _place_request(self) -> JSONResponse:
        try:
            g.client.ns('subscriptions').collection('requests').create(payload=self.request_body)
        except ClientError:
            # We do not return errors since in case we don't return OK to OA subscriptions may be
            # terminated. More information on issue LITE-14626
            pass
        return JSONResponse(status_code=200, content={})

    def _create_response_for_oa(self, response):
        return JSONResponse(
            content={},
            status_code=response.status_code,
            headers={},
        )

    @staticmethod
    def __calc_date_to_and_uom(date_from, delta_type, delta):
        if delta_type not in UOM_DICT:
            raise HTTPException(
                status_code=400,
                detail="Unsupported period type.",
            )

        uom = UOM_DICT[delta_type]
        if uom == DAILY:
            new_date = date_from + timedelta(days=delta)
        elif uom == HOURLY:
            new_date = date_from + timedelta(hours=delta)
        elif uom == MONTHLY:
            new_date = date_from + relativedelta(months=delta)
        else:
            new_date = date_from.replace(year=date_from.year + delta)

        return new_date, uom

    @property
    def renewal_obj(self):

        try:
            date_from = datetime.strptime(self.billing_data['start_date'], '%Y-%m-%dT%H:%M:%SZ')
            delta = int(self.billing_data['period'])
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Incorrect billing information data",
            )

        date_to, uom = self.__calc_date_to_and_uom(
            date_from,
            self.billing_data['period_type'],
            delta,
        )

        return {
            'from': self.billing_data['start_date'],
            'to': date_to.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'delta': delta,
            'uom': uom,
        }

    @property
    def items(self):
        return self._strip_zeros([
            {"id": key, "quantity": val}
            for key, val in self.tenant.resources.items()
            if key not in ('COUNTRY', 'ENVIRONMENT')
        ])

    @staticmethod
    def _strip_zeros(items):
        return list(filter(lambda i: i['quantity'] != 0, items))

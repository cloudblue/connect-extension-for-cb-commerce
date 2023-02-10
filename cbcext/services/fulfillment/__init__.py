from cbcext.services.client.apsconnectclient import request_types
from cbcext.services.fulfillment.billing import BillingRequest
from cbcext.services.fulfillment.change import ChangeRequest
from cbcext.services.fulfillment.purchase import PurchaseRequest
from cbcext.services.fulfillment.simple import SimpleRequest
from cbcext.services.fulfillment.validate import ValidateDraftRequest


class SuspendRequest(SimpleRequest):
    def __init__(self, tenant_id: str):
        super(SuspendRequest, self).__init__(tenant_id, request_types.suspend)


class ResumeRequest(SimpleRequest):
    def __init__(self, tenant_id: str):
        super(ResumeRequest, self).__init__(tenant_id, request_types.resume)


class CancelRequest(SimpleRequest):
    def __init__(self, tenant_id: str):
        super(CancelRequest, self).__init__(tenant_id, request_types.cancel)


__all__ = [
    "PurchaseRequest",
    "SuspendRequest",
    "ResumeRequest",
    "CancelRequest",
    "ChangeRequest",
    "BillingRequest",
    "ValidateDraftRequest",
]

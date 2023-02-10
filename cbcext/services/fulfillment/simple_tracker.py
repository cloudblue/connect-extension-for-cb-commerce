from datetime import datetime, timezone

from fastapi.responses import JSONResponse
from requests.exceptions import Timeout

from cbcext.services.client.apsconnectclient.response import MissingAssetError, PublicApiError
from cbcext.services.fulfillment import CancelRequest, ResumeRequest, SuspendRequest
from cbcext.services.fulfillment.request_tracker_utils import (
    aps_retry_header_obtain_request_error,
    handle_approved,
    handle_failed,
    handle_pending,
    update_tenant_with_request,
)
from cbcext.services.utils import approve_due_max_retries, get_last_request_by_tenant_id

# Time difference to recreate a request for resume and cancel type
BRUTE_FORCE_RECREATION = 300


class SimpleRequestTracker:
    operation = None

    def __init__(self, tenant_id):
        self.tenant_id = tenant_id

    def track(self, operation):
        self.operation = operation
        try:
            last_request = get_last_request_by_tenant_id(
                tenant_id=self.tenant_id,
                operation=operation,
            )
        except (PublicApiError, Timeout):
            # In case that something wrong with public api, let's reschedule at OA
            return JSONResponse(
                content={},
                status_code=202,
                headers=aps_retry_header_obtain_request_error(),
            )

        if not last_request:
            # Something gone wrong, somehow we are on Async Phase but there is no request
            # To ensure no OA issues, let's create what OA asks about, this issue may be easily
            # happen due canceled tasks

            try:
                if operation == "suspend":
                    return SuspendRequest(tenant_id=self.tenant_id).create
                if operation == "resume":
                    return ResumeRequest(tenant_id=self.tenant_id).create
                # Valid operations are suspend, resume or cancel

                return CancelRequest(tenant_id=self.tenant_id).create
            except MissingAssetError:
                return JSONResponse(content={}, status_code=204)

        request_status = last_request['status']

        if request_status in ('failed', 'revoked'):
            return self.handle_failures(last_request, operation)

        if request_status == "approved":
            answer_data = update_tenant_with_request(
                self.tenant_id,
                last_request,
            ) if operation != 'cancel' else {}

            return handle_approved(
                request=last_request,
                answer_data=answer_data,
            )
        # handling pending or potential and extreme case that is inquiring
        return handle_pending(request=last_request, operation=self.operation)

    def handle_failures(self, last_request, operation):
        # Please check carefully comments in regards of retry logic depending on failure
        if operation == "suspend":
            # OA has a glitch, suspension in billing has no real reflection in billing
            # and that means that irrelevant of what vendor says, is suspended. If we fail
            # suspension task, nobody notices that vendor keeps service active, additionally
            # there is no way to distinguish between a suspend due put subscription on hold
            # or a suspension prior cancellation, due this, even if failed...we return approved
            # this is weird, but hope is that in case of cancellation, our behaivour will be
            # good, please note that for resume we don't work that way since at least
            # operations will see WHY vendor don't wants to enable the service
            return handle_approved(
                request=last_request,
                answer_data={},
            )

        expected_reason = "The product doesn't support suspend/resume operations."
        if operation == "resume" and last_request['reason'] == expected_reason:
            # Here we have kind of our own glitch when working with OA
            # Product capability resume / suspend does not depend on published product, in the
            # case that vendor has disabled this while tracking...we can't recreate and we must
            # check the reason of failure, if is such one, let's return OK
            return handle_approved(
                request=last_request,
                answer_data={},
            )

        # Here we prepare a weird algorithm caused by how OA works, please read carefully how this
        # values are used on cancel and resume operations.
        # Basically we will check 2 things:
        # - Time difference between rejection by vendor of last request
        # - if last 5 requests created in Connect are from same type and all of them was failed
        # When request is type resume, we will return always last request and we will ping vendor
        # only if time difference
        # in the case of cancel, after certain amount of retries, we give up and then problem
        # moves from operations team to reconciliation one

        time_request_updated = datetime.fromisoformat(last_request['updated'])
        time_now = datetime.now(tz=timezone.utc)

        if operation == "cancel":
            # Once again OA has a glitch, cancel requests happens after subscription is terminated
            # in billing side, this means that in case vendor cancels the task gets stuck and
            # only thing that can be done is to cancel it and somehow clean OA
            # here we have a business challenge, in case we send to OA a success (old behavior
            # with product authentication, nobody notices it, and issue becomes a reconciliation
            # one that due systems involved into this, either never happens or nobody understand
            # seems more reasonable to fail the task and in case that is resubmitted a new
            # request gets created, final goal is that either operations, either the vendor
            # who rejects the request at the end gets annoyed and talks one with the other
            # to resolve the situation, accepting the cancellation or delaying it as much as
            # needed and approving finally the request

            time_difference_last_request = int((time_now - time_request_updated).total_seconds())

            if time_difference_last_request > BRUTE_FORCE_RECREATION:
                if approve_due_max_retries(
                        tenant_id=self.tenant_id,
                        operation=operation,
                        limit=5,
                ):
                    # We give up and return to CBC OK, reconciliation team will need to find out
                    # this.
                    return handle_approved(
                        request=last_request,
                        answer_data={},
                    )
                return CancelRequest(tenant_id=self.tenant_id).create

            # If time_difference_is less than brute force recreation, we return result of last
            # failed

        # Effectively only resume requests failures are returned with the aim that
        # operations team sees that even that maybe customer paid invoice, his service
        # is not running. exactly in same way as cancel, only way we can force to
        # parties to talk, is create new request

        if int((time_now - time_request_updated).total_seconds()) > BRUTE_FORCE_RECREATION:
            return ResumeRequest(tenant_id=self.tenant_id).create

        return handle_failed(last_request)

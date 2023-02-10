from collections import namedtuple

TIMEOUT = 30
RETRIES = 3
DELAY = 2

request_types = namedtuple("RequestType", "new cancel change suspend resume billing")(
    "purchase", "cancel", "change", "suspend", "resume", "provider",
)

request_statuses = namedtuple("RequestStatuses", "approved pending failed draft")(
    "approved", "pending", "failed", "draft",
)

# Ignore error triggering for
ASSET_STATUS_IGNORE_REQUEST_TYPES = {
    'active': ['resume'],
    'terminating': ['cancel', 'suspend'],
    'terminated': ['cancel', 'suspend'],
    'suspended': ['suspend'],
}

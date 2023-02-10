import uuid

import attr
from attr.validators import optional
from phonenumbers import parse as phone_parse

from cbcext.services.client.apsconnectclient import request_types
from cbcext.services.client.oaclient import OA, OACommunicationException
from cbcext.services.utils import get_actions
from cbcext.utils.generic import property_parser
from cbcext.utils.parameters import extract_activation_params
from cbcext.utils.phone import (
    parse_phone_number,
    substitute_plus,
    validate_phone_number,
)


def validate_telephone(instance, attribute, value):
    validate_phone_number(value)


@attr.s
class PostalAddressPublic(object):
    country = attr.ib()
    address_line2 = attr.ib()
    state = attr.ib()
    postal_code = attr.ib()
    city = attr.ib()
    address_line1 = attr.ib()


@attr.s
class PostalAddress(object):
    country_name = attr.ib()
    extended_address = attr.ib()
    locality = attr.ib()
    postal_code = attr.ib()
    region = attr.ib()
    street_address = attr.ib()


@attr.s
class PhoneNumber(object):
    area_code = attr.ib()
    country_code = attr.ib()
    extension = attr.ib()
    phone_number = attr.ib()


@attr.s
class TechContact(object):
    email = attr.ib()
    given_name = attr.ib()
    family_name = attr.ib()
    telephone = attr.ib(validator=[optional(validate_telephone)])

    # OA sends phone in two formats, if the format is not 123#123213#1231#123 it needs to convert it
    def __attrs_post_init__(self):
        if self.telephone and "#" not in self.telephone:
            self.telephone = substitute_plus(self.telephone)

            phone_obj = phone_parse(self.telephone)
            self.telephone = "{country_code}#{phone}".format(
                country_code=phone_obj.country_code,
                phone=phone_obj.national_number,
            )


@attr.s
class TechContactPublic(object):
    email = attr.ib()
    first_name = attr.ib()
    last_name = attr.ib()
    phone_number = attr.ib()


def make_address_public(address: dict) -> PostalAddressPublic:
    return PostalAddressPublic(
        country=address.get("countryName"),
        address_line2=address.get("extendedAddress"),
        state=address.get("region"),
        postal_code=address.get("postalCode"),
        city=address.get("locality"),
        address_line1=address.get("streetAddress"),
    )


def make_address(address: dict) -> PostalAddress:
    return PostalAddress(
        country_name=address.get("countryName"),
        extended_address=address.get("extendedAddress"),
        locality=address.get("locality"),
        postal_code=address.get("postalCode"),
        region=address.get("region"),
        street_address=address.get("streetAddress"),
    )


def make_contact(contact: dict) -> TechContact:
    return TechContact(
        email=contact.get("email"),
        given_name=contact.get("givenName"),
        family_name=contact.get("familyName"),
        telephone=contact.get("telVoice"),
    )


def make_contact_public(contact: dict) -> TechContactPublic:
    phone_number = contact.get("telVoice")
    if phone_number:
        validate_phone_number(phone_number)
        phone_number = PhoneNumber(**parse_phone_number(phone_number))

    if phone_number == '':
        phone_number = None

    return TechContactPublic(
        email=contact.get("email"),
        first_name=contact.get("givenName"),
        last_name=contact.get("familyName"),
        phone_number=phone_number,
    )


class Tenant(object):
    RENEW_EVENT_TYPE = "http://parallels.com/aps/events/pa/subscription/renewed"
    RENEW_HANDLER = "renewSubscription"
    SUBSCRIPTION_SOURCE_TYPE = "http://parallels.com/aps/types/pa/subscription/1.0"
    VENDOR_SUBSCRIPTION_TYPE = "http://aps-standard.org/types/core/external/identifiers/1"
    EXTERNAL_IDENTIFIERS_TYPE = "http://aps-standard.org/types/core/external/identifiers/1.1"
    SYNC_ACTIVATION_DATE_TYPE = "http://aps-standard.org/types/core/external/identifiers/1.2"
    DELAYED_ACTIVATION_TYPE = "http://parallels.com/aps/events/pa/subscription/activate/changes"
    DELAYED_CANCEL_TYPE = "http://parallels.com/aps/events/pa/subscription/cancel/changes"
    DELAYED_ACTIVATION_HANDLER = "onActivateScheduledChanges"
    DELAYED_CANCEL_HANDLER = "onCancelScheduledChanges"
    aps_type = None
    aps_status = None
    aps_id = None
    sub_id = None
    app_id = None
    account_id = None
    account_info = None
    status = None
    status_data = None
    resources = None
    activation_key = None
    params_form_url = None
    parameters = None
    draft_request_id = None
    asset_id = None
    vendor_subscription_id = None
    activationParameters = None
    fulfillmentParameters = None
    marketplace_id = None

    legacy_params_form_url = None
    legacy_asset_id = None
    legacy_vendor_subscription_id = None
    legacy_external_identifiers = None
    legacy_sync_activation_date = None
    legacy_marketplace_id = None
    legacy_planned_date_not_supported = None

    def __init__(self, tenant):
        parse = property_parser(tenant, desc="tenant")
        self.aps_id = parse("aps.id", required=True)
        self.sub_id = parse("aps.subscription", required=True)
        self.aps_type = parse("aps.type", required=True)
        self.aps_status = parse("aps.status", required=True)
        self.account_id = parse("account.aps.id")
        self.app_id = parse("app.aps.id")
        self.activation_key = parse("activationKey", default="")
        self.params_form_url = parse("paramsFormUrl", default="")
        self.asset_id = parse("assetId", default="")
        self.marketplace_id = parse("marketPlaceId", default="")
        self.vendor_subscription_id = parse("vendorSubscriptionId", default="")
        self.activationParameters = parse("activationParameters", default=[])
        self.fulfillmentParameters = parse("fulfillmentParameters", default=[])
        self.last_planned_request = parse("last_planned_request", default="")

        # In case of simple API and in case of somebody external metadata type
        # params comes over activationParameters, we keep old behaviour due backwards
        # compatibility

        parameters = parse('activationParameters', default=[])
        if not parameters:
            parameters = parse('activationParams', default=[])

        self.parameters, self.params = extract_activation_params(parameters)

        self.account_info = parse("accountInfo", required=True)
        self.resources = {}

        oa_schema = OA.get_tenant_schema(self.aps_type)
        props = oa_schema.get("properties", {})
        implements = oa_schema.get("implements", [])
        counters = [
            name for name, value in props.items() if "Counter" in value.get("type", "")
        ]

        self.legacy_params_form_url = "paramsFormUrl" not in props
        self.legacy_asset_id = "assetId" not in props
        self.legacy_vendor_subscription_id = not any(
            self.VENDOR_SUBSCRIPTION_TYPE in x for x in implements
        )
        self.legacy_external_identifiers = self._legacy_external_identifiers(implements)
        self.legacy_sync_activation_date = self.SYNC_ACTIVATION_DATE_TYPE not in implements
        self.legacy_marketplace_id = "marketPlaceId" not in props

        self.resources = {item: tenant[item]["limit"] for item in counters if item in tenant}
        self.items = [{"id": key, "quantity": val} for key, val in self.resources.items()]
        self.draft_request_id = parse('draftRequestId')
        self.legacy_planned_date_not_supported = "last_planned_request" not in props

    def _legacy_external_identifiers(self, implements):
        if self.EXTERNAL_IDENTIFIERS_TYPE in implements:
            return False
        if self.SYNC_ACTIVATION_DATE_TYPE in implements:
            return False
        return True

    @staticmethod
    def from_aps_id(aps_id):
        try:
            tenant = OA.get_resource(aps_id)
        except OACommunicationException as e:
            if "Transaction not found by" in str(e):
                tenant = OA.get_resource(aps_id, transaction=False)
            else:
                raise e
        return Tenant(tenant)

    def make_account(self):
        try:
            account = (
                OA.get_resource(self.account_id)
            )
        except OACommunicationException as e:
            # In some circumstances like daily billing, getting account using
            # transaction don't works, but it shall
            if "Transaction not found by" in str(e):
                account = (
                    OA.get_resource(self.account_id, transaction=False)
                )
            else:
                raise e
        try:
            from cbcext.services.vat import Vat
            vat = Vat(self.app_id)
            tax_id = vat.get_vat_code(aps_account_id=self.account_id)
        except Exception:
            """
            If we can't get VAT code, is OK...
            """
            tax_id = ""

        account["tax_id"] = tax_id

        return Account(account)

    def subscribe_for_renew(self):
        OA.subscribe_on(
            self.aps_id,
            Tenant.RENEW_EVENT_TYPE,
            Tenant.RENEW_HANDLER,
            "",
            Tenant.SUBSCRIPTION_SOURCE_TYPE,
        )

    def subscribe_for_delayed_actions(self):
        if not OA.check_resource_subscribed_to(
            aps_resource=self.aps_id,
            event_type=Tenant.DELAYED_ACTIVATION_TYPE,
        ):
            OA.subscribe_on(
                self.aps_id,
                Tenant.DELAYED_ACTIVATION_TYPE,
                Tenant.DELAYED_ACTIVATION_HANDLER,
                "",
                Tenant.SUBSCRIPTION_SOURCE_TYPE,
            )
            OA.subscribe_on(
                self.aps_id,
                Tenant.DELAYED_CANCEL_TYPE,
                Tenant.DELAYED_CANCEL_HANDLER,
                "",
                Tenant.SUBSCRIPTION_SOURCE_TYPE,
            )


class Account(object):
    aps_id: str = None
    oss_id: int = None
    type: str = None
    company_name: str = None
    tax_id: str = None
    postal_address: PostalAddress = None
    tech_contact = None
    parent = None

    def __init__(self, account):
        parse = property_parser(account, desc="account")
        self.aps_id = parse("aps.id", required=True)
        self.oss_id = parse("id", required=True)
        self.type = parse("type", required=False)
        self.company_name = parse("companyName", required=True)
        self.tax_id = parse("tax_id", required=False)
        self.postal_address = make_address(parse("addressPostal", required=True))
        self.postal_address_public = make_address_public(parse("addressPostal", required=True))
        self.tech_contact = make_contact(parse("techContact", required=True))
        self.tech_contact_public = make_contact_public(parse("techContact", required=True))
        self.parent = parse("parent.aps.id")

    def __repr__(self):
        return f"Account {self.oss_id}"

    def as_dict(self):
        return {
            "oss_uid": self.aps_id,
            "oss_id": str(self.oss_id),
            "type": self.type,
            "company_name": self.company_name,
            "tax_id": self.tax_id,
            "postal_address": attr.asdict(self.postal_address),
            "tech_contact": attr.asdict(self.tech_contact),
        }

    @property
    def dict(self):
        contact_info = attr.asdict(self.postal_address_public)
        contact_info["contact"] = attr.asdict(self.tech_contact_public)
        return {
            "external_uid": self.aps_id,
            "external_id": str(self.oss_id),
            "name": self.company_name,
            "tax_id": str(self.tax_id) if self.tax_id else None,
            "contact_info": contact_info,
            "type": self.type,
        }

    def as_tenant_account_info(self):
        return {
            "accountInfo": {
                "companyName": self.company_name,
                "tax_id": self.tax_id,
                "addressPostal": {
                    "countryName": self.postal_address.country_name,
                    "extendedAddress": self.postal_address.extended_address,
                    "locality": self.postal_address.locality,
                    "postalCode": self.postal_address.postal_code,
                    "region": self.postal_address.region,
                    "streetAddress": self.postal_address.street_address,
                },
                "techContact": {
                    "email": self.tech_contact.email,
                    "givenName": self.tech_contact.given_name,
                    "familyName": self.tech_contact.family_name,
                    "telVoice": self.tech_contact.telephone,
                },
            },
        }

    @staticmethod
    def from_aps_id(aps_id):
        account = OA.get_resource(aps_id)
        return Account(account)

    @staticmethod
    def from_external_scope(aps_id, impersonate_as):
        account = OA.get_resource(aps_id, impersonate_as=impersonate_as)
        return Account(account)

    @staticmethod
    def dummy():
        return Account(
            {
                "aps": {"id": None},
                "id": None,
                "type": None,
                "companyName": {},
                "tax_id": "",
                "addressPostal": {},
                "techContact": {},
            },
        )


class Subscription(object):
    aps_id = None
    oss_id = None
    name = None

    def __init__(self, subscription):
        parse = property_parser(subscription, desc="subscription")

        self.aps_id = parse("aps.id", required=True)
        self.oss_id = parse("subscriptionId", required=True)
        self.name = parse("name", required=True)

    @staticmethod
    def from_aps_id(aps_id):
        subscription = OA.get_resource(aps_id)
        return Subscription(subscription)

    @staticmethod
    def dummy():
        return Subscription({"aps": {"id": None}, "subscriptionId": None, "name": None})


class OAAccountBase(object):
    ACCOUNT_TYPE = "http://parallels.com/aps/types/pa/account/1.2"
    aps_id = None
    name = None
    type = None

    def __init__(self, data):
        self.aps_id = data["aps_id"]
        self.name = data["name"]
        if "type" in data:
            self.type = data["type"]

    def as_dict(self):
        return {"instance_id": self.aps_id, "name": self.name, "type": self.type}


class Provider(OAAccountBase):
    CORE_TYPE = "http://parallels.com/aps/types/pa/poa/1.0"

    @staticmethod
    def from_app_id(app_id):

        account = Reseller.from_app_id(app_id)
        app = OA.get_resources(
            f"/aps/2/resources/?implementing({Provider.CORE_TYPE})",
            impersonate_as=app_id,
        )[0]
        aps_id = app["aps"]["id"]

        return Provider({"aps_id": aps_id, "name": account.name})

    @staticmethod
    def dummy():
        return Provider({"aps_id": str(uuid.uuid4()), "name": "PLACEHOLDER"})


class Reseller(OAAccountBase):

    @staticmethod
    def from_app_id(app_id):
        account = OA.get_resources(
            f"/aps/2/resources/?implementing({Provider.ACCOUNT_TYPE}),eq(id,1)",
            impersonate_as=app_id,
        )[0]
        name = account["companyName"]
        reseller_uuid = account["aps"]["id"]

        return Reseller({"name": name, "aps_id": reseller_uuid})

    @staticmethod
    def get_oss_uid(initiator_id, resource_id):
        reseller_info = OA.get_resources(
            f"/aps/2/resources?implementing(http://parallels.com/aps/types/pa/user/1.0),"
            f"eq(aps.id,{initiator_id}),select(organization)",
            impersonate_as=resource_id,
        )[0]

        return reseller_info["organization"]["aps"]["id"]


class Event(object):

    def __init__(self, data, tenant_id):
        self.tenant_id = tenant_id

        parse = property_parser(data, "event")
        self.period = parse("parameters.newPeriod.period", required=True)
        self.period_type = parse("parameters.newPeriod.periodType", required=True)
        # Odin Automation sends in expirationDate the end of the billing period,
        # in other words the startDate of the new period requested
        # Please look at LITE-7289 for further details
        self.start_date = parse("parameters.expirationDate") or parse(
            "parameters.startDate", required=True,
        )

    def as_request_data(self):
        return {
            "subscription": {"oss_uid": self.tenant_id},
            "type": request_types.billing,
            "parameters": {
                "period": self.period,
                "period_type": self.period_type,
                "start_date": self.start_date,
            },
        }

    @property
    def billing_data(self):
        return {
            "period": self.period,
            "period_type": self.period_type,
            "start_date": self.start_date,
        }


class Product(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.name = kwargs.get("name")
        self.icon = kwargs.get("icon")


class TierConfig(object):
    LEVEL_SCOPE_MAP = {1: "tier1", 2: "tier2"}

    def __init__(self, data):
        parse = property_parser(data, "tier_config")
        self.id = parse("id", required=True)
        self.name = parse("name", default="")
        self.params = parse("params", required=True)
        self.product = Product(**parse("product", required=True))
        self.tier_level = parse("tier_level", required=True)
        self.open_request = parse("open_request")
        self.template = parse("template")
        self.account = parse("account")
        self.connection = parse("connection")
        self.actions = get_actions(self.product.id, self.scope)

    @property
    def scope(self):
        return self.LEVEL_SCOPE_MAP[int(self.tier_level)]

    @property
    def serialize(self):
        self.product = {"id": self.product.id, "name": self.product.name}
        return self.__dict__


class TierConfigRequest(object):

    def __init__(self, data):
        parse = property_parser(data, "tier_config_request")
        self.id = parse("id", required=True)
        self.type = parse("type", required=True)
        self.status = parse("status", required=True)
        self.params = parse("params", required=True)
        self.events = parse("events", default={})
        self.assignee = parse("assignee")
        self.environment = parse("environment")
        self.activation = parse("activation")
        self.configuration = TierConfig(parse("configuration", required=True))

    @property
    def serialize(self):
        self.configuration = self.configuration.serialize
        return self.__dict__


class DraftRequest(object):

    def __init__(self, data, app_id=None):
        parse = property_parser(data, desc="draft")

        self.app_id = app_id
        self.draft_request_id = parse("draftRequestId")
        self.assetId = parse("assetId")
        self.parameters = {}
        self.parameters, self.params = extract_activation_params(
            parse(
                "activationParams",
                default=[],
            ),
        )

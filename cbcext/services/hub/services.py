import os
from datetime import datetime
from json.decoder import JSONDecodeError
from xml.etree import ElementTree as XML_et

from requests_toolbelt.multipart.encoder import MultipartEncoder
from starlette_context import context as g

from cbcext.models.fulfillment_models import Account, Provider
from cbcext.services.client.oaclient import OA, OACommunicationException
from cbcext.services.db_services import (
    fetch_hub_uuid_by_app_id,
    update_or_create_hub_instance,
)

from connect.client import ClientError


def fetch_hub_data_from_connect(hub_uuid):
    """
    Fetches a hub info from Connect Public API
    :raises: ClientError
    """
    resp = g.client.hubs.filter(f'eq(instance__id,{hub_uuid})').first()
    return resp if resp else {}


def fetch_hub_uuid_from_oa(app_id):
    """
    Fetches APS Root resource and returns its APS UUID.
    """
    provider = Provider.from_app_id(app_id)
    return provider.aps_id


def schedule_healthcheck_in_oa(app_id):
    """
    Schedules healthcheck task in OA bound to target application.
    """
    resp = OA.schedule_task(
        task_name='Connect healthcheck',
        resource_id=app_id,
        period=305,
    )
    return resp


def schedule_usage_chunks_retrival_in_oa(app_id):
    '''
    Schedules daily poll for getting open chunk files in OA
    This will always be scheduled, but only working in OSA > 8.3
    '''
    resp = OA.schedule_task(
        task_name='Connect Chunk Usage Files retrieval',
        resource_id=app_id,
        period=86400,
    )
    return resp


def subscribe_on_account_data_changes(app_id):
    """
    Subscribe to notifications about changes of accounts belonging to Root Resource (all accounts)
    in OA.
    """
    OA.subscribe_on(
        resource_id=app_id,
        event_type='http://aps-standard.org/core/events/changed',
        handler='accountDataChange',
        source_type='http://aps-standard.org/types/core/account/1.0',
        transaction=True,
        impersonate_as=app_id,
    )


def subscribe_on_account_creation(app_id):
    """
    Subscribe to notifications about creation of accounts to link them and be able to get
    account data changes in accounts not directly owned by provider.
    """

    OA.subscribe_on(
        resource_id=app_id,
        event_type='http://aps-standard.org/core/events/available',
        handler='accountDataChange',
        source_type='http://aps-standard.org/types/core/account/1.0',
        transaction=True,
        impersonate_as=app_id,
    )


def fetch_chunk_files_by_hub_id(app_id, status="ready"):
    """
    Fetches usage files by given hub and given status
    """
    hub_uuid = fetch_hub_uuid_by_app_id(db=g.db, app_id=app_id)
    hub = fetch_hub_data_from_connect(hub_uuid)

    return g.client.ns(
        'usage',
    ).collection(
        'chunks',
    ).filter(
        f'status={status}&binding.hub.id={hub["id"]}',
    )


def close_chunk_file(chunk_file_id, billing_id, note):
    """closes a chunk file given it's id"""
    g.client.ns(
        'usage',
    ).collection(
        'chunks',
    ).resource(
        chunk_file_id,
    ).action('close').post(
        payload={
            'external_billing_id': str(billing_id),
            'external_billing_note': str(note),
        },
    )


def fetch_product_from_connect(product_id):
    """
    Fetches product from Connect Public API
    """
    resp = g.client.products[product_id].get()

    if resp and (
            resp['visibility']['listing'] is True or resp['visibility']['syndication'] is True
    ):
        return resp

    return {}


def fetch_product_item_by_local_id(product_id, local_id):
    """
    Fetches the Connect Item for a given product based on local_id,
    local_id is key on aps tenant schema
    """
    resp = g.client.products[product_id].items.filter(f'local_id={local_id}').first()
    return resp or {}


def fetch_product_connections(product_id, hub_id):
    """
    Returns product connections for given product and hub
    """
    resp = g.client.products[product_id].connections.filter('ne(hub.id,null())')

    for connection in resp:
        if 'hub' in connection and connection['hub']['id'] == hub_id:
            return connection
    return {}


def ping_oa(app_id):  # noqa: CCR001
    """
    Pings OSA to see if all is ok, including proxy communication
    Obtains also extension version and OA Version, with it it updates hub info on Connect side
    It may notify client that new version of HUB APP Extension is available
    :param app_id: str
    :return: dict, including status and warning in case of upgrade available
    :raises OA Communication Exception
    """
    try:
        aps_versions = OA.send_request(
            method='GET',
            path='/aps',
            transaction=False,
            impersonate_as=app_id,
            retry_num=2,
            timeout=60,
        )
        aps_version_max_value = max(
            aps_versions.get('versions').items(),
            key=lambda x: int(x[1].get('version').replace(".", "")),
        )
        oa_version = aps_version_max_value[1].get('version')
        extension_resource = OA.send_request(
            method='GET',
            path='/aps/2/resources/{app_id}'.format(app_id=app_id),
            transaction=False,
            impersonate_as=app_id,
            retry_num=2,
            timeout=60,
        )
        installed_extension_app_meta = OA.send_request(
            method='GET',
            path=extension_resource['aps']['package']['href'],
            impersonate_as=app_id,
            retry_num=2,
            timeout=60,
        )
        extension_version = float(installed_extension_app_meta.get('version'))
        extension_release = int(installed_extension_app_meta.get('release'))
        tree = XML_et.ElementTree(
            file=os.path.join(
                os.path.dirname(__file__),
                'aps_package/src/APP-META.xml',
            ),
        )
        ns = '{http://aps-standard.org/ns/2}'
        latest_version = float(tree.find('{ns}version'.format(ns=ns)).text)
        latest_release = int(tree.find('{ns}release'.format(ns=ns)).text)
        connect_update_hub_health_check(
            app_id=app_id,
            oa_version=oa_version,
            extension_version="{version}-{release}".format(
                version=extension_version,
                release=extension_release,
            ),
        )
        if (
                extension_version < latest_version
        ) or (
                extension_version == latest_version and extension_release < latest_release
        ):
            info = "New version {ver}-{rel} of CloudBlue Connect Extension available"
            return True, info.format(
                ver=latest_version,
                rel=latest_release,
            ), False

    except JSONDecodeError:
        return False, "APSC didn't answer with JSON.", False
    except OACommunicationException as e:
        return False, "Failed to reach APSC: {error}".format(error=str(e)), False

    update_external_identifiers = check_external_identifiers_update_required(app_id)

    return True, None, update_external_identifiers


def connect_update_hub_health_check(
        app_id,
        oa_version,
        extension_version,
):
    """
    updates HUB data relative to healthcheck obtained information
    :param app_id: str
    :param oa_version: str
    :param extension_version: str
    :return:
    """
    try:
        hub_uuid = fetch_hub_uuid_by_app_id(db=g.db, app_id=app_id)

        connect_hub = fetch_hub_data_from_connect(hub_uuid)
        connect_hub['version'] = str(oa_version)
        connect_hub['extension_version'] = str(extension_version)
        connect_hub['last_health_check'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        g.client.hubs[connect_hub['id']].update(connect_hub)

        # Update local database hub_instances to track controller uris
        update_or_create_hub_instance(
            db=g.db,
            hub_id=connect_hub['id'],
            app_instance_id=g.source_request.headers.get('APS_INSTANCE_ID'),
            ext_resource=hub_uuid,
            uri=g.source_request.headers.get('APS_CONTROLLER_URI'),
        )

    except ClientError:
        pass


def get_oa_usage_adapter_manager(app_id):
    """
    Obtains Usage adap
    :param app_id:
    :return:
    """
    try:
        usage_adapter_type = "http://com.odin.rating/usage-adapter-manager/1.0"
        instance_manager = OA.get_resources(
            rql_request="/aps/2/resources?implementing({type})".format(type=usage_adapter_type),
            impersonate_as=app_id)
        if len(instance_manager) == 1:
            return instance_manager[0]['aps']['id']
        return None
    except OACommunicationException:
        return None


def get_usage_files_from_oa(
        app_id,
        usage_adapter_manager_uuid,
        report_id,
        status=None,
):
    """
    Obtains list of usage reports based on a concrete id
    :param app_id: str uuid
    :param usage_adapter_manager_uuid: str uuid
    :param report_id: Connect Usage file ID
    :param status:
    :return:
    """
    try:
        if status:
            rql = '/{adapter}/usageReportsList?and(eq(reportId,{id}),eq(status,{status}))'
            rql = rql.format(
                adapter=usage_adapter_manager_uuid,
                id=report_id,
                status=status,
            )
        else:
            rql = '/{adapter}/usageReportsList?eq(reportId,{id})'
            rql = rql.format(
                adapter=usage_adapter_manager_uuid,
                id=report_id,
            )
        reports = OA.get_resources(
            rql_request='/aps/2/resources' + rql,
            impersonate_as=app_id,
        )
        return reports if reports else []
    except OACommunicationException:
        return []


def get_usage_chunk_file_content(chunk_file_id):
    return g.client.ns(
        'usage',
    ).collection(
        'chunks',
    ).resource(
        chunk_file_id,
    ).action(
        'download',
    ).get()


def update_chunk_file_external_id(chunk_file_id, external_id):
    """
    Sets the external_id to a given chunk file id
    :param chunk_file_id: str
    :param external_id: str
    :return: None
    """
    update_body = {
        'external_id': external_id,
    }
    g.client.ns('usage').collection('chunks').resource(chunk_file_id).update(payload=update_body)


def upload_to_oa(
        app_id,
        usage_adapter,
        chunk_file_id,
        stream,
):
    """
    Uploads usage file
    :param app_id: str uuid
    :param usage_adapter: str uuid
    :param chunk_file_id: str
    :param stream: usage file stream
    :return: None
    :raises OACommunicationException
    """
    try:
        location = 'aps/2/resources/{adapter_uid}/usageReports'.format(adapter_uid=usage_adapter)
        body = MultipartEncoder(
            fields={
                "files": ('{id}.xlsx'.format(id=chunk_file_id),
                          stream,
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          ),
            },
            boundary="usagefile",
        )
        headers = {"Content-Type": body.content_type}
        OA.send_request(
            'POST',
            location,
            impersonate_as=app_id,
            headers=headers,
            body=body,
            binary=True,
        )
        uploaded = True
    except OACommunicationException:
        uploaded = False
        try:
            update_chunk_file_external_id(
                chunk_file_id,
                "Error while uploading to Commerce, please try manual operation",
            )
        except ClientError:
            pass
    return uploaded


def get_oa_aps_openapi_adapter(app_id):
    """
    Provides open api adapter UUID to interact with it
    :param app_id: str uuid
    :return: str uuid
    """
    try:
        usage_adapter_type = "http://connect.cloudblue.com/aps-openapi-adapter/app/1.0"
        instance_manager = OA.get_resources(
            rql_request="/aps/2/resources?implementing({adapter_type})".format(
                adapter_type=usage_adapter_type,
            ),
            impersonate_as=app_id)
        if len(instance_manager) == 1:
            return instance_manager[0]['aps']['id']
        return None
    except OACommunicationException:
        return None


def aps_openapi_adapter_get_application_id(
        app_id,
        openapi_adapter,
        product_id,
):
    """
    Returns app instance ID for a given product if deployed
    :param app_id: string
    :param openapi_adapter: string
    :param product_id: string
    :return dict:
    """
    try:
        if product_id == "extension":
            product_aps_id = "http://odin.com/servicesSelector"
        else:
            product_aps_id = "http://aps.odin.com/app/{product}".format(
                product=product_id,
            )
        location = 'aps/2/resources/{adapter}/getApplicationId?package_id={aps_package}'.format(
            adapter=openapi_adapter,
            aps_package=product_aps_id,
        )
        return OA.send_request(
            method='GET',
            path=location,
            impersonate_as=app_id,
        )
    except OACommunicationException:
        return None


def aps_openapi_adapter_get_instances(
        app_id,
        openapi_adapter,
        oa_app_id,
):
    """
    Returns application instances for a given application using openapi adapter
    :param app_id: str uuid
    :param openapi_adapter: str uuid
    :param oa_app_id: int
    :return: dict containing app_id
    """
    try:
        location = 'aps/2/resources/{adapter}/getApplicationInstances?application_id={app}'.format(
            adapter=openapi_adapter,
            app=oa_app_id,
        )
        return OA.send_request(
            method='GET',
            path=location,
            impersonate_as=app_id,
        )
    except OACommunicationException:
        return None


def aps_openapi_adapter_import_package(
        app_id,
        openapi_adapter,
        package_url,
):
    """
    Import aps package to OSA using adapter
    :param app_id: str uuid
    :param openapi_adapter: str uuid
    :param package_url: where aps package can be found
    :return:
    """
    body = {
        'package_url': package_url,
    }

    return OA.send_request(
        method='POST',
        path='aps/2/resources/{adapter}/importPackage'.format(adapter=openapi_adapter),
        body=body,
        impersonate_as=app_id,
    )


def aps_openapi_adapter_create_instance(
        app_id,
        package,
        oauth_key,
        oauth_secret,
        backend_url,
):
    """
    Creates application instance using APS bus
    :param app_id: str uuid
    :param package: str Product id from connect
    :param oauth_key: str
    :param oauth_secret: str
    :param backend_url: str
    :return: dict representing aps resource of app
    """
    body = {
        'aps': {
            'package': {
                'type': 'http://aps.odin.com/app/{product}'.format(product=package),
            },
            'endpoint': backend_url,
            'network': 'proxy',
            'auth': {
                'oauth': {
                    'key': oauth_key,
                    'secret': oauth_secret,
                },
            },
        },
    }

    return OA.send_request(
        method='POST',
        body=body,
        path='aps/2/applications',
        impersonate_as=app_id,
        transaction=False,
    )


def create_core_types(app_id, openapi_adapter, oa_app_id, oa_instance_uuid, product_name):
    """
    Creates app service reference to app and tenant service for it
    :param app_id: str uuid
    :param openapi_adapter: str uuid
    :param oa_app_id: int
    :param oa_instance_uuid: str uuid
    :param product_name: str
    :return: list of int, always 2 items
    """
    rt_ids = []
    core_resource_types_payload = [
        {
            'resclass_name': 'rc.saas.service.link',
            'name': '{product_name} app instance'.format(product_name=product_name),
            'act_params': [
                {
                    'var_name': 'app_id',
                    'var_value': str(oa_app_id),
                },
                {
                    'var_name': 'resource_uid',
                    'var_value': oa_instance_uuid,
                },
            ],
        },
        {
            'resclass_name': 'rc.saas.service',
            'name': '{product_name} tenant'.format(product_name=product_name),
            'act_params': [
                {
                    'var_name': 'app_id',
                    'var_value': str(oa_app_id),
                },
                {
                    'var_name': 'service_id',
                    'var_value': 'tenant',
                },
                {
                    'var_name': 'autoprovide_service',
                    'var_value': '1',
                },
            ],
        },
    ]
    for t in core_resource_types_payload:
        result = OA.send_request(
            method='POST',
            path='aps/2/resources/{adapter}/addResourceType'.format(adapter=openapi_adapter),
            impersonate_as=app_id,
            body={
                'rt_structure': t,
            },
        )
        rt_ids.append({
            'name': t['name'],
            'class': t['resclass_name'],
            'limit': 1,
            'local_id': "",
            'id': result['resource_type_id'],
        })
    return rt_ids


def exists_item_profile_resource(app_id, product_id, item_profile_version):
    """
    Returns existance of any item profile for given product in OA
    :param app_id: str uuid
    :param product_id: str in form of Connect product ID
    :param item_profile_version: version
    :return: bool
    """
    data = OA.send_request(
        method='GET',
        path='aps/2/resources?implementing(http://aps.odin.com/app/{prod}/{type}/{ver}.0)'.format(
            prod=product_id,
            type="itemProfile",
            ver=item_profile_version,
        ),
        impersonate_as=app_id,
    )
    if len(data) > 0:
        return True
    return False


def get_existing_ref_rts(app_id, openapi_adapter, oa_app_id):
    """
    Gets from OA all resources for given app of class counted service reference
    :param app_id: str uuid
    :param openapi_adapter: str uuid
    :param oa_app_id: int
    :return: list of oa rt
    """
    rts = _get_oa_rts_by_class(app_id, openapi_adapter, 'rc.saas.countedlenk')
    existing_resources = []
    for resource in rts:
        aps_rt = _get_oa_rt(app_id, resource['resource_type_id'])
        if 'app_id' in aps_rt['activationParameters'] and int(
                aps_rt['activationParameters']['app_id'],
        ) == int(oa_app_id):
            existing_resources.append(aps_rt['activationParameters']['resource_id'])
    return existing_resources


def get_existing_counter_rts(app_id, openapi_adapter, oa_app_id):
    """
    Gets all existing resources for a given OA App
    :param app_id: str uuid
    :param openapi_adapter: str uuid
    :param oa_app_id: int
    :return: list of oa rt ids
    """
    existing_resources = []
    rt_classes = ['rc.saas.resource.kbps',
                  'rc.saas.resource',
                  'rc.saas.resource.mbh',
                  'rc.saas.resource.mhz',
                  'rc.saas.resource.mhzh',
                  'rc.saas.resource.unit',
                  'rc.saas.resource.unith',
                  ]
    for rt_class in rt_classes:
        rts = _get_oa_rts_by_class(app_id, openapi_adapter, rt_class)

        for resource in rts:
            aps_rt = _get_oa_rt(app_id, resource['resource_type_id'])
            if 'app_id' in aps_rt['activationParameters'] and int(
                    aps_rt['activationParameters']['app_id'],
            ) == int(oa_app_id):
                existing_resources.append(aps_rt['activationParameters']['resource_id'])
    return existing_resources


def _get_oa_rt(app_id, rt_id):
    """
    Obtains resource from OA given it's id
    :param app_id: str UUID
    :param rt_id: int
    :return:
    """
    return OA.send_request(
        method='GET',
        path='aps/2/services/resource-type-manager/resourceTypes/{rt_id}'.format(
            rt_id=rt_id,
        ),
        impersonate_as=app_id,
    )


def _get_oa_rts_by_class(app_id, openapi_adapter, rt_class):
    """
    gets from OA all resources for given class, it does not except more filtering
    :param app_id: uuid
    :param openapi_adapter: uuid
    :param rt_class: string oa resource class
    :return:
    """
    return OA.send_request(
        method='GET',
        path='aps/2/resources/{adapter}/getResourceTypesByClass?rc_class={rt_class}'.format(
            adapter=openapi_adapter,
            rt_class=rt_class,
        ),
        impersonate_as=app_id,
        transaction=False,
    )


def fetch_product_items_from_connect(product_id, get_end_of_sale=False):
    """
    Fetches all product items from connect
    :raises: ClientError
    """
    urlfilter = "in(type,(Reservation,PPU))&eq(dynamic,false)&in(status,(published))"
    if get_end_of_sale:
        urlfilter = "in(type,(Reservation,PPU))&eq(dynamic,false)&in(status,(published,endofsale))"

    return list(
        g.client.products[product_id].items.filter(urlfilter),
    )


def create_item_profile(
        app_id,
        product_id,
        connect_item,
        profile_version,
):
    """
    Creates item profile on APS side based on a given product
    :param app_id: string
    :param product_id: string in PRD form
    :param profile_version: int
    :param connect_item: item as obtained from connect API
    :return: aps resource
    """
    payload = {
        'aps': {
            'type': 'http://aps.odin.com/app/{prod}/{service}/{profile_version}.0'.format(
                prod=product_id,
                profile_version=profile_version,
                service="itemProfile",
            ),
        },
        'profileName': connect_item['display_name'],
        'mpn': connect_item['mpn'],
        'itemId': connect_item['id'],
    }

    return OA.send_request(
        method='POST',
        path='aps/2/resources',
        impersonate_as=app_id,
        body=payload,
        transaction=False,
    )


def fetch_tier_account_from_connect(account_uuid):
    """
    Fetches a tier account from Connect Public API by account_uuid.

    :rtype: dict
    :raises: ClientError
    """
    resp = g.client.ns('tier').collection('accounts').filter(f'external_uid={account_uuid}').first()
    return resp if resp else {}


def fetch_account_data_from_oa(account_uuid, app_id, get_vat=False):
    """
    Fetches account details from OA via APS Bus.

    :rtype: connector.v1.models.Account
    """
    account_resp = OA.get_resource(account_uuid, impersonate_as=app_id)
    if get_vat:
        from cbcext.services.vat import Vat
        vat = Vat(app_id)
        vat_code = vat.get_vat_code(account_resp['aps']['id'])
        if vat_code:
            account_resp['tax_id'] = vat_code
    return Account(account_resp)


def send_tier_account_request_to_connect(oa_account, connect_tier_account):
    """
    Posts tier account request to Connect Public API.

    :param connector.v1.models.Account oa_account: account with updated information.
    :param dict connect_tier_account: Connect Public API representation of tier account.

    :raises: ClientError
    """

    account_data = oa_account.dict
    if tier_account_needs_update(account_data, connect_tier_account):
        account_data.update({'id': connect_tier_account['id']})
        tier_request_body = {
            'type': 'update',
            'account': account_data,
        }
        g.client.ns('tier').collection('account-requests').create(payload=tier_request_body)


def tier_account_needs_update(oa_account_data, connect_tier_account):

    oa_flat = dict_flatten(oa_account_data)
    connect_ta_flat = dict_flatten(connect_tier_account)

    to_skip = [
        'external_uid',
        'external_id',
        'type',
    ]

    for key in oa_flat.keys():
        if key == 'tax_id' and oa_flat.get('tax_id', '') and (
                oa_flat.get('tax_id', '') != connect_ta_flat.get('tax_id', '')
        ):
            return True
        elif key in to_skip or key not in connect_ta_flat:
            continue
        elif connect_ta_flat[key] != oa_flat[key]:
            return True

    return False


def dict_flatten(dictionary, base_key=''):
    ret = {}
    for rkey, val in dictionary.items():
        key = base_key + rkey
        if isinstance(val, dict):
            ret.update(dict_flatten(val, key + '.'))
        else:
            ret[key] = val
    return ret


def get_init_wizard_editor(app_id):
    """
    Gets instance of platform component called edit-wizard-management
    :return: string
    """

    editor_type = 'http://odin.com/edit-wizard/edit-wizard-management/1'
    try:
        editor_request = OA.send_request(
            method='GET',
            path='aps/2/resources?implementing({type})'.format(
                type=editor_type,
            ),
            impersonate_as=app_id,
            transaction=False,
        )
        if len(editor_request) >= 1:
            return editor_request[0]['aps']['id']
        return None
    except OACommunicationException:
        return None


def get_platform_resources_over_editor(
        app_id,
        editor_id,
        app_instance_id,
        oa_app_id,
        get_in_id=None,
):
    """
    For a given app APS instance_id, returns list of existing RT of any class except core ones
    :param app_id: UUID
    :param editor_id: UUID
    :param app_instance_id: UUID
    :param oa_app_id: INT
    :param get_in_id: Bool
    :return: list
    """

    def _is_not_discard(res):
        classes_to_discard = ['rc.saas.service.link', 'rc.saas.service']
        return res['resClass'] not in classes_to_discard

    def _is_current_app(rt, app_id):
        return 'resource_id' in rt['actParams'] and int(rt['actParams']['app_id']) == app_id

    resources_request = OA.send_request(
        method='GET',
        path='aps/2/resources/{editor_uid}/getWizardData/{instance}'.format(
            editor_uid=editor_id,
            instance=app_instance_id,
        ),
        impersonate_as=app_id,
        transaction=False,
    )
    platform_items = []
    if 'resourceTypes' in resources_request:
        for rt in resources_request['resourceTypes']:
            if _is_not_discard(rt) and _is_current_app(rt, oa_app_id):
                if get_in_id is None:
                    platform_items.append(rt['actParams']['resource_id'])
                else:
                    platform_items.append(rt['id'])
    return platform_items


def check_external_identifiers_update_required(app_id):
    """
    Verifies if external identifiers core type is up to date
    This type is updated from time to time and only latest versions
    gets it without manual update
    :return: boolean
    """

    latest_version = 'http://aps-standard.org/types/core/external/identifiers/1.2'
    try:
        installed_type = OA.send_request(
            method='GET',
            path='aps/2/types?id={type}'.format(
                type=latest_version,
            ),
            impersonate_as=app_id,
            transaction=False,
        )
        for version in installed_type:
            if latest_version == version.get('id'):
                return False
        return True
    except OACommunicationException:
        return None

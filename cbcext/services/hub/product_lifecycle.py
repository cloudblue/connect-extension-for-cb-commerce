import concurrent.futures
import datetime

from fastapi.responses import JSONResponse
from starlette_context import context as g

from cbcext.services.client.oaclient import OA, OACommunicationException
from cbcext.services.exceptions import TokenException
from .services import (
    aps_openapi_adapter_create_instance,
    aps_openapi_adapter_get_application_id,
    aps_openapi_adapter_get_instances,
    aps_openapi_adapter_import_package,
    create_core_types,
    create_item_profile,
    exists_item_profile_resource,
    fetch_hub_data_from_connect,
    fetch_hub_uuid_by_app_id,
    fetch_product_connections,
    fetch_product_from_connect,
    fetch_product_items_from_connect,
    get_existing_counter_rts,
    get_existing_ref_rts,
    get_init_wizard_editor,
    get_oa_aps_openapi_adapter,
    get_platform_resources_over_editor,
)
from .utils import (
    get_resclass_name,
    get_st_representation,
    make_aps_headers_reschedule,
    split_in_chunks,
)

from connect.client import ClientError


class InitTask:
    """
    Class in charge of handling the init tasks, either can perform installation or upgrade
    of products or extension itself
    """
    phase = ""
    data = []
    oa_aps_openapi_adapter = ""
    hub_data = []
    hub_uuid = ""
    operation = ""
    product_id = ""
    app_id = ""
    step = ""
    retries = 0
    aps_transaction_id = None

    @staticmethod
    def handle_delete():
        return JSONResponse(content={}, status_code=204)

    @staticmethod
    def _validate_post(data):
        required_fields = (
            'productId',
            'operation',
            'aps',
            'globals',
        )
        if not all(data.get(key) for key in required_fields):
            return False
        return True

    def handle_create_init_task(self):
        self.data = g.source_request.json
        if not self._validate_post(self.data):
            return JSONResponse(
                content={
                    "message": "missing input parameters",
                },
                status_code=400,
            )
        self.phase = g.source_request.headers.get("aps-request-phase", "sync")
        self.app_id = self.data['globals']['aps']['id']
        self.oa_aps_openapi_adapter = None
        self.hub_uuid = None
        self.hub_data = None
        self.operation = self.data['operation']
        self.product_id = self.data['productId']
        self.step = self.data['step'] if 'step' in self.data else None
        self.retries = self.data['retries'] if 'retries' in self.data else 0
        self.aps_transaction_id = g.source_request.headers.get("Aps-Transaction-Id")

        if self.phase == "sync":
            if self.operation == "install" or self.operation == "upgrade":
                self.data['step'] = "import"
                return JSONResponse(
                    content=self.data,
                    status_code=202,
                    headers=make_aps_headers_reschedule(
                        delay=30,
                        message="Moving to import phase",
                        transaction_id=self.aps_transaction_id,
                    ),
                )

            return JSONResponse(content={"message": "unsupported operation"}, status_code=400)
        # Async Phase
        self.oa_aps_openapi_adapter = get_oa_aps_openapi_adapter(self.app_id)
        self.hub_uuid = fetch_hub_uuid_by_app_id(
            db=g.db,
            app_id=self.data['globals']['aps']['id'],
        )
        self.hub_data = fetch_hub_data_from_connect(self.hub_uuid)
        try:
            return self._run_current_step()

        except OACommunicationException:
            return JSONResponse(
                content={
                    "message": "Error while communicating with hub",
                    "type": "error",
                },
                status_code=400,
            )

        except ClientError:
            # In case of Connect API error, we reschedule task
            return JSONResponse(content=self.data, status_code=202)

    def _run_current_step(self):
        """
        This function controls the state machine
        """
        if self.step == "import":
            return self._import()
        elif self.step == "create_instance":
            return self._create_instance()
        elif self.step == "create_core_rts":
            return self._create_core_rts()
        elif self.step == "create_rts":
            return self._create_item_rts()
        elif self.step == "create_st":
            return self._create_st()
        elif self.step == "apply_st_limits":
            return self._apply_st_limits()
        elif self.step == "upgrade_instance":
            return self._upgrade_instance()
        elif self.step == "wait_upgrade_complete":
            return self._wait_upgrade_complete()
        elif self.step == "create_st_rest":
            return self._create_st_rest()
        elif self.step == "apply_st_limits_rest":
            return self._apply_st_limits_rest()
        else:
            return JSONResponse(content={"message": "Unsupported Step"}, status_code=500)

    def _import(self):
        """
        Imports an APS package in OA
        """
        if self.product_id == "extension":
            hub_info = fetch_hub_data_from_connect(self.hub_uuid)
            aps_openapi_adapter_import_package(
                app_id=self.app_id,
                openapi_adapter=self.oa_aps_openapi_adapter,
                package_url="{url}/apspackage".format(
                    url=hub_info['creds']['url'],
                ),
            )
            self.data['step'] = "upgrade_instance"
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    delay=30,
                    message="Moving to upgrade instance",
                    transaction_id=self.aps_transaction_id,
                ),
            )

        connection = fetch_product_connections(product_id=self.product_id,
                                               hub_id=self.hub_data['id'])
        aps_openapi_adapter_import_package(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            package_url=connection['frontend_url'],
        )
        if self.operation == 'install':
            self.data['step'] = "create_instance"
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    delay=30,
                    message="Moving to instance creation phase",
                    transaction_id=self.aps_transaction_id,
                ),
            )
        self.data['step'] = "upgrade_instance"
        return JSONResponse(
            content=self.data,
            status_code=202,
            headers=make_aps_headers_reschedule(
                delay=30,
                message="Moving to upgrade instance",
                transaction_id=self.aps_transaction_id,
            ),
        )

    def _create_instance(self):
        """
        Creates an APS instance in OA
        """
        oa_app_id = aps_openapi_adapter_get_application_id(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            product_id=self.product_id,
        )
        if oa_app_id is None and self.retries < 3:
            self.data['retries'] = self.data['retries'] + 1
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    delay=60,
                    message="Retrying instance creation step",
                    transaction_id=self.aps_transaction_id,
                ),
            )
        elif oa_app_id is None and self.retries >= 3:
            return JSONResponse(
                content={"message": "Application has not imported, please check tasks on OA"},
                status_code=400,
            )

        connection = fetch_product_connections(product_id=self.product_id,
                                               hub_id=self.hub_data['id'])
        aps_openapi_adapter_create_instance(
            app_id=self.app_id,
            package=self.product_id,
            oauth_key=connection['oauth_key'],
            oauth_secret=connection['oauth_secret'],
            backend_url=connection['endpoint_url'],
        )
        self.data['retries'] = 0
        self.data['step'] = "create_core_rts"
        return JSONResponse(
            content=self.data,
            status_code=202,
            headers=make_aps_headers_reschedule(
                delay=30,
                message="Moving to creation of core resource types",
                transaction_id=self.aps_transaction_id,
            ),
        )

    def _create_core_rts(self):
        """
        Creates 2 Resource types, one app service reference to globals (app instance)
        and app service that represents the tenant service
        :return:
        """
        oa_app_id = aps_openapi_adapter_get_application_id(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            product_id=self.product_id,
        )
        app_instances = aps_openapi_adapter_get_instances(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            oa_app_id=oa_app_id['app_id'],
        )
        product = fetch_product_from_connect(product_id=self.product_id)
        if app_instances is None or len(app_instances) == 0:
            self.data['step'] = "create_instance"
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    delay=30,
                    message="Moving to create instance due has been removed",
                    transaction_id=self.aps_transaction_id,
                ),
            )
        self.data['rts'] = create_core_types(app_id=self.app_id,
                                             openapi_adapter=self.oa_aps_openapi_adapter,
                                             oa_app_id=oa_app_id['app_id'],
                                             oa_instance_uuid=app_instances[0][
                                                 'application_resource_id'],
                                             product_name=product['name'])
        self.data['step'] = 'create_rts'
        return JSONResponse(
            content=self.data,
            status_code=202,
            headers=make_aps_headers_reschedule(
                delay=30,
                message="Moving to Resource types creation",
                transaction_id=self.aps_transaction_id,
            ),
        )

    def _sync_items_created(self):
        """
        Ini some cases, caused by OA returning exception, but in fact all was successful,
        may happen that we lost track of some resource type we added, we will add them back
        to self.data['rts'] as counted service references since we know that this only can
        happen on install, not on upgrade since there we don't add back resources to ST
        :return:
        """
        oa_app_id = aps_openapi_adapter_get_application_id(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            product_id=self.product_id,
        )
        editor_service = get_init_wizard_editor(self.app_id)
        app_instances = aps_openapi_adapter_get_instances(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            oa_app_id=oa_app_id['app_id'],
        )
        platform_items = get_platform_resources_over_editor(
            app_id=self.app_id,
            editor_id=editor_service,
            app_instance_id=app_instances[0]['application_resource_id'],
            oa_app_id=oa_app_id['app_id'],
            get_in_id=True,
        )

        data_ids = tuple((x['id'] for x in self.data['rts']))
        missing_items = filter(lambda pi: pi not in data_ids, platform_items)
        for item in missing_items:
            self.data['rts'].append(
                {
                    "id": item,
                    "name": "",
                    "class": "rc.saas.service.link",
                    "limit": 0,
                    "local_id": "",
                },
            )

    def _get_platform_items(self, use_item_profile, oa_app_id):
        """
        Obtains the platform items given an APP ID
        :param use_item_profile: boolean
        :param oa_app_id: int
        """
        editor_service = get_init_wizard_editor(self.app_id)
        if editor_service is not None:
            app_instances = aps_openapi_adapter_get_instances(
                app_id=self.app_id,
                openapi_adapter=self.oa_aps_openapi_adapter,
                oa_app_id=oa_app_id['app_id'],
            )
            platform_items = get_platform_resources_over_editor(
                app_id=self.app_id,
                editor_id=editor_service,
                app_instance_id=app_instances[0]['application_resource_id'],
                oa_app_id=oa_app_id['app_id'],
            )
        else:
            if use_item_profile:
                platform_items = get_existing_ref_rts(
                    app_id=self.app_id,
                    openapi_adapter=self.oa_aps_openapi_adapter,
                    oa_app_id=oa_app_id['app_id'],
                )
            else:
                platform_items = get_existing_counter_rts(
                    app_id=self.app_id,
                    openapi_adapter=self.oa_aps_openapi_adapter,
                    oa_app_id=oa_app_id['app_id'],
                )
        return platform_items

    def _use_item_profile(self, product):
        """
        Checks if usage of item profiles is possible, that must be true always on install
        only is checked in upgrade due backwards compatibility reasons with counters
        :param product:
        """
        if self.operation == "upgrade":
            use_item_profile = exists_item_profile_resource(
                app_id=self.app_id,
                product_id=self.product_id,
                item_profile_version=99,
            )
            if not use_item_profile:
                use_item_profile = exists_item_profile_resource(
                    app_id=self.app_id,
                    product_id=self.product_id,
                    item_profile_version=product['version'],
                )
            return use_item_profile
        return True

    def _create_items_rts_async(
            self,
            chunk,
            use_item_profile,
            oa_app_id,
            version,
    ):
        """
        Creates resource types in oa representing items, it accepts a chunk (list of items) to
        process them in parallel using threads
        :param chunk: list
        :param use_item_profile: bool
        :param oa_app_id: int
        :param version: int
        """
        responses = []
        exceptions = []
        futures = []

        def _create_product_item(
                product_item,
                use_item_profile,
                oa_app_id,
                version,
        ):
            """
            Creates Single item in OA, called by the parent function copying on each one the request
            :param product_item: item
            :param use_item_profile: bool
            :param oa_app_id: int
            :param version: int
            """
            # Title is limited to 250 characters if platform is >= 20.4 with HF for OA-16136
            # Unfortunately only way to detect that is via "try and error"
            # was decided that we will do that even that is not optimal
            title = product_item['name'][:250]
            if use_item_profile:
                try:
                    aps_item = create_item_profile(
                        app_id=self.app_id,
                        product_id=self.product_id,
                        connect_item=product_item,
                        profile_version=99,
                    )
                except OACommunicationException:
                    aps_item = create_item_profile(
                        app_id=self.app_id,
                        product_id=self.product_id,
                        connect_item=product_item,
                        profile_version=version,
                    )
                oa_unit_type = 'rc.saas.countedlenk'
                payload = {
                    'resclass_name': oa_unit_type,
                    'name': title,
                    'act_params': [
                        {
                            'var_name': 'app_id',
                            'var_value': str(oa_app_id),
                        },
                        {
                            'var_name': 'resource_uid',
                            'var_value': str(aps_item['aps']['id']),
                        },
                        {
                            'var_name': 'service_id',
                            'var_value': 'tenant',
                        },
                        {
                            'var_name': 'resource_id',
                            'var_value': str(product_item['local_id']),
                        },
                    ],
                }
            else:
                oa_unit_type = get_resclass_name(product_item['unit']['unit'])
                payload = {
                    'resclass_name': oa_unit_type,
                    'name': title,
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
                            'var_name': 'resource_id',
                            'var_value': str(product_item['local_id']),
                        },
                    ],
                }
            try:
                result = self._create_rt_oa(
                    payload=payload,
                )
            except OACommunicationException:
                # retry with title limit to 60 chars, suitable for versions < 20.5 or 20.4 without
                # Hotfix as described here: OA-16136
                title = title[:60]
                result = self._create_rt_oa(
                    payload=payload,
                )
            return {
                'name': title,
                'class': oa_unit_type,
                'limit': -1 if product_item['type'] == 'ppu' else 0,
                'local_id': str(product_item['local_id']),
                'id': result['resource_type_id'],
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for item in chunk:
                futures.append(
                    executor.submit(
                        _create_product_item,
                        item,
                        use_item_profile,
                        oa_app_id,
                        version,
                    ),
                )
            for future in concurrent.futures.as_completed(futures):
                try:
                    responses.append(future.result())
                except Exception as exc:
                    exceptions.append(exc)
        return responses, exceptions

    def _get_items_to_create(
            self,
            use_item_profile,
            oa_app_id,
    ):
        """
        Provides list of items missing in platform that must be created
        :param use_item_profile: bool
        :param oa_app_id: int
        :return: list
        """
        platform_items = self._get_platform_items(use_item_profile, oa_app_id)
        product_items = fetch_product_items_from_connect(product_id=self.product_id,
                                                         get_end_of_sale=self.data['includeEoS'])
        return filter(lambda pi: pi['local_id'] not in platform_items, product_items)

    def _reschedule_create_rts(self, items_created):
        """
        reschedules in OA the task due still missing ones and some condition has been generated
        :param items_created: list of items created in previous execution
        """
        self.data['retries'] = 0
        self.data['rts'] = self.data['rts'] + items_created
        self.data['step'] = "create_rts"
        message = "The creation of all resources for product {product}".format(
            product=self.product_id,
        )
        message += " is in progress, please wait..."
        return JSONResponse(
            content=self.data,
            status_code=202,
            headers=make_aps_headers_reschedule(
                delay=30,
                message=message,
                transaction_id=self.aps_transaction_id,
            ),
        )

    def _create_item_rts(self):
        """
        Main function to create items on OA, it prepares to create them in parallel using chunks
        """
        start_time = datetime.datetime.now()
        # When there are a lot of resources
        # somehow OA Get's unstable after 500 secs of execution time if we have a OA timeout of 600
        execution_timeout = 500
        product = fetch_product_from_connect(product_id=self.product_id)
        oa_app_id = aps_openapi_adapter_get_application_id(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            product_id=self.product_id,
        )
        use_item_profile = self._use_item_profile(product)
        items_created = []

        product_items_to_create = self._get_items_to_create(use_item_profile, oa_app_id)
        product_items_chunks = list(split_in_chunks(list(product_items_to_create), 5))
        for product_items_chunk in product_items_chunks:
            if start_time + datetime.timedelta(seconds=execution_timeout) < datetime.datetime.now():
                return self._reschedule_create_rts(items_created)

            responses, response_exceptions = self._create_items_rts_async(
                chunk=product_items_chunk,
                use_item_profile=use_item_profile,
                oa_app_id=str(oa_app_id['app_id']),
                version=product['version'],
            )
            items_created.extend(responses)
            missing_abstract_types = list(
                filter(
                    lambda x: 'is not found' in str(x), response_exceptions,
                ),
            )

            if missing_abstract_types:
                return JSONResponse(
                    content=str(missing_abstract_types[0]),
                    status_code=400,
                )

        # While creating RT OA may throw exceptions, we shall ensure we created all
        missing_items = self._get_items_to_create(use_item_profile, oa_app_id)
        if len(list(missing_items)) == 0:
            return self._handle_create_rts_response(items_created)

        self.data['retries'] = self.data['retries'] or 0
        self.data['retries'] += 1
        if self.data['retries'] < 10:
            return self._reschedule_create_rts(items_created)
        else:
            message = "We tried to create all resource types for product {product}".format(
                product=self.product_id,
            )
            message += " more than {amount} times, this maybe normal for large amount of ".format(
                amount=self.data['retries'],
            )
            message += "items to be created, but may indicate that CB Commerce can't process"
            message += "this creation right now and you may retry to run this task later"
            return JSONResponse(
                content={
                    "message": message,
                    "type": "error",
                },
                status_code=400,
            )

    def _handle_create_rts_response(self, items_created):
        """
        handles the response depending on case of upgrade vs install
        """
        self.data['rts'] = self.data['rts'] or []
        self.data['rts'] += items_created
        if self.operation == "install":
            self.data['step'] = "create_st_rest"
            self.data['retries'] = 0
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    delay=30,
                    message="Moving to service template creation",
                    transaction_id=self.aps_transaction_id,
                ),
            )
        # Operation was an upgrade and we completed what we can do
        self.data['step'] = "Completed"
        return JSONResponse(content=self.data, status_code=200)

    def _create_st_rest(self):
        """
        Creates the ST using REST interface instead of openapi
        :return:
        """
        product = fetch_product_from_connect(product_id=self.product_id)
        try:
            token = self._get_user_token(1)
        except TokenException:
            # In this use case, adapter may be busy...let's reschedule and retry
            message = "The Creation of the service tempalte for product {product}".format(
                product=self.product_id,
            )
            message += " is taking more than expected, please wait..."
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    30,
                    message,
                    self.aps_transaction_id,
                ),
            )
        st_resource = get_st_representation(product['name'])
        try:
            st = OA.send_request(
                method='POST',
                transaction=False,
                impersonate_as=None,
                auth='Token',
                headers={
                    'APS-Token': token['aps_token'],
                },
                path='aps/2/resources/',
                body=st_resource,
            )
        except OACommunicationException:
            # Was not possible to create ST using REST, let's move to old fashion
            self.data['step'] = "create_st"
            self.data['retries'] = 0
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    30,
                    "Moving to service template creation",
                    self.aps_transaction_id,
                ),
            )
        self.data['stid'] = st['serviceTemplateId']
        self.data['step'] = "apply_st_limits_rest"
        # In some situations OA returned exceptions when creating RTs
        # but in fact it created it and that's why we completed
        # to avoid losing them to be added to ST we perform a try to sync over editor
        # in forced way
        # this is just to ensure operator is happy to find resources in ST and not
        # waste his time searching if something is missing
        # exception is discarted due optional
        try:
            self._sync_items_created()
        except OACommunicationException:
            pass
        return JSONResponse(
            content=self.data,
            status_code=202,
            headers=make_aps_headers_reschedule(
                30,
                "Moving to service template limits definition over rest",
                self.aps_transaction_id,
            ),
        )

    def _get_resources_in_st(self, st_aps_id):
        """
        Provides list of resources available on a given service template
        :param st_aps_id: int
        :return:
        """
        st_rts = OA.send_request(
            method="GET",
            path="aps/2/resources/{st_uid}/limits".format(st_uid=st_aps_id),
            impersonate_as=self.app_id,
            transaction=False,
        )
        return list(
            {
                x['id'] for x in st_rts
            },
        )

    def _pending_to_be_added_to_st(self, st_aps_id):
        """
        Calculates resources that are pending to be added into the service template
        :param st_aps_id: uuid
        :return: list
        """
        existing_in_st = self._get_resources_in_st(st_aps_id)
        pending_rts = []
        for rt in self.data['rts']:
            if rt['id'] not in existing_in_st:
                pending_rts.append(rt)
        return pending_rts

    @staticmethod
    def _add_item_to_st(
            item,
            st_aps_id,
            token,
    ):
        """
        Adds single item into service template. Unfortunately OA can't process that in parallel
        without failing into deadlocks
        :param item: item
        :param st_aps_id: uuid
        :param token: admin token
        :return:
        """
        oa_item = {
            "id": item['id'],
            "unit": "unit",
            "limit": item['limit'],
        }
        return OA.send_request(
            method='POST',
            transaction=False,
            impersonate_as=None,
            auth='Token',
            headers={
                'APS-Token': token['aps_token'],
                "Content-Type": "application/json",
            },
            path='aps/2/resources/{st_uid}/limits'.format(
                st_uid=st_aps_id,
            ),
            body=oa_item,
        )

    def _apply_st_limits_rest(self):
        """
        Main function to add all resources into a given service template.
        Only used in Install process
        """
        start_time = datetime.datetime.now()
        execution_timeout = 500
        service_template = OA.get_resources(
            rql_request="aps/2/resources?implementing({type}),eq(serviceTemplateId,{id})".format(
                type="http://parallels.com/aps/types/pa/serviceTemplate/1.2",
                id=self.data['stid'],
            ),
            transaction=False,
            impersonate_as=self.app_id,
        )
        if not service_template or len(service_template) != 1:
            message = (
                "Service template has been removed, is not possible to set limits. "
                "You may want to cancel this task and proceed manually or remove the APS "
                "application manually and start again installation procedure"
            )
            return JSONResponse(
                content={
                    "message": message,
                    "type": "error",
                },
                status_code=400,
            )
        try:
            token = self._get_user_token(1)
        except TokenException:
            # In this use case, adapter may be busy...let's reschedule and retry
            message = "Adding resources to ST {st} for the product {product} ".format(
                st=self.data['stid'],
                product=self.product_id,
            )
            message += "is taking bit of time, Please wait"
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    30,
                    message,
                    self.aps_transaction_id,
                ),
            )
        pending_items = self._pending_to_be_added_to_st(service_template[0]['aps']['id'])

        for item in pending_items:
            if start_time + datetime.timedelta(seconds=execution_timeout) < datetime.datetime.now():
                return self._reschedule_st_creation()
            try:
                InitTask._add_item_to_st(
                    item=item,
                    st_aps_id=service_template[0]['aps']['id'],
                    token=token,
                )
            except OACommunicationException:
                # We don't care about exception since we made it stateless and reenterable
                pass

        if len(self._pending_to_be_added_to_st(service_template[0]['aps']['id'])) > 0:
            return self._reschedule_st_creation()

        self.data['step'] = "Completed"
        return JSONResponse(content=self.data, status_code=200)

    def _reschedule_st_creation(self):
        """
        Returns OA response to reschedule the creation of ST
        :return:
        """
        message = "Adding resources to ST {st} for the product {product} ".format(
            st=self.data['stid'],
            product=self.product_id,
        )
        message += "is taking bit of time, Please wait"
        return JSONResponse(
            content=self.data,
            status_code=202,
            headers=make_aps_headers_reschedule(
                30,
                message,
                self.aps_transaction_id,
            ),
        )

    def _get_user_token(self, user_id):
        """
        Gets user APS token
        :param user_id: int
        :return:
        """
        token = OA.send_request(
            method='GET',
            transaction=False,
            impersonate_as=self.app_id,
            path='aps/2/resources/{adapter_uid}/getToken?user_id={user_id}'.format(
                adapter_uid=self.oa_aps_openapi_adapter,
                user_id=user_id,
            ),
        )
        if 'aps_token' not in token:
            raise TokenException("No token obtained")
        return token

    def _create_st(self):  # noqa: CCR001
        """
        Creates Service template using Rest API on OA
        """
        if self.retries < 10:
            try:
                product = fetch_product_from_connect(product_id=self.product_id)
                payload = {
                    'name': product['name'],
                    'rts': [rt_id['id'] for rt_id in self.data['rts']],
                }
                st = OA.send_request(
                    method="POST",
                    path="aps/2/resources/{adapter_uid}/addServiceTemplate".format(
                        adapter_uid=self.oa_aps_openapi_adapter,
                    ),
                    body=payload,
                    impersonate_as=self.app_id,
                    transaction=False,
                )
                self.data['stid'] = st['st_id']
                self.data['step'] = "apply_st_limits"
                return JSONResponse(
                    content=self.data,
                    status_code=202,
                    headers=make_aps_headers_reschedule(
                        30,
                        "Moving to service template limits definition",
                        self.aps_transaction_id,
                    ),
                )
            except OACommunicationException:
                """
                When creating ST over openapi, we may get crash but operation keeps running
                due it, we will leave OA some time, maybe succeeds, to know if succeeds,
                we check if exists a ST with the name we expect, if so, we will move to
                apply limits
                """
                service_template = self._get_st_for_product()
                if len(service_template) == 1:
                    self.data['stid'] = service_template[0]['serviceTemplateId']
                    self.data['step'] = "apply_st_limits"
                    self.data['retries'] = 0
                    return JSONResponse(
                        content=self.data,
                        status_code=202,
                        headers=make_aps_headers_reschedule(
                            30,
                            "Moving to service template limits definition",
                            self.aps_transaction_id,
                        ),
                    )

                self.data['retries'] = self.retries + 1
                """
                Reexecution timeout set to 1000 secs in order to ensure that we are more
                than transaction timeout of OA, running before don't helps OA
                """
                return JSONResponse(
                    content=self.data,
                    status_code=202,
                    headers=make_aps_headers_reschedule(
                        1000,
                        "Waiting ST to be created",
                        self.aps_transaction_id,
                    ),
                )
        else:
            msg = "Sorry, but even after 10 retries we've failed to create a Service Template "
            msg += "with all of the Product Items. This might be caused by the fact that this "
            msg += "product has too many items, which results in more resources than CloudBlue "
            msg += "Commerce can handle. Please cancel this task and add required resources into "
            msg += "the Service Template manually."

            return JSONResponse(
                content={
                    "message": msg,
                    "type": "error",
                },
                status_code=400,
            )

    def _get_st_for_product(self):
        """
        Gets the service template that is used by given product
        this is only used on install process, hence st is singleton
        :return:
        """
        return OA.send_request(
            method='GET',
            transaction=False,
            impersonate_as=self.app_id,
            path="/aps/2/resources?implementing({st_type}),eq(appIDs,{base_type}{product})".format(
                st_type="http://parallels.com/aps/types/pa/serviceTemplate/1.1",
                base_type="http://aps.odin.com/app/",
                product=self.product_id,
            ),
        )

    def _apply_st_limits(self):
        """
        When Applaying ST Limits, it may happen that Communication crashes
        In such use case, adapter keeps running it over XML-RPC and due it
        we shall consider it "completed", unfortunately at difference
        than ST creation, we can't really know if finished or not to
        double check, due it, in case of failure of any kind, we mark the task as completed
        :return:
        """
        try:
            payload = {
                "st_id": self.data['stid'],
                "resource_types_limits": self.data['rts'],
            }
            OA.send_request(
                method='POST',
                impersonate_as=self.app_id,
                path="aps/2/resources/{adapter_uid}/applyServiceTemplateLimits".format(
                    adapter_uid=self.oa_aps_openapi_adapter,
                ),
                body=payload,
            )
        except OACommunicationException:
            pass
        self.data['step'] = "Completed"
        return JSONResponse(content=self.data, status_code=200)

    def _upgrade_instance(self):
        """
        Upgrades an Instance of product to latest version
        """
        oa_app_id = aps_openapi_adapter_get_application_id(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            product_id=self.product_id,
        )
        app_instances = aps_openapi_adapter_get_instances(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            oa_app_id=oa_app_id['app_id'],
        )
        OA.send_request(
            method='GET',
            impersonate_as=self.app_id,
            path="aps/2/resources/{adapter}/upgradeApplicationInstance?instance_id={inst}".format(
                adapter=self.oa_aps_openapi_adapter,
                inst=app_instances[0]['application_instance_id'],
            ),
        )
        if self.product_id == "extension":
            self.data['step'] = "Completed"
            return self.data, 200

        self.data['step'] = "wait_upgrade_complete"
        return JSONResponse(
            content=self.data,
            status_code=202,
            headers=make_aps_headers_reschedule(
                60,
                "Waiting upgrade to Complete",
                self.aps_transaction_id,
            ),
        )

    def _wait_upgrade_complete(self):
        product = fetch_product_from_connect(product_id=self.product_id)
        oa_app_id = aps_openapi_adapter_get_application_id(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            product_id=self.product_id,
        )
        app_instances = aps_openapi_adapter_get_instances(
            app_id=self.app_id,
            openapi_adapter=self.oa_aps_openapi_adapter,
            oa_app_id=oa_app_id['app_id'],
        )
        instance_status = OA.send_request(
            method='GET',
            impersonate_as=self.app_id,
            path="aps/2/resources/{adapter}/getApplicationInstance?instance_id={inst}".format(
                adapter=self.oa_aps_openapi_adapter,
                inst=app_instances[0]['application_instance_id'],
            ),
        )
        if instance_status['package_version'] == "{version}-0".format(
                version=product['version'],
        ):
            self.data['step'] = "create_rts"
            return JSONResponse(
                content=self.data,
                status_code=202,
                headers=make_aps_headers_reschedule(
                    delay=60,
                    message="Moving to Rts creation",
                    transaction_id=self.aps_transaction_id,
                ),
            )
        # Upgrade did not completed, we reschedule
        return JSONResponse(
            content=self.data,
            status_code=202,
            headers=make_aps_headers_reschedule(
                delay=60,
                message="Waiting upgrade to Complete",
                transaction_id=self.aps_transaction_id,
            ),
        )

    def _create_rt_oa(self, payload):
        return OA.send_request(
            method='POST',
            path='aps/2/resources/{adapter}/addResourceType'.format(
                adapter=self.oa_aps_openapi_adapter,
            ),
            impersonate_as=self.app_id,
            transaction=False,
            body={
                'rt_structure': payload,
            },
        )

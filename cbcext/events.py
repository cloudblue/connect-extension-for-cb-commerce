from connect.eaas.core.decorators import event, schedulable, variables
from connect.eaas.core.extension import EventsApplicationBase
from connect.eaas.core.responses import BackgroundResponse, ScheduledExecutionResponse

from cbcext.services.eaas_events.utils import (
    add_installation_hubs,
    add_product_connections,
    get_db_for_events,
)

from sqlalchemy.exc import DBAPIError
from connect.client import ClientError


@variables(
    [
        {
            "name": "DATABASE_URL",
            "initial_value": "postgresql+psycopg2://postgres:1q2w3e@db/extension_cbc",
            "secure": True,
        },
        {
            "name": "REDIS_LOCATION",
            "initial_value": "redis://redis:6379/0",
            "secure": True,
        },
    ],
)
class CbcEventsApplication(EventsApplicationBase):

    @event('installation_status_change', statuses=['installed', 'uninstalled'])
    def on_installation_status_change(
            self,
            request,
    ):
        account = f'{request["owner"]["name"]} ({request["owner"]["id"]})'
        if request['status'] == 'installed':
            self.logger.info(
                f'This extension has been installed by {account}: '
                f'id={request["id"]}, environment={request["environment"]["id"]}',
            )
            try:
                with get_db_for_events(self.config) as db:
                    add_product_connections(db, self.client, request['id'])
                    add_installation_hubs(db, self.client, request['id'])
            except (ClientError, DBAPIError):
                return BackgroundResponse.reschedule()
        else:
            self.logger.info(
                f'This extension has removed by {account}: '
                f'id={request["id"]}, environment={request["environment"]["id"]}',
            )

        return BackgroundResponse.done()

    @schedulable(
        'Update Authentication',
        'Periodic discovery of new hub and product connections',
    )
    def update_access_credentials(self, schedule):
        # Temp solution since can't be listened events of new connection created or new hub
        installations = self.client.ns(
            'devops',
        ).collection(
            'services',
        ).resource(
            self.context.extension_id,
        ).collection('installations').filter('eq(status,installed)')
        for installation in installations:
            try:
                with get_db_for_events(self.config) as db:
                    add_product_connections(
                        db,
                        self.get_installation_admin_client(installation_id=installation['id']),
                        installation['id'],
                    )
                    add_installation_hubs(
                        db,
                        self.get_installation_admin_client(installation_id=installation['id']),
                        installation['id'],
                    )
            except (ClientError, DBAPIError):
                return ScheduledExecutionResponse.reschedule()
        return ScheduledExecutionResponse.done()

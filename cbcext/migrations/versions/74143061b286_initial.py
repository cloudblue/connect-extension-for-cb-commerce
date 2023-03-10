"""initial

Revision ID: 74143061b286
Revises:
Create Date: 2023-02-01 17:06:58.150350

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '74143061b286'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'configuration',
        sa.Column('oauth_key', sa.String(length=100), nullable=False),
        sa.Column('oauth_secret', sa.String(length=100), nullable=True),
        sa.Column('product_id', sa.String(length=100), nullable=True),
        sa.Column('api_key', sa.String(length=100), nullable=True),
        sa.Column('provider_api_key', sa.String(length=100), nullable=True),
        sa.Column('api_url', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('oauth_key'),
    )
    op.create_table(
        'global_app_configuration',
        sa.Column('app_instance_id', sa.String(length=100), nullable=False),
        sa.Column('hub_uuid', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('app_instance_id'),
    )
    op.create_table(
        'hub_instances',
        sa.Column('hub_id', sa.String(length=100), nullable=False),
        sa.Column('app_instance_id', sa.String(length=100), nullable=True),
        sa.Column('extension_resource_uid', sa.String(length=100), nullable=True),
        sa.Column('controller_uri', sa.String(length=400), nullable=True),
        sa.Column('last_check', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('hub_id'),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('hub_instances')
    op.drop_table('global_app_configuration')
    op.drop_table('configuration')
    # ### end Alembic commands ###

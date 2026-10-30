"""pagamento da folha

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pago_em', sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.drop_column('pago_em')

"""vale-transporte por dias úteis

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('trabalhadores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dias_semana_trabalho', sa.String(length=7), nullable=False, server_default='12345'))
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dias_uteis', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.drop_column('dias_uteis')
    with op.batch_alter_table('trabalhadores', schema=None) as batch_op:
        batch_op.drop_column('dias_semana_trabalho')

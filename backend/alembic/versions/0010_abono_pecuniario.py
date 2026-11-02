"""abono pecuniário de férias

Revision ID: 0010
Revises: 0009

Gozos de férias ganham os dias vendidos (abono pecuniário, até 1/3 do período) e o valor pago por eles.
"""
from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('gozos_ferias', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dias_abono', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('valor_abono', sa.Numeric(precision=12, scale=2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('gozos_ferias', schema=None) as batch_op:
        batch_op.drop_column('valor_abono')
        batch_op.drop_column('dias_abono')

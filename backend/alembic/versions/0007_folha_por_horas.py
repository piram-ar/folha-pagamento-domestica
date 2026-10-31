"""folha por horas trabalhadas

Revision ID: 0007
Revises: 0006

O salário passa a ser pago pelas horas trabalhadas até a jornada mensal do trabalhador (padrão 200 h).
Folhas antigas tinham os dias trabalhados (mês de 30 dias): viram horas na mesma proporção.
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('trabalhadores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('horas_mensais', sa.Numeric(precision=6, scale=2), server_default='200',
                                      nullable=False))

    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('horas_trabalhadas', sa.Numeric(precision=6, scale=2), nullable=True))
        batch_op.add_column(sa.Column('horas_mensais', sa.Numeric(precision=6, scale=2), nullable=True))
    op.execute(
        "UPDATE folha_pagamento SET horas_mensais = 200, "
        "horas_trabalhadas = ROUND(MIN(dias_trabalhados, 30) * 200.0 / 30, 2)"
    )
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.alter_column('horas_trabalhadas', existing_type=sa.Numeric(precision=6, scale=2), nullable=False)
        batch_op.alter_column('horas_mensais', existing_type=sa.Numeric(precision=6, scale=2), nullable=False)
        batch_op.drop_column('dias_trabalhados')


def downgrade() -> None:
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dias_trabalhados', sa.Integer(), nullable=True))
    op.execute("UPDATE folha_pagamento SET dias_trabalhados = ROUND(horas_trabalhadas * 30.0 / horas_mensais)")
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.alter_column('dias_trabalhados', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('horas_mensais')
        batch_op.drop_column('horas_trabalhadas')

    with op.batch_alter_table('trabalhadores', schema=None) as batch_op:
        batch_op.drop_column('horas_mensais')

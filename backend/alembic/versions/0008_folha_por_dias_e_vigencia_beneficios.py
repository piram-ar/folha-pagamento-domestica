"""folha por dias e vigência dos benefícios

Revision ID: 0008
Revises: 0007

Volta a folha para dias trabalhados (mês completo = salário cheio; incompleto = proporcional aos dias
reais do mês); a jornada do cadastro fica só como divisor do valor-hora das horas extras.
Benefícios ganham o início da vigência; os existentes começam na admissão do trabalhador.
"""
from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

# Último dia do mês da competência (AAAA-MM), em SQL do SQLite
_DIAS_NO_MES = "CAST(strftime('%d', date(mes_ano || '-01', '+1 month', '-1 day')) AS INTEGER)"


def upgrade() -> None:
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dias_trabalhados', sa.Integer(), nullable=True))
    # Jornada completa = mês completo; menos horas voltam à proporção de 30 dias usada antes da 0007
    op.execute(
        "UPDATE folha_pagamento SET dias_trabalhados = CASE "
        f"WHEN horas_trabalhadas >= horas_mensais THEN {_DIAS_NO_MES} "
        "ELSE CAST(ROUND(horas_trabalhadas * 30.0 / horas_mensais) AS INTEGER) END"
    )
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.alter_column('dias_trabalhados', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('horas_trabalhadas')

    with op.batch_alter_table('beneficios_fixos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vigencia_inicio', sa.Date(), nullable=True))
    op.execute(
        "UPDATE beneficios_fixos SET vigencia_inicio = "
        "(SELECT data_admissao FROM trabalhadores WHERE trabalhadores.id = beneficios_fixos.trabalhador_id)"
    )
    with op.batch_alter_table('beneficios_fixos', schema=None) as batch_op:
        batch_op.alter_column('vigencia_inicio', existing_type=sa.Date(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('beneficios_fixos', schema=None) as batch_op:
        batch_op.drop_column('vigencia_inicio')

    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('horas_trabalhadas', sa.Numeric(precision=6, scale=2), nullable=True))
    op.execute(
        f"UPDATE folha_pagamento SET horas_trabalhadas = CASE WHEN dias_trabalhados >= {_DIAS_NO_MES} "
        "THEN horas_mensais ELSE ROUND(dias_trabalhados * horas_mensais / 30.0, 2) END"
    )
    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.alter_column('horas_trabalhadas', existing_type=sa.Numeric(precision=6, scale=2), nullable=False)
        batch_op.drop_column('dias_trabalhados')

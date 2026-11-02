"""pagamento de férias e 13º salário

Revision ID: 0009
Revises: 0008

Férias registradas ganham o cálculo do pagamento (salário dos dias + 1/3); a folha do mês desconta
os dias de férias, já pagos no recibo de férias. Nova tabela com as parcelas do 13º salário.
"""
from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

_DINHEIRO = sa.Numeric(precision=12, scale=2)
_PAGAMENTO_FERIAS = ('salario_base', 'media_variaveis', 'valor_ferias', 'valor_terco', 'inss', 'encargos', 'liquido')


def upgrade() -> None:
    with op.batch_alter_table('gozos_ferias', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data_pagamento', sa.Date(), nullable=True))
        for coluna in _PAGAMENTO_FERIAS:
            batch_op.add_column(sa.Column(coluna, _DINHEIRO, nullable=True))
        batch_op.add_column(sa.Column('detalhamento', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('calculado_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('pago_em', sa.Date(), nullable=True))

    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dias_ferias', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('desconto_ferias', _DINHEIRO, server_default='0', nullable=False))

    op.create_table(
        'decimo_terceiro',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trabalhador_id', sa.Integer(), nullable=False),
        sa.Column('ano', sa.Integer(), nullable=False),
        sa.Column('parcela', sa.Integer(), nullable=False),
        sa.Column('avos', sa.Integer(), nullable=False),
        sa.Column('salario_base', _DINHEIRO, nullable=False),
        sa.Column('media_variaveis', _DINHEIRO, nullable=False),
        sa.Column('valor_integral', _DINHEIRO, nullable=False),
        sa.Column('valor_bruto', _DINHEIRO, nullable=False),
        sa.Column('adiantamento', _DINHEIRO, nullable=False),
        sa.Column('inss', _DINHEIRO, nullable=False),
        sa.Column('encargos', _DINHEIRO, nullable=False),
        sa.Column('liquido', _DINHEIRO, nullable=False),
        sa.Column('data_pagamento', sa.Date(), nullable=False),
        sa.Column('pago_em', sa.Date(), nullable=True),
        sa.Column('detalhamento', sa.Text(), nullable=True),
        sa.Column('calculado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['trabalhador_id'], ['trabalhadores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trabalhador_id', 'ano', 'parcela'),
    )
    op.create_index('ix_decimo_terceiro_trabalhador_id', 'decimo_terceiro', ['trabalhador_id'])


def downgrade() -> None:
    op.drop_index('ix_decimo_terceiro_trabalhador_id', table_name='decimo_terceiro')
    op.drop_table('decimo_terceiro')

    with op.batch_alter_table('folha_pagamento', schema=None) as batch_op:
        batch_op.drop_column('desconto_ferias')
        batch_op.drop_column('dias_ferias')

    with op.batch_alter_table('gozos_ferias', schema=None) as batch_op:
        for coluna in ('pago_em', 'calculado_em', 'detalhamento', *_PAGAMENTO_FERIAS, 'data_pagamento'):
            batch_op.drop_column(coluna)

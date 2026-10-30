"""tabela inss e avisos de pagamento

Revision ID: 0004
Revises: 0003
"""
from datetime import date

from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('config_notificacoes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('antecedencias', sa.String(length=40), nullable=False),
    sa.Column('email_ativo', sa.Boolean(), nullable=False),
    sa.Column('destinatarios', sa.String(length=500), nullable=True),
    sa.Column('hora_envio', sa.Integer(), nullable=False),
    sa.Column('smtp_host', sa.String(length=160), nullable=True),
    sa.Column('smtp_porta', sa.Integer(), nullable=False),
    sa.Column('smtp_seguranca', sa.Enum('starttls', 'ssl', 'nenhuma', name='segurancasmtp', native_enum=False, length=30), nullable=False),
    sa.Column('smtp_usuario', sa.String(length=160), nullable=True),
    sa.Column('smtp_senha', sa.String(length=255), nullable=True),
    sa.Column('smtp_remetente', sa.String(length=160), nullable=True),
    sa.Column('token_calendario', sa.String(length=64), nullable=True),
    sa.Column('ultimo_envio_em', sa.DateTime(), nullable=True),
    sa.Column('ultimo_erro', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tabelas_inss',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('vigencia_inicio', sa.Date(), nullable=False),
    sa.Column('descricao', sa.String(length=120), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('vigencia_inicio')
    )
    op.create_table('faixas_inss',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tabela_id', sa.Integer(), nullable=False),
    sa.Column('teto', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('aliquota', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.ForeignKeyConstraint(['tabela_id'], ['tabelas_inss.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('faixas_inss', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_faixas_inss_tabela_id'), ['tabela_id'], unique=False)

    op.create_table('notificacoes_enviadas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trabalhador_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('salario', 'adiantamento', name='tipopagamento', native_enum=False, length=30), nullable=False),
    sa.Column('data_pagamento', sa.Date(), nullable=False),
    sa.Column('antecedencia', sa.Integer(), nullable=False),
    sa.Column('enviado_em', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['trabalhador_id'], ['trabalhadores.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trabalhador_id', 'tipo', 'data_pagamento', 'antecedencia')
    )
    with op.batch_alter_table('notificacoes_enviadas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notificacoes_enviadas_trabalhador_id'), ['trabalhador_id'], unique=False)

    # Tabela de 2025, até então fixa no código (services/tabelas.py)
    tabelas = sa.table('tabelas_inss', sa.column('id', sa.Integer), sa.column('vigencia_inicio', sa.Date),
                       sa.column('descricao', sa.String))
    faixas = sa.table('faixas_inss', sa.column('tabela_id', sa.Integer), sa.column('teto', sa.Numeric),
                      sa.column('aliquota', sa.Numeric))
    op.bulk_insert(tabelas, [{'id': 1, 'vigencia_inicio': date(2025, 1, 1), 'descricao': 'Tabela 2025'}])
    op.bulk_insert(faixas, [
        {'tabela_id': 1, 'teto': teto, 'aliquota': aliquota}
        for teto, aliquota in [(1518.00, 7.5), (2793.88, 9), (4190.83, 12), (8157.41, 14)]
    ])

    with op.batch_alter_table('trabalhadores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dia_pagamento_salario', sa.Integer(), server_default='5', nullable=False))
        batch_op.add_column(sa.Column('salario_dia_util', sa.Boolean(), server_default='1', nullable=False))
        batch_op.add_column(sa.Column('adiantamento_acordado', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('dia_pagamento_adiantamento', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('adiantamento_dia_util', sa.Boolean(), server_default='0', nullable=False))



def downgrade() -> None:
    with op.batch_alter_table('trabalhadores', schema=None) as batch_op:
        batch_op.drop_column('adiantamento_dia_util')
        batch_op.drop_column('dia_pagamento_adiantamento')
        batch_op.drop_column('adiantamento_acordado')
        batch_op.drop_column('salario_dia_util')
        batch_op.drop_column('dia_pagamento_salario')

    with op.batch_alter_table('notificacoes_enviadas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notificacoes_enviadas_trabalhador_id'))

    op.drop_table('notificacoes_enviadas')
    with op.batch_alter_table('faixas_inss', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_faixas_inss_tabela_id'))

    op.drop_table('faixas_inss')
    op.drop_table('tabelas_inss')
    op.drop_table('config_notificacoes')

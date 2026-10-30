"""reajustes salariais e funcao

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('reajustes_salariais',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trabalhador_id', sa.Integer(), nullable=False),
    sa.Column('vigencia', sa.Date(), nullable=False),
    sa.Column('tipo', sa.Enum('percentual', 'valor', 'novo_salario', name='tiporeajuste', native_enum=False, length=30), nullable=False),
    sa.Column('valor_informado', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('salario_anterior', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('salario_novo', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('motivo', sa.String(length=160), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['trabalhador_id'], ['trabalhadores.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trabalhador_id', 'vigencia')
    )
    with op.batch_alter_table('reajustes_salariais', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reajustes_salariais_trabalhador_id'), ['trabalhador_id'], unique=False)

    with op.batch_alter_table('trabalhadores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('funcao', sa.String(length=120), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('trabalhadores', schema=None) as batch_op:
        batch_op.drop_column('funcao')

    with op.batch_alter_table('reajustes_salariais', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reajustes_salariais_trabalhador_id'))

    op.drop_table('reajustes_salariais')

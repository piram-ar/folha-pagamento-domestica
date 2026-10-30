"""dados do empregador/contratante e local da prestação do serviço

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('contratante',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('cpf', sa.String(length=11), nullable=True),
    sa.Column('telefone', sa.String(length=20), nullable=True),
    sa.Column('email', sa.String(length=160), nullable=True),
    sa.Column('cep', sa.String(length=8), nullable=True),
    sa.Column('logradouro', sa.String(length=160), nullable=True),
    sa.Column('numero', sa.String(length=20), nullable=True),
    sa.Column('complemento', sa.String(length=80), nullable=True),
    sa.Column('bairro', sa.String(length=80), nullable=True),
    sa.Column('cidade', sa.String(length=80), nullable=True),
    sa.Column('uf', sa.String(length=2), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('contratante')

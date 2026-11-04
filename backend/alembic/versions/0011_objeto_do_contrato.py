"""objeto do contrato

Revision ID: 0011
Revises: 0010

Cadastro dos objetos do contrato (Serviços Domésticos, de Babá...) e o objeto de cada trabalhador, que sai em
todos os recibos. Quem já estava cadastrado fica com Serviços Domésticos, o texto usado até aqui.

A coluna entra com ALTER TABLE simples, sem batch: recriar `trabalhadores` com foreign_keys=ON apagaria em
cascata folhas, férias e lançamentos. Por isso ela não tem FOREIGN KEY no banco; a API valida o objeto.
"""
from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

OBJETOS = ['Serviços Domésticos', 'Serviços de Babá', 'Serviços de Diarista', 'Serviços de Cuidador(a)',
           'Serviços de Caseiro(a)']


def upgrade() -> None:
    objetos = op.create_table(
        'objetos_contrato',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('descricao', sa.String(length=120), nullable=False),
        sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False),
        sa.UniqueConstraint('descricao'),
    )
    op.bulk_insert(objetos, [{'descricao': d} for d in OBJETOS])
    op.execute('ALTER TABLE trabalhadores ADD COLUMN objeto_contrato_id INTEGER')
    op.execute("UPDATE trabalhadores SET objeto_contrato_id = "
               "(SELECT id FROM objetos_contrato WHERE descricao = 'Serviços Domésticos')")


def downgrade() -> None:
    op.execute('ALTER TABLE trabalhadores DROP COLUMN objeto_contrato_id')
    op.drop_table('objetos_contrato')

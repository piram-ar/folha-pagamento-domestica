"""segurança das sessões

Revision ID: 0012
Revises: 0011

- versao_sessao: entra no token de login; trocar a senha, o perfil ou desativar o usuário a incrementa e
  derruba as sessões abertas em todos os aparelhos.
- trocar_senha: obriga a pessoa a definir uma senha própria no próximo acesso. Já nasce marcada para quem
  ainda usa a senha de instalação (admin123) e, a partir daqui, para senhas definidas pelo administrador.
"""
import bcrypt
import sqlalchemy as sa
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE usuarios ADD COLUMN versao_sessao INTEGER NOT NULL DEFAULT 0')
    op.execute('ALTER TABLE usuarios ADD COLUMN trocar_senha BOOLEAN NOT NULL DEFAULT 0')
    conexao = op.get_bind()
    for usuario_id, senha_hash in conexao.execute(sa.text('SELECT id, senha_hash FROM usuarios')).all():
        try:
            padrao = bcrypt.checkpw(b'admin123', senha_hash.encode('utf-8'))
        except ValueError:
            padrao = False
        if padrao:
            conexao.execute(sa.text('UPDATE usuarios SET trocar_senha = 1 WHERE id = :id'), {'id': usuario_id})


def downgrade() -> None:
    op.execute('ALTER TABLE usuarios DROP COLUMN trocar_senha')
    op.execute('ALTER TABLE usuarios DROP COLUMN versao_sessao')

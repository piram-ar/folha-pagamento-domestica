import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { useAvisar } from '../components/feedback';
import { Alerta, Campo } from '../components/ui';

const MINIMO = 10;

/** Troca da própria senha. `obrigatoria`: primeiro acesso ou senha definida pelo administrador; nada mais abre antes. */
export default function TrocarSenha({ obrigatoria = false }) {
  const { usuario, trocarSenha, logout } = useAuth();
  const navigate = useNavigate();
  const avisar = useAvisar();
  const [form, setForm] = useState({ atual: '', nova: '', repetida: '' });
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);
  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  const enviar = async (e) => {
    e.preventDefault();
    setErro('');
    if (form.nova !== form.repetida) { setErro('A confirmação não confere com a nova senha.'); return; }
    setEnviando(true);
    try {
      await trocarSenha(form.atual, form.nova);
      avisar({ sucesso: 'Senha alterada. Os outros aparelhos conectados precisarão entrar de novo.' });
      if (!obrigatoria) navigate('/');
    } catch (err) {
      setErro(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const formulario = (
    <form className="painel" onSubmit={enviar}>
      <Alerta erro={erro} />
      {/* Campo oculto de usuário: ajuda o gerenciador de senhas a guardar a senha nova para o e-mail certo */}
      <input type="email" autoComplete="username" value={usuario.email} readOnly hidden />
      <Campo label={obrigatoria ? 'Senha provisória (a que você usou para entrar)' : 'Senha atual'}>
        <input type="password" autoComplete="current-password" value={form.atual} onChange={set('atual')} required autoFocus />
      </Campo>
      <Campo label="Nova senha" dica={`Mínimo de ${MINIMO} caracteres. Uma frase curta é fácil de lembrar e difícil de adivinhar.`}>
        <input type="password" autoComplete="new-password" minLength={MINIMO} maxLength={72} value={form.nova} onChange={set('nova')} required />
      </Campo>
      <Campo label="Repita a nova senha">
        <input type="password" autoComplete="new-password" minLength={MINIMO} maxLength={72} value={form.repetida} onChange={set('repetida')} required />
      </Campo>
      <button className="btn primario largo" disabled={enviando}>{enviando ? 'Salvando…' : 'Salvar nova senha'}</button>
    </form>
  );

  if (!obrigatoria) {
    return (
      <div className="login-caixa">
        <h2>Minha senha</h2>
        <p className="sub">Ao trocar, as sessões abertas em outros aparelhos são encerradas.</p>
        {formulario}
      </div>
    );
  }
  return (
    <div className="login-pagina">
      <div className="login-caixa">
        <h1 className="marca">Folha Doméstica</h1>
        <p className="sub">Olá, {usuario.nome}. Antes de continuar, defina uma senha só sua para substituir a provisória.</p>
        {formulario}
        <p className="dica"><button type="button" className="btn-link" onClick={logout}>Sair</button></p>
      </div>
    </div>
  );
}

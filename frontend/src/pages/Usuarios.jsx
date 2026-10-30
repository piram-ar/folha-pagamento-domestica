import { useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../AuthContext';
import { Alerta, Badge, Campo, Modal } from '../components/ui';
import { ROTULOS } from '../utils';

const VAZIO = { nome: '', email: '', senha: '', perfil: 'padrao', ativo: true };

function UsuarioForm({ inicial, onSalvar, onCancelar }) {
  const [form, setForm] = useState(inicial ? { ...inicial, senha: '' } : VAZIO);
  const [erro, setErro] = useState('');
  const set = (campo) => (e) =>
    setForm({ ...form, [campo]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

  const enviar = async (e) => {
    e.preventDefault();
    const dados = { ...form };
    if (inicial && !dados.senha) delete dados.senha;
    try { await onSalvar(dados); } catch (err) { setErro(err.message); }
  };

  return (
    <form onSubmit={enviar}>
      <Alerta erro={erro} />
      <div className="grade-form">
        <Campo label="Nome"><input value={form.nome} onChange={set('nome')} required /></Campo>
        <Campo label="E-mail"><input type="email" value={form.email} onChange={set('email')} required /></Campo>
        <Campo label={inicial ? 'Nova senha (deixe em branco para manter)' : 'Senha'}>
          <input type="password" minLength={6} value={form.senha} onChange={set('senha')} required={!inicial} />
        </Campo>
        <Campo label="Perfil" dica="Padrão: gerencia trabalhadores, folha e férias. Admin: também gerencia usuários.">
          <select value={form.perfil} onChange={set('perfil')}>
            <option value="padrao">Padrão</option>
            <option value="admin">Administrador</option>
          </select>
        </Campo>
        <label className="checkbox"><input type="checkbox" checked={form.ativo} onChange={set('ativo')} /> Ativo</label>
      </div>
      <div className="acoes direita">
        <button type="button" className="btn" onClick={onCancelar}>Cancelar</button>
        <button className="btn primario">Salvar</button>
      </div>
    </form>
  );
}

export default function Usuarios() {
  const { usuario: eu } = useAuth();
  const [lista, setLista] = useState([]);
  const [editando, setEditando] = useState(null); // null | 'novo' | usuario
  const [msg, setMsg] = useState({});

  const carregar = () => api.get('/usuarios').then(setLista).catch((e) => setMsg({ erro: e.message }));
  useEffect(() => { carregar(); }, []);

  const salvar = async (dados) => {
    if (editando === 'novo') await api.post('/usuarios', dados);
    else await api.put(`/usuarios/${editando.id}`, dados);
    setEditando(null);
    setMsg({ sucesso: 'Usuário salvo.' });
    carregar();
  };

  const excluir = async (u) => {
    if (!window.confirm(`Excluir o usuário ${u.nome}?`)) return;
    try {
      await api.del(`/usuarios/${u.id}`);
      carregar();
    } catch (e) { setMsg({ erro: e.message }); }
  };

  return (
    <>
      <div className="titulo-pagina">
        <h2>Usuários do sistema</h2>
        <button className="btn primario" onClick={() => setEditando('novo')}>Cadastrar usuário</button>
      </div>
      <Alerta {...msg} />
      <div className="tabela-container">
        <table className="tabela-pilha">
          <thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Situação</th><th /></tr></thead>
          <tbody>
            {lista.map((u) => (
              <tr key={u.id}>
                <td className="principal"><span><strong>{u.nome}</strong>{u.id === eu.id && <small> (você)</small>}</span></td>
                <td data-label="E-mail">{u.email}</td>
                <td data-label="Perfil"><Badge tipo={u.perfil === 'admin' ? 'azul' : 'neutro'}>{ROTULOS.perfil[u.perfil]}</Badge></td>
                <td data-label="Situação">{u.ativo ? <Badge tipo="verde">Ativo</Badge> : <Badge>Inativo</Badge>}</td>
                <td className="acoes-linha">
                  <button className="btn pequeno" onClick={() => setEditando(u)}>Editar</button>
                  {u.id !== eu.id && <button className="btn pequeno perigo" onClick={() => excluir(u)}>Excluir</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editando && (
        <Modal titulo={editando === 'novo' ? 'Novo usuário' : 'Editar usuário'} onClose={() => setEditando(null)}>
          <UsuarioForm inicial={editando === 'novo' ? null : editando} onSalvar={salvar} onCancelar={() => setEditando(null)} />
        </Modal>
      )}
    </>
  );
}

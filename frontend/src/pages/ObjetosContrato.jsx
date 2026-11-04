import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../AuthContext';
import { useAvisar, useConfirmar } from '../components/feedback';
import { Alerta, Badge, Campo, Carregando, ErroTela, Modal } from '../components/ui';

function FormObjeto({ objeto, onClose, onSalvar }) {
  const [descricao, setDescricao] = useState(objeto?.descricao || '');
  const [ativo, setAtivo] = useState(objeto?.ativo ?? true);
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setErro('');
    setSalvando(true);
    try {
      await onSalvar({ descricao, ativo });
    } catch (err) { setErro(err.message); } finally { setSalvando(false); }
  };

  return (
    <Modal titulo={objeto ? 'Editar objeto do contrato' : 'Novo objeto do contrato'} onClose={onClose}>
      <form onSubmit={enviar}>
        <Alerta erro={erro} />
        <Campo label="Descrição" dica='Sai nos recibos como está escrita aqui. Ex.: Serviços de Jardinagem.'>
          <input value={descricao} onChange={(e) => setDescricao(e.target.value)} required minLength={3} maxLength={120} autoFocus />
        </Campo>
        {objeto && (
          <label className="checkbox">
            <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} /> Disponível para novos cadastros
          </label>
        )}
        {objeto?.trabalhadores > 0 && (
          <p className="dica">Uma nova descrição vale para todos os recibos de quem usa este objeto, inclusive os reimpressos.</p>
        )}
        <div className="acoes direita">
          <button type="button" className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn primario" disabled={salvando}>{salvando ? 'Salvando…' : 'Salvar'}</button>
        </div>
      </form>
    </Modal>
  );
}

export default function ObjetosContrato() {
  const { isAdmin } = useAuth();
  const avisar = useAvisar();
  const confirmar = useConfirmar();
  const [lista, setLista] = useState(null);
  const [erro, setErro] = useState('');
  const [editando, setEditando] = useState(null); // null | 'novo' | objeto

  const carregar = useCallback(() => {
    setErro('');
    return api.get('/objetos-contrato').then(setLista).catch((e) => setErro(e.message));
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  const salvar = async (dados) => {
    if (editando === 'novo') await api.post('/objetos-contrato', dados);
    else await api.put(`/objetos-contrato/${editando.id}`, dados);
    setEditando(null);
    avisar({ sucesso: 'Objeto do contrato salvo.' });
    carregar();
  };

  const excluir = async (o) => {
    if (!await confirmar({ titulo: `Excluir ${o.descricao}?`, acao: 'Excluir objeto', perigo: true })) return;
    try {
      await api.del(`/objetos-contrato/${o.id}`);
      avisar({ sucesso: 'Objeto do contrato excluído.' });
      carregar();
    } catch (e) { avisar({ erro: e.message }); }
  };

  if (erro) return <ErroTela mensagem={erro} onTentar={carregar} />;
  if (!lista) return <Carregando />;

  return (
    <>
      <div className="titulo-pagina">
        <div>
          <h2>Objetos do contrato</h2>
          <p className="sub">O que cada contrato cobre. Escolhido no cadastro do trabalhador e impresso em todos os recibos.</p>
        </div>
        {isAdmin && <button className="btn primario" onClick={() => setEditando('novo')}>Novo objeto</button>}
      </div>
      <div className="tabela-container">
        <table className="tabela-pilha">
          <thead><tr><th>Descrição</th><th>Em uso por</th><th>Situação</th>{isAdmin && <th><span className="oculto">Ações</span></th>}</tr></thead>
          <tbody>
            {lista.length === 0 && <tr><td colSpan={4} className="vazio">Nenhum objeto cadastrado.</td></tr>}
            {lista.map((o) => (
              <tr key={o.id}>
                <td className="principal"><strong>{o.descricao}</strong></td>
                <td data-label="Em uso por">{o.trabalhadores === 0 ? '—' : `${o.trabalhadores} ${o.trabalhadores === 1 ? 'trabalhador' : 'trabalhadores'}`}</td>
                <td data-label="Situação">{o.ativo ? <Badge tipo="verde">Ativo</Badge> : <Badge>Desativado</Badge>}</td>
                {isAdmin && (
                  <td className="acoes-linha">
                    <button className="btn pequeno" onClick={() => setEditando(o)}>Editar</button>
                    {o.trabalhadores === 0 && <button className="btn pequeno perigo" onClick={() => excluir(o)}>Excluir</button>}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!isAdmin && <p className="dica">Somente administradores podem alterar esta lista.</p>}
      {editando && <FormObjeto objeto={editando === 'novo' ? null : editando} onClose={() => setEditando(null)} onSalvar={salvar} />}
    </>
  );
}

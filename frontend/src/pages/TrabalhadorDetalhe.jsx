import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import TrabalhadorForm from '../components/TrabalhadorForm';
import { Alerta, Badge, Campo } from '../components/ui';
import { brl, cpfFmt, DIAS_SEMANA, ROTULOS, vtPorDia } from '../utils';

const BENEFICIO_VAZIO = { tipo: 'vale_transporte', natureza: 'provento', descricao: '', valor: '' };

function ConfiguracaoFinanceira({ trabalhador, onAtualizar }) {
  const [salario, setSalario] = useState(trabalhador.salario_base);
  const [form, setForm] = useState(BENEFICIO_VAZIO);
  const [editandoId, setEditandoId] = useState(null);
  const [msg, setMsg] = useState({});

  const salvarSalario = async (e) => {
    e.preventDefault();
    try {
      await api.put(`/trabalhadores/${trabalhador.id}`, { salario_base: String(salario).replace(',', '.') });
      setMsg({ sucesso: 'Salário base atualizado.' });
      onAtualizar();
    } catch (err) { setMsg({ erro: err.message }); }
  };

  const salvarBeneficio = async (e) => {
    e.preventDefault();
    const dados = { ...form, descricao: form.descricao || null, valor: String(form.valor).replace(',', '.') };
    try {
      if (editandoId) await api.put(`/trabalhadores/${trabalhador.id}/beneficios/${editandoId}`, dados);
      else await api.post(`/trabalhadores/${trabalhador.id}/beneficios`, dados);
      setForm(BENEFICIO_VAZIO);
      setEditandoId(null);
      setMsg({ sucesso: 'Benefício salvo.' });
      onAtualizar();
    } catch (err) { setMsg({ erro: err.message }); }
  };

  const excluir = async (b) => {
    if (!window.confirm(`Remover ${ROTULOS.beneficio[b.tipo]}?`)) return;
    try {
      await api.del(`/trabalhadores/${trabalhador.id}/beneficios/${b.id}`);
      onAtualizar();
    } catch (err) { setMsg({ erro: err.message }); }
  };

  const editar = (b) => {
    setEditandoId(b.id);
    setForm({ tipo: b.tipo, natureza: b.natureza, descricao: b.descricao || '', valor: b.valor });
  };

  const valorHora = Number(trabalhador.salario_base) / 220;
  const cotaVT = Number(trabalhador.salario_base) * 0.06;

  return (
    <>
      <Alerta {...msg} />
      <section className="painel">
        <h3>Salário base</h3>
        <form className="linha-form" onSubmit={salvarSalario}>
          <Campo label="Salário mensal (R$)">
            <input type="number" min="0" step="0.01" value={salario} onChange={(e) => setSalario(e.target.value)} required />
          </Campo>
          <button className="btn primario">Salvar salário</button>
        </form>
        <p className="dica">
          Valor-hora (divisor 220h): <strong>{brl(valorHora)}</strong> · Hora extra 50%: {brl(valorHora * 1.5)} · 100%: {brl(valorHora * 2)}
        </p>
      </section>

      <section className="painel">
        <h3>Benefícios fixos mensais</h3>
        <p className="dica">
          Vale-transporte é informado por dia e multiplicado pelos dias úteis do mês
          ({DIAS_SEMANA.filter(([d]) => trabalhador.dias_semana_trabalho.includes(d)).map(([, r]) => r).join(', ')},
          sem feriados nacionais; ajustável na tela da folha).
        </p>
        <div className="tabela-container">
          <table>
            <thead><tr><th>Tipo</th><th>Descrição</th><th>Tratamento na folha</th><th>Valor</th><th /></tr></thead>
            <tbody>
              {trabalhador.beneficios.length === 0 && <tr><td colSpan={5} className="vazio">Nenhum benefício cadastrado.</td></tr>}
              {trabalhador.beneficios.map((b) => (
                <tr key={b.id}>
                  <td>{ROTULOS.beneficio[b.tipo]}</td>
                  <td>{b.descricao}</td>
                  <td><Badge tipo={b.natureza === 'provento' ? 'verde' : b.natureza === 'desconto' ? 'vermelho' : 'neutro'}>{ROTULOS.natureza[b.natureza]}</Badge></td>
                  <td>{brl(b.valor)}{vtPorDia(b) && ' / dia útil'}</td>
                  <td className="acoes-linha">
                    <button className="btn pequeno" onClick={() => editar(b)}>Editar</button>
                    <button className="btn pequeno perigo" onClick={() => excluir(b)}>Remover</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h4>{editandoId ? 'Editar benefício' : 'Adicionar benefício'}</h4>
        <form onSubmit={salvarBeneficio}>
          <div className="grade-form">
            <Campo label="Tipo">
              <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                {Object.entries(ROTULOS.beneficio).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Campo>
            <Campo label="Tratamento na folha" dica="Use 'Desconta do salário' para a cota do empregado no VT (até 6% do salário).">
              <select value={form.natureza} onChange={(e) => setForm({ ...form, natureza: e.target.value })}>
                {Object.entries(ROTULOS.natureza).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Campo>
            <Campo label="Descrição (opcional)">
              <input value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} placeholder="Ex.: Cota 6% VT" />
            </Campo>
            <Campo label={vtPorDia(form) ? 'Valor por dia útil (R$)' : 'Valor mensal (R$)'}
              dica={vtPorDia(form) ? 'Ida + volta de um dia de trabalho.' : undefined}>
              <input type="number" min="0" step="0.01" value={form.valor} onChange={(e) => setForm({ ...form, valor: e.target.value })} required />
            </Campo>
          </div>
          {form.tipo === 'vale_transporte' && form.natureza === 'desconto' && (
            <p className="dica">
              Sugestão de cota de 6%: {brl(cotaVT)}{' '}
              <button type="button" className="btn-link" onClick={() => setForm({ ...form, valor: cotaVT.toFixed(2) })}>usar este valor</button>
            </p>
          )}
          <div className="acoes direita">
            {editandoId && <button type="button" className="btn" onClick={() => { setEditandoId(null); setForm(BENEFICIO_VAZIO); }}>Cancelar</button>}
            <button className="btn primario">{editandoId ? 'Salvar alterações' : 'Adicionar'}</button>
          </div>
        </form>
      </section>
    </>
  );
}

export default function TrabalhadorDetalhe() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const aba = params.get('aba') || 'dados';
  const [trabalhador, setTrabalhador] = useState(null);
  const [msg, setMsg] = useState({});

  const carregar = useCallback(
    () => api.get(`/trabalhadores/${id}`).then(setTrabalhador).catch((e) => setMsg({ erro: e.message })),
    [id],
  );
  useEffect(() => { carregar(); }, [carregar]);

  if (!trabalhador) return msg.erro ? <Alerta erro={msg.erro} /> : <div className="carregando">Carregando…</div>;

  const salvarDados = async (dados) => {
    const t = await api.put(`/trabalhadores/${id}`, dados);
    setTrabalhador(t);
    setMsg({ sucesso: 'Dados atualizados.' });
  };

  const excluir = async () => {
    if (!window.confirm(`Excluir ${trabalhador.nome}? Lançamentos, férias e folhas em rascunho também serão apagados.`)) return;
    try {
      await api.del(`/trabalhadores/${id}`);
      navigate('/trabalhadores');
    } catch (err) { setMsg({ erro: err.message }); }
  };

  return (
    <>
      <div className="titulo-pagina">
        <div>
          <Link to="/trabalhadores" className="voltar">← Trabalhadores</Link>
          <h2>{trabalhador.nome}</h2>
          <p className="sub">CPF {cpfFmt(trabalhador.cpf)} · {ROTULOS.tipo_contrato[trabalhador.tipo_contrato]}</p>
        </div>
        <button className="btn perigo" onClick={excluir}>Excluir</button>
      </div>

      <div className="abas">
        <button className={aba === 'dados' ? 'ativa' : ''} onClick={() => setParams({ aba: 'dados' })}>Dados cadastrais</button>
        <button className={aba === 'financeiro' ? 'ativa' : ''} onClick={() => setParams({ aba: 'financeiro' })}>Configuração financeira</button>
      </div>

      {aba === 'dados' ? (
        <section className="painel">
          <Alerta {...msg} />
          <TrabalhadorForm key={trabalhador.id} inicial={trabalhador} onSalvar={salvarDados} />
        </section>
      ) : (
        <ConfiguracaoFinanceira key={trabalhador.salario_base} trabalhador={trabalhador} onAtualizar={carregar} />
      )}
    </>
  );
}

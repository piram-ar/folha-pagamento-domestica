import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { Alerta, Badge, Campo } from '../components/ui';
import { dataBR, hoje, ROTULOS, somarDias } from '../utils';

const COR_SITUACAO = {
  em_aquisicao: 'azul', disponivel: 'verde', vence_em_breve: 'amarelo', vencido: 'vermelho', quitado: 'neutro',
};

function RegistrarGozo({ resumo, onRegistrado }) {
  const comSaldo = resumo.periodos.filter((p) => p.saldo_dias > 0);
  const [form, setForm] = useState({ periodo: '', data_inicio: hoje(), dias: 15, observacao: '' });
  const [msg, setMsg] = useState({});
  const periodo = comSaldo.find((p) => String(p.id) === form.periodo) || comSaldo[0];
  const dias = Number(form.dias) || 0;

  const enviar = async (e) => {
    e.preventDefault();
    setMsg({});
    try {
      await api.post(`/ferias/trabalhador/${resumo.trabalhador_id}/gozos`, {
        historico_ferias_id: periodo?.id,
        data_inicio: form.data_inicio,
        dias,
        observacao: form.observacao || null,
      });
      setMsg({ sucesso: `${dias} dias de férias registrados.` });
      setForm({ ...form, observacao: '' });
      onRegistrado();
    } catch (err) { setMsg({ erro: err.message }); }
  };

  if (!comSaldo.length) return <p className="vazio">Sem saldo de férias disponível.</p>;

  return (
    <form onSubmit={enviar}>
      <Alerta {...msg} />
      <div className="grade-form">
        <Campo label="Período aquisitivo">
          <select value={form.periodo || String(periodo.id)} onChange={(e) => setForm({ ...form, periodo: e.target.value })}>
            {comSaldo.map((p) => (
              <option key={p.id} value={p.id}>
                {dataBR(p.periodo_aquisitivo_inicio)} a {dataBR(p.periodo_aquisitivo_fim)} — saldo {p.saldo_dias} dias
                {!p.completo ? ' (em aquisição)' : ''}
              </option>
            ))}
          </select>
        </Campo>
        <Campo label="Início das férias">
          <input type="date" value={form.data_inicio} onChange={(e) => setForm({ ...form, data_inicio: e.target.value })} required />
        </Campo>
        <Campo label="Dias de gozo">
          <input type="number" min="1" max={periodo.saldo_dias} value={form.dias} onChange={(e) => setForm({ ...form, dias: e.target.value })} required />
        </Campo>
        <Campo label="Observação">
          <input value={form.observacao} onChange={(e) => setForm({ ...form, observacao: e.target.value })} />
        </Campo>
      </div>
      {dias > 0 && (
        <p className="previa">
          Retorno após {dataBR(somarDias(form.data_inicio, dias - 1))} · Saldo restante no período:{' '}
          <strong>{periodo.saldo_dias - dias} dias</strong>
        </p>
      )}
      {!periodo.completo && <p className="alerta aviso">Este período ainda está em aquisição: seriam férias antecipadas.</p>}
      {dias > 0 && dias < 14 && periodo.dias_gozados === 0 && (
        <p className="dica">Lembrete (LC 150/2015): se dividir as férias em 2 períodos, um deles deve ter pelo menos 14 dias.</p>
      )}
      <div className="acoes direita"><button className="btn primario">Registrar férias</button></div>
    </form>
  );
}

export default function Ferias() {
  const [dashboard, setDashboard] = useState([]);
  const [selecionado, setSelecionado] = useState(null);
  const [erro, setErro] = useState('');

  const carregar = useCallback(() => api.get('/ferias/dashboard')
    .then((lista) => {
      setDashboard(lista);
      setSelecionado((atual) => atual ?? lista[0]?.trabalhador_id ?? null);
    })
    .catch((e) => setErro(e.message)), []);
  useEffect(() => { carregar(); }, [carregar]);

  const resumo = dashboard.find((r) => r.trabalhador_id === selecionado);

  const excluirGozo = async (g) => {
    if (!window.confirm('Excluir este registro de férias? Os dias voltarão ao saldo.')) return;
    try {
      await api.del(`/ferias/gozos/${g.id}`);
      carregar();
    } catch (e) { setErro(e.message); }
  };

  return (
    <>
      <h2>Férias</h2>
      <Alerta erro={erro} />
      <div className="cartoes-ferias">
        {dashboard.length === 0 && <p className="vazio">Nenhum trabalhador ativo.</p>}
        {dashboard.map((r) => (
          <button key={r.trabalhador_id} className={`cartao-ferias ${r.trabalhador_id === selecionado ? 'selecionado' : ''}`}
            onClick={() => setSelecionado(r.trabalhador_id)}>
            <strong>{r.trabalhador_nome}</strong>
            <span className="saldo">{r.saldo_total} <small>dias de saldo</small></span>
            {r.periodo_atual && (
              <>
                <div className="barra"><div style={{ width: `${(r.periodo_atual.dias_adquiridos / 30) * 100}%` }} /></div>
                <small>Período atual: {r.periodo_atual.dias_adquiridos}/30 dias adquiridos</small>
              </>
            )}
            {r.saldo_vencido > 0 && <Badge tipo="vermelho">{r.saldo_vencido} dias vencidos</Badge>}
          </button>
        ))}
      </div>

      {resumo && (
        <>
          {resumo.alertas.length > 0 && (
            <div className="alerta aviso"><ul>{resumo.alertas.map((a) => <li key={a}>{a}</li>)}</ul></div>
          )}

          <section className="painel">
            <h3>Períodos aquisitivos de {resumo.trabalhador_nome}</h3>
            <p className="dica">Início em {dataBR(resumo.data_admissao)}. Cada 12 meses trabalhados geram 30 dias de férias.</p>
            <div className="tabela-container">
              <table className="tabela-pilha">
                <thead>
                  <tr><th>Período aquisitivo</th><th>Conceder até</th><th>Adquiridos</th><th>Gozados</th><th>Saldo</th><th>Situação</th><th>Gozos registrados</th></tr>
                </thead>
                <tbody>
                  {resumo.periodos.map((p) => (
                    <tr key={p.id}>
                      <td className="principal"><strong>{dataBR(p.periodo_aquisitivo_inicio)} a {dataBR(p.periodo_aquisitivo_fim)}</strong></td>
                      <td data-label="Conceder até">{dataBR(p.limite_concessivo)}</td>
                      <td data-label="Adquiridos">{p.dias_adquiridos}</td>
                      <td data-label="Gozados">{p.dias_gozados}</td>
                      <td data-label="Saldo"><strong>{p.saldo_dias}</strong></td>
                      <td data-label="Situação"><Badge tipo={COR_SITUACAO[p.situacao]}>{ROTULOS.situacao_ferias[p.situacao]}</Badge></td>
                      <td data-label="Gozos registrados">
                        {p.gozos.length === 0 ? '—' : <div>{p.gozos.map((g) => (
                          <div key={g.id} className="gozo">
                            {dataBR(g.data_inicio)} a {dataBR(g.data_fim)} ({g.dias}d){g.observacao && ` · ${g.observacao}`}
                            <button className="btn-link perigo" onClick={() => excluirGozo(g)} title="Excluir">✕</button>
                          </div>
                        ))}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="painel">
            <h3>Registrar gozo de férias</h3>
            <RegistrarGozo key={resumo.trabalhador_id} resumo={resumo} onRegistrado={carregar} />
          </section>
        </>
      )}
    </>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { abrirPdf, api } from '../api';
import { MODO_APP } from '../plataforma';
import { useAvisar, useConfirmar } from '../components/feedback';
import { Alerta, Badge, Campo, Carregando, ErroTela, Modal, ModalPagamento } from '../components/ui';
import { brl, dataBR, hoje, ROTULOS, somarDias } from '../utils';

const COR_SITUACAO = {
  em_aquisicao: 'azul', disponivel: 'verde', vence_em_breve: 'amarelo', vencido: 'vermelho', quitado: 'neutro',
};

function RegistrarGozo({ resumo, onRegistrado, onClose }) {
  const comSaldo = resumo.periodos.filter((p) => p.saldo_dias > 0);
  const [form, setForm] = useState({
    periodo: '', data_inicio: hoje(), dias: 15, dias_abono: 0, observacao: '', data_pagamento: '',
  });
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);
  const avisar = useAvisar();
  const periodo = comSaldo.find((p) => String(p.id) === form.periodo) || comSaldo[0];
  const dias = Number(form.dias) || 0;
  const abono = Number(form.dias_abono) || 0;
  // Abono pecuniário: até 1/3 dos dias do período (10 de 30), descontado o que já foi vendido nele
  const abonoUsado = periodo ? periodo.gozos.reduce((s, g) => s + (g.dias_abono || 0), 0) : 0;
  const abonoMaximo = periodo ? Math.max(0, Math.min(Math.floor(periodo.dias_adquiridos / 3) - abonoUsado, periodo.saldo_dias - dias)) : 0;
  // Pagamento até 2 dias antes do início (art. 145 da CLT)
  const pagamento = form.data_pagamento || somarDias(form.data_inicio, -2);

  const enviar = async (e) => {
    e.preventDefault();
    setErro('');
    setEnviando(true);
    try {
      await api.post(`/ferias/trabalhador/${resumo.trabalhador_id}/gozos`, {
        historico_ferias_id: periodo?.id,
        data_inicio: form.data_inicio,
        dias,
        dias_abono: abono,
        observacao: form.observacao || null,
        data_pagamento: pagamento,
      });
      avisar({ sucesso: `${dias} dias de férias${abono ? ` e ${abono} de abono` : ''} registrados e pagamento calculado. O recibo já pode ser gerado.` });
      onRegistrado();
      onClose();
    } catch (err) { setErro(err.message); setEnviando(false); }
  };

  return (
    <form onSubmit={enviar}>
      <Alerta erro={erro} />
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
          <input type="number" min="1" max={periodo.saldo_dias - abono} value={form.dias} onChange={(e) => setForm({ ...form, dias: e.target.value })} required />
        </Campo>
        <Campo label="Dias vendidos (abono pecuniário)" dica={`Até ${abonoMaximo} dia(s). O trabalhador trabalha esses dias e recebe o abono + 1/3, sem INSS.`}>
          <input type="number" min="0" max={abonoMaximo} value={form.dias_abono} onChange={(e) => setForm({ ...form, dias_abono: e.target.value })} />
        </Campo>
        <Campo label="Pagamento das férias" dica="Até 2 dias antes do início.">
          <input type="date" value={pagamento} onChange={(e) => setForm({ ...form, data_pagamento: e.target.value })} required />
        </Campo>
        <Campo label="Observação">
          <input value={form.observacao} onChange={(e) => setForm({ ...form, observacao: e.target.value })} />
        </Campo>
      </div>
      {dias > 0 && form.data_inicio && (
        <p className="previa">
          Retorno após {dataBR(somarDias(form.data_inicio, dias - 1))}
          {abono > 0 && <> · {abono} dias vendidos</>} · Saldo restante no período:{' '}
          <strong>{periodo.saldo_dias - dias - abono} dias</strong>
        </p>
      )}
      {!periodo.completo && <p className="alerta aviso">Este período ainda está em aquisição: seriam férias antecipadas.</p>}
      {abono > 0 && (
        <p className="dica">
          Abono pecuniário (LC 150/2015, art. 17): o trabalhador pode vender até 1/3 das férias, pedindo até 30 dias antes
          do fim do período aquisitivo. Os dias vendidos são trabalhados e pagos normalmente na folha.
        </p>
      )}
      {dias > 0 && dias < 14 && periodo.dias_gozados === 0 && (
        <p className="dica">Lembrete (LC 150/2015): se dividir as férias em 2 períodos, um deles deve ter pelo menos 14 dias.</p>
      )}
      <div className="acoes direita">
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
        <button className="btn primario" disabled={enviando}>{enviando ? 'Registrando…' : 'Registrar férias'}</button>
      </div>
    </form>
  );
}

/** Recalcula o pagamento (salário dos dias + média de horas extras + 1/3), podendo mudar a data. */
function CalcularPagamento({ gozo, onClose, onConfirmar }) {
  const [data, setData] = useState(gozo.data_pagamento || somarDias(gozo.data_inicio, -2));
  return (
    <Modal titulo="Calcular pagamento das férias" onClose={onClose}>
      <form onSubmit={(e) => { e.preventDefault(); onConfirmar(data); }}>
        <p>Férias de {dataBR(gozo.data_inicio)} a {dataBR(gozo.data_fim)} ({gozo.dias} dias).</p>
        <Campo label="Data do pagamento" dica="Até 2 dias antes do início das férias.">
          <input type="date" value={data} onChange={(e) => setData(e.target.value)} required autoFocus />
        </Campo>
        <div className="acoes direita">
          <button type="button" className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn primario">Calcular</button>
        </div>
      </form>
    </Modal>
  );
}

/** Valor de cada férias registrada, recibo (gerado só aqui) e situação do pagamento. */
function PagamentosFerias({ resumo, onAlterado }) {
  const avisar = useAvisar();
  const confirmar = useConfirmar();
  const [calculando, setCalculando] = useState(null);
  const [pagando, setPagando] = useState(null);
  const gozos = resumo.periodos.flatMap((p) => p.gozos).sort((a, b) => b.data_inicio.localeCompare(a.data_inicio));
  if (!gozos.length) return <p className="vazio">Nenhuma férias registrada.</p>;

  const executar = (acao) => acao().then(onAlterado).catch((e) => avisar({ erro: e.message }));
  const calcular = (g, data) => executar(async () => {
    await api.post(`/ferias/gozos/${g.id}/calcular`, { data_pagamento: data });
    setCalculando(null);
  });
  const pagar = (g, data) => executar(async () => {
    await api.post(`/ferias/gozos/${g.id}/pagar`, { pago_em: data });
    setPagando(null);
  });
  const desfazer = async (g) => {
    if (!await confirmar({ titulo: 'Desfazer o pagamento?', texto: 'Estas férias voltam a ficar em aberto.', acao: 'Desfazer pagamento' })) return;
    executar(() => api.del(`/ferias/gozos/${g.id}/pagamento`));
  };
  const recibo = (g) => abrirPdf(`/ferias/gozos/${g.id}/recibo.pdf`).catch((e) => avisar({ erro: e.message }));

  return (
    <>
      <div className="tabela-container">
        <table className="tabela-pilha">
          <thead>
            <tr>
              <th>Período</th><th className="num">Férias</th><th className="num">1/3</th><th className="num">Abono + 1/3</th>
              <th className="num">INSS</th><th className="num">Líquido</th><th>Situação</th><th><span className="oculto">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            {gozos.map((g) => {
              const calculado = g.valor_ferias != null;
              return (
                <tr key={g.id}>
                  <td className="principal">
                    <span>
                      <strong>{dataBR(g.data_inicio)} a {dataBR(g.data_fim)}</strong><br />
                      <small>{g.dias} dias{g.dias_abono > 0 && ` + ${g.dias_abono} vendidos`}{calculado && ` · pagamento em ${dataBR(g.data_pagamento)}`}</small>
                    </span>
                  </td>
                  <td className="num" data-label="Férias">{calculado ? brl(g.valor_ferias) : '—'}</td>
                  <td className="num" data-label="1/3">{calculado ? brl(g.valor_terco) : '—'}</td>
                  <td className="num" data-label="Abono + 1/3">{calculado && Number(g.valor_abono) ? brl(g.valor_abono) : '—'}</td>
                  <td className="num" data-label="INSS">{calculado ? brl(g.inss) : '—'}</td>
                  <td className="num" data-label="Líquido"><strong>{calculado ? brl(g.liquido) : '—'}</strong></td>
                  <td data-label="Situação">
                    {!calculado ? <Badge>Não calculado</Badge>
                      : g.pago_em ? <Badge tipo="verde">Pago em {dataBR(g.pago_em)}</Badge>
                        : <Badge tipo="vermelho">Em aberto</Badge>}
                  </td>
                  <td className="acoes-linha">
                    {!g.pago_em && (
                      <button className={`btn pequeno ${calculado ? '' : 'primario'}`} onClick={() => setCalculando(g)}>
                        {calculado ? 'Recalcular' : 'Calcular pagamento'}
                      </button>
                    )}
                    {calculado && (
                      <button className="btn pequeno primario" onClick={() => recibo(g)}>
                        {MODO_APP ? 'Enviar recibo' : 'Gerar recibo'}
                      </button>
                    )}
                    {calculado && !g.pago_em && <button className="btn pequeno sucesso" onClick={() => setPagando(g)}>Marcar pago</button>}
                    {g.pago_em && <button className="btn pequeno" onClick={() => desfazer(g)}>Desfazer</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="dica">
        Férias = salário ÷ 30 × dias gozados, mais a média mensal das horas extras do período aquisitivo e o 1/3
        constitucional{resumo.tipo_contrato === 'com_registro' ? ', menos o INSS' : ''}. Dias vendidos (abono pecuniário) são
        pagos pela mesma conta, com 1/3, sem INSS. Como esse valor é pago antes, a folha
        dos meses de férias desconta os dias de férias do salário: recalcule a folha desses meses depois de registrar as férias.
      </p>
      {calculando && <CalcularPagamento gozo={calculando} onClose={() => setCalculando(null)} onConfirmar={(d) => calcular(calculando, d)} />}
      {pagando && (
        <ModalPagamento
          descricao={`Férias de ${dataBR(pagando.data_inicio)} a ${dataBR(pagando.data_fim)}`}
          valor={pagando.liquido}
          onClose={() => setPagando(null)}
          onConfirmar={(d) => pagar(pagando, d)}
        />
      )}
    </>
  );
}

export default function Ferias() {
  const [dashboard, setDashboard] = useState(null);
  const [registrando, setRegistrando] = useState(false);
  const avisar = useAvisar();
  const confirmar = useConfirmar();
  const [selecionado, setSelecionado] = useState(null);
  const [erro, setErro] = useState('');

  const carregar = useCallback(() => {
    setErro('');
    return api.get('/ferias/dashboard').then((lista) => {
      setDashboard(lista);
      setSelecionado((atual) => atual ?? lista[0]?.trabalhador_id ?? null);
    }).catch((e) => setErro(e.message));
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  if (erro) return <ErroTela mensagem={erro} onTentar={carregar} />;
  if (!dashboard) return <Carregando linhas={5} />;

  const resumo = dashboard.find((r) => r.trabalhador_id === selecionado);
  const temSaldo = resumo?.periodos.some((p) => p.saldo_dias > 0);

  const excluirGozo = async (g) => {
    if (!await confirmar({ titulo: 'Excluir este registro de férias?', texto: `De ${dataBR(g.data_inicio)} a ${dataBR(g.data_fim)}. Os dias voltam ao saldo.`, acao: 'Excluir registro', perigo: true })) return;
    try {
      await api.del(`/ferias/gozos/${g.id}`);
      avisar({ sucesso: 'Registro de férias excluído.' });
      carregar();
    } catch (e) { avisar({ erro: e.message }); }
  };

  return (
    <>
      <div className="titulo-pagina">
        <h2>Férias</h2>
        {resumo && (
          <button className="btn primario" disabled={!temSaldo} title={temSaldo ? undefined : 'Sem saldo de férias disponível'}
            onClick={() => setRegistrando(true)}>
            Registrar férias
          </button>
        )}
      </div>
      <div className="cartoes-ferias">
        {dashboard.length === 0 && <p className="vazio">Nenhum trabalhador ativo.</p>}
        {dashboard.map((r) => (
          <button key={r.trabalhador_id} className={`cartao-ferias ${r.trabalhador_id === selecionado ? 'selecionado' : ''}`}
            aria-pressed={r.trabalhador_id === selecionado} onClick={() => setSelecionado(r.trabalhador_id)}>
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
            <h3>Pagamento das férias</h3>
            <PagamentosFerias resumo={resumo} onAlterado={carregar} />
          </section>

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
                            {dataBR(g.data_inicio)} a {dataBR(g.data_fim)} ({g.dias}d{g.dias_abono > 0 && ` + ${g.dias_abono} vendidos`}){g.observacao && ` · ${g.observacao}`}
                            <button className="btn-link perigo" onClick={() => excluirGozo(g)} aria-label={`Excluir férias de ${dataBR(g.data_inicio)}`}>✕</button>
                          </div>
                        ))}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {registrando && (
            <Modal titulo={`Registrar férias de ${resumo.trabalhador_nome}`} onClose={() => setRegistrando(false)} largo>
              <RegistrarGozo key={resumo.trabalhador_id} resumo={resumo} onRegistrado={carregar} onClose={() => setRegistrando(false)} />
            </Modal>
          )}
        </>
      )}
    </>
  );
}

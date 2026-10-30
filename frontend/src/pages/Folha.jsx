import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { abrirPdf, api } from '../api';
import { useAuth } from '../AuthContext';
import { Alerta, Campo, Modal, SituacaoFolha, useTrabalhadores } from '../components/ui';
import { brl, mesAtual, mesExtenso, mesLongo, ROTULOS } from '../utils';

function DetalheFolha({ folha, onClose, onPdf, onExcluir, onReabrir }) {
  const d = folha.detalhamento || { itens: [], encargos: { itens: {} } };
  const fechada = folha.status === 'fechada';
  return (
    <Modal titulo={`${folha.trabalhador_nome}, ${mesExtenso(folha.mes_ano).toLowerCase()}`} onClose={onClose} largo>
      <div className="tabela-container">
        <table>
          <thead><tr><th>Código</th><th>Descrição</th><th>Referência</th><th className="num">Proventos</th><th className="num">Descontos</th></tr></thead>
          <tbody>
            {d.itens.map((it, i) => (
              <tr key={i}>
                <td>{it.codigo}</td><td>{it.descricao}</td><td>{it.referencia}</td>
                <td className="num">{it.tipo === 'provento' ? brl(it.valor) : ''}</td>
                <td className="num">{it.tipo === 'desconto' ? brl(it.valor) : ''}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td colSpan={3}>Totais</td><td className="num">{brl(folha.total_proventos)}</td><td className="num">{brl(folha.total_descontos)}</td></tr>
            <tr className="destaque"><td colSpan={3}>Líquido a pagar</td><td colSpan={2} className="num">{brl(folha.salario_liquido)}</td></tr>
          </tfoot>
        </table>
      </div>
      {d.beneficios_informativos?.length > 0 && (
        <p className="dica">Pagos à parte: {d.beneficios_informativos.map((b) => `${b.descricao} ${brl(b.valor)}`).join(' · ')}</p>
      )}
      <div className="painel encargos">
        <h4>{d.encargos.titulo}</h4>
        <ul>
          {Object.entries(d.encargos.itens).map(([k, v]) => <li key={k}><span>{k}</span><strong>{brl(v)}</strong></li>)}
        </ul>
        <p className="total-encargos">Total: <strong>{brl(folha.encargos_recolher_guardar)}</strong></p>
        {folha.tipo_contrato === 'com_registro' ? (
          <p className="dica">Estimativa da guia DAE do eSocial (vence dia 20 do mês seguinte). Confira sempre no portal do eSocial.</p>
        ) : (
          <p className="dica">Valor sugerido para guardar mensalmente e cobrir férias + 1/3 e 13º salário.</p>
        )}
      </div>
      <div className="acoes direita">
        {!fechada && <button className="btn perigo" onClick={onExcluir}>Excluir rascunho</button>}
        {fechada && onReabrir && <button className="btn" onClick={onReabrir}>Reabrir folha</button>}
        <button className="btn primario" onClick={onPdf}>{fechada ? 'Imprimir recibo' : 'Ver recibo (rascunho)'}</button>
      </div>
    </Modal>
  );
}

export default function Folha() {
  const { isAdmin } = useAuth();
  const trabalhadores = useTrabalhadores();
  const [mes, setMes] = useState(mesAtual());
  const [folhas, setFolhas] = useState([]);
  const [dias, setDias] = useState({});
  const [uteis, setUteis] = useState({});
  const [sugestao, setSugestao] = useState({});
  const [detalhe, setDetalhe] = useState(null);
  const [msg, setMsg] = useState({});
  const [ocupado, setOcupado] = useState(false);
  const [semContratante, setSemContratante] = useState(false);
  const [recemFechada, setRecemFechada] = useState(null);

  useEffect(() => {
    api.get('/contratante').then((c) => setSemContratante(!c)).catch(() => {});
  }, []);

  const carregar = useCallback(async () => {
    try {
      const [lista, sugeridos] = await Promise.all([
        api.get(`/folha?mes_ano=${mes}`),
        api.get(`/folha/dias-uteis?mes_ano=${mes}`),
      ]);
      setFolhas(lista);
      setDias(Object.fromEntries(lista.map((f) => [f.trabalhador_id, f.dias_trabalhados])));
      const porId = Object.fromEntries(sugeridos.map((s) => [s.trabalhador_id, s]));
      setSugestao(porId);
      // Folha já calculada mantém os dias úteis usados; senão, sugere pelo calendário do trabalhador
      const salvos = Object.fromEntries(lista.filter((f) => f.dias_uteis != null).map((f) => [f.trabalhador_id, f.dias_uteis]));
      setUteis({ ...Object.fromEntries(sugeridos.map((s) => [s.trabalhador_id, s.dias_uteis])), ...salvos });
    } catch (e) { setMsg({ erro: e.message }); }
  }, [mes]);
  useEffect(() => { carregar(); }, [carregar]);

  const porTrabalhador = Object.fromEntries(folhas.map((f) => [f.trabalhador_id, f]));
  // Inclui trabalhadores inativos que já tenham folha no mês
  const linhas = [
    ...trabalhadores,
    ...folhas.filter((f) => !trabalhadores.some((t) => t.id === f.trabalhador_id))
      .map((f) => ({ id: f.trabalhador_id, nome: f.trabalhador_nome, tipo_contrato: f.tipo_contrato })),
  ];

  const executar = async (acao, sucesso) => {
    setMsg({});
    setOcupado(true);
    try {
      await acao();
      if (sucesso) setMsg({ sucesso });
      await carregar();
    } catch (e) { setMsg({ erro: e.message }); } finally { setOcupado(false); }
  };

  const corpo = (t) => ({
    trabalhador_id: t.id,
    mes_ano: mes,
    dias_trabalhados: Number(dias[t.id] ?? 30),
    // Vazio = o servidor calcula pelo calendário do trabalhador
    dias_uteis: uteis[t.id] === '' || uteis[t.id] == null ? undefined : Number(uteis[t.id]),
  });

  const calcular = (t) => executar(
    () => api.post('/folha/calcular', corpo(t)),
    `Folha de ${t.nome} calculada.`,
  );

  const calcularTodos = () => executar(async () => {
    for (const t of linhas) {
      if (porTrabalhador[t.id]?.status === 'fechada') continue;
      await api.post('/folha/calcular', corpo(t));
    }
  }, 'Folhas em rascunho recalculadas.');

  const fechar = (f) => {
    if (!window.confirm(`Fechar a folha de ${f.trabalhador_nome}? Os lançamentos do mês ficarão bloqueados.`)) return;
    executar(async () => {
      await api.post(`/folha/${f.id}/fechar`);
      setRecemFechada(f.id);
    }, `Folha de ${f.trabalhador_nome} fechada. O recibo já pode ser impresso.`);
  };
  const reabrir = (f) => executar(() => api.post(`/folha/${f.id}/reabrir`), `Folha de ${f.trabalhador_nome} reaberta.`);
  const excluir = (f) => {
    if (!window.confirm(`Excluir o rascunho da folha de ${f.trabalhador_nome}?`)) return;
    executar(() => api.del(`/folha/${f.id}`), 'Rascunho excluído.');
  };
  const pdf = (f) => abrirPdf(`/folha/${f.id}/recibo.pdf`).catch((e) => setMsg({ erro: e.message }));

  const total = (campo) => folhas.reduce((s, f) => s + Number(f[campo]), 0);

  return (
    <>
      <div className="titulo-pagina">
        <div>
          <h2>Folha de pagamento</h2>
          <p className="sub">{mesLongo(mes)}</p>
        </div>
        <div className="acoes">
          <Campo label="Competência">
            <input type="month" value={mes} onChange={(e) => e.target.value && setMes(e.target.value)} />
          </Campo>
          <button className="btn primario" onClick={calcularTodos} disabled={ocupado || !linhas.length}>Calcular todas</button>
        </div>
      </div>
      <Alerta {...msg} />
      {semContratante && (
        <div className="alerta erro">
          Os dados do empregador/contratante e do local do serviço ainda não foram cadastrados e não sairão no recibo.{' '}
          <Link to="/contratante">Cadastrar agora</Link>
        </div>
      )}
      <p className="dica">
        Dias trabalhados: 30 é o mês completo; use menos só em admissão ou desligamento.
        Os dias úteis do vale-transporte vêm do calendário de cada trabalhador; ajuste se houver feriado local ou folga.
      </p>

      <div className="tabela-container">
        <table className="tabela-pilha">
          <thead>
            <tr>
              <th>Trabalhador</th><th>Dias</th><th title="Dias úteis do vale-transporte">Dias úteis (VT)</th>
              <th className="num">Líquido</th><th className="num">Encargos / reserva</th><th>Situação</th><th><span className="oculto">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            {linhas.length === 0 && <tr><td colSpan={7} className="vazio">Nenhum trabalhador ativo.</td></tr>}
            {linhas.map((t) => {
              const f = porTrabalhador[t.id];
              const fechada = f?.status === 'fechada';
              return (
                <tr key={t.id}>
                  <td className="principal"><span><strong>{t.nome}</strong><br /><small>{ROTULOS.tipo_contrato[t.tipo_contrato]}</small></span></td>
                  <td data-label="Dias trabalhados">
                    <input className="input-dias" type="number" min="0" max="31" disabled={fechada}
                      value={dias[t.id] ?? 30} onChange={(e) => setDias({ ...dias, [t.id]: e.target.value })} />
                  </td>
                  <td data-label="Dias úteis (VT)">
                    {sugestao[t.id]?.tem_vt_diario ? (
                      <input className="input-dias" type="number" min="0" max="31" disabled={fechada}
                        title={`Sugerido: ${sugestao[t.id].dias_uteis}`}
                        value={uteis[t.id] ?? ''} onChange={(e) => setUteis({ ...uteis, [t.id]: e.target.value })} />
                    ) : '—'}
                  </td>
                  <td className="num" data-label="Líquido"><strong>{f ? brl(f.salario_liquido) : '—'}</strong></td>
                  <td className="num" data-label="Encargos / reserva">{f ? brl(f.encargos_recolher_guardar) : '—'}</td>
                  <td data-label="Situação"><SituacaoFolha folha={f} recemFechada={f?.id === recemFechada} /></td>
                  <td className="acoes-linha">
                    {/* Uma ação principal por etapa: calcular → fechar → imprimir */}
                    {!f && <button className="btn pequeno primario" disabled={ocupado} onClick={() => calcular(t)}>Calcular</button>}
                    {f && !fechada && <button className="btn pequeno" disabled={ocupado} onClick={() => calcular(t)}>Recalcular</button>}
                    {f && !fechada && <button className="btn pequeno sucesso" disabled={ocupado} onClick={() => fechar(f)}>Fechar</button>}
                    {fechada && <button className="btn pequeno primario" onClick={() => pdf(f)}>Recibo</button>}
                    {f && <button className="btn pequeno" onClick={() => setDetalhe(f)}>Detalhes</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {folhas.length > 0 && (
            <tfoot>
              <tr>
                <td colSpan={3}>Totais do mês</td>
                <td className="num">{brl(total('salario_liquido'))}</td>
                <td className="num">{brl(total('encargos_recolher_guardar'))}</td>
                <td colSpan={2} />
                <td className="total-movel">Líquido do mês <span>{brl(total('salario_liquido'))}</span></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {detalhe && (
        <DetalheFolha
          folha={detalhe}
          onClose={() => setDetalhe(null)}
          onPdf={() => pdf(detalhe)}
          onExcluir={() => { setDetalhe(null); excluir(detalhe); }}
          onReabrir={isAdmin ? () => { setDetalhe(null); reabrir(detalhe); } : null}
        />
      )}
    </>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { abrirPdf, api, baixarArquivo } from '../../api';
import { useAvisar, useConfirmar } from '../../components/feedback';
import { Carregando, ErroTela, ModalPagamento, SeletorMes, SituacaoFolha, useTrabalhadores } from '../../components/ui';
import { MODO_APP } from '../../plataforma';
import { brl, diasDoMes, mesLongo, ROTULOS } from '../../utils';
import DetalheFolha from './DetalheFolha';

/** Calcular, conferir, fechar e pagar a folha de uma competência. */
export default function FolhaDoMes({ mes, onMes }) {
  const avisar = useAvisar();
  const confirmar = useConfirmar();
  const trabalhadores = useTrabalhadores();
  const [folhas, setFolhas] = useState(null);
  const [dias, setDias] = useState({});
  const [uteis, setUteis] = useState({});
  const [sugestao, setSugestao] = useState({});
  const [detalhe, setDetalhe] = useState(null);
  const [pagando, setPagando] = useState(null);
  const [erro, setErro] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [recemFechada, setRecemFechada] = useState(null);

  const carregar = useCallback(async () => {
    setErro('');
    try {
      const [lista, sugeridos] = await Promise.all([
        api.get(`/folha?mes_ano=${mes}&resumida=true`),
        api.get(`/folha/dias-uteis?mes_ano=${mes}`),
      ]);
      setFolhas(lista);
      setDias(Object.fromEntries(lista.map((f) => [f.trabalhador_id, f.dias_trabalhados])));
      setSugestao(Object.fromEntries(sugeridos.map((s) => [s.trabalhador_id, s])));
      // Folha já calculada mantém os dias úteis usados; senão, sugere pelo calendário do trabalhador
      const salvos = Object.fromEntries(lista.filter((f) => f.dias_uteis != null).map((f) => [f.trabalhador_id, f.dias_uteis]));
      setUteis({ ...Object.fromEntries(sugeridos.map((s) => [s.trabalhador_id, s.dias_uteis])), ...salvos });
    } catch (e) { setErro(e.message); }
  }, [mes]);
  useEffect(() => { setFolhas(null); carregar(); }, [carregar]);

  const seletor = (
    <div className="barra-tela">
      <SeletorMes mes={mes} onChange={onMes} />
    </div>
  );
  if (erro) return <>{seletor}<ErroTela mensagem={erro} onTentar={carregar} /></>;
  if (!folhas || !trabalhadores) return <>{seletor}<Carregando linhas={4} /></>;

  const porTrabalhador = Object.fromEntries(folhas.map((f) => [f.trabalhador_id, f]));
  // Inclui trabalhadores inativos que já tenham folha no mês
  const linhas = [
    ...trabalhadores,
    ...folhas.filter((f) => !trabalhadores.some((t) => t.id === f.trabalhador_id))
      .map((f) => ({ id: f.trabalhador_id, nome: f.trabalhador_nome, tipo_contrato: f.tipo_contrato })),
  ];
  const diasNoMes = diasDoMes(mes);
  // Sem folha calculada: mês completo, ou a partir da admissão no mês dela
  const diasPadrao = (t) => sugestao[t.id]?.dias_sugeridos ?? diasNoMes;
  const abertas = linhas.filter((t) => porTrabalhador[t.id]?.status !== 'fechada');

  const executar = async (acao, sucesso) => {
    setOcupado(true);
    try {
      await acao();
      if (sucesso) avisar({ sucesso });
      await carregar();
    } catch (e) { avisar({ erro: e.message }); } finally { setOcupado(false); }
  };

  const corpo = (t) => ({
    trabalhador_id: t.id,
    mes_ano: mes,
    dias_trabalhados: Number(dias[t.id] ?? diasPadrao(t)),
    // Vazio = o servidor calcula pelo calendário do trabalhador
    dias_uteis: uteis[t.id] === '' || uteis[t.id] == null ? undefined : Number(uteis[t.id]),
  });

  const calcular = (t) => executar(() => api.post('/folha/calcular', corpo(t)), `Folha de ${t.nome} calculada.`);

  const calcularTodas = () => executar(async () => {
    for (const t of abertas) await api.post('/folha/calcular', corpo(t));
  }, abertas.length === 1 ? 'Folha calculada.' : `${abertas.length} folhas calculadas.`);

  const fechar = async (f) => {
    if (!await confirmar({
      titulo: `Fechar a folha de ${f.trabalhador_nome}?`,
      texto: `Os lançamentos de ${mesLongo(mes).toLowerCase()} ficam bloqueados e o recibo passa a valer.`,
      acao: 'Fechar folha',
    })) return;
    executar(async () => {
      await api.post(`/folha/${f.id}/fechar`);
      setRecemFechada(f.id);
    }, `Folha de ${f.trabalhador_nome} fechada. O recibo já pode ser impresso.`);
  };
  const pagar = (f, data) => executar(async () => {
    await api.post(`/folha/${f.id}/pagar`, { pago_em: data });
    setPagando(null);
  }, `Pagamento de ${f.trabalhador_nome} registrado.`);
  const pdf = (f) => abrirPdf(`/folha/${f.id}/recibo.pdf`).catch((e) => avisar({ erro: e.message }));

  const total = (campo) => folhas.reduce((s, f) => s + Number(f[campo]), 0);
  const comRegistro = folhas.some((f) => f.tipo_contrato === 'com_registro');
  const guiaPdf = () => abrirPdf(`/folha/esocial.pdf?mes_ano=${mes}`).catch((e) => avisar({ erro: e.message }));
  const guiaCsv = () => baixarArquivo(`/folha/esocial.csv?mes_ano=${mes}`, `esocial_${mes}.csv`).catch((e) => avisar({ erro: e.message }));

  return (
    <>
      <div className="barra-tela">
        <SeletorMes mes={mes} onChange={onMes} />
        {abertas.length > 0 && (
          <button className="btn primario" onClick={calcularTodas} disabled={ocupado}>
            {ocupado ? 'Calculando…' : 'Calcular todas'}
          </button>
        )}
      </div>

      <div className="tabela-container">
        <table className="tabela-pilha">
          <thead>
            <tr>
              <th>Trabalhador</th><th>Dias trabalhados</th><th title="Dias úteis do vale-transporte">Dias úteis (VT)</th>
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
                    <span className="dias-folha">
                      <input className="input-dias" type="number" min="0" max={diasNoMes} disabled={fechada} aria-label={`Dias trabalhados de ${t.nome}`}
                        value={dias[t.id] ?? diasPadrao(t)} onChange={(e) => setDias({ ...dias, [t.id]: e.target.value })} />
                      <small>de {diasNoMes}</small>
                    </span>
                  </td>
                  <td data-label="Dias úteis (VT)">
                    {sugestao[t.id]?.tem_vt_diario ? (
                      <input className="input-dias" type="number" min="0" max="31" disabled={fechada} aria-label={`Dias úteis do vale-transporte de ${t.nome}`}
                        title={`Sugerido: ${sugestao[t.id].dias_uteis}`}
                        value={uteis[t.id] ?? ''} onChange={(e) => setUteis({ ...uteis, [t.id]: e.target.value })} />
                    ) : '—'}
                  </td>
                  <td className="num" data-label="Líquido"><strong>{f ? brl(f.salario_liquido) : '—'}</strong></td>
                  <td className="num" data-label="Encargos / reserva">{f ? brl(f.encargos_recolher_guardar) : '—'}</td>
                  <td data-label="Situação"><SituacaoFolha folha={f} recemFechada={f?.id === recemFechada} /></td>
                  <td className="acoes-linha">
                    {/* Uma ação principal por etapa: calcular → fechar → imprimir → pagar */}
                    {!f && <button className="btn pequeno primario" disabled={ocupado} onClick={() => calcular(t)}>Calcular</button>}
                    {f && !fechada && <button className="btn pequeno" disabled={ocupado} onClick={() => calcular(t)}>Recalcular</button>}
                    {f && !fechada && <button className="btn pequeno sucesso" disabled={ocupado} onClick={() => fechar(f)}>Fechar</button>}
                    {fechada && (
                      <button className="btn pequeno primario" onClick={() => pdf(f)}>
                        {MODO_APP ? 'Enviar ' : ''}{t.tipo_contrato === 'com_registro' ? (MODO_APP ? 'holerite' : 'Holerite') : (MODO_APP ? 'recibo' : 'Recibo')}
                      </button>
                    )}
                    {fechada && !f.pago_em && <button className="btn pequeno sucesso" disabled={ocupado} onClick={() => setPagando(f)}>Marcar paga</button>}
                    {f && <button className="btn pequeno" onClick={() => setDetalhe(f.id)}>Detalhes</button>}
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

      <details className="explicacao">
        <summary>Como os dias entram no cálculo</summary>
        <p>
          Mês completo ({diasNoMes} dias) paga o salário cheio, como no mês comercial de 30 dias. Use menos dias só em
          admissão, desligamento ou afastamento: o salário fica proporcional aos {diasNoMes} dias do mês. Faltas e horas
          extras vão em Lançamentos. O vale-transporte segue os dias úteis do calendário de cada trabalhador; ajuste se
          houver feriado local ou folga.
        </p>
      </details>

      {comRegistro && (
        <section className="painel espaco-acima">
          <h3>Lançar no eSocial</h3>
          <p className="dica">
            O eSocial do empregador doméstico não aceita importação de arquivos: a folha é digitada no portal.
            A guia traz, para cada empregado com registro, as rubricas do eSocial e os valores a informar em
            Folha/Recolhimento. Salário e INSS o eSocial calcula sozinho; use-os para conferir.
          </p>
          <div className="acoes">
            <button className="btn" onClick={guiaPdf}>Guia de lançamento (PDF)</button>
            <button className="btn" onClick={guiaCsv}>Planilha (CSV)</button>
          </div>
        </section>
      )}

      {detalhe && <DetalheFolha folhaId={detalhe} onClose={() => setDetalhe(null)} onAlterado={carregar} />}
      {pagando && (
        <ModalPagamento
          descricao={`Folha de ${pagando.trabalhador_nome}`}
          valor={pagando.salario_liquido}
          onClose={() => setPagando(null)}
          onConfirmar={(data) => pagar(pagando, data)}
        />
      )}
    </>
  );
}

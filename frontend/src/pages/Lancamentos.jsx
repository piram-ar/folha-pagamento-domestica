import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { useAvisar, useConfirmar } from '../components/feedback';
import { Abas, Badge, Campo, Carregando, InputValor, SeletorMes, useTrabalhadores } from '../components/ui';
import { brl, dataBR, diasDoMes, hoje, mesAtual, mesLongo, numero, ROTULOS } from '../utils';

const ABAS = [
  { tipo: 'vale_antecipacao', label: 'Vale / adiantamento' },
  { tipo: 'hora_extra', label: 'Hora extra' },
  { tipo: 'falta', label: 'Falta' },
  { tipo: 'bonus', label: 'Bônus' },
];

const FORM_VAZIO = { valor: '', horas: '', percentual: '50', faltaPor: 'dias', dias: '1', descricao: '', data: hoje() };

export default function Lancamentos() {
  const lista = useTrabalhadores();
  const trabalhadores = useMemo(() => lista || [], [lista]);
  const [mes, setMes] = useState(mesAtual());
  const [trabalhadorId, setTrabalhadorId] = useState('');
  const [tipo, setTipo] = useState('vale_antecipacao');
  const [form, setForm] = useState(FORM_VAZIO);
  const [eventos, setEventos] = useState(null);
  const [fechadas, setFechadas] = useState([]);
  const [enviando, setEnviando] = useState(false);
  const avisar = useAvisar();
  const confirmar = useConfirmar();

  useEffect(() => {
    if (!trabalhadorId && trabalhadores.length) setTrabalhadorId(String(trabalhadores[0].id));
  }, [trabalhadores, trabalhadorId]);

  const carregar = useCallback(
    () => Promise.all([api.get(`/eventos?mes_ano=${mes}`), api.get(`/folha?mes_ano=${mes}&resumida=true`)])
      .then(([lancados, folhas]) => {
        setEventos(lancados);
        setFechadas(folhas.filter((f) => f.status === 'fechada').map((f) => String(f.trabalhador_id)));
      })
      .catch((e) => avisar({ erro: e.message })),
    [mes, avisar],
  );
  useEffect(() => { carregar(); }, [carregar]);

  const trabalhador = trabalhadores.find((t) => String(t.id) === trabalhadorId);
  const salario = Number(trabalhador?.salario_base || 0);
  const valorHora = salario / Number(trabalhador?.horas_mensais || 200);
  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  // Pré-visualização do valor calculado (o backend recalcula com precisão)
  const previa = useMemo(() => {
    const horas = Number(numero(form.horas)) || 0;
    if (tipo === 'hora_extra') return valorHora * (1 + Number(form.percentual) / 100) * horas;
    if (tipo === 'falta') return form.faltaPor === 'dias' ? (salario / diasDoMes(mes)) * (Number(form.dias) || 0) : valorHora * horas;
    return null;
  }, [tipo, form, salario, valorHora, mes]);

  const enviar = async (e) => {
    e.preventDefault();
    const base = {
      trabalhador_id: Number(trabalhadorId),
      mes_ano: mes,
      tipo,
      data_lancamento: form.data,
      descricao: form.descricao || null,
    };
    const num = numero;
    let dados;
    if (tipo === 'hora_extra') {
      dados = { ...base, quantidade_horas: num(form.horas), percentual_adicional: form.percentual };
    } else if (tipo === 'falta' && form.faltaPor === 'horas') {
      dados = { ...base, quantidade_horas: num(form.horas) };
    } else if (tipo === 'falta') {
      // O servidor calcula pelo salário do mês do lançamento (considera reajustes)
      dados = { ...base, quantidade_dias: Number(form.dias) };
    } else {
      dados = { ...base, valor: num(form.valor) };
    }
    setEnviando(true);
    try {
      const ev = await api.post('/eventos', dados);
      avisar({ sucesso: `${ROTULOS.evento[ev.tipo]} de ${brl(ev.valor)} lançado para ${trabalhador.nome}.` });
      setForm({ ...FORM_VAZIO, percentual: form.percentual, data: form.data });
      carregar();
    } catch (err) { avisar({ erro: err.message }); } finally { setEnviando(false); }
  };

  const excluir = async (ev) => {
    if (!await confirmar({ titulo: 'Excluir este lançamento?', texto: `${ROTULOS.evento[ev.tipo]} de ${brl(ev.valor)}, ${dataBR(ev.data_lancamento)}.`, acao: 'Excluir lançamento', perigo: true })) return;
    try {
      await api.del(`/eventos/${ev.id}`);
      carregar();
    } catch (err) { avisar({ erro: err.message }); }
  };

  if (!lista) return <Carregando linhas={5} />;

  const bloqueado = fechadas.includes(trabalhadorId);
  const nomes = Object.fromEntries(trabalhadores.map((t) => [t.id, t.nome]));
  const totais = (eventos || []).reduce((acc, ev) => ({ ...acc, [ev.tipo]: (acc[ev.tipo] || 0) + Number(ev.valor) }), {});

  return (
    <>
      <div className="titulo-pagina">
        <h2>Lançamentos do mês</h2>
        <SeletorMes mes={mes} onChange={setMes} />
      </div>

      <section className="painel">
        <Abas rotulo="Tipo de lançamento" ativa={tipo} onChange={setTipo} abas={ABAS.map((a) => ({ id: a.tipo, label: a.label.split(' /')[0] }))} />
        {trabalhadores.length === 0 ? <p className="vazio">Cadastre um trabalhador ativo para lançar vales, horas extras e faltas.</p> : (
          <form onSubmit={enviar}>
            <div className="grade-form">
              <Campo label="Trabalhador">
                <select value={trabalhadorId} onChange={(e) => setTrabalhadorId(e.target.value)}>
                  {trabalhadores.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
                </select>
              </Campo>
              <Campo label="Data">
                <input type="date" value={form.data} onChange={set('data')} required />
              </Campo>

              {(tipo === 'vale_antecipacao' || tipo === 'bonus') && (
                <Campo label="Valor (R$)">
                  <InputValor value={form.valor} onChange={set('valor')} required autoFocus />
                </Campo>
              )}

              {tipo === 'hora_extra' && (
                <>
                  <Campo label="Quantidade de horas">
                    <InputValor value={form.horas} onChange={set('horas')} required autoFocus />
                  </Campo>
                  <Campo label="Adicional" dica="50% em dias normais; 100% em domingos e feriados.">
                    <select value={form.percentual} onChange={set('percentual')}>
                      <option value="50">50%</option>
                      <option value="100">100%</option>
                    </select>
                  </Campo>
                </>
              )}

              {tipo === 'falta' && (
                <>
                  <Campo label="Descontar por">
                    <select value={form.faltaPor} onChange={set('faltaPor')}>
                      <option value="dias">Dias</option>
                      <option value="horas">Horas (atrasos)</option>
                    </select>
                  </Campo>
                  {form.faltaPor === 'dias' ? (
                    <Campo label="Dias de falta">
                      <input type="number" min="1" max="30" value={form.dias} onChange={set('dias')} required />
                    </Campo>
                  ) : (
                    <Campo label="Horas">
                      <InputValor value={form.horas} onChange={set('horas')} required />
                    </Campo>
                  )}
                </>
              )}

              <Campo label="Descrição (opcional)">
                <input value={form.descricao} onChange={set('descricao')} />
              </Campo>
            </div>
            {previa !== null && (
              <p className="previa">
                Valor-hora: {brl(valorHora)} · <strong>Valor do lançamento: {brl(previa)}</strong>
              </p>
            )}
            {tipo === 'falta' && (
              <p className="dica">Registre faltas aqui e mantenha 30 dias trabalhados na folha, para não descontar em dobro.</p>
            )}
            {bloqueado && (
              <p className="alerta aviso">
                A folha de {trabalhador?.nome} em {mesLongo(mes).toLowerCase()} está fechada. Reabra-a na tela da folha para lançar.
              </p>
            )}
            <div className="acoes direita">
              <button className="btn primario" disabled={bloqueado || enviando}>
                {enviando ? 'Lançando…' : `Lançar ${ABAS.find((a) => a.tipo === tipo).label.toLowerCase()}`}
              </button>
            </div>
          </form>
        )}
      </section>

      <section className="painel">
        <h3>Lançados em {mesLongo(mes).toLowerCase()}</h3>
        <div className="totais-linha">
          {ABAS.map((a) => <span key={a.tipo}>{a.label}: <strong>{brl(totais[a.tipo])}</strong></span>)}
        </div>
        {!eventos ? <Carregando /> : (
        <div className="tabela-container">
          <table className="tabela-pilha">
            <thead><tr><th>Data</th><th>Trabalhador</th><th>Tipo</th><th>Detalhe</th><th className="num">Valor</th><th><span className="oculto">Ações</span></th></tr></thead>
            <tbody>
              {eventos.length === 0 && <tr><td colSpan={6} className="vazio">Nenhum lançamento neste mês.</td></tr>}
              {eventos.map((ev) => (
                <tr key={ev.id}>
                  <td data-label="Data">{dataBR(ev.data_lancamento)}</td>
                  <td className="principal"><strong>{nomes[ev.trabalhador_id] || `#${ev.trabalhador_id}`}</strong></td>
                  <td data-label="Tipo"><Badge tipo={ev.tipo === 'hora_extra' || ev.tipo === 'bonus' ? 'verde' : 'vermelho'}>{ROTULOS.evento[ev.tipo]}</Badge></td>
                  <td data-label="Detalhe">
                    {ev.quantidade_horas && `${Number(ev.quantidade_horas)}h`}
                    {ev.percentual_adicional && ` a ${Number(ev.percentual_adicional)}%`}
                    {ev.descricao && ` ${ev.descricao}`}
                  </td>
                  <td className="num" data-label="Valor">{brl(ev.valor)}</td>
                  <td className="acoes-linha">
                    {!fechadas.includes(String(ev.trabalhador_id)) && <button className="btn pequeno perigo" onClick={() => excluir(ev)}>Excluir</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
      </section>
    </>
  );
}

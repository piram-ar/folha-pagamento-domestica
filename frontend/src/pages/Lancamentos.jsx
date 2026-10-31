import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { Alerta, Badge, Campo, useTrabalhadores } from '../components/ui';
import { brl, dataBR, diasDoMes, hoje, mesAtual, mesLongo, ROTULOS } from '../utils';

const ABAS = [
  { tipo: 'vale_antecipacao', label: 'Vale / adiantamento' },
  { tipo: 'hora_extra', label: 'Hora extra' },
  { tipo: 'falta', label: 'Falta' },
  { tipo: 'bonus', label: 'Bônus' },
];

const FORM_VAZIO = { valor: '', horas: '', percentual: '50', faltaPor: 'dias', dias: '1', descricao: '', data: hoje() };

export default function Lancamentos() {
  const trabalhadores = useTrabalhadores();
  const [mes, setMes] = useState(mesAtual());
  const [trabalhadorId, setTrabalhadorId] = useState('');
  const [tipo, setTipo] = useState('vale_antecipacao');
  const [form, setForm] = useState(FORM_VAZIO);
  const [eventos, setEventos] = useState([]);
  const [msg, setMsg] = useState({});

  useEffect(() => {
    if (!trabalhadorId && trabalhadores.length) setTrabalhadorId(String(trabalhadores[0].id));
  }, [trabalhadores, trabalhadorId]);

  const carregar = useCallback(
    () => api.get(`/eventos?mes_ano=${mes}`).then(setEventos).catch((e) => setMsg({ erro: e.message })),
    [mes],
  );
  useEffect(() => { carregar(); }, [carregar]);

  const trabalhador = trabalhadores.find((t) => String(t.id) === trabalhadorId);
  const salario = Number(trabalhador?.salario_base || 0);
  const valorHora = salario / Number(trabalhador?.horas_mensais || 200);
  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  // Pré-visualização do valor calculado (o backend recalcula com precisão)
  const previa = useMemo(() => {
    const horas = Number(String(form.horas).replace(',', '.')) || 0;
    if (tipo === 'hora_extra') return valorHora * (1 + Number(form.percentual) / 100) * horas;
    if (tipo === 'falta') return form.faltaPor === 'dias' ? (salario / diasDoMes(mes)) * (Number(form.dias) || 0) : valorHora * horas;
    return null;
  }, [tipo, form, salario, valorHora, mes]);

  const enviar = async (e) => {
    e.preventDefault();
    setMsg({});
    const base = {
      trabalhador_id: Number(trabalhadorId),
      mes_ano: mes,
      tipo,
      data_lancamento: form.data,
      descricao: form.descricao || null,
    };
    const num = (v) => String(v).replace(',', '.');
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
    try {
      const ev = await api.post('/eventos', dados);
      setMsg({ sucesso: `${ROTULOS.evento[ev.tipo]} de ${brl(ev.valor)} lançado para ${trabalhador.nome}.` });
      setForm({ ...FORM_VAZIO, percentual: form.percentual, data: form.data });
      carregar();
    } catch (err) { setMsg({ erro: err.message }); }
  };

  const excluir = async (ev) => {
    if (!window.confirm('Excluir este lançamento?')) return;
    try {
      await api.del(`/eventos/${ev.id}`);
      carregar();
    } catch (err) { setMsg({ erro: err.message }); }
  };

  const nomes = Object.fromEntries(trabalhadores.map((t) => [t.id, t.nome]));
  const totais = eventos.reduce((acc, ev) => ({ ...acc, [ev.tipo]: (acc[ev.tipo] || 0) + Number(ev.valor) }), {});

  return (
    <>
      <div className="titulo-pagina">
        <h2>Lançamentos do mês</h2>
        <Campo label="Competência">
          <input type="month" value={mes} onChange={(e) => e.target.value && setMes(e.target.value)} />
        </Campo>
      </div>

      <section className="painel">
        <div className="abas">
          {ABAS.map((a) => (
            <button key={a.tipo} className={tipo === a.tipo ? 'ativa' : ''} onClick={() => setTipo(a.tipo)}>{a.label}</button>
          ))}
        </div>
        <Alerta {...msg} />
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
                  <input type="number" min="0.01" step="0.01" value={form.valor} onChange={set('valor')} required autoFocus />
                </Campo>
              )}

              {tipo === 'hora_extra' && (
                <>
                  <Campo label="Quantidade de horas">
                    <input type="number" min="0.25" step="0.25" value={form.horas} onChange={set('horas')} required autoFocus />
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
                      <input type="number" min="0.25" step="0.25" value={form.horas} onChange={set('horas')} required />
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
            <div className="acoes direita">
              <button className="btn primario">Lançar {ABAS.find((a) => a.tipo === tipo).label.toLowerCase()}</button>
            </div>
          </form>
        )}
      </section>

      <section className="painel">
        <h3>Lançados em {mesLongo(mes).toLowerCase()}</h3>
        <div className="totais-linha">
          {ABAS.map((a) => <span key={a.tipo}>{a.label}: <strong>{brl(totais[a.tipo])}</strong></span>)}
        </div>
        <div className="tabela-container">
          <table className="tabela-pilha">
            <thead><tr><th>Data</th><th>Trabalhador</th><th>Tipo</th><th>Detalhe</th><th className="num">Valor</th><th /></tr></thead>
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
                  <td className="acoes-linha"><button className="btn pequeno perigo" onClick={() => excluir(ev)}>Excluir</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

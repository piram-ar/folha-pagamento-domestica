import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { MODO_APP } from '../plataforma';
import { Alerta, SituacaoFolha } from '../components/ui';
import { brl, mesAtual, mesLongo, ROTULOS } from '../utils';

/** O próximo passo do mês, na ordem da rotina: cadastrar → calcular → fechar. */
function proximoPasso(trabalhadores, porTrabalhador, mes) {
  const nomeMes = mesLongo(mes).split(' ')[0].toLowerCase();
  if (!trabalhadores.length) return MODO_APP ? null : { to: '/trabalhadores', texto: 'Cadastrar trabalhador' };
  if (trabalhadores.some((t) => !porTrabalhador[t.id])) return { to: '/folha', texto: `Calcular folha de ${nomeMes}` };
  if (trabalhadores.some((t) => porTrabalhador[t.id].status !== 'fechada')) return { to: '/folha', texto: 'Revisar e fechar folhas' };
  return null;
}

export default function Dashboard() {
  const mes = mesAtual();
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    Promise.all([
      api.get('/trabalhadores?apenas_ativos=true'),
      api.get(`/folha?mes_ano=${mes}`),
      api.get(`/eventos?mes_ano=${mes}`),
      api.get('/ferias/dashboard'),
    ])
      .then(([trabalhadores, folhas, eventos, ferias]) => setDados({ trabalhadores, folhas, eventos, ferias }))
      .catch((e) => setErro(e.message));
  }, [mes]);

  if (erro) return <Alerta erro={erro} />;
  if (!dados) return <div className="carregando">Carregando…</div>;

  const { trabalhadores, folhas, eventos, ferias } = dados;
  const porTrabalhador = Object.fromEntries(folhas.map((f) => [f.trabalhador_id, f]));
  const fechadas = trabalhadores.filter((t) => porTrabalhador[t.id]?.status === 'fechada').length;
  const soma = (lista, campo) => lista.reduce((s, x) => s + Number(x[campo]), 0);
  const passo = proximoPasso(trabalhadores, porTrabalhador, mes);
  const alertas = ferias.flatMap((f) => f.alertas.map((a) => ({ nome: f.trabalhador_nome, texto: a })));

  const lancamentosDe = (id) => eventos.filter((e) => e.trabalhador_id === id);
  const resumoLancamentos = (id) => {
    const lista = lancamentosDe(id);
    if (!lista.length) return 'Nenhum lançamento';
    const tipos = [...new Set(lista.map((e) => ROTULOS.evento[e.tipo].split(' /')[0].toLowerCase()))];
    return `${lista.length} ${lista.length === 1 ? 'lançamento' : 'lançamentos'}: ${tipos.join(', ')}`;
  };

  return (
    <>
      <header className="mes-cabecalho">
        <div>
          <h2>{mesLongo(mes)}</h2>
          {trabalhadores.length === 0 ? (
            <p>Cadastre quem trabalha na casa{MODO_APP ? ' (pelo navegador)' : ''} para começar a folha do mês.</p>
          ) : (
            <p>
              {fechadas === trabalhadores.length
                ? 'Todas as folhas do mês estão fechadas. '
                : `${fechadas} de ${trabalhadores.length} ${trabalhadores.length === 1 ? 'folha fechada' : 'folhas fechadas'}. `}
              {folhas.length > 0 && (
                <>Líquido a pagar <strong>{brl(soma(folhas, 'salario_liquido'))}</strong>; encargos e reserva <strong>{brl(soma(folhas, 'encargos_recolher_guardar'))}</strong>.</>
              )}
            </p>
          )}
        </div>
        {passo && <Link className="btn primario" to={passo.to}>{passo.texto}</Link>}
      </header>

      {trabalhadores.length > 0 && (
        <section className="secao">
          <h3>Folha do mês</h3>
          <ul className="folha-mes">
            {trabalhadores.map((t) => {
              const f = porTrabalhador[t.id];
              return (
                <li key={t.id}>
                  <div>
                    {MODO_APP ? <span className="nome">{t.nome}</span> : <Link className="nome" to={`/trabalhadores/${t.id}`}>{t.nome}</Link>}
                    <small>{ROTULOS.tipo_contrato[t.tipo_contrato]}</small>
                  </div>
                  <div className="lancamentos">
                    <Link to="/lancamentos">{resumoLancamentos(t.id)}</Link>
                  </div>
                  <div className="valor">{f ? brl(f.salario_liquido) : <small>a calcular</small>}</div>
                  <div className="situacao"><SituacaoFolha folha={f} /></div>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="secao">
        <h3>Férias</h3>
        {alertas.length === 0 ? (
          <p className="vazio">Nenhum período vencido ou vencendo nos próximos 60 dias.</p>
        ) : (
          <ul className="lista-alertas">
            {alertas.map((a) => <li key={a.nome + a.texto}><strong>{a.nome}</strong>: {a.texto}</li>)}
          </ul>
        )}
        <Link to="/ferias">Ver saldos e registrar férias</Link>
      </section>
    </>
  );
}

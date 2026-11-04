import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { MODO_APP } from '../plataforma';
import { Campo, Carregando, ErroTela, SituacaoFolha } from '../components/ui';
import { brl, mesAtual, mesLongo, ROTULOS } from '../utils';

/** O próximo passo do mês, na ordem da rotina: cadastrar → calcular → fechar. */
function proximoPasso(trabalhadores, porTrabalhador, mes) {
  const nomeMes = mesLongo(mes).split(' ')[0].toLowerCase();
  if (!trabalhadores.length) return MODO_APP ? null : { to: '/trabalhadores', texto: 'Cadastrar trabalhador' };
  if (trabalhadores.some((t) => !porTrabalhador[t.id])) return { to: '/folha', texto: `Calcular folha de ${nomeMes}` };
  if (trabalhadores.some((t) => porTrabalhador[t.id].status !== 'fechada')) return { to: '/folha', texto: 'Revisar e fechar folhas' };
  return null;
}

/** O que deve estar guardado hoje para férias, 13º e encargos: provisões desde a admissão menos o já pago. */
function Reservas({ resumo }) {
  const ativos = resumo.trabalhadores.filter((t) => t.provisoes);
  if (!ativos.length) return null;
  const linha = (rotulo, p) => (
    <div key={rotulo}>
      <dt>{rotulo}</dt>
      <dd>{brl(p.saldo)}</dd>
      <dd className="detalhe">{brl(p.provisionado)} provisionado, {brl(p.pago)} pago</dd>
    </div>
  );
  return (
    <section className="secao">
      <h3>Reservas para férias, 13º e encargos</h3>
      <p className="sub bloco">Quanto deveria estar guardado hoje: 1/12 da remuneração por mês para o 13º e 1/12 + 1/3 para as férias, menos o que já foi pago.</p>
      <div className="cartoes-resumo">
        {ativos.map((t) => {
          const p = t.provisoes;
          return (
            <article key={t.trabalhador_id} className="cartao-resumo">
              <header><strong>{t.trabalhador_nome}</strong><small>{ROTULOS.tipo_contrato[t.tipo_contrato]}</small></header>
              <dl className="linhas-resumo">
                {linha('Férias + 1/3', p.ferias)}
                {p.decimo_terceiro.map((d) => linha(`13º de ${d.ano}`, d))}
                {p.encargos && linha('Encargos sobre férias e 13º', p.encargos)}
              </dl>
              <footer><span>Reserva</span><strong>{brl(p.saldo_total)}</strong></footer>
              {p.meses_estimados > 0 && (
                <small>{p.meses_estimados} {p.meses_estimados === 1 ? 'mês sem folha calculada entrou' : 'meses sem folha calculada entraram'} pelo salário do cadastro.</small>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

/** Quanto cada ocorrência (folha, benefícios, férias, 13º, encargos) custou no ano, por colaborador. */
function PagamentosDoAno({ resumo, ano, onAno }) {
  const anoAtual = new Date().getFullYear();
  const anos = Array.from({ length: 5 }, (_, i) => anoAtual - i);
  return (
    <section className="secao">
      <div className="titulo-pagina compacto">
        <div>
          <h3>Pagamentos em {ano}</h3>
          <p className="sub">
            Total do ano <strong>{brl(resumo.totais.total)}</strong>
            {resumo.totais.em_aberto > 0 && <>; {brl(resumo.totais.em_aberto)} ainda em aberto</>}.
          </p>
        </div>
        <Campo label="Ano">
          <select value={ano} onChange={(e) => onAno(Number(e.target.value))}>
            {anos.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </Campo>
      </div>
      {resumo.trabalhadores.length === 0 ? <p className="vazio">Nenhum pagamento em {ano}.</p> : (
        <div className="cartoes-resumo">
          {resumo.trabalhadores.map((t) => (
            <article key={t.trabalhador_id} className="cartao-resumo">
              <header><strong>{t.trabalhador_nome}</strong><small>{ROTULOS.tipo_contrato[t.tipo_contrato]}{!t.ativo && ' · inativo'}</small></header>
              <dl className="linhas-resumo">
                {Object.entries(resumo.categorias).map(([chave, rotulo]) => {
                  if (chave === 'encargos' && t.tipo_contrato !== 'com_registro' && !t.valores[chave]) return null;
                  return (
                    <div key={chave} className={t.valores[chave] ? '' : 'zerado'}>
                      <dt>{rotulo}</dt><dd>{t.valores[chave] ? brl(t.valores[chave]) : '—'}</dd>
                    </div>
                  );
                })}
              </dl>
              <footer><span>Total</span><strong>{brl(t.total)}</strong></footer>
              {t.pendentes > 0 && <small>{t.pendentes} {t.pendentes === 1 ? 'pagamento' : 'pagamentos'} em aberto: {brl(t.em_aberto)} líquidos.</small>}
            </article>
          ))}
        </div>
      )}
      <p className="dica">
        Folhas entram pela competência; férias e 13º, pela data de pagamento. Encargos: INSS patronal, GILRAT e FGTS
        estimados da guia DAE (sem o INSS descontado do empregado).
      </p>
    </section>
  );
}

/** Os números que respondem "como estamos?" antes de qualquer lista. */
function Indicadores({ folhas, resumo, ano }) {
  const aPagar = folhas.filter((f) => !f.pago_em).reduce((s, f) => s + Number(f.salario_liquido), 0);
  const itens = [
    ['A pagar no mês', brl(aPagar), folhas.length ? 'folhas ainda não pagas' : 'nenhuma folha calculada'],
    ['Em aberto', resumo ? brl(resumo.totais.em_aberto) : null, `todos os pagamentos de ${ano}`],
    ['Reserva a manter', resumo ? brl(resumo.totais.reservas) : null, 'férias, 13º e encargos'],
    [`Custo em ${ano}`, resumo ? brl(resumo.totais.total) : null, 'salários, benefícios e encargos'],
  ];
  return (
    <dl className="indicadores">
      {itens.map(([rotulo, valor, nota]) => (
        <div key={rotulo}>
          <dt>{rotulo}</dt>
          <dd>{valor ?? <span className="traco" aria-label="Carregando" />}</dd>
          <dd className="nota">{nota}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Primeiro uso: o caminho até a primeira folha. Some quando tudo está cadastrado. */
function PrimeirosPassos({ contratante, trabalhadores }) {
  if (MODO_APP || (contratante && trabalhadores.length)) return null;
  return (
    <section className="painel">
      <h3>Primeiros passos</h3>
      <ol className="passos">
        <li className={contratante ? 'feito' : ''}><Link to="/contratante">Informe o empregador e o local do serviço</Link>: saem nos recibos.</li>
        <li className={trabalhadores.length ? 'feito' : ''}><Link to="/trabalhadores">Cadastre quem trabalha na casa</Link>, com o objeto do contrato e o salário.</li>
        <li>Lance vales e horas extras do mês e calcule a folha.</li>
      </ol>
    </section>
  );
}

export default function Dashboard() {
  const mes = mesAtual();
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState('');
  const [ano, setAno] = useState(new Date().getFullYear());
  const [resumo, setResumo] = useState(null);

  useEffect(() => {
    api.get(`/resumo?ano=${ano}`).then(setResumo).catch((e) => setErro(e.message));
  }, [ano]);

  const carregar = useCallback(() => {
    setErro('');
    return Promise.all([
      api.get('/trabalhadores?apenas_ativos=true'),
      api.get(`/folha?mes_ano=${mes}&resumida=true`),
      api.get(`/eventos?mes_ano=${mes}`),
      api.get('/ferias/dashboard'),
      api.get('/contratante'),
    ])
      .then(([trabalhadores, folhas, eventos, ferias, contratante]) => setDados({ trabalhadores, folhas, eventos, ferias, contratante }))
      .catch((e) => setErro(e.message));
  }, [mes]);
  useEffect(() => { carregar(); }, [carregar]);

  if (erro) return <ErroTela mensagem={erro} onTentar={carregar} />;
  if (!dados) return <Carregando linhas={6} />;

  const { trabalhadores, folhas, eventos, ferias, contratante } = dados;
  const porTrabalhador = Object.fromEntries(folhas.map((f) => [f.trabalhador_id, f]));
  const fechadas = trabalhadores.filter((t) => porTrabalhador[t.id]?.status === 'fechada').length;
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
                : `${fechadas} de ${trabalhadores.length} ${trabalhadores.length === 1 ? 'folha fechada' : 'folhas fechadas'}.`}
            </p>
          )}
        </div>
        {passo && <Link className="btn primario" to={passo.to}>{passo.texto}</Link>}
      </header>

      <PrimeirosPassos contratante={contratante} trabalhadores={trabalhadores} />
      {trabalhadores.length > 0 && <Indicadores folhas={folhas} resumo={resumo} ano={ano} />}

      {alertas.length > 0 && (
        <section className="secao">
          <h3>Férias a conceder</h3>
          <ul className="lista-alertas">
            {alertas.map((a) => <li key={a.nome + a.texto}><strong>{a.nome}</strong>: {a.texto}</li>)}
          </ul>
          <Link to="/ferias">Ver saldos e registrar férias</Link>
        </section>
      )}

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

      {resumo && <Reservas resumo={resumo} />}
      {resumo && <PagamentosDoAno resumo={resumo} ano={ano} onAno={setAno} />}
    </>
  );
}

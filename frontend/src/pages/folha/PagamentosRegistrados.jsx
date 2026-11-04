import { useCallback, useEffect, useState } from 'react';
import { abrirPdf, api } from '../../api';
import { useAvisar } from '../../components/feedback';
import { Badge, Campo, Carregando, ErroTela, ModalPagamento } from '../../components/ui';
import { brl, dataBR } from '../../utils';
import { ROTULO_TIPO, TIPOS, unificar } from './comum';
import DetalheFolha from './DetalheFolha';

const SITUACOES = [['', 'Todas'], ['aberto', 'Em aberto'], ['paga', 'Pagas']];

/** Tudo o que já foi calculado (folhas, férias e 13º), com a situação do pagamento.
 * Recibos de férias só são gerados na tela de Férias; aqui eles só podem ser vistos. */
export default function PagamentosRegistrados({ onAbrirMes }) {
  const avisar = useAvisar();
  const [registros, setRegistros] = useState(null);
  const [erro, setErro] = useState('');
  const [ano, setAno] = useState(String(new Date().getFullYear()));
  const [trabalhador, setTrabalhador] = useState('');
  const [situacao, setSituacao] = useState('');
  const [tipo, setTipo] = useState('');
  const [pagando, setPagando] = useState(null);
  const [detalhe, setDetalhe] = useState(null);

  const carregar = useCallback(async () => {
    setErro('');
    try {
      const [folhas, ferias, decimos] = await Promise.all([
        api.get('/folha?resumida=true'), api.get('/ferias/pagamentos'), api.get('/decimo-terceiro'),
      ]);
      setRegistros(unificar(folhas, ferias, decimos));
    } catch (e) { setErro(e.message); }
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  if (erro) return <ErroTela mensagem={erro} onTentar={carregar} />;
  if (!registros) return <Carregando linhas={5} />;

  const anos = [...new Set(registros.map((r) => r.data.slice(0, 4)))];
  const nomes = [...new Map(registros.map((r) => [r.trabalhador_id, r.trabalhador_nome])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1]));
  const visiveis = registros.filter((r) => (!ano || r.data.startsWith(ano))
    && (!trabalhador || r.trabalhador_id === Number(trabalhador))
    && (!situacao || (situacao === 'paga') === Boolean(r.pago_em)) && (!tipo || r.tipo === tipo));
  const emAberto = registros.filter((r) => !r.pago_em);

  const pagar = async (r, data) => {
    try {
      await api.post(r.tipo === 'decimo' ? `/decimo-terceiro/${r.original.id}/pagar` : `/folha/${r.original.id}/pagar`, { pago_em: data });
      setPagando(null);
      avisar({ sucesso: `Pagamento de ${r.trabalhador_nome} registrado.` });
      carregar();
    } catch (e) { avisar({ erro: e.message }); }
  };
  const recibo = (r) => abrirPdf(r.tipo === 'ferias' ? `/ferias/gozos/${r.original.id}/recibo.pdf`
    : `/decimo-terceiro/${r.original.id}/recibo.pdf`).catch((e) => avisar({ erro: e.message }));

  return (
    <>
      <p className="sub">
        {emAberto.length === 0 ? 'Nenhum pagamento em aberto.'
          : `${emAberto.length} em aberto, somando ${brl(emAberto.reduce((s, r) => s + Number(r.liquido), 0))} líquidos.`}
      </p>
      <div className="barra-tela filtros">
        <Campo label="Ano">
          <select value={ano} onChange={(e) => setAno(e.target.value)}>
            <option value="">Todos</option>
            {!anos.includes(ano) && ano && <option value={ano}>{ano}</option>}
            {anos.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </Campo>
        <Campo label="Trabalhador">
          <select value={trabalhador} onChange={(e) => setTrabalhador(e.target.value)}>
            <option value="">Todos</option>
            {nomes.map(([id, nome]) => <option key={id} value={id}>{nome}</option>)}
          </select>
        </Campo>
        <Campo label="Tipo">
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Campo>
        <Campo label="Situação">
          <select value={situacao} onChange={(e) => setSituacao(e.target.value)}>
            {SITUACOES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Campo>
      </div>
      <div className="tabela-container">
        <table className="tabela-pilha">
          <thead>
            <tr><th>Referência</th><th>Tipo</th><th>Trabalhador</th><th className="num">Líquido</th><th>Situação</th><th><span className="oculto">Ações</span></th></tr>
          </thead>
          <tbody>
            {visiveis.length === 0 && <tr><td colSpan={6} className="vazio">Nenhum pagamento encontrado com estes filtros.</td></tr>}
            {visiveis.map((r) => (
              <tr key={r.chave}>
                <td className="principal">
                  {r.tipo === 'folha'
                    ? <button className="btn-link" onClick={() => onAbrirMes(r.original.mes_ano)}>{r.referencia}</button>
                    : <strong>{r.referencia}</strong>}
                </td>
                <td data-label="Tipo">{ROTULO_TIPO[r.tipo]}</td>
                <td data-label="Trabalhador">{r.trabalhador_nome}</td>
                <td className="num" data-label="Líquido">{brl(r.liquido)}</td>
                <td data-label="Situação">
                  {r.pago_em ? <Badge tipo="verde">Paga em {dataBR(r.pago_em)}</Badge>
                    : <Badge tipo="vermelho">{r.rascunho ? 'Em aberto (rascunho)' : 'Em aberto'}</Badge>}
                </td>
                <td className="acoes-linha">
                  {r.tipo !== 'ferias' && !r.pago_em && (
                    <button className="btn pequeno sucesso" onClick={() => setPagando(r)}>Marcar paga</button>
                  )}
                  {r.tipo === 'folha'
                    ? <button className="btn pequeno" onClick={() => setDetalhe(r.original.id)}>Detalhes</button>
                    : <button className="btn pequeno" onClick={() => recibo(r)}>Ver recibo</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pagando && (
        <ModalPagamento
          descricao={`${pagando.trabalhador_nome}, ${ROTULO_TIPO[pagando.tipo].toLowerCase()} (${pagando.referencia.toLowerCase()})`}
          valor={pagando.liquido}
          aviso={pagando.rascunho ? 'A folha ainda está em rascunho e será fechada junto.' : null}
          onClose={() => setPagando(null)}
          onConfirmar={(data) => pagar(pagando, data)}
        />
      )}
      {detalhe && <DetalheFolha folhaId={detalhe} onClose={() => setDetalhe(null)} onAlterado={carregar} />}
    </>
  );
}

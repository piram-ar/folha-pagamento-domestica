import { useCallback, useEffect, useState } from 'react';
import { abrirPdf, api } from '../../api';
import { useAvisar, useConfirmar } from '../../components/feedback';
import { Badge, Campo, Carregando, ErroTela, Modal, ModalPagamento } from '../../components/ui';
import { MODO_APP } from '../../plataforma';
import { brl, dataBR, ROTULOS } from '../../utils';
import { nomeParcela } from './comum';

/** Gera (ou recalcula) uma parcela do 13º com a data do pagamento. */
function GerarParcela({ linha, parcela, existente, ano, onClose, onConfirmar }) {
  const [data, setData] = useState(existente?.data_pagamento || (parcela === 1 ? `${ano}-11-30` : `${ano}-12-20`));
  const unica = parcela === 2 && !linha.parcelas.some((d) => d.parcela === 1);
  return (
    <Modal titulo={`13º de ${linha.trabalhador_nome}: ${parcela === 1 ? '1ª parcela' : unica ? 'parcela única' : '2ª parcela'}`} onClose={onClose}>
      <form onSubmit={(e) => { e.preventDefault(); onConfirmar(data); }}>
        <p className="dica">
          {parcela === 1
            ? 'Metade do 13º, sem desconto de INSS. Prazo: entre fevereiro e 30 de novembro.'
            : `13º integral (${linha.avos}/12 avos)${unica ? '' : ' menos a 1ª parcela'}${linha.tipo_contrato === 'com_registro' ? ' e o INSS' : ''}. Prazo: 20 de dezembro${unica ? ' (parcela única: até 30 de novembro)' : ''}.`}
        </p>
        <Campo label="Data do pagamento">
          <input type="date" value={data} onChange={(e) => setData(e.target.value)} required autoFocus />
        </Campo>
        <div className="acoes direita">
          <button type="button" className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn primario">{existente ? 'Recalcular' : 'Gerar parcela'}</button>
        </div>
      </form>
    </Modal>
  );
}

/** Parcelas do 13º salário do ano: geradas aqui, abatidas da provisão anual do 13º na tela Início. */
export default function DecimoTerceiro() {
  const avisar = useAvisar();
  const confirmar = useConfirmar();
  const [ano, setAno] = useState(new Date().getFullYear());
  const [linhas, setLinhas] = useState(null);
  const [erro, setErro] = useState('');
  const [gerando, setGerando] = useState(null);
  const [pagando, setPagando] = useState(null);

  const carregar = useCallback(() => {
    setErro('');
    return api.get(`/decimo-terceiro/previa?ano=${ano}`).then(setLinhas).catch((e) => setErro(e.message));
  }, [ano]);
  useEffect(() => { carregar(); }, [carregar]);

  const executar = async (acao, sucesso) => {
    try {
      await acao();
      avisar({ sucesso });
      await carregar();
    } catch (e) { avisar({ erro: e.message }); }
  };
  const gerar = (linha, parcela, data) => executar(async () => {
    await api.post('/decimo-terceiro', { trabalhador_id: linha.trabalhador_id, ano, parcela, data_pagamento: data });
    setGerando(null);
  }, `13º de ${linha.trabalhador_nome} calculado. O recibo já pode ser gerado.`);
  const pagar = (d, data) => executar(async () => {
    await api.post(`/decimo-terceiro/${d.id}/pagar`, { pago_em: data });
    setPagando(null);
  }, `${nomeParcela(d)} do 13º de ${d.trabalhador_nome} marcada como paga.`);
  const desfazer = async (d) => {
    if (!await confirmar({ titulo: 'Desfazer o pagamento?', texto: `A ${nomeParcela(d).toLowerCase()} do 13º de ${d.trabalhador_nome} volta a ficar em aberto.`, acao: 'Desfazer pagamento' })) return;
    executar(() => api.del(`/decimo-terceiro/${d.id}/pagamento`), 'Pagamento desfeito.');
  };
  const excluir = async (d) => {
    if (!await confirmar({ titulo: `Excluir a ${nomeParcela(d).toLowerCase()}?`, texto: `13º de ${d.trabalhador_nome}, ${d.ano}.`, acao: 'Excluir parcela', perigo: true })) return;
    executar(() => api.del(`/decimo-terceiro/${d.id}`), 'Parcela excluída.');
  };
  const recibo = (d) => abrirPdf(`/decimo-terceiro/${d.id}/recibo.pdf`).catch((e) => avisar({ erro: e.message }));

  const celula = (linha, parcela) => {
    const d = linha.parcelas.find((x) => x.parcela === parcela);
    const temSegunda = linha.parcelas.some((x) => x.parcela === 2);
    if (!d) {
      if (parcela === 1 && temSegunda) return '—';
      const rotulo = parcela === 1 ? 'Gerar 1ª parcela' : linha.parcelas.length ? 'Gerar 2ª parcela' : 'Gerar parcela única';
      return <button className="btn pequeno" onClick={() => setGerando({ linha, parcela })}>{rotulo}</button>;
    }
    return (
      <div className="parcela-13">
        <span><strong>{brl(d.liquido)}</strong> <small>em {dataBR(d.data_pagamento)}</small></span>
        {d.pago_em ? <Badge tipo="verde">Paga em {dataBR(d.pago_em)}</Badge> : <Badge tipo="vermelho">Em aberto</Badge>}
        <span className="acoes-linha">
          <button className="btn pequeno primario" onClick={() => recibo(d)}>{MODO_APP ? 'Enviar recibo' : 'Recibo'}</button>
          {!d.pago_em && <button className="btn pequeno sucesso" onClick={() => setPagando(d)}>Marcar paga</button>}
          {d.pago_em && <button className="btn pequeno" onClick={() => desfazer(d)}>Desfazer</button>}
          {!d.pago_em && !(parcela === 1 && temSegunda) && (
            <button className="btn pequeno" onClick={() => setGerando({ linha, parcela, existente: d })}>Recalcular</button>
          )}
          {!d.pago_em && !(parcela === 1 && temSegunda) && <button className="btn-link perigo" onClick={() => excluir(d)}>Excluir</button>}
        </span>
      </div>
    );
  };

  const anoAtual = new Date().getFullYear();
  const anos = Array.from({ length: 6 }, (_, i) => anoAtual + 1 - i);

  return (
    <>
      <div className="barra-tela">
        <Campo label="Ano">
          <select value={ano} onChange={(e) => { setLinhas(null); setAno(Number(e.target.value)); }}>
            {anos.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </Campo>
        <p className="dica">1ª parcela até 30/11 (metade, sem INSS); 2ª até 20/12, descontando a 1ª e o INSS.</p>
      </div>
      {erro && <ErroTela mensagem={erro} onTentar={carregar} />}
      {!erro && !linhas && <Carregando />}
      {linhas && (
        <div className="tabela-container">
          <table className="tabela-pilha">
            <thead>
              <tr><th>Trabalhador</th><th>Avos</th><th className="num">13º previsto</th><th>1ª parcela</th><th>2ª parcela / única</th></tr>
            </thead>
            <tbody>
              {linhas.length === 0 && <tr><td colSpan={5} className="vazio">Nenhum trabalhador ativo com meses trabalhados em {ano}.</td></tr>}
              {linhas.map((l) => (
                <tr key={l.trabalhador_id}>
                  <td className="principal"><span><strong>{l.trabalhador_nome}</strong><br /><small>{ROTULOS.tipo_contrato[l.tipo_contrato]}</small></span></td>
                  <td data-label="Avos">{l.avos}/12</td>
                  <td className="num" data-label="13º previsto">{brl(l.valor_integral)}</td>
                  <td data-label="1ª parcela">{celula(l, 1)}</td>
                  <td data-label="2ª parcela / única">{celula(l, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <details className="explicacao">
        <summary>Como o 13º é calculado</summary>
        <p>
          O 13º previsto usa o salário de dezembro e a média mensal das horas extras do ano. Cada mês com 15 dias ou mais de
          trabalho conta 1/12. Os valores pagos são descontados da reserva do 13º mostrada na tela Início.
        </p>
      </details>
      {gerando && (
        <GerarParcela {...gerando} ano={ano} onClose={() => setGerando(null)}
          onConfirmar={(data) => gerar(gerando.linha, gerando.parcela, data)} />
      )}
      {pagando && (
        <ModalPagamento descricao={`${nomeParcela(pagando)} do 13º de ${pagando.trabalhador_nome}`} valor={pagando.liquido}
          onClose={() => setPagando(null)} onConfirmar={(data) => pagar(pagando, data)} />
      )}
    </>
  );
}

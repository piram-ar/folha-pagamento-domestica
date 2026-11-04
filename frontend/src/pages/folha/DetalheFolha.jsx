import { useEffect, useState } from 'react';
import { abrirPdf, api } from '../../api';
import { useAuth } from '../../AuthContext';
import { useAvisar, useConfirmar } from '../../components/feedback';
import { Carregando, Modal, ModalPagamento } from '../../components/ui';
import { MODO_APP } from '../../plataforma';
import { brl, mesExtenso } from '../../utils';

/** Holerite na tela e tudo o que se faz com uma folha. O detalhamento só é buscado aqui: as listas vêm sem ele. */
export default function DetalheFolha({ folhaId, onClose, onAlterado }) {
  const { isAdmin } = useAuth();
  const avisar = useAvisar();
  const confirmar = useConfirmar();
  const [folha, setFolha] = useState(null);
  const [pagando, setPagando] = useState(false);

  useEffect(() => {
    api.get(`/folha/${folhaId}`).then(setFolha).catch((e) => { avisar({ erro: e.message }); onClose(); });
  }, [folhaId]); // eslint-disable-line react-hooks/exhaustive-deps

  const executar = async (acao, sucesso) => {
    try {
      await acao();
      avisar({ sucesso });
      onClose();
      onAlterado();
    } catch (e) { avisar({ erro: e.message }); }
  };

  if (!folha) return <Modal titulo="Folha" onClose={onClose} largo><Carregando linhas={5} /></Modal>;

  const d = folha.detalhamento || { itens: [], encargos: { itens: {} } };
  const fechada = folha.status === 'fechada';
  const comRegistro = folha.tipo_contrato === 'com_registro';
  const nome = folha.trabalhador_nome;

  const excluir = async () => {
    if (!await confirmar({ titulo: `Excluir o rascunho da folha de ${nome}?`, acao: 'Excluir rascunho', perigo: true })) return;
    executar(() => api.del(`/folha/${folha.id}`), 'Rascunho excluído.');
  };
  const desfazer = async () => {
    if (!await confirmar({ titulo: 'Desfazer o pagamento?', texto: `A folha de ${nome} volta a ficar em aberto.`, acao: 'Desfazer pagamento' })) return;
    executar(() => api.del(`/folha/${folha.id}/pagamento`), 'Pagamento desfeito: a folha voltou a ficar em aberto.');
  };
  const pagar = (data) => executar(() => api.post(`/folha/${folha.id}/pagar`, { pago_em: data }), `Pagamento de ${nome} registrado.`);
  const pdf = () => abrirPdf(`/folha/${folha.id}/recibo.pdf`).catch((e) => avisar({ erro: e.message }));

  return (
    <>
      <Modal titulo={`${nome}, ${mesExtenso(folha.mes_ano).toLowerCase()}`} onClose={onClose} largo fecharFora>
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
          <p className="dica">
            {comRegistro
              ? 'Estimativa da guia DAE do eSocial (vence dia 20 do mês seguinte). Confira sempre no portal do eSocial.'
              : 'Valor sugerido para guardar mensalmente e cobrir férias + 1/3 e 13º salário.'}
          </p>
        </div>
        <div className="acoes direita">
          {!fechada && <button className="btn perigo" onClick={excluir}>Excluir rascunho</button>}
          {fechada && !folha.pago_em && isAdmin && (
            <button className="btn" onClick={() => executar(() => api.post(`/folha/${folha.id}/reabrir`), `Folha de ${nome} reaberta.`)}>Reabrir folha</button>
          )}
          {folha.pago_em
            ? <button className="btn" onClick={desfazer}>Desfazer pagamento</button>
            : <button className="btn sucesso" onClick={() => setPagando(true)}>Marcar como paga</button>}
          <button className="btn primario" onClick={pdf}>
            {MODO_APP ? 'Enviar recibo' : fechada ? 'Imprimir recibo' : 'Ver recibo (rascunho)'}
          </button>
        </div>
      </Modal>
      {pagando && (
        <ModalPagamento
          descricao={`Folha de ${nome}`}
          valor={folha.salario_liquido}
          aviso={fechada ? null : 'A folha ainda está em rascunho e será fechada junto.'}
          onClose={() => setPagando(false)}
          onConfirmar={pagar}
        />
      )}
    </>
  );
}

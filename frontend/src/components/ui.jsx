import { useEffect, useState } from 'react';
import { api } from '../api';
import { brl, dataBR, hoje } from '../utils';

export function Modal({ titulo, onClose, children, largo = false }) {
  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onClose]);

  return (
    <div className="modal-fundo" onMouseDown={onClose}>
      <div className={`modal ${largo ? 'largo' : ''}`} onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-cabecalho">
          <h3>{titulo}</h3>
          <button className="btn-link" onClick={onClose} aria-label="Fechar">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Alerta({ erro, sucesso }) {
  if (erro) return <div className="alerta erro">{erro}</div>;
  if (sucesso) return <div className="alerta sucesso">{sucesso}</div>;
  return null;
}

export function Campo({ label, children, dica }) {
  return (
    <label className="campo">
      <span>{label}</span>
      {children}
      {dica && <small className="dica">{dica}</small>}
    </label>
  );
}

export function Badge({ tipo = 'neutro', children }) {
  return <span className={`badge ${tipo}`}>{children}</span>;
}

/** Situação da folha do mês; a fechada recebe o carimbo (animado só quando acabou de ser fechada). */
export function SituacaoFolha({ folha, recemFechada = false }) {
  if (!folha) return <Badge>Não calculada</Badge>;
  if (folha.pago_em) return <Badge tipo="verde">Paga em {dataBR(folha.pago_em)}</Badge>;
  if (folha.status === 'fechada') return <span className={`carimbo ${recemFechada ? 'novo' : ''}`}>Fechada</span>;
  return <Badge tipo="amarelo">Rascunho</Badge>;
}

/** Lista de trabalhadores (ativos por padrão) usada nos seletores. */
export function useTrabalhadores(apenasAtivos = true) {
  const [lista, setLista] = useState([]);
  useEffect(() => {
    api.get(`/trabalhadores${apenasAtivos ? '?apenas_ativos=true' : ''}`).then(setLista).catch(() => {});
  }, [apenasAtivos]);
  return lista;
}

/** Data em que um pagamento (folha, férias, 13º) foi feito. */
export function ModalPagamento({ descricao, valor, aviso, onClose, onConfirmar }) {
  const [data, setData] = useState(hoje());
  return (
    <Modal titulo="Registrar pagamento" onClose={onClose}>
      <form onSubmit={(e) => { e.preventDefault(); onConfirmar(data); }}>
        <p>{descricao}: <strong>{brl(valor)}</strong></p>
        <Campo label="Pago em">
          <input type="date" value={data} onChange={(e) => setData(e.target.value)} required autoFocus />
        </Campo>
        {aviso && <p className="dica">{aviso}</p>}
        <div className="acoes direita">
          <button type="button" className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn primario">Marcar como pago</button>
        </div>
      </form>
    </Modal>
  );
}

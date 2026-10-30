import { useEffect, useState } from 'react';
import { api } from '../api';

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

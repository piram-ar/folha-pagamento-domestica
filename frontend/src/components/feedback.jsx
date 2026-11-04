import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { Modal } from './ui';

const Contexto = createContext(null);

const TEMPO_SUCESSO = 5000;

/** Avisos flutuantes e confirmações, disponíveis em todas as telas.
 * O aviso aparece onde a pessoa está olhando, mesmo no fim de uma tabela longa. Erro só sai quando é dispensado. */
export function FeedbackProvider({ children }) {
  const [avisos, setAvisos] = useState([]);
  const [pedido, setPedido] = useState(null);
  const proximo = useRef(0);

  const dispensar = useCallback((id) => setAvisos((lista) => lista.filter((a) => a.id !== id)), []);

  const avisar = useCallback(({ sucesso, erro }) => {
    if (!sucesso && !erro) return;
    const id = ++proximo.current;
    setAvisos((lista) => [...lista.slice(-2), { id, sucesso, erro }]);
    if (sucesso) setTimeout(() => dispensar(id), TEMPO_SUCESSO);
  }, [dispensar]);

  const confirmar = useCallback((opcoes) => new Promise((resolve) => setPedido({ ...opcoes, resolve })), []);

  const responder = (resposta) => {
    pedido.resolve(resposta);
    setPedido(null);
  };

  const valor = useMemo(() => ({ avisar, confirmar }), [avisar, confirmar]);

  return (
    <Contexto.Provider value={valor}>
      {children}
      <div className="avisos" aria-live="polite">
        {avisos.map((a) => (
          <div key={a.id} className={`aviso ${a.erro ? 'erro' : 'sucesso'}`} role={a.erro ? 'alert' : 'status'}>
            <span>{a.erro || a.sucesso}</span>
            <button type="button" className="btn-link" onClick={() => dispensar(a.id)} aria-label="Dispensar aviso">✕</button>
          </div>
        ))}
      </div>
      {pedido && (
        <Modal titulo={pedido.titulo} onClose={() => responder(false)}>
          {pedido.texto && <p>{pedido.texto}</p>}
          <div className="acoes direita">
            <button type="button" className="btn" onClick={() => responder(false)}>Cancelar</button>
            <button type="button" data-foco className={`btn ${pedido.perigo ? 'perigo-cheio' : 'primario'}`} onClick={() => responder(true)}>
              {pedido.acao}
            </button>
          </div>
        </Modal>
      )}
    </Contexto.Provider>
  );
}

/** `avisar({ sucesso })` ou `avisar({ erro })`. */
export const useAvisar = () => useContext(Contexto).avisar;

/** `await confirmar({ titulo, texto, acao: 'Excluir', perigo: true })` devolve true ou false. */
export const useConfirmar = () => useContext(Contexto).confirmar;

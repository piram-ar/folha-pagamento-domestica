import { useEffect, useId, useRef, useState } from 'react';
import { api } from '../api';
import { brl, dataBR, hoje, mesLongo, somarMeses } from '../utils';

const FOCAVEIS = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Diálogo: prende o foco, trava a rolagem do fundo e devolve o foco a quem o abriu.
 * Clique fora só fecha com `fecharFora`: em formulários, um clique perdido apagaria o que foi digitado. */
export function Modal({ titulo, onClose, children, largo = false, fecharFora = false }) {
  const caixa = useRef(null);
  const tituloId = useId();
  const anterior = useRef(document.activeElement); // lido antes do autoFocus dos campos
  const fechar = useRef(onClose);
  fechar.current = onClose;

  useEffect(() => {
    if (!caixa.current.contains(document.activeElement)) {
      (caixa.current.querySelector('[data-foco], input, select, textarea') || caixa.current).focus();
    }
    const estouro = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const teclado = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); fechar.current(); return; }
      if (e.key !== 'Tab') return;
      const itens = [...caixa.current.querySelectorAll(FOCAVEIS)];
      if (!itens.length) return;
      const [primeiro, ultimo] = [itens[0], itens[itens.length - 1]];
      if (!caixa.current.contains(document.activeElement)) {  // clique no fundo tira o foco do diálogo
        e.preventDefault();
        primeiro.focus();
      } else if (e.shiftKey && (document.activeElement === primeiro || document.activeElement === caixa.current)) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    };
    window.addEventListener('keydown', teclado);
    return () => {
      window.removeEventListener('keydown', teclado);
      document.body.style.overflow = estouro;
      anterior.current?.focus?.();
    };
  }, []);

  return (
    <div className="modal-fundo" onMouseDown={fecharFora ? onClose : undefined}>
      <div ref={caixa} className={`modal ${largo ? 'largo' : ''}`} role="dialog" aria-modal="true" aria-labelledby={tituloId}
        tabIndex={-1} onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-cabecalho">
          <h3 id={tituloId}>{titulo}</h3>
          <button type="button" className="btn-link" onClick={onClose} aria-label="Fechar">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Alerta({ erro, sucesso }) {
  if (erro) return <div className="alerta erro" role="alert">{erro}</div>;
  if (sucesso) return <div className="alerta sucesso" role="status">{sucesso}</div>;
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

/** Conjunto de controles com um rótulo só (checkboxes, dia + tipo de dia). */
export function Grupo({ label, children, dica }) {
  return (
    <fieldset className="campo grupo">
      <legend>{label}</legend>
      {children}
      {dica && <small className="dica">{dica}</small>}
    </fieldset>
  );
}

/** Valor digitado à brasileira (1.234,56): teclado numérico no celular e sem mudar de valor com a roda do mouse. */
export function InputValor(props) {
  return <input type="text" inputMode="decimal" autoComplete="off" pattern="[0-9.,]+" title="Use só números, como 1.234,56" {...props} />;
}

export function Badge({ tipo = 'neutro', children }) {
  return <span className={`badge ${tipo}`}>{children}</span>;
}

/** Lugar do conteúdo enquanto os dados chegam, para a tela não pular nem mostrar "nada encontrado" antes da hora. */
export function Carregando({ linhas = 3 }) {
  return (
    <div className="esqueleto" role="status" aria-label="Carregando">
      {Array.from({ length: linhas }, (_, i) => <span key={i} />)}
    </div>
  );
}

/** Falha ao abrir a tela, com a saída: tentar de novo. */
export function ErroTela({ mensagem, onTentar }) {
  return (
    <div className="alerta erro" role="alert">
      <p>{mensagem}</p>
      {onTentar && <button className="btn pequeno" onClick={onTentar}>Tentar de novo</button>}
    </div>
  );
}

/** Abas de uma tela. O painel fica com quem usa; ←/→ trocam de aba. */
export function Abas({ abas, ativa, onChange, rotulo }) {
  const teclado = (e) => {
    const passo = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!passo) return;
    e.preventDefault();
    const i = abas.findIndex((a) => a.id === ativa);
    onChange(abas[(i + passo + abas.length) % abas.length].id);
  };
  const atual = useRef(null);
  useEffect(() => {
    if (atual.current?.parentElement.contains(document.activeElement)) atual.current.focus();
  }, [ativa]);
  return (
    <div className="abas" role="tablist" aria-label={rotulo} onKeyDown={teclado}>
      {abas.map((a) => (
        <button key={a.id} type="button" role="tab" ref={a.id === ativa ? atual : null} aria-selected={a.id === ativa}
          tabIndex={a.id === ativa ? 0 : -1} className={a.id === ativa ? 'ativa' : ''} onClick={() => onChange(a.id)}>
          {a.label}
        </button>
      ))}
    </div>
  );
}

const MESES_CURTOS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

/** Competência: setas para o mês vizinho e listas para ir longe. Substitui o <input type="month">, que
 * não existe no Firefox nem no Safari de computador. */
export function SeletorMes({ mes, onChange }) {
  const [ano, numero] = mes.split('-');
  const anoAtual = new Date().getFullYear();
  const inicio = Math.min(Number(ano), anoAtual - 6);
  const anos = Array.from({ length: anoAtual + 1 - inicio + 1 }, (_, i) => inicio + i);
  return (
    <div className="seletor-mes" role="group" aria-label={`Competência: ${mesLongo(mes)}`}>
      <button type="button" className="btn" onClick={() => onChange(somarMeses(mes, -1))} aria-label="Mês anterior">‹</button>
      <select value={numero} onChange={(e) => onChange(`${ano}-${e.target.value}`)} aria-label="Mês">
        {MESES_CURTOS.map((m, i) => <option key={m} value={String(i + 1).padStart(2, '0')}>{m}</option>)}
      </select>
      <select value={ano} onChange={(e) => onChange(`${e.target.value}-${numero}`)} aria-label="Ano">
        {anos.map((a) => <option key={a} value={a}>{a}</option>)}
      </select>
      <button type="button" className="btn" onClick={() => onChange(somarMeses(mes, 1))} aria-label="Próximo mês">›</button>
    </div>
  );
}

/** Situação da folha do mês; a fechada recebe o carimbo (animado só quando acabou de ser fechada). */
export function SituacaoFolha({ folha, recemFechada = false }) {
  if (!folha) return <Badge>Não calculada</Badge>;
  if (folha.pago_em) return <Badge tipo="verde">Paga em {dataBR(folha.pago_em)}</Badge>;
  if (folha.status === 'fechada') return <span className={`carimbo ${recemFechada ? 'novo' : ''}`}>Fechada</span>;
  return <Badge tipo="amarelo">Rascunho</Badge>;
}

/** Trabalhadores ativos, para os seletores; `null` enquanto carrega. */
export function useTrabalhadores() {
  const [lista, setLista] = useState(null);
  useEffect(() => {
    api.get('/trabalhadores?apenas_ativos=true').then(setLista).catch(() => setLista([]));
  }, []);
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

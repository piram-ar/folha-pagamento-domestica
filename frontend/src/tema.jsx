import { useSyncExternalStore } from 'react';

const CHAVE = 'folha_tema';
export const TEMAS = [['sistema', 'Sistema'], ['claro', 'Claro'], ['escuro', 'Escuro']];

// Preferência por aparelho (cada celular/computador escolhe o seu); o index.html aplica antes de pintar a tela
function lerTema() {
  try {
    return localStorage.getItem(CHAVE) || 'sistema';
  } catch {
    return 'sistema';
  }
}

let temaAtual = lerTema();
const ouvintes = new Set();

function aplicarTema() {
  const raiz = document.documentElement;
  if (temaAtual === 'sistema') delete raiz.dataset.theme;
  else raiz.dataset.theme = temaAtual === 'escuro' ? 'dark' : 'light';
  // Cor da barra do navegador no celular acompanha o fundo
  const fundo = getComputedStyle(raiz).getPropertyValue('--papel').trim();
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', fundo);
}

function definirTema(tema) {
  temaAtual = tema;
  try {
    localStorage.setItem(CHAVE, tema);
  } catch { /* navegação privada: vale só nesta visita */ }
  aplicarTema();
  ouvintes.forEach((avisar) => avisar());
}

// No modo "Sistema", acompanha a troca de claro/escuro feita no aparelho
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (temaAtual === 'sistema') aplicarTema();
});
aplicarTema();

function assinar(avisar) {
  ouvintes.add(avisar);
  return () => ouvintes.delete(avisar);
}

export function SeletorTema() {
  const tema = useSyncExternalStore(assinar, () => temaAtual);
  return (
    <div className="seletor-tema" role="radiogroup" aria-label="Aparência">
      {TEMAS.map(([valor, rotulo]) => (
        <button key={valor} type="button" role="radio" aria-checked={tema === valor}
          className={tema === valor ? 'ativo' : ''} onClick={() => definirTema(valor)}>
          {rotulo}
        </button>
      ))}
    </div>
  );
}

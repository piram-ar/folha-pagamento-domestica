/**
 * O mesmo código React gera o site (servido pelo Pi) e o app Android (Capacitor).
 * No app (`vite build --mode app`), a API fica em outro endereço: o do Pi, informado pelo usuário.
 */
export const MODO_APP = import.meta.env.VITE_MODO_APP === '1';

const SERVIDOR_KEY = 'folha_servidor';
export const SERVIDOR_PADRAO = 'https://192.168.68.73';

export function getServidor() {
  return localStorage.getItem(SERVIDOR_KEY) || '';
}

export function setServidor(url) {
  localStorage.setItem(SERVIDOR_KEY, normalizarServidor(url));
}

/** "192.168.68.73" -> "https://192.168.68.73" (sem barra no fim) */
export function normalizarServidor(url) {
  const limpo = url.trim().replace(/\/+$/, '');
  return /^https?:\/\//i.test(limpo) ? limpo : `https://${limpo}`;
}

/** Servidor salvo ainda em http://: se o Pi já responde por HTTPS, passa a usar HTTPS (senha e dados cifrados no Wi-Fi). */
export async function migrarParaHttps() {
  const atual = getServidor();
  if (!MODO_APP || !/^http:\/\//i.test(atual)) return;
  const seguro = atual.replace(/^http:/i, 'https:');
  const limite = new AbortController();
  const relogio = setTimeout(() => limite.abort(), 5000);
  try {
    const res = await fetch(`${seguro}/api/health`, { signal: limite.signal });
    if (res.ok) setServidor(seguro);
  } catch { /* sem HTTPS (ou CA não instalada no celular): segue em http até a próxima abertura */ } finally {
    clearTimeout(relogio);
  }
}

export const apiBase = () => (MODO_APP ? `${getServidor()}/api` : '/api');

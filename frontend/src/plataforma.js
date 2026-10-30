/**
 * O mesmo código React gera o site (servido pelo Pi) e o app Android (Capacitor).
 * No app (`vite build --mode app`), a API fica em outro endereço: o do Pi, informado pelo usuário.
 */
export const MODO_APP = import.meta.env.VITE_MODO_APP === '1';

const SERVIDOR_KEY = 'folha_servidor';
export const SERVIDOR_PADRAO = 'http://192.168.5.7';

export function getServidor() {
  return localStorage.getItem(SERVIDOR_KEY) || '';
}

export function setServidor(url) {
  localStorage.setItem(SERVIDOR_KEY, normalizarServidor(url));
}

/** "192.168.5.7" -> "http://192.168.5.7" (sem barra no fim) */
export function normalizarServidor(url) {
  const limpo = url.trim().replace(/\/+$/, '');
  return /^https?:\/\//i.test(limpo) ? limpo : `http://${limpo}`;
}

export const apiBase = () => (MODO_APP ? `${getServidor()}/api` : '/api');

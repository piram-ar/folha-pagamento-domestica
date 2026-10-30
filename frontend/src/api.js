import { apiBase, MODO_APP } from './plataforma';

const TOKEN_KEY = 'folha_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

function mensagemErro(detail, status) {
  if (!detail) return `Erro ${status}`;
  if (typeof detail === 'string') return detail;
  // Erros de validação do FastAPI/Pydantic
  if (Array.isArray(detail)) {
    return detail
      .map((d) => `${(d.loc || []).filter((p) => p !== 'body').join('.')}: ${d.msg}`)
      .join('; ');
  }
  return JSON.stringify(detail);
}

async function request(method, path, body) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  let res;
  try {
    res = await fetch(`${apiBase()}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    // TypeError = falha de rede (o AuthContext usa o tipo para não confundir com sessão expirada)
    throw new TypeError(MODO_APP
      ? 'Sem conexão com o servidor. Confira se o celular está no Wi-Fi de casa e se o Pi está ligado.'
      : 'Sem conexão com o servidor.');
  }

  if (res.status === 401 && path !== '/auth/login') {
    clearToken();
    window.location.href = '/login';
    throw new Error('Sessão expirada');
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(mensagemErro(data.detail, res.status));
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b ?? {}),
  put: (p, b) => request('PUT', p, b),
  del: (p) => request('DELETE', p),
};

async function buscarArquivo(path) {
  const res = await fetch(`${apiBase()}${path}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error('Não foi possível gerar o arquivo');
  // Nome sugerido pelo servidor (ex.: recibo_2026-10_ana.pdf)
  const nome = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '')?.[1];
  return { blob: await res.blob(), nome };
}

/** No app: grava o arquivo no cache e abre o menu "Compartilhar" do Android (WhatsApp, e-mail...). */
async function compartilhar(path, nomePadrao) {
  const [{ Filesystem, Directory }, { Share }] = await Promise.all([
    import('@capacitor/filesystem'), import('@capacitor/share'),
  ]);
  const { blob, nome } = await buscarArquivo(path);
  const base64 = await new Promise((resolve, reject) => {
    const leitor = new FileReader();
    leitor.onload = () => resolve(String(leitor.result).split(',')[1]);
    leitor.onerror = reject;
    leitor.readAsDataURL(blob);
  });
  const arquivo = await Filesystem.writeFile({ path: nome || nomePadrao, data: base64, directory: Directory.Cache });
  try {
    await Share.share({ title: nome || nomePadrao, files: [arquivo.uri], dialogTitle: 'Compartilhar' });
  } catch (erro) {
    if (!/cancel/i.test(String(erro?.message))) throw erro; // fechar o menu sem escolher não é erro
  }
}

/** Abre o PDF autenticado em uma nova aba (o token não vai na URL); no app, compartilha. */
export async function abrirPdf(path) {
  if (MODO_APP) return compartilhar(path, 'documento.pdf');
  const janela = window.open('', '_blank');
  try {
    const { blob } = await buscarArquivo(path);
    const url = URL.createObjectURL(blob);
    if (janela) janela.location.href = url;
    else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (erro) {
    janela?.close();
    throw new Error('Não foi possível gerar o PDF');
  }
  return undefined;
}

/** Baixa um arquivo autenticado (ex.: calendário .ics) com o nome indicado; no app, compartilha. */
export async function baixarArquivo(path, nome) {
  if (MODO_APP) return compartilhar(path, nome);
  const { blob } = await buscarArquivo(path);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = nome;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return undefined;
}

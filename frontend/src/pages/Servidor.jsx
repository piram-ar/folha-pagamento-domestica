import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { Alerta, Campo } from '../components/ui';
import { getServidor, normalizarServidor, SERVIDOR_PADRAO, setServidor } from '../plataforma';

/** Só no app: endereço do Raspberry Pi na rede de casa. */
export default function Servidor() {
  const navigate = useNavigate();
  const { usuario, verificarSessao } = useAuth();
  const [endereco, setEndereco] = useState(getServidor() || SERVIDOR_PADRAO);
  const [msg, setMsg] = useState({});
  const [testando, setTestando] = useState(false);

  const salvar = async (e) => {
    e.preventDefault();
    setMsg({});
    setTestando(true);
    const url = normalizarServidor(endereco);
    const limite = new AbortController();
    const relogio = setTimeout(() => limite.abort(), 6000);
    try {
      const res = await fetch(`${url}/api/health`, { signal: limite.signal });
      if (!res.ok) throw new Error();
      setServidor(url);
      verificarSessao();
      navigate(usuario ? '/' : '/login');
    } catch {
      setMsg({ erro: `Não encontrei a Folha Doméstica em ${url}. Confira o endereço e se o celular está no Wi-Fi de casa.` });
    } finally {
      clearTimeout(relogio);
      setTestando(false);
    }
  };

  return (
    <div className={usuario ? '' : 'login-pagina'}>
      <div className={usuario ? '' : 'login-caixa'}>
        {usuario ? <h2>Servidor</h2> : <h1 className="marca">Folha Doméstica</h1>}
        <p className="sub">
          Endereço do Raspberry Pi na rede de casa: o mesmo que você usa no navegador (ex.: {SERVIDOR_PADRAO}).
        </p>
        <form className="painel" onSubmit={salvar}>
          <Alerta {...msg} />
          <Campo label="Endereço do servidor">
            <input value={endereco} onChange={(e) => setEndereco(e.target.value)} inputMode="url" autoCapitalize="off"
              autoCorrect="off" required autoFocus />
          </Campo>
          <button className="btn primario largo espaco-acima" disabled={testando}>
            {testando ? 'Procurando…' : 'Conectar'}
          </button>
        </form>
      </div>
    </div>
  );
}

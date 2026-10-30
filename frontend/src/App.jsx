import { useEffect } from 'react';
import { Link, Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './AuthContext';
import Layout from './components/Layout';
import { sincronizarAvisos } from './notificacoesApp';
import Avisos from './pages/Avisos';
import AvisosApp from './pages/AvisosApp';
import Contratante from './pages/Contratante';
import Dashboard from './pages/Dashboard';
import Ferias from './pages/Ferias';
import Folha from './pages/Folha';
import Inss from './pages/Inss';
import Lancamentos from './pages/Lancamentos';
import Login from './pages/Login';
import Servidor from './pages/Servidor';
import TrabalhadorDetalhe from './pages/TrabalhadorDetalhe';
import Trabalhadores from './pages/Trabalhadores';
import Usuarios from './pages/Usuarios';
import { getServidor, MODO_APP } from './plataforma';

function SemConexao() {
  const { verificarSessao } = useAuth();
  return (
    <div className="login-pagina">
      <div className="login-caixa">
        <h1 className="marca">Folha Doméstica</h1>
        <div className="alerta erro">
          Sem conexão com o servidor. Confira se o celular está no Wi-Fi de casa e se o Raspberry Pi está ligado.
        </div>
        <div className="acoes">
          <button className="btn primario" onClick={verificarSessao}>Tentar de novo</button>
          {MODO_APP && <Link className="btn" to="/servidor">Trocar servidor</Link>}
        </div>
      </div>
    </div>
  );
}

function Protegida({ children, somenteAdmin = false }) {
  const { usuario, isAdmin, carregando, semConexao } = useAuth();
  if (MODO_APP && !getServidor()) return <Navigate to="/servidor" replace />;
  if (carregando) return <div className="carregando">Carregando…</div>;
  if (semConexao) return <SemConexao />;
  if (!usuario) return <Navigate to="/login" replace />;
  if (somenteAdmin && !isAdmin) return <Navigate to="/" replace />;
  return children;
}

/** No app, sem endereço do Pi salvo, vai para a tela de servidor. Avaliado a cada navegação (não no render do App). */
function ExigeServidor({ children }) {
  return getServidor() ? children : <Navigate to="/servidor" replace />;
}

/** No app: refaz a agenda de avisos ao entrar e sempre que o app volta para a frente. */
function useAvisosNoApp(usuario) {
  useEffect(() => {
    if (!MODO_APP || !usuario) return undefined;
    const sincronizar = () => sincronizarAvisos().catch(() => { /* fora de casa: mantém a agenda anterior */ });
    sincronizar();
    const ouvinte = import('@capacitor/app').then(({ App: AppNativo }) => AppNativo.addListener('resume', sincronizar));
    return () => { ouvinte.then((o) => o.remove()); };
  }, [usuario]);
}

export default function App() {
  const { usuario } = useAuth();
  useAvisosNoApp(usuario);

  if (MODO_APP) {
    // App Android: só a rotina do mês (cadastros e configurações ficam no navegador)
    return (
      <Routes>
        <Route path="/servidor" element={<Servidor />} />
        <Route path="/login" element={<ExigeServidor><Login /></ExigeServidor>} />
        <Route element={<Protegida><Layout /></Protegida>}>
          <Route index element={<Dashboard />} />
          <Route path="lancamentos" element={<Lancamentos />} />
          <Route path="folha" element={<Folha />} />
          <Route path="ferias" element={<Ferias />} />
          <Route path="avisos-celular" element={<AvisosApp />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protegida><Layout /></Protegida>}>
        <Route index element={<Dashboard />} />
        <Route path="trabalhadores" element={<Trabalhadores />} />
        <Route path="trabalhadores/:id" element={<TrabalhadorDetalhe />} />
        <Route path="lancamentos" element={<Lancamentos />} />
        <Route path="folha" element={<Folha />} />
        <Route path="ferias" element={<Ferias />} />
        <Route path="contratante" element={<Contratante />} />
        <Route path="avisos" element={<Avisos />} />
        <Route path="inss" element={<Inss />} />
        <Route path="usuarios" element={<Protegida somenteAdmin><Usuarios /></Protegida>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './AuthContext';
import Layout from './components/Layout';
import Contratante from './pages/Contratante';
import Dashboard from './pages/Dashboard';
import Ferias from './pages/Ferias';
import Folha from './pages/Folha';
import Lancamentos from './pages/Lancamentos';
import Login from './pages/Login';
import TrabalhadorDetalhe from './pages/TrabalhadorDetalhe';
import Trabalhadores from './pages/Trabalhadores';
import Usuarios from './pages/Usuarios';

function Protegida({ children, somenteAdmin = false }) {
  const { usuario, isAdmin, carregando } = useAuth();
  if (carregando) return <div className="carregando">Carregando…</div>;
  if (!usuario) return <Navigate to="/login" replace />;
  if (somenteAdmin && !isAdmin) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
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
        <Route path="usuarios" element={<Protegida somenteAdmin><Usuarios /></Protegida>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

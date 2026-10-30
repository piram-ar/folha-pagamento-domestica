import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, clearToken, getToken, setToken } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [carregando, setCarregando] = useState(Boolean(getToken()));
  // Servidor fora do ar ou celular fora da rede de casa: mantém o login e oferece tentar de novo
  const [semConexao, setSemConexao] = useState(false);

  const verificarSessao = useCallback(() => {
    if (!getToken()) return;
    setCarregando(true);
    setSemConexao(false);
    api.get('/auth/me')
      .then(setUsuario)
      .catch((erro) => {
        if (erro instanceof TypeError) setSemConexao(true); // falha de rede, não de login
        else clearToken();
      })
      .finally(() => setCarregando(false));
  }, []);

  useEffect(() => { verificarSessao(); }, [verificarSessao]);

  const login = async (email, senha) => {
    const data = await api.post('/auth/login', { email, senha });
    setToken(data.access_token);
    setUsuario(data.usuario);
  };

  const logout = () => {
    clearToken();
    setUsuario(null);
  };

  const isAdmin = usuario?.perfil === 'admin';

  return (
    <AuthContext.Provider value={{ usuario, isAdmin, carregando, semConexao, verificarSessao, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

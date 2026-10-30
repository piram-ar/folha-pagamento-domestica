import { createContext, useContext, useEffect, useState } from 'react';
import { api, clearToken, getToken, setToken } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [carregando, setCarregando] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) return;
    api.get('/auth/me')
      .then(setUsuario)
      .catch(() => clearToken())
      .finally(() => setCarregando(false));
  }, []);

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
    <AuthContext.Provider value={{ usuario, isAdmin, carregando, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

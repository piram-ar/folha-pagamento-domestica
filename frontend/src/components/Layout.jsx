import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { MODO_APP } from '../plataforma';
import { SeletorTema } from '../tema';
import { Modal } from './ui';

// Rotina do mês: aparecem no menu inferior do celular
const PRINCIPAIS = [
  { to: '/', label: 'Início', curto: 'Início', end: true, icone: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z' },
  { to: '/lancamentos', label: 'Lançamentos do mês', curto: 'Lançar', icone: 'M12 5v14M5 12h14' },
  { to: '/folha', label: 'Folha de pagamento', curto: 'Folha', icone: 'M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6' },
  { to: '/ferias', label: 'Férias', curto: 'Férias', icone: 'M4 7h16v13H4zM4 11h16M9 3v6M15 3v6' },
];
// Cadastros: ficam em "Mais" no celular
const CADASTROS = [
  { to: '/trabalhadores', label: 'Trabalhadores' },
  { to: '/avisos', label: 'Avisos de pagamento' },
  { to: '/contratante', label: 'Empregador / contratante' },
  { to: '/inss', label: 'Tabela do INSS' },
];
// No app Android, cadastros e configurações ficam no navegador; o "Mais" só tem o que é do celular
const OPCOES_APP = [
  { to: '/avisos-celular', label: 'Avisos neste celular' },
  { to: '/servidor', label: 'Servidor (Raspberry Pi)' },
];

function Icone({ d }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export default function Layout() {
  const { usuario, isAdmin, logout } = useAuth();
  const { pathname } = useLocation();
  const [maisAberto, setMaisAberto] = useState(false);
  const cadastros = MODO_APP ? OPCOES_APP
    : isAdmin ? [...CADASTROS, { to: '/usuarios', label: 'Usuários do sistema' }] : CADASTROS;
  const emCadastro = cadastros.some((l) => pathname.startsWith(l.to));

  return (
    <div className="app">
      <aside className="lateral">
        <Link to="/" className="marca">Folha Doméstica</Link>
        <nav aria-label="Menu principal">
          {PRINCIPAIS.map((l) => <NavLink key={l.to} to={l.to} end={l.end}>{l.label}</NavLink>)}
          <div className="grupo-secundario" />
          {cadastros.map((l) => <NavLink key={l.to} to={l.to}>{l.label}</NavLink>)}
        </nav>
        <div className="sessao">
          <SeletorTema />
          <strong>{usuario.nome}</strong>
          <button className="btn-link" onClick={logout}>Sair</button>
        </div>
      </aside>

      <header className="topo-movel">
        <Link to="/" className="marca">Folha Doméstica</Link>
        <small>{usuario.nome}</small>
      </header>

      <main className="conteudo">
        <Outlet />
      </main>

      <nav className="menu-inferior" aria-label="Menu">
        {PRINCIPAIS.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end}><Icone d={l.icone} />{l.curto}</NavLink>
        ))}
        <button className={emCadastro ? 'ativo' : ''} onClick={() => setMaisAberto(true)}>
          <Icone d="M5 12h.01M12 12h.01M19 12h.01" />Mais
        </button>
      </nav>

      {maisAberto && (
        <Modal titulo="Mais opções" onClose={() => setMaisAberto(false)}>
          <div className="folha-mais" onClick={() => setMaisAberto(false)}>
            {cadastros.map((l) => <Link key={l.to} to={l.to}>{l.label}</Link>)}
          </div>
          <div className="tema-mais">
            <span>Aparência</span>
            <SeletorTema />
          </div>
          <div className="folha-mais">
            <button className="sair" onClick={logout}>Sair ({usuario.nome})</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

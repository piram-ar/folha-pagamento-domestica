import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, baixarArquivo } from '../api';
import { useAuth } from '../AuthContext';
import { Alerta, Badge, Campo } from '../components/ui';
import { dataBR, diaSemana, ROTULOS } from '../utils';

const faltam = (d) => (d === 0 ? 'hoje' : d === 1 ? 'amanhã' : `em ${d} dias`);

/** Servidores SMTP mais comuns (Gmail e Outlook exigem "senha de app"). */
const PROVEDORES = {
  gmail: { smtp_host: 'smtp.gmail.com', smtp_porta: 587, smtp_seguranca: 'starttls' },
  outlook: { smtp_host: 'smtp-mail.outlook.com', smtp_porta: 587, smtp_seguranca: 'starttls' },
};

function ProximosPagamentos() {
  const [lista, setLista] = useState(null);
  useEffect(() => { api.get('/notificacoes/proximos?dias=45').then(setLista).catch(() => setLista([])); }, []);
  if (!lista) return <div className="carregando">Carregando…</div>;
  if (!lista.length) return <p className="vazio">Nenhum pagamento nos próximos 45 dias (cadastre trabalhadores ativos).</p>;
  return (
    <ul className="proximos">
      {lista.map((p) => (
        <li key={`${p.trabalhador_id}-${p.tipo}-${p.data}`}>
          <span className="data"><strong>{dataBR(p.data).slice(0, 5)}</strong><small>{diaSemana(p.data)}</small></span>
          <span>
            <Link to={`/trabalhadores/${p.trabalhador_id}`}>{p.trabalhador_nome}</Link>
            <small>{ROTULOS.pagamento[p.tipo]} · ref. {p.competencia.slice(5)}/{p.competencia.slice(0, 4)}</small>
          </span>
          <Badge tipo={p.dias_faltando <= 3 ? 'amarelo' : 'neutro'}>{faltam(p.dias_faltando)}</Badge>
        </li>
      ))}
    </ul>
  );
}

export default function Avisos() {
  const { isAdmin } = useAuth();
  const [config, setConfig] = useState(null);
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState({});
  const [ocupado, setOcupado] = useState(false);

  const aplicar = useCallback((c) => {
    setConfig(c);
    setForm({ ...c, destinatarios: c.destinatarios || '', smtp_host: c.smtp_host || '', smtp_usuario: c.smtp_usuario || '',
      smtp_remetente: c.smtp_remetente || '', smtp_senha: '' });
  }, []);
  useEffect(() => { api.get('/notificacoes/config').then(aplicar).catch((e) => setMsg({ erro: e.message })); }, [aplicar]);

  if (!form) return msg.erro ? <Alerta erro={msg.erro} /> : <div className="carregando">Carregando…</div>;

  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  const linkAssinatura = config.token_calendario
    ? `${window.location.origin}/api/notificacoes/assinatura/${config.token_calendario}.ics` : null;

  const executar = async (acao) => {
    setMsg({});
    setOcupado(true);
    try { await acao(); } catch (e) { setMsg({ erro: e.message }); } finally { setOcupado(false); }
  };

  const salvar = (e) => {
    e.preventDefault();
    executar(async () => {
      aplicar(await api.put('/notificacoes/config', { ...form, hora_envio: Number(form.hora_envio), smtp_porta: Number(form.smtp_porta) }));
      setMsg({ sucesso: 'Configuração salva.' });
    });
  };
  const testar = () => executar(async () => setMsg({ sucesso: (await api.post('/notificacoes/teste')).mensagem }));
  const novoLink = () => {
    if (config.token_calendario && !window.confirm('Gerar um novo link? Agendas que assinaram o link atual deixarão de atualizar.')) return;
    executar(async () => aplicar(await api.post('/notificacoes/novo-link')));
  };
  const copiar = () => navigator.clipboard?.writeText(linkAssinatura).then(() => setMsg({ sucesso: 'Link copiado.' }));
  const baixar = (formato) => executar(() => baixarArquivo(`/notificacoes/calendario.${formato}`, `pagamentos-folha.${formato}`));

  return (
    <>
      <div className="titulo-pagina">
        <div>
          <h2>Avisos de pagamento</h2>
          <p className="sub">
            Lembretes do salário e do adiantamento de cada trabalhador. As datas vêm do cadastro do trabalhador.
          </p>
        </div>
      </div>
      <Alerta {...msg} />

      <section className="secao">
        <h3>Próximos pagamentos</h3>
        <ProximosPagamentos />
      </section>

      <section className="painel">
        <h3>Agenda do celular ou computador</h3>
        <p className="dica">
          Importe o arquivo na sua agenda (Google Agenda, Outlook, calendário do iPhone ou Android). Os pagamentos
          entram como eventos que se repetem todo mês, com alarmes na antecedência definida abaixo. Se mudar as datas de
          pagamento ou os trabalhadores, baixe e importe de novo.
        </p>
        <div className="acoes">
          <button type="button" className="btn primario" onClick={() => baixar('ics')}>Baixar .ics (recomendado)</button>
          <button type="button" className="btn" onClick={() => baixar('vcs')}>Baixar .vcs (agendas antigas)</button>
        </div>
        <p className="dica">O .vcs não tem repetição automática: traz as datas dos próximos 12 meses.</p>

        <h4>Assinatura automática</h4>
        <p className="dica">
          Com o link, a agenda busca as datas sozinha e se atualiza quando algo muda. Funciona apenas em aparelhos
          conectados à rede de casa (a agenda do Google na web não alcança o Raspberry Pi). Quem tiver o link vê
          os nomes e as datas de pagamento, sem valores.
        </p>
        {linkAssinatura ? (
          <div className="link-assinatura">
            <code>{linkAssinatura}</code>
            <div className="acoes">
              <button type="button" className="btn pequeno" onClick={copiar}>Copiar link</button>
              <a className="btn pequeno" href={linkAssinatura.replace(/^https?:/, 'webcal:')}>Abrir na agenda</a>
              {isAdmin && <button type="button" className="btn pequeno perigo" onClick={novoLink}>Gerar novo link</button>}
            </div>
          </div>
        ) : isAdmin ? (
          <button type="button" className="btn" onClick={novoLink}>Criar link de assinatura</button>
        ) : <p className="vazio">Nenhum link criado. Peça a um administrador.</p>}
      </section>

      <form onSubmit={salvar}>
        <fieldset disabled={!isAdmin || ocupado} className="sem-borda">
          <section className="painel">
            <h3>Antecedência dos avisos</h3>
            <Campo label="Avisar quantos dias antes" dica="Separe por vírgula. Ex.: 3,1 avisa 3 dias antes e na véspera; 0 avisa no próprio dia. Vale para o e-mail e para os alarmes da agenda.">
              <input value={form.antecedencias} onChange={set('antecedencias')} placeholder="3,1" required />
            </Campo>
          </section>


          <section className="painel">
            <h3>Aviso por e-mail</h3>
            <label className="checkbox">
              <input type="checkbox" checked={form.email_ativo} onChange={set('email_ativo')} /> Enviar avisos por e-mail
            </label>
            <div className="grade-form">
              <Campo label="Destinatários" dica="Um ou mais e-mails, separados por vírgula.">
                <input value={form.destinatarios} onChange={set('destinatarios')} placeholder="voce@exemplo.com" />
              </Campo>
              <Campo label="Horário do envio" dica="O Pi verifica a cada 10 minutos; se estiver desligado nesse horário, envia quando voltar.">
                <select value={form.hora_envio} onChange={set('hora_envio')}>
                  {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>)}
                </select>
              </Campo>
            </div>

            <h4>Servidor de envio (SMTP)</h4>
            <p className="dica">
              No Gmail e no Outlook, use uma <strong>senha de app</strong> (criada na conta Google/Microsoft com a
              verificação em duas etapas ativa), não a senha normal.
            </p>
            {isAdmin && (
              <div className="acoes">
                <button type="button" className="btn pequeno" onClick={() => setForm({ ...form, ...PROVEDORES.gmail })}>Preencher Gmail</button>
                <button type="button" className="btn pequeno" onClick={() => setForm({ ...form, ...PROVEDORES.outlook })}>Preencher Outlook</button>
              </div>
            )}
            <div className="grade-form espaco-acima">
              <Campo label="Servidor"><input value={form.smtp_host} onChange={set('smtp_host')} placeholder="smtp.gmail.com" /></Campo>
              <Campo label="Porta"><input type="number" min="1" max="65535" value={form.smtp_porta} onChange={set('smtp_porta')} /></Campo>
              <Campo label="Segurança">
                <select value={form.smtp_seguranca} onChange={set('smtp_seguranca')}>
                  <option value="starttls">STARTTLS (porta 587)</option>
                  <option value="ssl">SSL/TLS (porta 465)</option>
                  <option value="nenhuma">Nenhuma</option>
                </select>
              </Campo>
              <Campo label="Usuário"><input value={form.smtp_usuario} onChange={set('smtp_usuario')} autoComplete="off" /></Campo>
              <Campo label="Senha" dica={config.smtp_senha_definida ? 'Já cadastrada. Deixe em branco para manter.' : ''}>
                <input type="password" value={form.smtp_senha} onChange={set('smtp_senha')} autoComplete="new-password" />
              </Campo>
              <Campo label="Remetente (opcional)" dica="Se vazio, usa o usuário.">
                <input value={form.smtp_remetente} onChange={set('smtp_remetente')} />
              </Campo>
            </div>

            {config.ultimo_envio_em && (
              <p className="dica">Último aviso enviado em {dataBR(config.ultimo_envio_em)} às {config.ultimo_envio_em.slice(11, 16)}.</p>
            )}
            {config.ultimo_erro && <div className="alerta erro">Última falha de envio: {config.ultimo_erro}</div>}

            {isAdmin && (
              <div className="acoes direita">
                <button type="button" className="btn" onClick={testar} disabled={!config.smtp_host}
                  title={config.smtp_host ? '' : 'Salve a configuração antes de testar'}>Enviar e-mail de teste</button>
                <button className="btn primario">Salvar</button>
              </div>
            )}
          </section>
        </fieldset>
      </form>
      {!isAdmin && <p className="dica">Somente administradores podem alterar a configuração dos avisos.</p>}
    </>
  );
}

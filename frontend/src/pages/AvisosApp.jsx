import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { Alerta } from '../components/ui';
import {
  ativarAvisos, avisoDeTeste, avisosAgendados, avisosAtivos, sincronizarAvisos, ultimaSincronia,
} from '../notificacoesApp';

const dois = (n) => String(n).padStart(2, '0');
/** Data e hora locais ("07/11/2026 às 08:00"); toISOString usaria UTC e trocaria o dia à noite. */
const quando = (iso) => {
  const d = new Date(iso);
  return `${dois(d.getDate())}/${dois(d.getMonth() + 1)}/${d.getFullYear()} às ${dois(d.getHours())}:${dois(d.getMinutes())}`;
};

/** Só no app: liga/desliga as notificações de pagamento neste celular. */
export default function AvisosApp() {
  const [ativo, setAtivo] = useState(avisosAtivos());
  const [config, setConfig] = useState(null);
  const [agendados, setAgendados] = useState([]);
  const [msg, setMsg] = useState({});
  const [ocupado, setOcupado] = useState(false);

  const atualizarLista = useCallback(() => avisosAgendados().then(setAgendados).catch(() => setAgendados([])), []);
  useEffect(() => {
    api.get('/notificacoes/config').then(setConfig).catch(() => {});
    atualizarLista();
  }, [atualizarLista]);

  const executar = async (acao) => {
    setMsg({});
    setOcupado(true);
    try { await acao(); } catch (e) { setMsg({ erro: e.message }); } finally {
      setOcupado(false);
      atualizarLista();
    }
  };

  const alternar = () => executar(async () => {
    const n = await ativarAvisos(!ativo);
    setAtivo(!ativo);
    setMsg({ sucesso: ativo ? 'Avisos desligados neste celular.' : `Avisos ligados: ${n} lembrete(s) agendado(s).` });
  });
  const sincronizar = () => executar(async () => setMsg({ sucesso: `${await sincronizarAvisos()} lembrete(s) agendado(s).` }));
  const testar = () => executar(async () => {
    await avisoDeTeste();
    setMsg({ sucesso: 'Um aviso de teste vai aparecer em 5 segundos.' });
  });

  const sincronia = ultimaSincronia();
  const antecedencias = config?.antecedencias.split(',').map((n) => (n === '0' ? 'no dia' : `${n} dia(s) antes`)).join(', ');

  return (
    <>
      <h2>Avisos neste celular</h2>
      <Alerta {...msg} />
      <section className="painel">
        <label className="checkbox">
          <input type="checkbox" checked={ativo} onChange={alternar} disabled={ocupado} />
          Receber avisos de pagamento neste celular
        </label>
        <p className="dica">
          Os lembretes ficam agendados no próprio celular e aparecem mesmo com o app fechado e fora de casa.
          {config && <> Antecedência: <strong>{antecedencias}</strong>, às {String(config.hora_envio).padStart(2, '0')}:00 (definidas em Avisos de pagamento, no navegador).</>}
        </p>
        <p className="dica">
          A agenda é atualizada sempre que você abre o app em casa. Se mudar datas de pagamento ou trabalhadores,
          abra o app no Wi-Fi de casa para atualizar.
          {sincronia && <> Última atualização: {quando(sincronia)}.</>}
        </p>
        {ativo && (
          <div className="acoes">
            <button className="btn" onClick={sincronizar} disabled={ocupado}>Atualizar agora</button>
            <button className="btn" onClick={testar} disabled={ocupado}>Enviar aviso de teste</button>
          </div>
        )}
      </section>

      {ativo && (
        <section className="secao">
          <h3>Próximos avisos agendados</h3>
          {agendados.length === 0 ? <p className="vazio">Nenhum aviso agendado.</p> : (
            <ul className="proximos">
              {agendados.slice(0, 20).map((n) => (
                <li key={n.id}>
                  <span className="data"><strong>{n.schedule?.at ? quando(n.schedule.at).slice(0, 5) : ''}</strong><small>{n.schedule?.at ? quando(n.schedule.at).slice(-5) : ''}</small></span>
                  <span><strong>{n.title}</strong><small>{n.body}</small></span>
                  <span />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}

/**
 * Avisos de pagamento no app Android: as datas são previsíveis, então o app busca no Pi os próximos
 * pagamentos e agenda notificações locais no próprio celular. Elas disparam com o app fechado e fora
 * de casa; a cada abertura do app (com o Pi alcançável) a agenda é refeita com os dados atuais.
 */
import { api } from './api';
import { MODO_APP } from './plataforma';
import { dataBR, diaSemana, ROTULOS } from './utils';

const CHAVE_ATIVO = 'folha_avisos_app';
const CHAVE_SINCRONIA = 'folha_avisos_sincronia';
const CANAL = 'pagamentos';
const DIAS_A_FRENTE = 120;
const MAXIMO_AGENDADOS = 60;

export const avisosAtivos = () => localStorage.getItem(CHAVE_ATIVO) === '1';
export const ultimaSincronia = () => localStorage.getItem(CHAVE_SINCRONIA);

// Devolve o módulo, nunca o plugin: o plugin é um proxy que trata qualquer método (inclusive o
// `.then` que a Promise procura ao resolver) como chamada nativa, e um `async` que o retorna quebra.
const modulo = () => import('@capacitor/local-notifications');

function titulo(dias) {
  if (dias === 0) return 'Pagamento hoje';
  if (dias === 1) return 'Pagamento amanhã';
  return `Pagamento em ${dias} dias`;
}

async function cancelarTodos(LocalNotifications) {
  const { notifications } = await LocalNotifications.getPending();
  if (notifications.length) await LocalNotifications.cancel({ notifications: notifications.map((n) => ({ id: n.id })) });
}

/** Refaz a agenda de avisos. Retorna quantos foram agendados (0 se desativado ou fora do app). */
export async function sincronizarAvisos() {
  if (!MODO_APP || !avisosAtivos()) return 0;
  const { LocalNotifications } = await modulo();
  const [config, proximos] = await Promise.all([
    api.get('/notificacoes/config'),
    api.get(`/notificacoes/proximos?dias=${DIAS_A_FRENTE}`),
  ]);
  const antecedencias = config.antecedencias.split(',').map(Number).filter((n) => !Number.isNaN(n));
  const agora = new Date();
  const avisos = [];
  for (const p of proximos) {
    const [ano, mes, dia] = p.data.split('-').map(Number);
    for (const a of antecedencias) {
      // Mesmo horário escolhido para o e-mail na tela de avisos
      const quando = new Date(ano, mes - 1, dia - a, config.hora_envio, 0, 0);
      if (quando <= agora) continue;
      avisos.push({
        title: titulo(a),
        body: `${ROTULOS.pagamento[p.tipo]} de ${p.trabalhador_nome}: ${dataBR(p.data).slice(0, 5)} (${diaSemana(p.data)})`,
        schedule: { at: quando, allowWhileIdle: true },
        channelId: CANAL,
        isExactNotification: false,
      });
    }
  }
  avisos.sort((x, y) => x.schedule.at - y.schedule.at);

  await cancelarTodos(LocalNotifications);
  const lote = avisos.slice(0, MAXIMO_AGENDADOS).map((n, i) => ({ ...n, id: i + 1 }));
  if (lote.length) await LocalNotifications.schedule({ notifications: lote });
  localStorage.setItem(CHAVE_SINCRONIA, new Date().toISOString());
  return lote.length;
}

/** Liga os avisos (pede a permissão do Android 13+) ou desliga e cancela os agendados. */
export async function ativarAvisos(ativar) {
  const { LocalNotifications } = await modulo();
  if (!ativar) {
    localStorage.setItem(CHAVE_ATIVO, '0');
    await cancelarTodos(LocalNotifications);
    return 0;
  }
  const { display } = await LocalNotifications.requestPermissions();
  if (display !== 'granted') {
    throw new Error('O Android não permitiu notificações. Libere em Configurações > Apps > Folha Doméstica > Notificações.');
  }
  await LocalNotifications.createChannel({
    id: CANAL, name: 'Avisos de pagamento', description: 'Lembretes do salário e do adiantamento', importance: 4,
  });
  localStorage.setItem(CHAVE_ATIVO, '1');
  return sincronizarAvisos();
}

export async function avisosAgendados() {
  if (!MODO_APP) return [];
  const { LocalNotifications } = await modulo();
  const { notifications } = await LocalNotifications.getPending();
  return notifications.sort((x, y) => new Date(x.schedule?.at) - new Date(y.schedule?.at));
}

export async function avisoDeTeste() {
  const { LocalNotifications } = await modulo();
  await LocalNotifications.schedule({
    notifications: [{
      id: 9999, title: 'Folha Doméstica', body: 'Os avisos de pagamento estão funcionando neste celular.',
      schedule: { at: new Date(Date.now() + 5000), allowWhileIdle: true }, channelId: CANAL, isExactNotification: false,
    }],
  });
}

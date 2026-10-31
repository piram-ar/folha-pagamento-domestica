export const brl = (v) =>
  Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

export const dataBR = (iso) => {
  if (!iso) return '';
  const [a, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${a}`;
};

export const cpfFmt = (cpf = '') => {
  const d = cpf.replace(/\D/g, '');
  return d.length === 11 ? `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}` : cpf;
};

export const hoje = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export const mesAtual = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};

const MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho',
  'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
export const diasDoMes = (mesAno) => {
  const [a, m] = mesAno.split('-').map(Number);
  return new Date(a, m, 0).getDate();
};

export const mesExtenso = (mesAno) => {
  const [a, m] = mesAno.split('-');
  return `${MESES[Number(m) - 1]}/${a}`;
};

/** "2026-10" -> "Outubro de 2026" */
export const mesLongo = (mesAno) => {
  const [a, m] = mesAno.split('-');
  return `${MESES[Number(m) - 1]} de ${a}`;
};

export const somarDias =(iso, dias) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + dias);
  return d.toISOString().slice(0, 10);
};

// Dias da semana no padrão ISO usado pela API (1 = segunda ... 7 = domingo)
export const DIAS_SEMANA = [['1', 'Seg'], ['2', 'Ter'], ['3', 'Qua'], ['4', 'Qui'], ['5', 'Sex'], ['6', 'Sáb'], ['7', 'Dom']];

/** Vale-transporte pago (no salário ou à parte) é informado por dia; a cota descontada é mensal. */
export const vtPorDia = (b) => b.tipo === 'vale_transporte' && b.natureza !== 'desconto';

/** "5º dia útil" / "dia 20" */
export const regraPagamentoTexto = (dia, util) => (util ? `${dia}º dia útil` : `dia ${dia}`);

const DIAS_SEMANA_LONGO = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];
export const diaSemana = (iso) => DIAS_SEMANA_LONGO[new Date(`${iso}T12:00:00`).getDay()];

export const ROTULOS = {
  pagamento: { salario: 'Salário', adiantamento: 'Adiantamento' },
  tipo_contrato: { com_registro: 'Com registro (CLT)', sem_registro: 'Sem registro' },
  perfil: { admin: 'Administrador', padrao: 'Padrão' },
  beneficio: {
    vale_transporte: 'Vale-transporte',
    vale_mercado: 'Vale-mercado',
    vale_refeicao: 'Vale-refeição',
    plano_saude: 'Plano de saúde',
    outro: 'Outro',
  },
  natureza: {
    provento: 'Soma ao salário',
    desconto: 'Desconta do salário',
    informativo: 'Pago à parte (informativo)',
  },
  evento: {
    vale_antecipacao: 'Vale / adiantamento',
    hora_extra: 'Hora extra',
    falta: 'Falta',
    bonus: 'Bônus',
  },
  situacao_ferias: {
    em_aquisicao: 'Em aquisição',
    disponivel: 'Disponível',
    vence_em_breve: 'Vence em breve',
    vencido: 'Vencido',
    quitado: 'Quitado',
  },
};

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

/** CPF com pontuação enquanto se digita. */
export const cpfMascara = (valor) => {
  const d = valor.replace(/\D/g, '').slice(0, 11);
  return d.replace(/^(\d{3})(\d)/, '$1.$2').replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3').replace(/\.(\d{3})(\d)/, '.$1-$2');
};

export const cepMascara = (valor) => {
  const d = valor.replace(/\D/g, '').slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
};

/** Texto digitado à brasileira para o formato da API: "1.234,56" -> "1234.56". Ponto sem vírgula é decimal,
 * salvo quando separa milhares ("1.500"). */
export const numero = (valor) => {
  const s = String(valor).trim();
  if (s.includes(',')) return s.replace(/\./g, '').replace(',', '.');
  return /^\d{1,3}(\.\d{3})+$/.test(s) ? s.replace(/\./g, '') : s;
};

/** Valor da API para o campo de texto: 2000.00 -> "2000,00". */
export const valorCampo = (v) => (v === '' || v == null ? '' : Number(v).toFixed(2).replace('.', ','));

export const hoje = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export const mesAtual = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};

/** Mês vizinho: somarMeses('2026-12', 1) -> '2027-01'. */
export const somarMeses = (mesAno, n) => {
  const [a, m] = mesAno.split('-').map(Number);
  const d = new Date(a, m - 1 + n, 1);
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

/** Vazio com data vazia ou incompleta: o campo fica assim enquanto a pessoa digita. */
export const somarDias = (iso, dias) => {
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return '';
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

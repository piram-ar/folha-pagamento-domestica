import { dataBR, mesExtenso } from '../../utils';

export const nomeParcela = (d) => (d.parcela === 1 ? '1ª parcela' : d.adiantamento > 0 ? '2ª parcela' : 'Parcela única');

export const TIPOS = [['', 'Todos'], ['folha', 'Folha mensal'], ['ferias', 'Férias'], ['decimo', '13º salário']];
export const ROTULO_TIPO = Object.fromEntries(TIPOS);

/** Uma folha no formato da lista geral de pagamentos. */
export const registroDeFolha = (f) => ({
  chave: `f${f.id}`, tipo: 'folha', data: `${f.mes_ano}-01`, referencia: mesExtenso(f.mes_ano),
  trabalhador_id: f.trabalhador_id, trabalhador_nome: f.trabalhador_nome, liquido: f.salario_liquido,
  pago_em: f.pago_em, rascunho: f.status !== 'fechada', original: f,
});

/** Folhas, férias e 13º num formato só, do pagamento mais recente para o mais antigo. */
export function unificar(folhas, ferias, decimos) {
  return [
    ...folhas.map(registroDeFolha),
    ...ferias.map((g) => ({
      chave: `g${g.id}`, tipo: 'ferias', data: g.data_pagamento, referencia: `${dataBR(g.data_inicio)} a ${dataBR(g.data_fim)}`,
      trabalhador_id: g.trabalhador_id, trabalhador_nome: g.trabalhador_nome, liquido: g.liquido, pago_em: g.pago_em, original: g,
    })),
    ...decimos.map((d) => ({
      chave: `d${d.id}`, tipo: 'decimo', data: d.data_pagamento, referencia: `${d.ano}, ${nomeParcela(d).toLowerCase()}`,
      trabalhador_id: d.trabalhador_id, trabalhador_nome: d.trabalhador_nome, liquido: d.liquido, pago_em: d.pago_em, original: d,
    })),
  ].sort((a, b) => b.data.localeCompare(a.data) || a.trabalhador_nome.localeCompare(b.trabalhador_nome));
}

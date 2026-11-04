import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Alerta, Campo, Grupo, InputValor } from './ui';
import { cpfFmt, cpfMascara, DIAS_SEMANA, hoje, numero, valorCampo } from '../utils';

const VAZIO = {
  nome: '', cpf: '', tipo_contrato: 'com_registro', objeto_contrato_id: '', salario_base: '', data_admissao: hoje(), ativo: true,
  dias_semana_trabalho: '12345', horas_mensais: 200,
  dia_pagamento_salario: 5, salario_dia_util: true,
  adiantamento_acordado: false, dia_pagamento_adiantamento: 20, adiantamento_dia_util: false,
};

/** Dia de pagamento: "5º dia útil" ou "dia 20 do mês". */
function RegraPagamento({ label, dia, util, onDia, onUtil, dica }) {
  return (
    <Grupo label={label} dica={dica}>
      <span className="regra-pagamento">
        <input type="number" min="1" max={util ? 24 : 31} value={dia} onChange={(e) => onDia(e.target.value)} required aria-label={`${label}: dia`} />
        <select value={util ? 'util' : 'corrido'} onChange={(e) => onUtil(e.target.value === 'util')} aria-label={`${label}: tipo de dia`}>
          <option value="util">º dia útil</option>
          <option value="corrido">dia do mês</option>
        </select>
      </span>
    </Grupo>
  );
}

/** Objetos que podem ser escolhidos: os ativos e, em quem já o usa, um objeto que foi desativado depois. */
function useObjetosContrato(atual) {
  const [objetos, setObjetos] = useState([]);
  useEffect(() => {
    api.get('/objetos-contrato')
      .then((lista) => setObjetos(lista.filter((o) => o.ativo || o.id === atual)))
      .catch(() => setObjetos([]));
  }, [atual]);
  return objetos;
}

export default function TrabalhadorForm({ inicial, onSalvar, onCancelar, textoBotao = 'Salvar' }) {
  const [form, setForm] = useState(inicial
    ? {
      ...inicial, cpf: cpfFmt(inicial.cpf), salario_base: valorCampo(inicial.salario_base),
      objeto_contrato_id: inicial.objeto_contrato_id ?? '', dia_pagamento_adiantamento: inicial.dia_pagamento_adiantamento ?? 20,
    }
    : VAZIO);
  const objetos = useObjetosContrato(inicial?.objeto_contrato_id);
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);
  const set = (campo) => (e) =>
    setForm({ ...form, [campo]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  const alternarDia = (dia) => {
    const atual = form.dias_semana_trabalho;
    const novo = atual.includes(dia) ? atual.replace(dia, '') : [...atual, dia].sort().join('');
    setForm({ ...form, dias_semana_trabalho: novo });
  };
  const comRegistro = form.tipo_contrato === 'com_registro';

  // Cadastro novo já vem com o objeto mais comum selecionado
  useEffect(() => {
    if (form.objeto_contrato_id === '' && objetos.length) {
      const padrao = objetos.find((o) => o.descricao === 'Serviços Domésticos') || objetos[0];
      setForm((f) => ({ ...f, objeto_contrato_id: padrao.id }));
    }
  }, [objetos, form.objeto_contrato_id]);

  const enviar = async (e) => {
    e.preventDefault();
    setErro('');
    if (!form.dias_semana_trabalho) {
      setErro('Marque ao menos um dia da semana trabalhado.');
      return;
    }
    setSalvando(true);
    try {
      await onSalvar({
        ...form,
        salario_base: numero(form.salario_base),
        horas_mensais: numero(form.horas_mensais),
        objeto_contrato_id: Number(form.objeto_contrato_id),
        dia_pagamento_salario: Number(form.dia_pagamento_salario),
        dia_pagamento_adiantamento: form.adiantamento_acordado ? Number(form.dia_pagamento_adiantamento) : null,
        funcao: form.funcao?.trim() || null,
      });
    } catch (err) {
      setErro(err.message);
    } finally {
      setSalvando(false);
    }
  };

  return (
    <form onSubmit={enviar}>
      <Alerta erro={erro} />
      <h4 className="primeiro">Identificação</h4>
      <div className="grade-form">
        <Campo label="Nome completo">
          <input value={form.nome} onChange={set('nome')} autoComplete="off" required minLength={2} />
        </Campo>
        <Campo label="CPF">
          <input value={form.cpf} onChange={(e) => setForm({ ...form, cpf: cpfMascara(e.target.value) })}
            inputMode="numeric" autoComplete="off" placeholder="000.000.000-00" required />
        </Campo>
      </div>

      <h4>Contrato</h4>
      <div className="grade-form">
        <Campo label="Tipo de contrato" dica="Com registro: eSocial (INSS/FGTS). Sem registro: o sistema calcula um fundo de reserva.">
          <select value={form.tipo_contrato} onChange={set('tipo_contrato')}>
            <option value="com_registro">Com registro (CLT / eSocial)</option>
            <option value="sem_registro">Sem registro</option>
          </select>
        </Campo>
        <Campo label="Objeto do contrato"
          dica={<>Sai em todos os recibos. Falta algum? Cadastre em <Link to="/objetos-contrato">Objetos do contrato</Link>.</>}>
          <select value={form.objeto_contrato_id} onChange={set('objeto_contrato_id')} required>
            {objetos.length === 0 && <option value="">Carregando…</option>}
            {objetos.map((o) => <option key={o.id} value={o.id}>{o.descricao}</option>)}
          </select>
        </Campo>
        {comRegistro && (
          <Campo label="Função (opcional)" dica="Sai no holerite. Ex.: cuidador(a) de idosos, babá, caseiro(a).">
            <input value={form.funcao || ''} onChange={set('funcao')} placeholder="Empregado(a) doméstico(a)" maxLength={120} />
          </Campo>
        )}
        <Campo label="Salário base mensal (R$)"
          dica={inicial?.reajustes?.length ? 'Há reajustes registrados: altere o salário em Configuração financeira > Reajustes.' : ''}>
          <InputValor value={form.salario_base} onChange={set('salario_base')} required disabled={Boolean(inicial?.reajustes?.length)} />
        </Campo>
        <Campo label={comRegistro ? 'Data de admissão' : 'Data de início'}>
          <input type="date" value={form.data_admissao} onChange={set('data_admissao')} required />
        </Campo>
      </div>

      <h4>Jornada</h4>
      <div className="grade-form">
        <Grupo label="Dias da semana trabalhados" dica="Base dos dias úteis do vale-transporte (feriados nacionais são descontados).">
          <span className="dias-semana">
            {DIAS_SEMANA.map(([dia, rotulo]) => (
              <label key={dia} className="checkbox">
                <input type="checkbox" checked={form.dias_semana_trabalho.includes(dia)} onChange={() => alternarDia(dia)} /> {rotulo}
              </label>
            ))}
          </span>
        </Grupo>
        <Campo label="Divisor de horas do mês" dica="Base do valor-hora das horas extras e atrasos (salário ÷ divisor). Padrão 200 h.">
          <input type="number" min="1" max="220" step="0.5" value={form.horas_mensais} onChange={set('horas_mensais')} required />
        </Campo>
      </div>

      <h4>Datas de pagamento</h4>
      <p className="dica">
        Usadas nos avisos de pagamento. Dia útil conta de segunda a sábado, sem feriados nacionais (o prazo legal do
        salário é o 5º dia útil). Se o dia do mês cair em domingo ou feriado, o aviso considera o dia útil anterior.
      </p>
      <div className="grade-form pagamentos">
        <RegraPagamento
          label="Salário (pagamento integral)"
          dia={form.dia_pagamento_salario} util={form.salario_dia_util}
          onDia={(v) => setForm({ ...form, dia_pagamento_salario: v })}
          onUtil={(v) => setForm({ ...form, salario_dia_util: v })}
        />
        <div>
          <label className="checkbox">
            <input type="checkbox" checked={form.adiantamento_acordado} onChange={set('adiantamento_acordado')} />
            Há adiantamento (vale) acordado
          </label>
          {form.adiantamento_acordado && (
            <RegraPagamento
              label="Adiantamento"
              dia={form.dia_pagamento_adiantamento} util={form.adiantamento_dia_util}
              onDia={(v) => setForm({ ...form, dia_pagamento_adiantamento: v })}
              onUtil={(v) => setForm({ ...form, adiantamento_dia_util: v })}
            />
          )}
        </div>
      </div>

      {inicial && (
        <label className="checkbox espaco-acima">
          <input type="checkbox" checked={form.ativo} onChange={set('ativo')} /> Ativo (desmarque quando o contrato terminar: o histórico é mantido)
        </label>
      )}
      <div className="acoes direita">
        {onCancelar && <button type="button" className="btn" onClick={onCancelar}>Cancelar</button>}
        <button className="btn primario" disabled={salvando}>{salvando ? 'Salvando…' : textoBotao}</button>
      </div>
    </form>
  );
}

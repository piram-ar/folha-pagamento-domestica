import { useState } from 'react';
import { Alerta, Campo } from './ui';
import { cpfFmt, DIAS_SEMANA, hoje } from '../utils';

const VAZIO = {
  nome: '', cpf: '', tipo_contrato: 'com_registro', salario_base: '', data_admissao: hoje(), ativo: true,
  dias_semana_trabalho: '12345',
};

export default function TrabalhadorForm({ inicial, onSalvar, onCancelar, textoBotao = 'Salvar' }) {
  const [form, setForm] = useState(inicial ? { ...inicial, cpf: cpfFmt(inicial.cpf) } : VAZIO);
  const [erro, setErro] = useState('');
  const [salvando, setSalvando] = useState(false);
  const set = (campo) => (e) =>
    setForm({ ...form, [campo]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  const alternarDia = (dia) => {
    const atual = form.dias_semana_trabalho;
    const novo = atual.includes(dia) ? atual.replace(dia, '') : [...atual, dia].sort().join('');
    setForm({ ...form, dias_semana_trabalho: novo });
  };

  const enviar = async (e) => {
    e.preventDefault();
    setErro('');
    if (!form.dias_semana_trabalho) {
      setErro('Marque ao menos um dia da semana trabalhado.');
      return;
    }
    setSalvando(true);
    try {
      await onSalvar({ ...form, salario_base: String(form.salario_base).replace(',', '.') });
    } catch (err) {
      setErro(err.message);
    } finally {
      setSalvando(false);
    }
  };

  return (
    <form onSubmit={enviar}>
      <Alerta erro={erro} />
      <div className="grade-form">
        <Campo label="Nome completo">
          <input value={form.nome} onChange={set('nome')} required />
        </Campo>
        <Campo label="CPF">
          <input value={form.cpf} onChange={set('cpf')} placeholder="000.000.000-00" required />
        </Campo>
        <Campo label="Tipo de contrato" dica="Com registro: eSocial (INSS/FGTS). Sem registro: o sistema calcula um fundo de reserva.">
          <select value={form.tipo_contrato} onChange={set('tipo_contrato')}>
            <option value="com_registro">Com registro (CLT / eSocial)</option>
            <option value="sem_registro">Sem registro</option>
          </select>
        </Campo>
        <Campo label="Salário base mensal (R$)">
          <input type="number" min="0" step="0.01" value={form.salario_base} onChange={set('salario_base')} required />
        </Campo>
        <Campo label={form.tipo_contrato === 'com_registro' ? 'Data de admissão' : 'Data de início'}>
          <input type="date" value={form.data_admissao} onChange={set('data_admissao')} required />
        </Campo>
        <Campo label="Dias da semana trabalhados" dica="Base dos dias úteis do vale-transporte (feriados nacionais são descontados).">
          <span className="dias-semana">
            {DIAS_SEMANA.map(([dia, rotulo]) => (
              <label key={dia} className="checkbox">
                <input type="checkbox" checked={form.dias_semana_trabalho.includes(dia)} onChange={() => alternarDia(dia)} /> {rotulo}
              </label>
            ))}
          </span>
        </Campo>
        <label className="checkbox">
          <input type="checkbox" checked={form.ativo} onChange={set('ativo')} /> Ativo
        </label>
      </div>
      <div className="acoes direita">
        {onCancelar && <button type="button" className="btn" onClick={onCancelar}>Cancelar</button>}
        <button className="btn primario" disabled={salvando}>{salvando ? 'Salvando…' : textoBotao}</button>
      </div>
    </form>
  );
}

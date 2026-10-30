import { useState } from 'react';
import { api } from '../api';
import { brl, mesAtual } from '../utils';
import { Campo } from './ui';

const TIPOS = { percentual: 'Percentual (%)', valor: 'Acréscimo em R$', novo_salario: 'Novo salário (R$)' };
const mesBR = (iso) => `${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
const pct = (v) => `${Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`;

function proximoMes(mesAno) {
  const [a, m] = mesAno.split('-').map(Number);
  return m === 12 ? `${a + 1}-01` : `${a}-${String(m + 1).padStart(2, '0')}`;
}

function novoSalario(anterior, tipo, valor) {
  if (!valor) return null;
  if (tipo === 'percentual') return Math.round(anterior * (1 + valor / 100) * 100) / 100;
  if (tipo === 'valor') return anterior + valor;
  return valor;
}

function descricaoReajuste(r) {
  if (r.tipo === 'percentual') return pct(r.valor_informado);
  if (r.tipo === 'valor') return `+ ${brl(r.valor_informado)}`;
  return 'Novo salário';
}

/** Histórico de aumentos e formulário para registrar um novo (percentual, acréscimo ou novo valor). */
export default function Reajustes({ trabalhador, onAtualizar, setMsg }) {
  const reajustes = trabalhador.reajustes || [];
  const ultimo = reajustes[reajustes.length - 1];
  const minimo = ultimo ? proximoMes(ultimo.vigencia.slice(0, 7)) : trabalhador.data_admissao.slice(0, 7);
  const sugerido = proximoMes(mesAtual()) > minimo ? proximoMes(mesAtual()) : minimo;
  const [form, setForm] = useState({ vigencia: sugerido, tipo: 'percentual', valor: '', motivo: '' });
  const [salvando, setSalvando] = useState(false);

  // Como o reajuste só entra no fim do histórico, a base é o último salário registrado
  const anterior = Number(ultimo ? ultimo.salario_novo : trabalhador.salario_base);
  const valor = Number(String(form.valor).replace(',', '.')) || 0;
  const previsto = novoSalario(anterior, form.tipo, valor);
  const futuro = reajustes.filter((r) => r.vigencia.slice(0, 7) > mesAtual());

  const registrar = async (e) => {
    e.preventDefault();
    setMsg({});
    setSalvando(true);
    try {
      const r = await api.post(`/trabalhadores/${trabalhador.id}/reajustes`, {
        vigencia: form.vigencia, tipo: form.tipo, valor: String(form.valor).replace(',', '.'), motivo: form.motivo || null,
      });
      setMsg({ sucesso: `Reajuste registrado: ${brl(r.salario_anterior)} → ${brl(r.salario_novo)} a partir de ${mesBR(r.vigencia)}.` });
      setForm({ ...form, valor: '', motivo: '' });
      onAtualizar();
    } catch (err) { setMsg({ erro: err.message }); } finally { setSalvando(false); }
  };

  const excluir = async (r) => {
    if (!window.confirm(`Excluir o reajuste de ${mesBR(r.vigencia)}? O salário volta a ${brl(r.salario_anterior)}.`)) return;
    try {
      await api.del(`/trabalhadores/${trabalhador.id}/reajustes/${r.id}`);
      setMsg({ sucesso: 'Reajuste excluído.' });
      onAtualizar();
    } catch (err) { setMsg({ erro: err.message }); }
  };

  return (
    <section className="painel">
      <h3>Reajustes salariais</h3>
      <p className="dica">
        O reajuste vale a partir da competência informada: folhas desse mês em diante usam o novo salário e as
        anteriores continuam com o antigo. Folhas em rascunho passam a usá-lo ao serem recalculadas.
      </p>
      {futuro.length > 0 && (
        <p className="alerta aviso">
          Reajuste agendado: {brl(futuro[0].salario_novo)} a partir de {mesBR(futuro[0].vigencia)}. O salário do cadastro
          muda sozinho quando chegar o mês.
        </p>
      )}

      {reajustes.length > 0 && (
        <div className="tabela-container">
          <table className="tabela-pilha">
            <thead><tr><th>A partir de</th><th>Reajuste</th><th className="num">De</th><th className="num">Para</th><th className="num">Variação</th><th>Motivo</th><th /></tr></thead>
            <tbody>
              {[...reajustes].reverse().map((r) => (
                <tr key={r.id}>
                  <td className="principal">{mesBR(r.vigencia)}</td>
                  <td data-label="Reajuste">{descricaoReajuste(r)}</td>
                  <td className="num" data-label="De">{brl(r.salario_anterior)}</td>
                  <td className="num" data-label="Para"><strong>{brl(r.salario_novo)}</strong></td>
                  <td className="num" data-label="Variação">{pct(((r.salario_novo / r.salario_anterior) - 1) * 100)}</td>
                  <td data-label="Motivo">{r.motivo || '—'}</td>
                  <td className="acoes-linha">
                    {r === ultimo && <button className="btn pequeno perigo" onClick={() => excluir(r)}>Excluir</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4>Registrar reajuste</h4>
      <form onSubmit={registrar}>
        <div className="grade-form">
          <Campo label="Vale a partir de" dica={ultimo ? `Depois de ${mesBR(ultimo.vigencia)} (último reajuste).` : ''}>
            <input type="month" min={minimo} value={form.vigencia} onChange={(e) => setForm({ ...form, vigencia: e.target.value })} required />
          </Campo>
          <Campo label="Tipo de reajuste">
            <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
              {Object.entries(TIPOS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Campo>
          <Campo label={form.tipo === 'percentual' ? 'Percentual (%)' : 'Valor (R$)'}>
            <input type="number" min="0.01" step="0.01" value={form.valor} onChange={(e) => setForm({ ...form, valor: e.target.value })} required />
          </Campo>
          <Campo label="Motivo (opcional)">
            <input value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} placeholder="Ex.: reajuste anual, salário mínimo" maxLength={160} />
          </Campo>
        </div>
        {previsto !== null && (
          <p className="previa">
            {brl(anterior)} → <strong>{brl(previsto)}</strong>
            {previsto > anterior ? ` (+${pct(((previsto / anterior) - 1) * 100)})` : ' (precisa ser maior que o atual)'}
          </p>
        )}
        <div className="acoes direita">
          <button className="btn primario" disabled={salvando || !(previsto > anterior)}>Registrar reajuste</button>
        </div>
      </form>
    </section>
  );
}

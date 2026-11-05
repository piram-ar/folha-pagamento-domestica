import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../AuthContext';
import { useAvisar, useConfirmar } from '../components/feedback';
import { Alerta, Carregando, Badge, Campo, ErroTela, Grupo, InputValor, Modal, SeletorMes } from '../components/ui';
import { brl, numero } from '../utils';

const pct = (v) => `${Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`;
const mesVigencia = (iso) => `${iso.slice(5, 7)}/${iso.slice(0, 4)}`;

/** Rótulo do teto: a faixa começa um centavo acima do teto da anterior, que pode estar pela metade na digitação. */
function rotuloTeto(faixaAnterior) {
  if (!faixaAnterior) return 'Até (R$)';
  const anterior = Number(numero(faixaAnterior.teto));
  return `De ${faixaAnterior.teto && Number.isFinite(anterior) ? brl(anterior + 0.01) : '…'} até (R$)`;
}

/** Mesma conta do backend: cada faixa tributa só a parte do salário dentro dela. */
function calcularInss(salario, faixas) {
  let total = 0;
  let piso = 0;
  const partes = [];
  for (const f of faixas) {
    const teto = Number(f.teto);
    if (salario <= piso) break;
    const base = Math.min(salario, teto) - piso;
    const valor = (base * Number(f.aliquota)) / 100;
    partes.push({ ...f, base, valor });
    total += valor;
    piso = teto;
  }
  return { total: Math.round(total * 100) / 100, partes };
}

function FormTabela({ inicial, onSalvar, onCancelar }) {
  const ano = new Date().getFullYear() + (new Date().getMonth() >= 10 ? 1 : 0);
  const [form, setForm] = useState(() => (inicial
    ? { vigencia: inicial.vigencia_inicio.slice(0, 7), descricao: inicial.descricao || '', faixas: inicial.faixas.map((f) => ({ ...f })) }
    : { vigencia: `${ano}-01`, descricao: `Tabela ${ano}`, faixas: [{ teto: '', aliquota: '7.5' }, { teto: '', aliquota: '9' }, { teto: '', aliquota: '12' }, { teto: '', aliquota: '14' }] }));
  const [erro, setErro] = useState('');

  const setFaixa = (i, campo, valor) => setForm({ ...form, faixas: form.faixas.map((f, j) => (j === i ? { ...f, [campo]: valor } : f)) });

  const enviar = async (e) => {
    e.preventDefault();
    setErro('');
    try {
      await onSalvar({
        vigencia_inicio: `${form.vigencia}-01`,
        descricao: form.descricao || null,
        faixas: form.faixas.map((f) => ({ teto: numero(f.teto), aliquota: numero(f.aliquota) })),
      });
    } catch (err) { setErro(err.message); }
  };

  return (
    <form onSubmit={enviar}>
      <Alerta erro={erro} />
      <div className="grade-form">
        <Grupo label="Vale a partir de" dica="Usada nas folhas a partir deste mês, até a próxima vigência cadastrada.">
          <SeletorMes mes={form.vigencia} onChange={(vigencia) => setForm({ ...form, vigencia })} />
        </Grupo>
        <Campo label="Descrição"><input value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} /></Campo>
      </div>

      <h4>Faixas de contribuição</h4>
      <p className="dica">Informe o teto de cada faixa (salário de contribuição) e a alíquota, da menor para a maior.</p>
      <div className="faixas-edicao">
        {form.faixas.map((f, i) => (
          <div key={i} className="faixa-linha">
            <span className="faixa-num">{i + 1}ª</span>
            <Campo label={rotuloTeto(form.faixas[i - 1])}>
              <InputValor value={f.teto} onChange={(e) => setFaixa(i, 'teto', e.target.value)} required />
            </Campo>
            <Campo label="Alíquota (%)">
              <input type="number" min="0.01" max="100" step="0.01" value={f.aliquota} onChange={(e) => setFaixa(i, 'aliquota', e.target.value)} required />
            </Campo>
            <button type="button" className="btn pequeno perigo" disabled={form.faixas.length === 1}
              onClick={() => setForm({ ...form, faixas: form.faixas.filter((_, j) => j !== i) })}>Remover</button>
          </div>
        ))}
      </div>
      <button type="button" className="btn pequeno" onClick={() => setForm({ ...form, faixas: [...form.faixas, { teto: '', aliquota: '' }] })}>+ Faixa</button>

      <div className="acoes direita">
        <button type="button" className="btn" onClick={onCancelar}>Cancelar</button>
        <button className="btn primario">Salvar tabela</button>
      </div>
    </form>
  );
}

export default function Inss() {
  const { isAdmin } = useAuth();
  const [tabelas, setTabelas] = useState(null);
  const [editando, setEditando] = useState(null); // null | 'nova' | tabela
  const [salario, setSalario] = useState('2000');
  const [erro, setErro] = useState('');
  const setMsg = useAvisar();
  const confirmar = useConfirmar();

  const carregar = useCallback(() => {
    setErro('');
    return api.get('/inss/tabelas').then(setTabelas).catch((e) => setErro(e.message));
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  if (erro) return <ErroTela mensagem={erro} onTentar={carregar} />;
  if (!tabelas) return <Carregando />;

  const vigente = tabelas.find((t) => t.vigente);
  const simulacao = vigente ? calcularInss(Number(numero(salario)) || 0, vigente.faixas) : null;
  const anoAtual = new Date().getFullYear();
  const desatualizada = vigente && Number(vigente.vigencia_inicio.slice(0, 4)) < anoAtual;

  const salvar = async (dados) => {
    if (editando === 'nova') await api.post('/inss/tabelas', dados);
    else await api.put(`/inss/tabelas/${editando.id}`, dados);
    setEditando(null);
    setMsg({ sucesso: 'Tabela salva. Folhas em rascunho passam a usá-la ao serem recalculadas; folhas fechadas não mudam.' });
    carregar();
  };

  const excluir = async (t) => {
    if (!await confirmar({ titulo: `Excluir a tabela de ${mesVigencia(t.vigencia_inicio)}?`, texto: 'Folhas já calculadas não mudam.', acao: 'Excluir tabela', perigo: true })) return;
    try {
      await api.del(`/inss/tabelas/${t.id}`);
      carregar();
    } catch (e) { setMsg({ erro: e.message }); }
  };

  return (
    <>
      <div className="titulo-pagina">
        <div>
          <h2>Tabela do INSS</h2>
          <p className="sub">Desconto do INSS do empregado com registro, calculado faixa a faixa (tabela progressiva).</p>
        </div>
        {isAdmin && <button className="btn primario" onClick={() => setEditando('nova')}>+ Nova vigência</button>}
      </div>
      {desatualizada && (
        <div className="alerta aviso">
          A tabela em uso é de {vigente.vigencia_inicio.slice(0, 4)}. O INSS reajusta as faixas todo ano, normalmente em
          janeiro: cadastre a tabela de {anoAtual} quando ela for publicada.
        </div>
      )}
      {!isAdmin && <p className="dica">Somente administradores podem alterar as tabelas.</p>}

      {vigente && (
        <section className="painel">
          <h3>Simular desconto (tabela em uso)</h3>
          <div className="linha-form">
            <Campo label="Salário bruto (R$)">
              <InputValor value={salario} onChange={(e) => setSalario(e.target.value)} />
            </Campo>
            <p className="simulacao-total">INSS: <strong>{brl(simulacao.total)}</strong></p>
          </div>
          {simulacao.partes.length > 0 && (
            <p className="dica">
              {simulacao.partes.map((p) => `${brl(p.base)} × ${pct(p.aliquota)} = ${brl(p.valor)}`).join('  +  ')}
            </p>
          )}
        </section>
      )}

      {tabelas.length === 0 && <p className="vazio">Nenhuma tabela cadastrada: o sistema usa a tabela padrão de 2025.</p>}
      {tabelas.map((t) => (
        <section key={t.id} className="painel">
          <div className="titulo-pagina compacto">
            <div>
              <h3>{t.descricao || 'Tabela'} {t.vigente && <Badge tipo="verde">Em uso</Badge>}</h3>
              <p className="sub">Vigência a partir de {mesVigencia(t.vigencia_inicio)}</p>
            </div>
            {isAdmin && (
              <div className="acoes">
                <button className="btn pequeno" onClick={() => setEditando(t)}>Editar</button>
                <button className="btn pequeno perigo" onClick={() => excluir(t)}>Excluir</button>
              </div>
            )}
          </div>
          <div className="tabela-container">
            <table>
              <thead><tr><th>Faixa</th><th>Salário de contribuição</th><th className="num">Alíquota</th></tr></thead>
              <tbody>
                {t.faixas.map((f, i) => (
                  <tr key={f.teto}>
                    <td>{i + 1}ª</td>
                    <td>{i === 0 ? `até ${brl(f.teto)}` : `de ${brl(Number(t.faixas[i - 1].teto) + 0.01)} até ${brl(f.teto)}`}</td>
                    <td className="num">{pct(f.aliquota)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {editando && (
        <Modal titulo={editando === 'nova' ? 'Nova tabela do INSS' : 'Editar tabela do INSS'} onClose={() => setEditando(null)} largo>
          <FormTabela inicial={editando === 'nova' ? null : editando} onSalvar={salvar} onCancelar={() => setEditando(null)} />
        </Modal>
      )}
    </>
  );
}

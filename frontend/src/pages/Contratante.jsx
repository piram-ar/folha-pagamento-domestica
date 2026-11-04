import { useEffect, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../AuthContext';
import { useAvisar } from '../components/feedback';
import { Alerta, Carregando, Campo } from '../components/ui';
import { cepMascara, cpfFmt, cpfMascara } from '../utils';

const VAZIO = {
  nome: '', cpf: '', telefone: '', email: '',
  cep: '', logradouro: '', numero: '', complemento: '', bairro: '', cidade: '', uf: '',
};

const UFS = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR',
  'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'];

export default function Contratante() {
  const { isAdmin } = useAuth();
  const [form, setForm] = useState(null);
  const [erro, setErro] = useState('');
  const avisar = useAvisar();
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    // A API devolve null enquanto nada foi cadastrado
    api.get('/contratante')
      .then((c) => {
        if (!c) return setForm(VAZIO);
        const dados = Object.fromEntries(Object.keys(VAZIO).map((k) => [k, c[k] ?? '']));
        setForm({ ...dados, cpf: cpfFmt(dados.cpf), cep: cepMascara(dados.cep) });
      })
      .catch((e) => setErro(e.message));
  }, []);

  if (!form) return erro ? <Alerta erro={erro} /> : <Carregando />;

  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  const salvar = async (e) => {
    e.preventDefault();
    setSalvando(true);
    try {
      await api.put('/contratante', form);
      avisar({ sucesso: 'Dados salvos. Eles serão usados nos próximos recibos.' });
    } catch (err) { avisar({ erro: err.message }); } finally { setSalvando(false); }
  };

  return (
    <>
      <div className="titulo-pagina">
        <h2>Empregador / Contratante</h2>
      </div>
      {!isAdmin && <p className="dica">Somente administradores podem alterar estes dados.</p>}

      <form onSubmit={salvar}>
        <fieldset disabled={!isAdmin} className="sem-borda">
          <section className="painel">
            <h3>Dados do empregador / contratante</h3>
            <p className="dica">
              No recibo, aparece como <strong>Empregador(a)</strong> para trabalhadores com registro (CLT)
              e como <strong>Contratante</strong> para os sem registro.
            </p>
            <div className="grade-form">
              <Campo label="Nome completo"><input value={form.nome} onChange={set('nome')} required /></Campo>
              <Campo label="CPF"><input value={form.cpf} onChange={(e) => setForm({ ...form, cpf: cpfMascara(e.target.value) })} inputMode="numeric" placeholder="000.000.000-00" /></Campo>
              <Campo label="Telefone"><input type="tel" value={form.telefone} onChange={set('telefone')} /></Campo>
              <Campo label="E-mail"><input type="email" value={form.email} onChange={set('email')} /></Campo>
            </div>
          </section>

          <section className="painel">
            <h3>Local da prestação do serviço</h3>
            <div className="grade-form">
              <Campo label="CEP"><input value={form.cep} onChange={(e) => setForm({ ...form, cep: cepMascara(e.target.value) })} inputMode="numeric" placeholder="00000-000" /></Campo>
              <Campo label="Logradouro"><input value={form.logradouro} onChange={set('logradouro')} placeholder="Rua, avenida…" /></Campo>
              <Campo label="Número"><input value={form.numero} onChange={set('numero')} /></Campo>
              <Campo label="Complemento"><input value={form.complemento} onChange={set('complemento')} placeholder="Apto, bloco…" /></Campo>
              <Campo label="Bairro"><input value={form.bairro} onChange={set('bairro')} /></Campo>
              <Campo label="Cidade"><input value={form.cidade} onChange={set('cidade')} /></Campo>
              <Campo label="UF">
                <select value={form.uf} onChange={set('uf')}>
                  <option value="">—</option>
                  {UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}
                </select>
              </Campo>
            </div>
          </section>

          {isAdmin && (
            <div className="acoes direita">
              <button className="btn primario" disabled={salvando}>{salvando ? 'Salvando…' : 'Salvar'}</button>
            </div>
          )}
        </fieldset>
      </form>
    </>
  );
}

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';
import TrabalhadorForm from '../components/TrabalhadorForm';
import { Alerta, Badge, Modal } from '../components/ui';
import { brl, cpfFmt, dataBR, ROTULOS } from '../utils';

export default function Trabalhadores() {
  const navigate = useNavigate();
  const [lista, setLista] = useState([]);
  const [mostrarInativos, setMostrarInativos] = useState(false);
  const [novo, setNovo] = useState(false);
  const [erro, setErro] = useState('');

  const carregar = () =>
    api.get(`/trabalhadores${mostrarInativos ? '' : '?apenas_ativos=true'}`).then(setLista).catch((e) => setErro(e.message));

  useEffect(() => { carregar(); }, [mostrarInativos]); // eslint-disable-line react-hooks/exhaustive-deps

  const criar = async (dados) => {
    const t = await api.post('/trabalhadores', dados);
    setNovo(false);
    navigate(`/trabalhadores/${t.id}?aba=financeiro`);
  };

  return (
    <>
      <div className="titulo-pagina">
        <h2>Trabalhadores</h2>
        <button className="btn primario" onClick={() => setNovo(true)}>Cadastrar trabalhador</button>
      </div>
      <Alerta erro={erro} />
      <label className="checkbox">
        <input type="checkbox" checked={mostrarInativos} onChange={(e) => setMostrarInativos(e.target.checked)} />
        Mostrar inativos
      </label>
      <div className="tabela-container">
        <table className="tabela-pilha">
          <thead>
            <tr><th>Nome</th><th>CPF</th><th>Contrato</th><th className="num">Salário base</th><th>Início</th><th>Situação</th><th /></tr>
          </thead>
          <tbody>
            {lista.length === 0 && (
              <tr><td colSpan={7} className="vazio">
                {mostrarInativos ? 'Nenhum trabalhador cadastrado.' : 'Nenhum trabalhador ativo.'}{' '}
                <button className="btn-link" onClick={() => setNovo(true)}>Cadastrar o primeiro</button>
              </td></tr>
            )}
            {lista.map((t) => (
              <tr key={t.id}>
                <td className="principal"><Link to={`/trabalhadores/${t.id}`}><strong>{t.nome}</strong></Link></td>
                <td data-label="CPF">{cpfFmt(t.cpf)}</td>
                <td data-label="Contrato"><Badge tipo={t.tipo_contrato === 'com_registro' ? 'azul' : 'neutro'}>{ROTULOS.tipo_contrato[t.tipo_contrato]}</Badge></td>
                <td className="num" data-label="Salário base">{brl(t.salario_base)}</td>
                <td data-label="Início">{dataBR(t.data_admissao)}</td>
                <td data-label="Situação">{t.ativo ? <Badge tipo="verde">Ativo</Badge> : <Badge>Inativo</Badge>}</td>
                <td className="acoes-linha"><Link className="btn pequeno" to={`/trabalhadores/${t.id}`}>Abrir cadastro</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {novo && (
        <Modal titulo="Novo trabalhador" onClose={() => setNovo(false)}>
          <TrabalhadorForm onSalvar={criar} onCancelar={() => setNovo(false)} textoBotao="Cadastrar" />
        </Modal>
      )}
    </>
  );
}

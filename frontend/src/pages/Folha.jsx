import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Abas } from '../components/ui';
import { MODO_APP } from '../plataforma';
import { mesAtual } from '../utils';
import DecimoTerceiro from './folha/DecimoTerceiro';
import FolhaDoMes from './folha/FolhaDoMes';
import PagamentosRegistrados from './folha/PagamentosRegistrados';

const ABAS = [
  { id: 'mes', label: 'Folha do mês' },
  { id: 'decimo', label: '13º salário' },
  { id: 'pagamentos', label: 'Pagamentos' },
];

/** Três rotinas, uma aba para cada: a aba e o mês ficam na URL, e cada uma só busca os dados dela. */
export default function Folha() {
  const [params, setParams] = useSearchParams();
  const aba = ABAS.some((a) => a.id === params.get('aba')) ? params.get('aba') : 'mes';
  const mes = params.get('mes') || mesAtual();
  const [semContratante, setSemContratante] = useState(false);

  useEffect(() => {
    api.get('/contratante').then((c) => setSemContratante(!c)).catch(() => {});
  }, []);

  const irPara = (novaAba, novoMes = mes) => setParams({ aba: novaAba, mes: novoMes }, { replace: novaAba === aba });

  return (
    <>
      <h2>Folha de pagamento</h2>
      {semContratante && (
        <div className="alerta aviso">
          Os dados do empregador/contratante e do local do serviço ainda não foram cadastrados e não sairão no recibo.{' '}
          {MODO_APP ? 'Cadastre pelo navegador.' : <Link to="/contratante">Cadastrar agora</Link>}
        </div>
      )}
      <Abas rotulo="Rotinas da folha" abas={ABAS} ativa={aba} onChange={(a) => irPara(a)} />
      <div role="tabpanel">
        {aba === 'mes' && <FolhaDoMes mes={mes} onMes={(m) => irPara('mes', m)} />}
        {aba === 'decimo' && <DecimoTerceiro />}
        {aba === 'pagamentos' && <PagamentosRegistrados onAbrirMes={(m) => irPara('mes', m)} />}
      </div>
    </>
  );
}

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import usuario_atual
from ..models import HistoricoFerias, Trabalhador
from ..services.calculo_folha import ZERO, q
from ..services.resumo import CATEGORIAS, pagamentos_do_ano, provisoes

router = APIRouter(prefix="/resumo", tags=["Resumo"], dependencies=[Depends(usuario_atual)])


@router.get("")
def resumo(ano: int | None = None, db: Session = Depends(get_db)):
    """Pagamentos do ano por trabalhador (folha, benefícios, férias, 13º, encargos) e o saldo das provisões
    que o contratante deve ter guardado para férias, 13º e encargos."""
    ano = ano or date.today().year
    trabalhadores = db.scalars(
        select(Trabalhador)
        .options(selectinload(Trabalhador.folhas), selectinload(Trabalhador.reajustes),
                 selectinload(Trabalhador.decimos_terceiros),
                 selectinload(Trabalhador.historico_ferias).selectinload(HistoricoFerias.gozos))
        .order_by(Trabalhador.nome)
    ).all()

    lista = []
    totais = dict.fromkeys(CATEGORIAS, ZERO)
    reservas = ZERO
    for t in trabalhadores:
        pagamentos = pagamentos_do_ano(t, ano)
        if not t.ativo and not pagamentos["total"]:
            continue
        prov = provisoes(t) if t.ativo else None
        for k, v in pagamentos["valores"].items():
            totais[k] += v
        if prov:
            reservas += prov["saldo_total"]
        lista.append({"trabalhador_id": t.id, "trabalhador_nome": t.nome, "tipo_contrato": t.tipo_contrato,
                      "ativo": t.ativo, **pagamentos, "provisoes": prov})

    return {
        "ano": ano,
        "categorias": CATEGORIAS,
        "trabalhadores": lista,
        "totais": {"valores": totais, "total": q(sum(totais.values(), ZERO)),
                   "em_aberto": q(sum((x["em_aberto"] for x in lista), ZERO)), "reservas": q(reservas)},
    }

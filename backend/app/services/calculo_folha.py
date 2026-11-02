"""Motor de cálculo da folha de pagamento do trabalhador doméstico."""
import json
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    EventoFolha,
    FolhaPagamento,
    NaturezaBeneficio,
    StatusFolha,
    TipoBeneficio,
    TipoContrato,
    TipoEvento,
    Trabalhador,
)
from . import tabelas
from .calendario import dias_em_comum, dias_no_mes
from .calendario import dias_uteis as calcular_dias_uteis
from .esocial import rubrica_beneficio
from .inss import faixas_do_mes, inss_progressivo
from .salario import salario_do_mes

CENTAVO = Decimal("0.01")
ZERO = Decimal("0")

ROTULO_BENEFICIO = {
    TipoBeneficio.vale_transporte: "Vale-transporte",
    TipoBeneficio.vale_mercado: "Vale-mercado",
    TipoBeneficio.vale_refeicao: "Vale-refeição",
    TipoBeneficio.plano_saude: "Plano de saúde",
    TipoBeneficio.outro: "Benefício",
}


def q(valor) -> Decimal:
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _fmt(valor: Decimal) -> str:
    """Número sem zeros à direita, com vírgula decimal (ex.: 1.50 -> '1,5')."""
    texto = f"{Decimal(valor):f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def valor_hora(salario_base: Decimal, horas_mensais: Decimal) -> Decimal:
    """Salário dividido pela jornada mensal do trabalhador (cadastro)."""
    return Decimal(salario_base) / Decimal(horas_mensais)


def valor_hora_extra(salario_base: Decimal, horas_mensais: Decimal, horas: Decimal, percentual: Decimal) -> Decimal:
    fator = 1 + Decimal(percentual) / 100
    return q(valor_hora(salario_base, horas_mensais) * fator * Decimal(horas))


def valor_horas_falta(salario_base: Decimal, horas_mensais: Decimal, horas: Decimal) -> Decimal:
    return q(valor_hora(salario_base, horas_mensais) * Decimal(horas))


def valor_dias(salario_base: Decimal, mes_ano: str, dias: int) -> Decimal:
    """Mês incompleto (admissão, desligamento, afastamento, faltas): proporcional aos dias reais do mês."""
    return q(Decimal(salario_base) / dias_no_mes(mes_ano) * dias)


def beneficio_vigente(beneficio, mes_ano: str) -> bool:
    """O benefício entra a partir da competência em que começou a valer."""
    return beneficio.vigencia_inicio.strftime("%Y-%m") <= mes_ano


def media_horas_extras(trabalhador: Trabalhador, meses: list[str]) -> Decimal:
    """Média mensal das horas extras nas folhas das competências informadas (base de férias e 13º)."""
    if not meses:
        return ZERO
    total = sum((Decimal(f.total_horas_extras) for f in trabalhador.folhas if f.mes_ano in meses), ZERO)
    return q(total / len(meses))


def remuneracao_do_mes(folha: FolhaPagamento) -> Decimal:
    """Remuneração do mês, contando os dias de férias (pagos à parte): base das provisões."""
    return Decimal(folha.salario_bruto) + Decimal(folha.desconto_ferias or 0)


def ferias_no_mes(trabalhador: Trabalhador, mes_ano: str) -> list[tuple]:
    """(gozo, dias do gozo nesta competência) das férias que caem no mês."""
    resultado = []
    for periodo in trabalhador.historico_ferias:
        for gozo in periodo.gozos:
            dias = dias_em_comum(gozo.data_inicio, gozo.data_fim, mes_ano)
            if dias:
                resultado.append((gozo, dias))
    return resultado


def vt_por_dia(beneficio) -> bool:
    """Vale-transporte pago (no salário ou à parte) é cadastrado por dia e multiplicado pelos dias úteis.

    A cota descontada do empregado (natureza "desconto") continua sendo um valor mensal fixo.
    """
    return beneficio.tipo == TipoBeneficio.vale_transporte and beneficio.natureza != NaturezaBeneficio.desconto


def calcular(db: Session, trabalhador: Trabalhador, mes_ano: str, dias_trabalhados: int,
             dias_uteis: int | None = None) -> dict:
    """Calcula os valores da folha do mês. Não faz commit, mas corrige na sessão o valor das horas
    extras e dos atrasos lançados para o divisor de horas e o salário atuais.

    Mensalista: mês completo (todos os dias do mês, seja de 28 ou 31) paga o salário cheio, pelo mês
    comercial; mês incompleto paga proporcional aos dias reais do mês. As horas extras usam o valor-hora
    pelo divisor do cadastro (ex.: 200 h). O vale-transporte segue os dias úteis.
    """
    total_dias = dias_no_mes(mes_ano)
    if dias_trabalhados > total_dias:
        raise ValueError(f"{mes_ano[5:]}/{mes_ano[:4]} tem {total_dias} dias.")
    horas_mensais = Decimal(trabalhador.horas_mensais)
    if dias_uteis is None:
        dias_uteis = calcular_dias_uteis(mes_ano, trabalhador.dias_semana_trabalho)
    salario_base = salario_do_mes(trabalhador, mes_ano)  # considera reajustes vigentes no mês
    completo = dias_trabalhados == total_dias
    salario_proporcional = q(salario_base) if completo else valor_dias(salario_base, mes_ano, dias_trabalhados)

    eventos = db.scalars(
        select(EventoFolha)
        .where(EventoFolha.trabalhador_id == trabalhador.id, EventoFolha.mes_ano == mes_ano)
        .order_by(EventoFolha.data_lancamento)
    ).all()

    itens: list[dict] = []

    def item(codigo, descricao, referencia, tipo, valor, esocial=None, beneficio=None):
        if valor:
            itens.append({
                "codigo": codigo, "descricao": descricao, "referencia": referencia,
                "tipo": tipo, "valor": str(q(valor)), "esocial": esocial, "beneficio": beneficio,
            })

    clt = trabalhador.tipo_contrato == TipoContrato.com_registro
    referencia = "30 dias" if completo else f"{dias_trabalhados}/{total_dias} dias"
    item("001", "Salário" if clt else "Serviços prestados", referencia, "provento", salario_proporcional, "1000")

    # Horas extras agrupadas por percentual
    he_por_pct: dict[Decimal, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    total_bonus = total_faltas = total_vales = total_atrasos = ZERO
    horas_atraso = ZERO
    qtd_vales = 0
    for ev in eventos:
        # Lançamentos em horas valem pela jornada e pelo salário do mês (corrige os feitos antes de um
        # reajuste ou de mudança na jornada)
        if ev.tipo == TipoEvento.hora_extra and ev.quantidade_horas:
            ev.valor = valor_hora_extra(salario_base, horas_mensais, ev.quantidade_horas,
                                        ev.percentual_adicional or 50)
        elif ev.tipo == TipoEvento.falta and ev.quantidade_horas:
            ev.valor = valor_horas_falta(salario_base, horas_mensais, ev.quantidade_horas)
        if ev.tipo == TipoEvento.hora_extra:
            pct = Decimal(ev.percentual_adicional or 50)
            he_por_pct[pct][0] += Decimal(ev.quantidade_horas or 0)
            he_por_pct[pct][1] += Decimal(ev.valor)
        elif ev.tipo == TipoEvento.bonus:
            total_bonus += Decimal(ev.valor)
        elif ev.tipo == TipoEvento.falta and ev.quantidade_horas:  # lançada em horas: atraso
            total_atrasos += Decimal(ev.valor)
            horas_atraso += Decimal(ev.quantidade_horas)
        elif ev.tipo == TipoEvento.falta:
            total_faltas += Decimal(ev.valor)
        elif ev.tipo == TipoEvento.vale_antecipacao:
            total_vales += Decimal(ev.valor)
            qtd_vales += 1

    total_he = ZERO
    for pct in sorted(he_por_pct):
        horas, valor = he_por_pct[pct]
        total_he += valor
        item("002", f"Horas extras {_fmt(pct)}%", f"{_fmt(horas)} h" if horas else "", "provento", valor, "1100")
    item("003", "Bônus / gratificação", "", "provento", total_bonus, "1410")

    total_benef_prov = total_benef_desc = ZERO
    informativos = []
    for b in trabalhador.beneficios:
        if not beneficio_vigente(b, mes_ano):
            continue
        rotulo = b.descricao or ROTULO_BENEFICIO[b.tipo]
        valor, referencia = Decimal(b.valor), ""
        if vt_por_dia(b):
            valor = q(valor * dias_uteis)
            referencia = f"{dias_uteis} d × {q(b.valor)}".replace(".", ",")
        if b.natureza == NaturezaBeneficio.provento:
            total_benef_prov += valor
            item("004", rotulo, referencia, "provento", valor, rubrica_beneficio(b.tipo.value, False), b.tipo.value)
        elif b.natureza == NaturezaBeneficio.desconto:
            total_benef_desc += valor
            item("104", b.descricao or f"Desconto {rotulo.lower()}", "", "desconto", valor,
                 rubrica_beneficio(b.tipo.value, True), b.tipo.value)
        elif valor:
            descricao = f"{rotulo} ({dias_uteis} dias úteis)" if vt_por_dia(b) else rotulo
            informativos.append({"descricao": descricao, "valor": str(q(valor)), "beneficio": b.tipo.value})

    # Dias de férias no mês: já pagos antecipadamente no recibo de férias, saem do salário da folha
    gozos_no_mes = ferias_no_mes(trabalhador, mes_ano)
    dias_ferias = sum(dias for _, dias in gozos_no_mes)
    desconto_ferias = min(q(salario_base / tabelas.DIAS_MES_COMERCIAL * dias_ferias), salario_proporcional)
    item("106", "Férias (pagas no recibo de férias)", f"{dias_ferias} dias", "desconto", desconto_ferias)

    item("101", "Faltas", "", "desconto", total_faltas, "5060")
    item("105", "Atrasos", f"{_fmt(horas_atraso)} h", "desconto", total_atrasos, "5050")
    item("102", "Adiantamento salarial (vales)", f"{qtd_vales} lanç.", "desconto", total_vales, "5098")
    total_faltas += total_atrasos

    # Base de cálculo dos encargos: remuneração (sem benefícios indenizatórios nem os dias de férias)
    salario_bruto = max(q(salario_proporcional + total_he + total_bonus - total_faltas - desconto_ferias), ZERO)

    inss_empregado = ZERO
    tabela_inss = None
    if trabalhador.tipo_contrato == TipoContrato.com_registro:
        # Férias entram na competência dos dias gozados: o INSS do mês é sobre salário + férias, menos o
        # que já foi descontado no recibo de férias (proporcional aos dias deste mês)
        base_ferias = inss_ferias = ZERO
        for gozo, dias in gozos_no_mes:
            if gozo.valor_ferias is not None:
                base_ferias += gozo.bruto * dias / gozo.dias
                inss_ferias += Decimal(gozo.inss) * dias / gozo.dias
        base_ferias, inss_ferias = q(base_ferias), q(inss_ferias)
        faixas, tabela_inss = faixas_do_mes(db, mes_ano)
        inss_total = inss_progressivo(salario_bruto + base_ferias, faixas)
        inss_empregado = max(inss_total - inss_ferias, ZERO)
        item("103", "INSS", f"tabela {tabela_inss}", "desconto", inss_empregado, "5180")
        base = salario_bruto + base_ferias
        sufixo = " (salário + férias)" if base_ferias else ""
        partes = {
            f"INSS do empregado (descontado nos recibos){sufixo}": inss_total,
            f"INSS patronal ({_fmt(tabelas.ALIQ_INSS_PATRONAL * 100)}%)": q(base * tabelas.ALIQ_INSS_PATRONAL),
            f"GILRAT ({_fmt(tabelas.ALIQ_GILRAT * 100)}%)": q(base * tabelas.ALIQ_GILRAT),
            f"FGTS ({_fmt(tabelas.ALIQ_FGTS * 100)}%)": q(base * tabelas.ALIQ_FGTS),
            f"FGTS indenização compensatória ({_fmt(tabelas.ALIQ_FGTS_INDENIZATORIO * 100)}%)":
                q(base * tabelas.ALIQ_FGTS_INDENIZATORIO),
        }
        encargos_empregador = q(sum(partes.values(), ZERO) - inss_total)
        titulo_encargos = "Guia DAE eSocial (estimativa a recolher)"
    else:
        remuneracao = salario_bruto + desconto_ferias  # a reserva continua durante as férias
        provisao_ferias = q(remuneracao / 12)
        partes = {
            "Provisão de férias (1/12)": provisao_ferias,
            "Provisão de 1/3 de férias": q(provisao_ferias / 3),
            "Provisão de 13º salário (1/12)": q(remuneracao / 12),
        }
        encargos_empregador = ZERO
        titulo_encargos = "Fundo de reserva (valor a guardar)"

    encargos = {k: str(v) for k, v in partes.items()}
    total_encargos = q(sum(partes.values(), ZERO))

    total_proventos = q(salario_proporcional + total_he + total_bonus + total_benef_prov)
    total_descontos = q(total_faltas + total_vales + total_benef_desc + inss_empregado + desconto_ferias)
    salario_liquido = q(total_proventos - total_descontos)

    return {
        "horas_mensais": horas_mensais,
        "dias_uteis": dias_uteis,
        "dias_ferias": dias_ferias,
        "desconto_ferias": desconto_ferias,
        "salario_base": q(salario_base),
        "salario_proporcional": salario_proporcional,
        "total_horas_extras": q(total_he),
        "total_bonus": q(total_bonus),
        "total_faltas": q(total_faltas),
        "total_descontos_vales": q(total_vales),
        "total_beneficios": q(total_benef_prov),
        "total_descontos_beneficios": q(total_benef_desc),
        "inss_empregado": inss_empregado,
        "salario_bruto": salario_bruto,
        "total_proventos": total_proventos,
        "total_descontos": total_descontos,
        "encargos_recolher_guardar": total_encargos,
        "salario_liquido": salario_liquido,
        "detalhamento": {
            "itens": itens,
            "beneficios_informativos": informativos,
            "encargos": {"titulo": titulo_encargos, "itens": encargos, "total": str(total_encargos)},
            "encargos_empregador": str(encargos_empregador),
            "valor_hora": str(q(valor_hora(salario_base, horas_mensais))),
            "tabela_inss": tabela_inss,
        },
    }


def gerar_ou_atualizar(db: Session, trabalhador: Trabalhador, mes_ano: str, dias_trabalhados: int,
                       dias_uteis: int | None = None) -> FolhaPagamento:
    folha = db.scalar(
        select(FolhaPagamento).where(
            FolhaPagamento.trabalhador_id == trabalhador.id, FolhaPagamento.mes_ano == mes_ano
        )
    )
    if folha and folha.status == StatusFolha.fechada:
        raise ValueError("A folha deste mês já está fechada. Reabra-a para recalcular.")

    resultado = calcular(db, trabalhador, mes_ano, dias_trabalhados, dias_uteis)
    detalhamento = resultado.pop("detalhamento")
    if folha is None:
        folha = FolhaPagamento(trabalhador_id=trabalhador.id, mes_ano=mes_ano, status=StatusFolha.rascunho)
        db.add(folha)
    folha.dias_trabalhados = dias_trabalhados
    for campo, valor in resultado.items():
        setattr(folha, campo, valor)
    folha.detalhamento = json.dumps(detalhamento, ensure_ascii=False)
    folha.calculado_em = datetime.now()
    db.commit()
    db.refresh(folha)
    return folha

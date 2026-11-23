"""Tela "Conferir ficha" (v4h), parte sem Streamlit: funções puras (sem rede, sem IA, sem escrever arquivo) que usam conferir_ficha_v2, formato_v3
e orcamento_tokens (verificar_execucao). Não avalia se a ficha está CERTA: mede formato, literalidade do trecho e se o valor tem suporte no texto.

Status por campo (da conferir_ficha_v2):
  literal              o trecho existe na página citada
  página errada        o trecho existe, mas em OUTRA página (diz qual)
  em nenhuma página    o trecho não existe em nenhuma página do documento
  reticências          o trecho tem '...' e cada fragmento é literal na página citada (contado à parte)
  não é citação        o trecho é frase do modelo, igual ao valor ou ao item, ou é a justificativa de 'utilidade'
  sem trecho           o trecho veio vazio"""
import csv
import io
import json
import re
from pathlib import Path

import conferir_ficha_v2 as cf
import formato_v3
import orcamento_tokens

AVISO_LITERAL = ("Citação literal só prova que o texto existe na página, não que a ficha está certa; "
                 "atributo, marca, utilidade e compatível são revisão humana.")
STATUS_LITERAL, STATUS_OUTRA, STATUS_AUSENTE = "literal", "página errada", "em nenhuma página"
STATUS_RETICENCIAS, STATUS_NAO_CITACAO, STATUS_VAZIO = "reticências (fragmentos literais)", "não é citação", "sem trecho"
REVISAO_HUMANA = {"atributo do item", "marca ou modelo", "utilidade", "compativel"}


def ler_recorte(pasta):
    """(paginas, item, info) de uma pasta saida\\recortes\\<doc>: paginas.json, 'item pedido' do cabeçalho do recorte.txt e recorte_info.json (ou None)."""
    pasta = Path(pasta)
    paginas = json.loads((pasta / "paginas.json").read_text(encoding="utf-8"))
    cab = ((pasta / "recorte.txt").read_text(encoding="utf-8").splitlines() or [""])[0]
    m = re.search(r"item pedido: (.+?) \|", cab)
    try:
        info = json.loads((pasta / "recorte_info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = None
    return paginas, (m.group(1).strip() if m else ""), info


def _status(r):
    if r["tipo_do_trecho"] == "vazio":
        return STATUS_VAZIO
    if r["tipo_do_trecho"] == "não-citação":
        return STATUS_NAO_CITACAO
    e = r["estado_do_trecho"]
    if e == cf.LITERAL_CITADA:
        return STATUS_LITERAL
    if e == cf.LITERAL_OUTRA:
        return f"{STATUS_OUTRA} (literal na pág. {r['outra_pagina']})"
    if e == cf.RETICENCIAS:
        return STATUS_RETICENCIAS
    return STATUS_AUSENTE


def _inteiro(txt):
    """Campo opcional: '' -> None; '8963' ou '8.963' -> 8963; qualquer outra coisa -> ValueError."""
    t = str(txt if txt is not None else "").strip().replace(".", "").replace(" ", "")
    if not t:
        return None
    if not t.isdigit():
        raise ValueError(f"não é um número inteiro: {txt!r}")
    return int(t)


def conferir_resposta(resposta, paginas, instrucao, item="", prompt_eval_count="", num_ctx=16384):
    """Devolve {'ficha_encontrada', 'linhas', 'resumo', 'formato', 'formato_ok', 'verificacao', 'possivel_corte', 'raciocinio_descartado', 'erro_campos', 'csv'}.
    'resposta' é o texto colado (vale só o que vem depois do último '<channel|>'); 'paginas' é a lista de textos por página (paginas.json)."""
    out = {"ficha_encontrada": False, "linhas": [], "resumo": {}, "formato": {}, "formato_ok": False, "verificacao": "SEM DADO", "possivel_corte": False,
           "raciocinio_descartado": False, "erro_campos": "", "csv": b"", "alertas": []}
    racio, final = cf.separar(resposta)
    out["raciocinio_descartado"] = bool(racio.strip())
    try:
        pec, ctx = _inteiro(prompt_eval_count), _inteiro(num_ctx) or 16384
    except ValueError as e:
        out["erro_campos"] = str(e); pec, ctx = None, 16384
    rows = cf.conferir(final, paginas, item, instrucao)
    fmt = formato_v3.formato(final)
    out["formato"] = fmt; out["formato_ok"] = bool(fmt["formato_ok"]); out["ficha_encontrada"] = bool(rows)
    out["resumo"] = cf.resumo(rows)
    out["alertas"] = cf.alertas_revisar(final, item)   # Pedido 25 (Fase 5): só regras; revisar, não erro
    out["verificacao"] = orcamento_tokens.verificar_execucao(ctx, pec, out["formato_ok"])
    out["possivel_corte"] = out["verificacao"] == "POSSÍVEL CORTE"
    out["num_ctx"], out["prompt_eval_count"] = ctx, pec
    linhas = []
    for r in rows:
        linhas.append({"campo": r["campo"], "valor": r["valor"], "pagina": r["pagina_citada"], "trecho": r["trecho"], "status": _status(r),
                       "valor_com_suporte_no_texto": r["valor_com_suporte"], "revisao_humana": "sim" if r["campo"] in REVISAO_HUMANA else "não",
                       "valor_igual_ao_modelo_da_instrucao": "sim" if r["valor_invalido_instrucao"] else "não"})
    out["linhas"] = linhas
    buf = io.StringIO()
    if linhas:
        w = csv.DictWriter(buf, fieldnames=list(linhas[0]) + ["formato_ok", "verificacao_pos_execucao"], delimiter=";")
        w.writeheader()
        for l in linhas:
            w.writerow({**l, "formato_ok": "sim" if out["formato_ok"] else "não", "verificacao_pos_execucao": out["verificacao"]})
    out["csv"] = buf.getvalue().encode("utf-8-sig")
    return out


def frase_resumo(res):
    """Uma linha com os números da conferência (os mesmos que os relatórios usam): X de Y literais, página errada, em nenhuma página, não-citações."""
    r = res["resumo"]
    if not res["ficha_encontrada"]:
        return "Não achei a tabela da ficha na resposta (menos de 5 dos 9 campos)."
    return (f"{r['literais']} de {r['citacoes']} citações literais · página errada: {r['outra_pagina']} · em nenhuma página: {r['ausentes']} · "
            f"reticências: {r['reticencias']} · não é citação: {r['nao_citacoes']} · valores sem suporte no texto: {len(r['valores_sem_suporte'])} · "
            f"formato_ok: {'sim' if res['formato_ok'] else 'não'}")


def frase_alerta(a):
    """Uma linha para a tela: 'Revisar · campo: detalhe'."""
    return f"Revisar · {a['campo']}: {a['detalhe']}"

"""Guarda de contexto no recorte (v4h): mantém as páginas do recorte NA ORDEM DE INCLUSÃO do seletor (recorte_teste_ia.py, que não foi alterado)
até a estimativa de tokens (instrução incluída) chegar ao limite (fração da janela, padrão 70%); PARA na primeira página que não couber.
Funções puras (sem rede, sem arquivo), exceto ler_recorte_info.

Ordem de inclusão do seletor (reproduzida de recorte_teste_ia.py, linhas 34-46): página 1; as 3 páginas com mais ocorrências do padrão de garantia
(maior contagem primeiro; empate: página maior primeiro); as 3 do padrão de prazo (idem); depois as de maior pontuação (itens x 3 + apoio, só se
a página tem o item; empate: página maior primeiro). O seletor para em MAX_PAG páginas. As duas expressões de garantia e de prazo ficam DENTRO da
função main do seletor, por isso são repetidas aqui (RX_GAR, RX_PRA); a conferência de fidelidade abaixo avisa se um dia divergirem."""
import json
import re
import unicodedata
from pathlib import Path

RX_GAR = re.compile(r"garantia[^.]{0,120}?\d+\s*(\([^)]{0,30}\)\s*)?(meses|anos|mes|ano)\b")      # copiadas de recorte_teste_ia.py (linhas 36-37)
RX_PRA = re.compile(r"prazo\s+(maximo\s+)?(de|para)\s+(a\s+)?entrega|entregues?\s+em\s+ate|prazo\s+de\s+entrega")


def _norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def ordem_de_inclusao(paginas, rx_item, apoio):
    """Lista de números de página (1, 2, ...) na ordem em que o seletor as inclui, continuada além do limite do seletor."""
    rx_i, rx_a = re.compile(rx_item), re.compile(apoio)
    textos = [_norm(p or "") for p in paginas]
    pont = []
    for i, t in enumerate(textos, 1):
        a, b = len(rx_i.findall(t)), len(rx_a.findall(t))
        pont.append((a * 3 + b if a else 0, i))
    seq = [1] if paginas else []
    for rx_c in (RX_GAR, RX_PRA):
        cont = sorted(((len(rx_c.findall(t)), i) for i, t in enumerate(textos, 1)), reverse=True)
        for c, i in cont[:3]:
            if c > 0 and i not in seq:
                seq.append(i)
    for s, i in sorted(pont, reverse=True):
        if s > 0 and i not in seq:
            seq.append(i)
    return seq


def paginas_do_cabecalho(texto_recorte):
    """Páginas da linha 'DOCUMENTO ... | páginas incluídas: 1, 3, 5' do recorte (lista de int). [] se não achar."""
    m = re.search(r"páginas incluídas: ([\d, ]+)", (texto_recorte or "").splitlines()[0] if texto_recorte else "")
    return [int(x) for x in re.findall(r"\d+", m.group(1))] if m else []


def montar_recorte(cabecalho_prefixo, paginas, selecionadas):
    """Mesmo formato do seletor: cabeçalho + '=== PÁGINA N ===' para cada página, em ordem numérica."""
    sel = sorted(selecionadas)
    corpo = [f"{cabecalho_prefixo}{', '.join(map(str, sel))}\n"]
    for i in sel:
        corpo.append(f"\n=== PÁGINA {i} ===\n{(paginas[i - 1] or '').strip()}\n")
    return "".join(corpo)


def aplicar_limite(paginas, recorte_do_seletor, rx_item, apoio, max_pag, instrucao, estimar, ler_fracao=None):
    """Aplica o limite ao recorte que o seletor montou. 'estimar(prompt) -> dict' devolve {'tokens_prompt', 'limite_tokens', 'acima_do_limite', ...}
    (o prompt é instrução + '\\n\\n' + recorte, como na opção 5). Devolve um dict com o recorte final e os números para a tela:
    {'texto', 'relevantes', 'mantidas', 'fora', 'reduzido', 'fidelidade', 'estimativa', 'limite', 'parou_antes_da', 'aviso_fidelidade'}.
    Se a ordem do seletor NÃO puder ser reproduzida, o recorte do seletor fica como está (sem limite) e 'fidelidade' é False: nunca corta em silêncio."""
    relevantes = sorted(paginas_do_cabecalho(recorte_do_seletor))
    prefixo = re.match(r"(.*páginas incluídas: )", recorte_do_seletor.splitlines()[0]).group(1) if relevantes else ""
    seq = ordem_de_inclusao(paginas, rx_item, apoio)
    esperado = sorted(seq[:max_pag])
    base = {"relevantes": relevantes, "n_relevantes": len(relevantes)}
    if not relevantes or esperado != relevantes:
        est = estimar(instrucao.rstrip() + "\n\n" + recorte_do_seletor)
        return {**base, "texto": recorte_do_seletor, "mantidas": relevantes, "fora": [], "reduzido": False, "fidelidade": False, "estimativa": est["tokens_prompt"], "limite": est["limite_tokens"],
                "acima_do_limite": est["acima_do_limite"], "parou_antes_da": None,
                "aviso_fidelidade": "Não foi possível reproduzir a ordem de inclusão do seletor; o recorte do seletor foi mantido SEM o limite de contexto."
                                    + (" A estimativa passa do limite." if est["acima_do_limite"] else "")}
    ordem = seq[:len(relevantes)]
    mantidas, parou = [], None
    for p in ordem:
        est = estimar(instrucao.rstrip() + "\n\n" + montar_recorte(prefixo, paginas, mantidas + [p]))
        if est["acima_do_limite"]:
            parou = p
            break
        mantidas.append(p)
    texto = montar_recorte(prefixo, paginas, mantidas)
    est = estimar(instrucao.rstrip() + "\n\n" + texto)
    fora = sorted(p for p in relevantes if p not in mantidas)
    return {**base, "texto": texto, "mantidas": sorted(mantidas), "fora": fora, "reduzido": bool(fora), "fidelidade": True, "estimativa": est["tokens_prompt"], "limite": est["limite_tokens"],
            "acima_do_limite": est["acima_do_limite"], "parou_antes_da": parou, "aviso_fidelidade": ""}


def _pt(v, casas=0):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def linha_do_recorte(info):
    """'Recorte: X de Y páginas relevantes · estimativa Z tokens (limite 70% = 11.468,8)' (mostrada SEMPRE)."""
    pct = info.get("fracao_janela")
    pct_txt = f"{pct:.0%}" if pct else "70%"
    return (f"Recorte: {len(info['mantidas'])} de {info['n_relevantes']} páginas relevantes · estimativa {_pt(info['estimativa'])} tokens "
            f"(limite {pct_txt} = {_pt(info['limite'], 1)})")


def aviso_do_recorte(info):
    """Aviso 'Recorte reduzido' com as páginas que ficaram de fora; vazio quando nada foi cortado e a fidelidade está ok."""
    partes = []
    if info.get("reduzido"):
        partes.append("Recorte reduzido: ficaram de fora as páginas " + ", ".join(map(str, info["fora"]))
                      + f" (o limite de contexto foi atingido antes da página {info['parou_antes_da']}). Se o campo que você procura estiver nelas, ele sairá como \"não encontrado\".")
    if info.get("aviso_fidelidade"):
        partes.append(info["aviso_fidelidade"])
    return " ".join(partes)


def ler_recorte_info(pasta_recorte):
    """recorte_info.json gravado ao lado do recorte.txt; None se não existir ou estiver ilegível (a tela então não mostra nada, não inventa)."""
    try:
        return json.loads((Path(pasta_recorte) / "recorte_info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

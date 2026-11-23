"""Conferência por código (offline, funções puras) da ficha de 9 campos que a IA devolve.

Não lê arquivo, não usa rede. Quem chama passa: o texto da resposta, as páginas (lista de textos) e, se quiser, o nome do item
e o texto da instrução. Não avalia se o valor está CERTO: mede formato, literalidade do trecho e se o valor tem suporte no texto.

Regras (pedido da Fase 2):
 1. Cada trecho é comparado com a página citada sem acento, sem diferença de caixa e com espaços normalizados.
 2. Estados do trecho (excludentes, nesta ordem): LITERAL_CITADA (literal na página citada) | LITERAL_OUTRA (literal em outra
    página; diz qual) | RETICENCIAS (tem '...' e cada fragmento é literal na página citada; contado à parte) | AUSENTE.
 3. Campos de ESCOLHA (tipo, lei, compatível, utilidade) ficam separados dos de TEXTO e NÚMERO (sem 'valor sem suporte' nos de escolha).
 4. Números (ano, garantia, prazo) comparam-se pelos dígitos ('30 dias' casa com '30 (trinta) dias').
 5. Valor igual ao texto da instrução (ex.: 'copie o trecho') é INVÁLIDO.
 6. Tabela de duas colunas (sem Página nem Trecho) é ficha com os 9 campos sem página.
 7. O trecho do campo 'utilidade' é justificativa: conta como não-citação.
 8. Só vale a parte da resposta depois de '<channel|>' (o Nemotron escreve o raciocínio antes)."""
import re
import unicodedata

CAMPOS = ["tipo de documento", "ano do documento", "lei de base", "atributo do item", "compativel", "garantia", "prazo de entrega", "marca ou modelo", "utilidade"]
ESCOLHA = {"tipo de documento", "lei de base", "compativel", "utilidade"}
NUMERICO = {"ano do documento", "garantia", "prazo de entrega"}
TEXTO = {"atributo do item", "marca ou modelo"}
MIN_CAMPOS_FICHA = 5          # menos de 5 dos 9 campos = a saída não é a ficha (ex.: análise livre com tabelas)

LITERAL_CITADA = "literal na página citada"
LITERAL_OUTRA = "literal em outra página"
RETICENCIAS = "reticências com fragmentos literais"
AUSENTE = "não encontrado em nenhuma página"

_PADRAO_NAO_CITACAO = re.compile(r"^(nao encontrad|nao ha\b|nao consta|nao se\b|o documento (nao|menciona|e |trata)|nao especific|nao informad|nao foi\b|nao existe|sem \w|nao indicad|nao trata|nao menciona|nao apresent|nao cita)")


def sem_acento(s):
    """Sem acento, minúsculas, espaços normalizados (regra 1)."""
    t = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def _sem_parenteses(s):
    return sem_acento(re.sub(r"\([^)]*\)", " ", str(s or "")))


def digitos(valor):
    """Grupos de dígitos do valor: '30 (trinta) dias' -> ['30']."""
    return re.findall(r"\d+", str(valor or ""))


def classe_do_campo(campo):
    return "escolha" if campo in ESCOLHA else ("número" if campo in NUMERICO else "texto")


def separar(texto):
    """Regra 8. Devolve (raciocinio, resposta_final). Sem '<|channel>' o texto todo é resposta. Raciocínio aberto e nunca
    fechado (sem '<channel|>'): resposta final vazia. Vale a parte depois do ÚLTIMO '<channel|>'."""
    texto = texto or ""
    if "<|channel>" not in texto and "<channel|>" not in texto:
        return "", texto
    if "<channel|>" not in texto:
        return texto, ""
    ant, _, depois = texto.rpartition("<channel|>")
    return ant, depois


def linhas_da_ficha(texto):
    """Linhas da tabela: (campo, valor, página, trecho). Só a primeira ocorrência de cada campo. Aceita 2 colunas (página e trecho vazios,
    regra 6). Se menos de MIN_CAMPOS_FICHA campos aparecem, devolve [] (não é a ficha)."""
    achados, saida = set(), []
    for l in (texto or "").splitlines():
        if not l.strip().startswith("|"):
            continue
        cel = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cel) < 2 or set("".join(cel)) <= set("-: "):
            continue
        for k in CAMPOS:
            if k in sem_acento(cel[0]) and k not in achados:
                achados.add(k)
                saida.append((k, cel[1], cel[2] if len(cel) > 2 else "", cel[3] if len(cel) > 3 else ""))
                break
    return saida if len(saida) >= MIN_CAMPOS_FICHA else []


def formato(texto):
    """campos_presentes, formato_ok (9 campos e todo campo com valor tem página numérica), ficha_sem_pagina (regra 6: 9 campos e nenhuma página)."""
    lin = linhas_da_ficha(texto)
    com_valor = [r for r in lin if "nao encontrado" not in sem_acento(r[1])]
    com_pag = [r for r in com_valor if re.search(r"\d", r[2])]
    return {"campos_presentes": len(lin), "formato_ok": len(lin) == 9 and len(com_pag) == len(com_valor),
            "ficha_sem_pagina": len(lin) == 9 and not any(re.search(r"\d", r[2]) for r in lin), "campos_com_valor": len(com_valor), "com_valor_e_pagina_numerica": len(com_pag)}


def valores_da_instrucao(instrucao):
    """Textos que a instrução usa como modelo/opção em campos que NÃO são de escolha (ex.: 'copie o trecho', o texto entre parênteses do
    atributo). Valor igual a um deles é inválido (regra 5). Campos de escolha têm opções válidas e ficam de fora. 'não' e 'não encontrado'
    são respostas legítimas e nunca entram."""
    achados = {}
    for l in (instrucao or "").splitlines():
        if not l.strip().startswith("|"):
            continue
        cel = [c.strip() for c in l.strip().strip("|").split("|")]
        if not cel:
            continue
        nome = sem_acento(cel[0])
        campo = next((k for k in CAMPOS if k in nome), None)
        if campo is None or campo in ESCOLHA:
            continue
        m = re.search(r"\(([^)]*)\)", cel[0])
        if not m:
            continue
        itens = {sem_acento(m.group(1))}
        itens |= {sem_acento(x) for x in m.group(1).split("/")}
        achados.setdefault(campo, set()).update(i for i in itens if len(i) >= 6 and i not in ("nao", "nao encontrado"))
    return achados


def tipo_trecho(campo, valor, trecho, item=""):
    """'vazio' | 'não-citação' (regra 7 para utilidade; frases do modelo; trecho igual ao valor ou ao item) | 'citação'."""
    t = sem_acento(trecho)
    if not t:
        return "vazio"
    if campo == "utilidade":
        return "não-citação"
    if _PADRAO_NAO_CITACAO.match(t) or t == sem_acento(valor) or (item and t == sem_acento(item)):
        return "não-citação"
    return "citação"


def valor_invalido_instrucao(campo, valor, instrucao_vals):
    v = sem_acento(valor)
    return bool(v) and v in instrucao_vals.get(campo, set())


def suporte_valor(campo, valor, paginas_norm):
    """Só campos de TEXTO e NÚMERO: 'sim' / 'não' / 'n.a.'. Números: todos os dígitos do valor aparecem (grupos inteiros) nas páginas."""
    v = sem_acento(valor)
    if campo in ESCOLHA or "nao encontrado" in v or v in ("nao", ""):
        return "n.a."
    todo = " ".join(paginas_norm)
    if campo in NUMERICO:
        nums = digitos(valor)
        if not nums:
            return "não"
        return "sim" if all(re.search(r"(?<!\d)" + re.escape(n) + r"(?!\d)", todo) for n in nums) else "não"
    if v in todo:
        return "sim"
    toks = re.findall(r"[a-z0-9]{3,}", v)
    base = set(re.findall(r"[a-z0-9]{3,}", todo))
    return "sim" if toks and sum(1 for w in toks if w in base) / len(toks) >= 0.8 else "não"


def estado_do_trecho(campo, trecho, citadas, pg, pg_sp):
    """Regra 2. Devolve (estado, outras_paginas). pg/pg_sp: páginas normalizadas (com e sem parênteses)."""
    t = sem_acento(trecho)
    ok = [p for p in citadas if t in pg[p - 1]]
    if not ok and campo in NUMERICO:                       # regra 4: '30 dias' casa com '30 (trinta) dias'
        ts = _sem_parenteses(trecho)
        ok = [p for p in citadas if ts and ts in pg_sp[p - 1]]
    if ok:
        return LITERAL_CITADA, []
    outras = [i + 1 for i, p in enumerate(pg) if t in p and (i + 1) not in citadas]
    if outras:
        return LITERAL_OUTRA, outras
    if "..." in trecho or "…" in trecho:
        fr = [sem_acento(x) for x in re.split(r"\.\.\.|…", trecho) if len(sem_acento(x)) >= 12]
        if fr and all(any(x in pg[p - 1] for p in citadas) for x in fr):
            return RETICENCIAS, []
    return AUSENTE, []


def conferir(texto, paginas, item="", instrucao=""):
    """Confere a ficha contra as páginas. 'texto' deve ser a resposta FINAL (use separar antes). Uma linha de resultado por campo."""
    pg = [sem_acento(p) for p in paginas]
    pg_sp = [_sem_parenteses(p) for p in paginas]
    instr = valores_da_instrucao(instrucao)
    out = []
    for k, valor, pag, trecho in linhas_da_ficha(texto):
        citadas = sorted({int(x) for x in re.findall(r"\d+", pag or "") if 1 <= int(x) <= len(paginas)})
        tipo = tipo_trecho(k, valor, trecho, item)
        estado, outras = ("", [])
        if tipo == "citação":
            estado, outras = estado_do_trecho(k, trecho, citadas, pg, pg_sp)
        out.append({"campo": k, "classe": classe_do_campo(k), "valor": valor, "pagina_citada": pag, "sem_pagina": not re.search(r"\d", pag or ""),
                    "tipo_do_trecho": tipo, "estado_do_trecho": estado, "outra_pagina": ",".join(map(str, outras)),
                    "valor_invalido_instrucao": valor_invalido_instrucao(k, valor, instr), "valor_com_suporte": suporte_valor(k, valor, pg), "trecho": trecho})
    return out


def _contar(linhas):
    cit = [r for r in linhas if r["tipo_do_trecho"] == "citação"]
    c = lambda e: sum(1 for r in cit if r["estado_do_trecho"] == e)
    return {"linhas": len(linhas), "citacoes": len(cit), "literais": c(LITERAL_CITADA), "outra_pagina": c(LITERAL_OUTRA), "reticencias": c(RETICENCIAS), "ausentes": c(AUSENTE),
            "nao_citacoes": sum(1 for r in linhas if r["tipo_do_trecho"] == "não-citação"), "trechos_vazios": sum(1 for r in linhas if r["tipo_do_trecho"] == "vazio"),
            "valores_invalidos_instrucao": [(r["campo"], str(r["valor"])[:60]) for r in linhas if r["valor_invalido_instrucao"]],
            "valores_sem_suporte": [(r["campo"], str(r["valor"])[:60]) for r in linhas if r["valor_com_suporte"] == "não"]}


def resumo(out):
    """Totais e, separados, os de campos de ESCOLHA e os de TEXTO+NÚMERO (regra 3)."""
    r = _contar(out)
    r["escolha"] = _contar([x for x in out if x["classe"] == "escolha"])
    r["texto_numero"] = _contar([x for x in out if x["classe"] != "escolha"])
    return r

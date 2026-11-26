"""Fase 2 – testes OFFLINE de conferir_ficha.py (socket bloqueado). Dados simulados só nos testes unitários (U).
R1 e R2 são as regressões sobre dados reais já gravados em disco (só leitura).
Uso (na pasta do app): python -I -B -X utf8 tests\\test_conferir_ficha.py"""
import csv, re, socket, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ))
sys.dont_write_bytecode = True

def _sem_rede(*a, **k): raise AssertionError("TENTOU ABRIR REDE")
socket.socket.connect = _sem_rede

import conferir_ficha as cf

SOND = next(x for x in (DADOS, DADOS.parent) if (x / "noite_2026-11-18").is_dir())   # ...\sondagem_v5 (v4h: pasta irmã; v4g: dois níveis acima)
N17 = SOND / "noite_2026-11-17" / "fase_e"
N18 = SOND / "noite_2026-11-18"
ITENS = {"5606": "instalação elétrica", "22977": "câmeras de vigilância", "16551": "marcenaria"}
INSTR = (RAIZ / "config" / "INSTRUCAO_FICHA.txt").read_text(encoding="utf-8")
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

def ficha(linhas):
    return "| Campo | Valor | Página | Trecho literal |\n|---|---|---|---|\n" + "\n".join(linhas)

print("=== U. unitários (dados simulados, só aqui) ===")
PG = ["TERMO DE REFERÊNCIA 2026\nGarantia de 12 meses do fabricante.", "Prazo de entrega: 30 (trinta) dias corridos. Marca XPTO modelo Z1000 para uso interno do órgão.", "Texto da página três sobre outro assunto qualquer"]
# regra 1
r = cf.conferir(ficha(["| garantia | 12 meses | 1 | GARANTIA   DE 12 MESES do fabricante |"]*1 + ["| ano do documento | 2026 | 1 | termo de referencia 2026 |", "| tipo de documento | TR | 1 | TERMO DE REFERÊNCIA |", "| lei de base | não encontrado | | |", "| atributo do item | marca XPTO | 2 | marca xpto modelo z1000 |"]), PG)
checa([x["estado_do_trecho"] for x in r] == [cf.LITERAL_CITADA] * 3 + ["", cf.LITERAL_CITADA], "regra 1: sem acento, sem caixa, espaços normalizados -> literal na página citada (4 de 4 com trecho; o 5º é 'não encontrado' sem trecho)")
# regra 2: estados
f2 = ficha(["| tipo de documento | TR | 1 | TERMO DE REFERÊNCIA |", "| ano do documento | 2026 | 1 | Prazo de entrega: 30 (trinta) dias corridos |", "| lei de base | não encontrado | | |",
            "| atributo do item | x | 2 | Marca XPTO ... para uso interno do órgão |", "| compativel | mesmo | 1 | texto que não existe em página nenhuma |", "| garantia | 12 | 3 | garantia de 12 meses do fabricante |"])
r = {x["campo"]: x for x in cf.conferir(f2, PG)}
checa(r["tipo de documento"]["estado_do_trecho"] == cf.LITERAL_CITADA, "estado 1: literal na página citada")
checa(r["ano do documento"]["estado_do_trecho"] == cf.LITERAL_OUTRA and r["ano do documento"]["outra_pagina"] == "2", f"estado 2: literal em OUTRA página e diz qual (2): {r['ano do documento']['outra_pagina']}")
checa(r["atributo do item"]["estado_do_trecho"] == cf.RETICENCIAS, "estado 3: reticências com fragmentos literais (contado à parte)")
checa(r["compativel"]["estado_do_trecho"] == cf.AUSENTE, "estado 4: não encontrado em nenhuma página")
checa(r["garantia"]["estado_do_trecho"] == cf.LITERAL_OUTRA and r["garantia"]["outra_pagina"] == "1", "página citada errada (3) mas o trecho existe na 1")
checa(r["lei de base"]["tipo_do_trecho"] == "vazio" and r["lei de base"]["estado_do_trecho"] == "", "campo 'não encontrado' sem trecho: vazio, sem estado")
rs = cf.resumo(list(r.values()))
checa((rs["literais"], rs["outra_pagina"], rs["reticencias"], rs["ausentes"], rs["citacoes"]) == (1, 2, 1, 1, 5), f"resumo conta cada estado à parte: {(rs['literais'], rs['outra_pagina'], rs['reticencias'], rs['ausentes'], rs['citacoes'])}")
f2b = ficha(["| atributo do item | x | 2 | Marca ZZZZ que não existe aqui ... para uso interno do órgão |", "| tipo de documento | TR | 1 | TERMO |", "| ano do documento | 2026 | 1 | 2026 |", "| lei de base | x | | |", "| compativel | x | | |"])
checa(cf.conferir(f2b, PG)[0]["estado_do_trecho"] == cf.AUSENTE, "reticências com UM fragmento não literal: ausente (não vira reticência)")
# regra 3
rs = cf.resumo(cf.conferir(f2, PG))
checa(rs["escolha"]["linhas"] == 3 and rs["texto_numero"]["linhas"] == 3 and rs["escolha"]["linhas"] + rs["texto_numero"]["linhas"] == rs["linhas"], f"regra 3: escolha {rs['escolha']['linhas']} + texto/número {rs['texto_numero']['linhas']} = {rs['linhas']}")
rr = cf.conferir(ficha(["| tipo de documento | Edital | | |", "| ano do documento | 2026 | | |", "| lei de base | 14.133 | | |", "| compativel | próximo | | |", "| utilidade | média | | |"]), PG)
checa(all(x["valor_com_suporte"] == "n.a." for x in rr if x["classe"] == "escolha"), "regra 3: campo de escolha nunca tem 'valor sem suporte' (valor 'próximo', 'média' não estão no texto)")
# regra 4
rr = {x["campo"]: x for x in cf.conferir(ficha(["| prazo de entrega | 30 dias | 2 | Prazo de entrega: 30 dias corridos |", "| garantia | 12 meses | 1 | Garantia de 12 meses |", "| ano do documento | 2027 | 1 | 2027 |", "| tipo de documento | TR | 1 | TERMO |", "| lei de base | x | | |"]), PG)}
checa(rr["prazo de entrega"]["estado_do_trecho"] == cf.LITERAL_CITADA, "regra 4: trecho '30 dias' casa com '30 (trinta) dias' na página (pelos dígitos)")
checa(rr["prazo de entrega"]["valor_com_suporte"] == "sim" and rr["garantia"]["valor_com_suporte"] == "sim", "regra 4: valor '30 dias' e '12 meses' têm suporte pelos dígitos")
checa(rr["ano do documento"]["valor_com_suporte"] == "não", "regra 4: ano 2027 (dígitos ausentes do texto) -> sem suporte")
checa(cf.digitos("30 (trinta) dias") == ["30"] and cf.digitos("sem número") == [], "digitos('30 (trinta) dias') = ['30']")
checa(cf.suporte_valor("prazo de entrega", "130 dias", ["prazo de 30 dias"]) == "não", "dígitos por grupo inteiro: '130' não casa com '30'")
# regra 5
iv = cf.valores_da_instrucao(INSTR)
checa("copie o trecho" in iv.get("marca ou modelo", set()) and "nao" not in iv.get("marca ou modelo", set()), f"regra 5: a instrução fornece 'copie o trecho' (e não 'não') para marca ou modelo: {sorted(iv.get('marca ou modelo', []))}")
checa(not any(c in iv for c in cf.ESCOLHA), "regra 5: campos de escolha não têm valor 'modelo' inválido (as opções deles são válidas)")
rr = {x["campo"]: x for x in cf.conferir(ficha(["| marca ou modelo | copie o trecho | 2 | Marca XPTO |", "| garantia | não encontrado | | |", "| tipo de documento | TR | 1 | TERMO |", "| ano do documento | 2026 | 1 | 2026 |", "| lei de base | x | | |"]), PG, instrucao=INSTR)}
checa(rr["marca ou modelo"]["valor_invalido_instrucao"] is True, "regra 5: valor 'copie o trecho' é INVÁLIDO")
rr = {x["campo"]: x for x in cf.conferir(ficha(["| marca ou modelo | não | | |", "| garantia | não encontrado | | |", "| tipo de documento | edital com TR | 1 | TERMO |", "| ano do documento | 2026 | 1 | 2026 |", "| lei de base | x | | |"]), PG, instrucao=INSTR)}
checa(not rr["marca ou modelo"]["valor_invalido_instrucao"] and not rr["garantia"]["valor_invalido_instrucao"] and not rr["tipo de documento"]["valor_invalido_instrucao"], "regra 5: 'não', 'não encontrado' e opção de campo de escolha são válidos")
# regra 6
f6 = "| Campo | Valor |\n|---|---|\n" + "\n".join(f"| {c} | v |" for c in ["tipo de documento", "ano do documento", "lei de base", "atributo do item", "compatível com o item", "garantia do produto", "prazo de entrega", "marca ou modelo", "utilidade como modelo"])
checa(len(cf.linhas_da_ficha(f6)) == 9 and cf.formato(f6)["ficha_sem_pagina"] and not cf.formato(f6)["formato_ok"], "regra 6: tabela de 2 colunas = ficha de 9 campos sem página (formato_ok falso)")
checa(all(x["sem_pagina"] and x["tipo_do_trecho"] == "vazio" for x in cf.conferir(f6, PG)), "regra 6: as 9 linhas saem 'sem página' e sem trecho")
checa(cf.linhas_da_ficha("| Campo | Valor |\n|--|--|\n| garantia | 12 |\n| prazo | 3 |") == [], "menos de 5 campos: não é ficha")
# regra 7
rr = {x["campo"]: x for x in cf.conferir(ficha(["| utilidade | alta | 1 | TERMO DE REFERÊNCIA 2026 |", "| tipo de documento | TR | 1 | TERMO |", "| ano do documento | 2026 | 1 | 2026 |", "| lei de base | x | | |", "| compativel | x | | |"]), PG)}
checa(rr["utilidade"]["tipo_do_trecho"] == "não-citação" and rr["utilidade"]["estado_do_trecho"] == "", "regra 7: trecho de 'utilidade' é não-citação mesmo se existir no texto")
rr = {x["campo"]: x for x in cf.conferir(ficha(["| atributo do item | x | 1 | O documento não menciona o item pedido |", "| marca ou modelo | XPTO | 2 | XPTO |", "| tipo de documento | TR | 1 | TERMO |", "| ano do documento | 2026 | 1 | 2026 |", "| lei de base | x | | |"]), PG)}
checa(rr["atributo do item"]["tipo_do_trecho"] == "não-citação" and rr["marca ou modelo"]["tipo_do_trecho"] == "não-citação", "frase do modelo e trecho igual ao valor: não-citação")
# regra 8
checa(cf.separar("raciocínio qualquer<channel|>resposta") == ("raciocínio qualquer", "resposta"), "regra 8: vale só o que vem depois de '<channel|>'")
checa(cf.separar("a<|channel>thought x<channel|>b<channel|>final")[1] == "final", "regra 8: vale a parte depois do ÚLTIMO '<channel|>'")
checa(cf.separar("<|channel>thought nunca fecha")[1] == "" and cf.separar("sem marcador")[1] == "sem marcador", "regra 8: raciocínio aberto -> resposta vazia; sem marcador -> tudo é resposta")
tabela_no_raciocinio = ficha(["| garantia | 99 | 1 | x |"] * 1 + ["| tipo de documento | TR | 1 | TERMO |", "| ano do documento | 2026 | 1 | 2026 |", "| lei de base | x | | |", "| compativel | x | | |"])
checa(cf.linhas_da_ficha(cf.separar("<|channel>thought " + tabela_no_raciocinio)[1]) == [], "regra 8: tabela dentro do raciocínio não vira ficha")

def carregar_saidas(pasta, filtro=lambda p: True):
    return [p for p in sorted(pasta.glob("*.txt")) if not p.name.endswith(".thinking.txt") and filtro(p)]
def paginas(cod): return __import__("json").loads((N17 / "recortes" / f"TR_{cod}" / "paginas.json").read_text(encoding="utf-8"))
def rodar(p):
    cod = re.search(r"TR(\d+)", p.stem).group(1)
    _, final = cf.separar(p.read_text(encoding="utf-8"))
    return cf.conferir(final, paginas(cod), ITENS[cod], INSTR)

print("\n=== R1. regressão Parte 1: conferencia_literais.csv (qwen, noite 17/11) referência 18 literais / 2 página errada / 15 não-citações (era 21/2/12; ver nota abaixo) ===")
q = carregar_saidas(N17 / "saidas")
old = list(csv.DictReader((N18 / "conferencia_literais.csv").open(encoding="utf-8-sig"), delimiter=";"))
novas = {p.stem: rodar(p) for p in q}
linhas_novas = [(s, x) for s, o in novas.items() for x in o]
tot = cf.resumo([x for _, x in linhas_novas])
print(f"saídas lidas: {len(q)}; linhas de ficha: novo {tot['linhas']} | antigo {len(old)}")
print(f"NOVO : literais {tot['literais']} | em outra página {tot['outra_pagina']} | reticências {tot['reticencias']} | ausentes (citação em nenhuma página) {tot['ausentes']} | não-citações {tot['nao_citacoes']} | vazios {tot['trechos_vazios']}")
ant = {"sim": sum(1 for o in old if o["literal_na_pagina_citada"] == "sim"), "outra": sum(1 for o in old if o["existe_em_outra_pagina"]), "nenhuma": sum(1 for o in old if o["existe_em_nenhuma_pagina"] == "sim"), "sem": sum(1 for o in old if o["literal_na_pagina_citada"] == "sem trecho")}
print(f"ANTIGO (Parte 1): literais {ant['sim']} | outra página {ant['outra']} | em nenhuma {ant['nenhuma']} | sem trecho {ant['sem']}")
# comparação linha a linha: (saída, campo) antigo x novo
dif = []
for o in old:
    chave = o["saida"]; nv = next((x for x in novas.get(chave, []) if x["campo"] == o["campo"]), None)
    if nv is None: dif.append((chave, o["campo"], "linha ausente no novo", "")); continue
    a = "literal" if o["literal_na_pagina_citada"] == "sim" else ("sem trecho" if o["literal_na_pagina_citada"] == "sem trecho" else ("outra pág. " + o["existe_em_outra_pagina"] if o["existe_em_outra_pagina"] else "nenhuma"))
    n = {cf.LITERAL_CITADA: "literal", cf.LITERAL_OUTRA: "outra pág. " + nv["outra_pagina"]}.get(nv["estado_do_trecho"], None)
    if n is None: n = "sem trecho" if nv["tipo_do_trecho"] == "vazio" else ("não-citação" if nv["tipo_do_trecho"] == "não-citação" else ("reticências" if nv["estado_do_trecho"] == cf.RETICENCIAS else "nenhuma"))
    print(f"  {chave.replace('qwen3_4b_instruct_', ''):20} {o['campo']:20} antigo={a:14} novo={n}")
    if (a, n) not in (("literal", "literal"), ("sem trecho", "sem trecho"), ("nenhuma", "não-citação")) and a != n: dif.append((chave, o["campo"], a, n))
# NOTA (decisão do desenvolvedor, Fase 3): o pedido original se CONTRADIZIA. A regra 7 manda contar o trecho de 'utilidade' como não-citação, mas a
# contagem antiga da Parte 1 (21 literais / 2 página errada / 12 em nenhuma) contava esse trecho como literal quando existia no texto. Por isso o valor
# de referência passou a 18 literais / 2 página errada / 15 não-citações, com EXATAMENTE as 3 exceções declaradas abaixo em relação a 21/2/12.
EXCECOES_DECLARADAS = {("qwen3_4b_instruct_TR16551_ctx16384", "utilidade"), ("qwen3_4b_instruct_TR22977_ctx16384", "marca ou modelo"), ("qwen3_4b_instruct_TR22977_ctx8192", "marca ou modelo")}
checa((tot["literais"], tot["outra_pagina"], tot["nao_citacoes"]) == (18, 2, 15), f"R1: referência 18 literais / 2 página errada / 15 não-citações -> obtido {(tot['literais'], tot['outra_pagina'], tot['nao_citacoes'])}")
checa({(d[0], d[1]) for d in dif} == EXCECOES_DECLARADAS and all(d[2] == "literal" and d[3] == "não-citação" for d in dif), f"R1: as diferenças linha a linha contra a Parte 1 são SOMENTE as 3 exceções declaradas (utilidade TR16551 ctx16384; marca ou modelo com trecho 'não' = valor 'não' em TR22977 ctx16384 e ctx8192), todas literal -> não-citação; encontradas {len(dif)}: {sorted((d[0][-20:], d[1]) for d in dif)}")
checa(tot["literais"] + len(EXCECOES_DECLARADAS) == 21 and tot["nao_citacoes"] - len(EXCECOES_DECLARADAS) == 12, "R1: com as 3 exceções devolvidas, volta a 21 literais e 12 não-citações (a conta fecha)")
# '10 vazios' (novo) x '8 sem trecho' (antigo): as linhas a mais
chaves_old = {(o["saida"], o["campo"]) for o in old}
extras = [(s, x) for s, x in linhas_novas if (s, x["campo"]) not in chaves_old]
print(f"linhas a mais no novo (45 contra 43): {len(extras)}")
for s, x in extras:
    print(f"  EXTRA {s} | campo={x['campo']} | valor={x['valor']!r} | célula 3 (Página)={x['pagina_citada']!r} | célula 4 (Trecho)={x['trecho']!r} | tipo_do_trecho={x['tipo_do_trecho']}")
checa(len(extras) == 2 and {(s.replace("qwen3_4b_instruct_", ""), x["campo"]) for s, x in extras} == {("TR5606_ctx16384", "utilidade"), ("TR5606_ctx8192", "utilidade")} and all(x["tipo_do_trecho"] == "vazio" for _, x in extras), "vazios: as 2 linhas a mais são a linha 'utilidade' de TR5606 (ctx16384 e ctx8192), e entram como 'vazio': 8 antigos 'sem trecho' + 2 = 10")
for nome in ("TR5606_ctx16384", "TR5606_ctx8192"):
    _, fin = cf.separar((N17 / "saidas" / f"qwen3_4b_instruct_{nome}.txt").read_text(encoding="utf-8"))
    ult = [l for l in fin.splitlines() if l.strip().startswith("|")][-1]
    ncel = len(ult.strip().strip("|").split("|"))
    print(f"  linha bruta da tabela, {nome}: {ult[:160]} ... | células = {ncel}")
    checa(ncel == 3 and ult.lower().lstrip("| ").startswith("utilidade"), f"{nome}: a última linha da tabela (utilidade) tem 3 células, não 4; o script antigo exigia >= 4 células (conf_literais.py linha 20: 'len(cel) < 4') e a descartava; o novo aceita >= 2")
checa(sum(1 for _, x in linhas_novas if x["tipo_do_trecho"] == "vazio") == 8 + 2 == tot["trechos_vazios"], f"vazios: novo {tot['trechos_vazios']} = 8 antigos + 2 linhas a mais")

print("\n=== R2. regressão Parte 2: comparacao_lado_a_lado.csv deve dar Nemotron 51 de 59, qwen 18 de 20, 5 com reticências e 3 de fato ausentes ===")
nem = carregar_saidas(N18 / "fase_f" / "saidas")
res = {("qwen", p.stem): rodar(p) for p in q}; res.update({("nemotron", p.stem): rodar(p) for p in nem})
comp = list(csv.DictReader((N18 / "fase_f" / "comparacao_lado_a_lado.csv").open(encoding="utf-8-sig"), delimiter=";"))
checa(len(comp) == len(res) == 20, f"R2: 20 saídas (6 qwen + 14 nemotron) nos dois lados: CSV {len(comp)}, novo {len(res)}")
print(f"{'modelo':9} {'saída':46} {'cit':>3} {'lit':>3} {'outra':>5} {'retic':>5} {'ausen':>5} {'n-cit':>5} | csv: cit lit errada retic nenhuma n-cit")
difs2 = []
for c in comp:
    s = cf.resumo(res[(c["modelo"], c["saida"])]); a = {k: int(c[k]) for k in ("citacoes", "literais", "pagina_errada", "reticencias_fragmentos_literais", "citacao_em_nenhuma_pagina", "nao_citacoes")}
    n = {"citacoes": s["citacoes"], "literais": s["literais"], "pagina_errada": s["outra_pagina"], "reticencias_fragmentos_literais": s["reticencias"], "citacao_em_nenhuma_pagina": s["ausentes"] + s["reticencias"], "nao_citacoes": s["nao_citacoes"]}
    print(f"{c['modelo']:9} {c['saida']:46} {s['citacoes']:>3} {s['literais']:>3} {s['outra_pagina']:>5} {s['reticencias']:>5} {s['ausentes']:>5} {s['nao_citacoes']:>5} | {a['citacoes']:>9} {a['literais']:>3} {a['pagina_errada']:>6} {a['reticencias_fragmentos_literais']:>5} {a['citacao_em_nenhuma_pagina']:>8} {a['nao_citacoes']:>5}")
    if a != n: difs2.append((c["saida"], {k: (a[k], n[k]) for k in a if a[k] != n[k]}))
def soma(modelo, campo): return sum(cf.resumo(v)[campo] for (m, _), v in res.items() if m == modelo)
nq, nn = (soma("qwen", "citacoes"), soma("qwen", "literais")), (soma("nemotron", "citacoes"), soma("nemotron", "literais"))
checa(nn == (59, 51) and nq == (20, 18), f"R2: Nemotron {nn[1]} de {nn[0]} (esperado 51 de 59); qwen {nq[1]} de {nq[0]} (esperado 18 de 20)")
checa(soma("nemotron", "reticencias") == 5 and soma("nemotron", "ausentes") == 3, f"R2: Nemotron com reticências {soma('nemotron', 'reticencias')} (esperado 5) e de fato ausentes {soma('nemotron', 'ausentes')} (esperado 3)")
checa(soma("qwen", "reticencias") == 0 and soma("qwen", "ausentes") == 0 and soma("qwen", "outra_pagina") == 2, f"R2: qwen com reticências {soma('qwen', 'reticencias')}, ausentes {soma('qwen', 'ausentes')}, página errada {soma('qwen', 'outra_pagina')} (esperado 0, 0, 2)")
checa(not difs2, f"R2: coluna a coluna, saída a saída, igual ao CSV da Parte 2: {len(difs2)} diferença(s) {difs2}")
inval = [(k[1], x["campo"], x["valor"]) for k, v in res.items() for x in v if x["valor_invalido_instrucao"]]
print(f"valores iguais ao texto da instrução (regra 5) nas 20 saídas reais: {len(inval)}: {inval}")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

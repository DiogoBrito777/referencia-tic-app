"""v4h, Pedido 13J, PARTE 1 – texto padrão do "Item pedido" (SEM rede, socket bloqueado). Dados REAIS: pedido12b\\servicos_precos_todas.csv (3.693 linhas, só código, descrição do item, sem órgão
nem fornecedor). Prova: (1.1) as medições do texto padrão atual; (1.2/1.3) a tabela das variantes (experimento em pedido13j\\experimento_1_2.py, resultado em experimento_1_2.json) e a DECISÃO:
o padrão NÃO mudou (nenhuma variante cumpriu o critério em todas as linhas reais), então o comportamento tem que ser IDÊNTICO ao do 13I (comparado com o servicos.py de backups); (1.4) a regra vale
para outro software real do CSV sem mudar código (XDR, Azure, antivírus); nenhum produto escrito na lógica; (1.5) o campo continua editável e a legenda 'O app procura no documento: …' aparece.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13j_item_pedido.py   (na pasta do app)"""
import csv, datetime as dt, importlib.util, inspect, json, re, socket, statistics, sys, time, unicodedata
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
_o = socket.socket.connect
LOOP = []
def _b(self, a, *x, **k):
    h, p = (a[0], a[1]) if isinstance(a, tuple) else (str(a), None)
    if h in ("127.0.0.1", "::1") and p != 11434:
        LOOP.append((h, p)); return _o(self, a, *x, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
from streamlit.testing.v1 import AppTest
import ferramenta as f
import servicos as sv
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
norm = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
rows = list(csv.DictReader((DADOS / "pedido12b" / "servicos_precos_todas.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
nomes = {r["codigoServico"]: r["nomeServico"] for r in sv.ler_catalogo()}
palavras = lambda t: re.findall(r"[a-zà-ÿ0-9]+", t.lower())
padrao = lambda r: sv.item_pedido_inicial(r["descricao"], [nomes.get(r["codigo"], "")])
RES = {}

print("=== 1.1 medição do texto padrão ATUAL nas linhas reais ===")
g27 = [r for r in rows if r["codigo"] == "27499"]; gw = [r for r in rows if re.search(r"windows ?11 ?pro", norm(r["descricao"]))]; gx = [r for r in rows if "xdr" in norm(r["descricao"])]
checa(len(rows) == 3693 and len(g27) == 96 and len(gw) == 21 and len(gx) == 2, f"linhas do CSV: {len(rows)} no total, {len(g27)} do código 27499, {len(gw)} citam 'windows 11 pro', {len(gx)} citam 'xdr'")
def estat(rs):
    t = [padrao(r) for r in rs]; n = [len(palavras(x)) for x in t]
    return {"linhas": len(rs), "min": min(n), "mediana": statistics.median(n), "max": max(n), "vazias": sum(1 for x in t if not x.strip()), "textos": t}
e27, ew, ex = estat(g27), estat(gw), estat(gx)
for nome, e in (("27499", e27), ("windows 11 pro", ew), ("xdr", ex)):
    print(f"   {nome:16s}: {e['linhas']:3d} linhas | palavras mín/med/máx {e['min']}/{e['mediana']}/{e['max']} | vazias {e['vazias']}")
checa((e27["min"], e27["max"], e27["vazias"]) == (0, 12, 54) and (ew["min"], ew["mediana"], ew["max"], ew["vazias"]) == (4, 12, 12, 0) and (ex["min"], ex["max"], ex["vazias"]) == (12, 12, 0),
      "números medidos: 27499 = 0 a 12 palavras com 54 de 96 vazias (a descrição só repete o nome do serviço); 'windows 11 pro' = 4 a 12 (mediana 12), 0 vazias; 'xdr' = 12 e 12, 0 vazias")
w_com_office = sum(1 for t in ew["textos"] if re.search(r"office|ltsc", norm(t)))
of = [r for r in rows if re.search(r"office ?ltsc", norm(r["descricao"]))]; of_com_win = sum(1 for r in of if "windows" in norm(padrao(r)))
checa((w_com_office, len(of), of_com_win) == (1, 10, 1), f"palavra de OUTRO item: {w_com_office} de {len(gw)} textos do Windows citam office/ltsc; {of_com_win} de {len(of)} textos do Office citam windows")
RES["medicao_1_1"] = {"27499": {k: e27[k] for k in ("linhas", "min", "mediana", "max", "vazias")}, "windows_11_pro": {k: ew[k] for k in ("linhas", "min", "mediana", "max", "vazias")}, "xdr": {k: ex[k] for k in ("linhas", "min", "mediana", "max", "vazias")},
                      "windows_com_office": w_com_office, "office_linhas": len(of), "office_com_windows": of_com_win}

print("\n=== 1.2/1.3 tabela das variantes (experimento_1_2.json) e a decisão ===")
exp = json.loads((DADOS / "pedido13j" / "experimento_1_2.json").read_text(encoding="utf-8"))
tab = {v["variante"]: v for v in exp["variantes"]}
for nome, v in tab.items():
    print(f"   {nome:28s} cumpre={v['cumpre']} | " + " | ".join(f"{c['item'][0]}{c['linha']}: fora {c['paginas_do_item_fora'] or '-'}, {c['tokens']} tok" for c in v["casos"]))
checa(len(tab) >= 8 and {"A (como está)", "A6 (como está, 6 palavras)"} <= set(tab) and any(k.startswith("B ") for k in tab) and any(k.startswith("C ") for k in tab), f"variantes testadas: {list(tab)}")
checa(not any(v["cumpre"] for v in tab.values()), "NENHUMA variante cumpre o critério (nenhuma página do item fora, 1ªs linhas diferentes, tokens <= 70%) em TODAS as linhas reais: por isso nada foi adotado")
par13i = lambda v: [c for c in v["casos"] if c["linha"] in (97, 98)]
checa(any(c["paginas_do_item_fora"] for c in par13i(tab["A (como está)"])), f"o problema do 13I se repete com a regra atual (par 13I: {[(c['item'], c['linha'], c['paginas_do_item_fora']) for c in par13i(tab['A (como está)'])]})")
checa(all(not c["paginas_do_item_fora"] for c in par13i(tab["A6 (como está, 6 palavras)"])) and any(c["paginas_do_item_fora"] for c in tab["A6 (como está, 6 palavras)"]["casos"] if c["linha"] not in (97, 98)), "só no par do 13I, 6 palavras resolveria; outras linhas reais do Windows continuam com a pág. 9 fora (não é regra geral)")
RES["variantes"] = {k: {"cumpre": v["cumpre"], "casos": [{x: c[x] for x in ("item", "linha", "palavras", "mantidas", "fora", "tokens", "paginas_do_item_fora")} for c in v["casos"]]} for k, v in tab.items()}

print("\n=== decisão: o comportamento padrão é IDÊNTICO ao do 13I ===")
import importlib.machinery
spec = importlib.util.spec_from_loader("servicos_13i", importlib.machinery.SourceFileLoader("servicos_13i", str(DADOS / "backups" / "servicos.py__antes_pedido13j")))
antigo = importlib.util.module_from_spec(spec); spec.loader.exec_module(antigo)
checa(sv.ITEM_FREQ_MAX is None and sv.ITEM_MAX_PALAVRAS == 12, f"padrões do código: ITEM_FREQ_MAX={sv.ITEM_FREQ_MAX}, ITEM_MAX_PALAVRAS={sv.ITEM_MAX_PALAVRAS}")
dif = [r for r in rows if antigo.item_pedido_inicial(r["descricao"], [nomes.get(r["codigo"], "")]) != sv.item_pedido_inicial(r["descricao"], [nomes.get(r["codigo"], "")])]
ctx = [r["descricao"] for r in g27]
dif2 = [r for r in g27 if antigo.item_pedido_inicial(r["descricao"], [nomes["27499"]]) != sv.item_pedido_inicial(r["descricao"], [nomes["27499"]], contexto=ctx)]
dif3 = [r for r in rows if antigo.item_para_recorte(padrao(r), ["Notebook"]) != sv.item_para_recorte(padrao(r), ["Notebook"])]
checa(not dif and not dif2 and not dif3, f"nas {len(rows)} linhas reais: texto padrão e texto para o seletor idênticos ao servicos.py do 13I (diferenças: {len(dif)}, {len(dif2)} com contexto passado, {len(dif3)} no seletor)")

print("\n=== 1.4 regra geral: outro software real do CSV, sem mudar código ===")
amostras = {}
for nome, pad in (("XDR", r"xdr"), ("Azure", r"azure"), ("antivírus", r"antiv")):
    r = next(x for x in rows if re.search(pad, norm(x["descricao"])))
    t = padrao(r); amostras[nome] = {"codigo": r["codigo"], "descricao_inicio": r["descricao"][:100], "texto_padrao": t, "texto_para_o_seletor": sv.item_para_recorte(t, ["Notebook"])}
    print(f"   {nome:10s} (código {r['codigo']}): padrão = {t!r}\n   {'':10s}  seletor = {amostras[nome]['texto_para_o_seletor']!r}")
    sel_txt = amostras[nome]["texto_para_o_seletor"]
    if pad == "xdr":
        checa(pad in norm(t) and pad not in norm(sel_txt) and " |" not in sel_txt, f"LIMITAÇÃO MEDIDA ({nome}): o texto padrão TEM '{pad}', mas o texto para o seletor NÃO (sigla de 3 letras: a conversão só guarda palavras de 4+ letras; não mudei a regra, pergunto no relatório)")
        amostras[nome]["limitacao"] = "sigla de 3 letras ('xdr') não chega ao texto para o seletor"
    else:
        checa(bool(t.strip()) and pad in norm(sel_txt) and " |" not in sel_txt, f"{nome}: o texto padrão não é vazio e o texto para o seletor leva a palavra que identifica o item ('{pad}')")
RES["regra_geral_1_4"] = amostras
fonte = "\n".join(inspect.getsource(x) for x in (sv.item_pedido_inicial, sv.item_para_recorte, sv.frequencia_de_palavras, sv._palavras_do_texto))
checa(not re.search(r"windows|office|microsoft|xdr|azure|antiv|ltsc|365", fonte, re.I), "nenhum produto escrito na lógica do 'Item pedido' (funções lidas do código)")

print("\n=== 1.5 o campo continua editável, com a legenda 'O app procura no documento: …' ===")
TMP = DADOS / "tmp_teste_fase4" / f"p13j_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat(); ESTADO = {"ligar": False}
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "TR", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]
DESC = [r["descricao"] for r in gw if padrao(r)][:1] + ["SERVICO SIMULADO 1"]
def get(url, params=None, binario=False):
    if "3_consultarServico" in url:
        lote = [{"idCompra": f"92515806001192{i:03d}", "numeroItemCompra": i + 1, "descricaoItem": DESC[i % len(DESC)], "codigoItemCatalogo": 27499, "siglaUnidadeMedida": "UN", "quantidade": 1.0, "precoUnitario": 100.0 + i,
                 "nomeOrgao": f"ORGAO SIMULADO {i}", "estado": "DF", "dataCompra": HOJE, "dataResultado": HOJE} for i in range(4)]
        return 200, {"totalRegistros": 4, "paginasRestantes": 0, "resultado": lote}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url: return 200, {"resultado": [REG] if ESTADO["ligar"] else []}, {}
    if url.endswith("/arquivos"): return 200, LISTA, {}
    if re.search(r"/arquivos/(\d+)$", url): return 200, b"%PDF-1.4 conteudo simulado", {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get; f.extrair_paginas = lambda caminho: (["Texto simulado da pagina um. " * 5] * 6, "")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
at.text_input(key="serv_codigo_av").set_value("27499").run(); next(b for b in at.button if b.label == "Buscar compras do serviço").click().run()
ESTADO["ligar"] = True; next(b for b in at.button if b.label == "Baixar documentos da linha").click().run()
campo = next(t for t in at.text_input if t.label.startswith("Item pedido"))
checa(len(at.exception) == 0 and not campo.disabled and campo.value, f"serviço: campo 'Item pedido' presente, editável e preenchido: {campo.value[:60]!r}")
campo.set_value("palavra1 palavra2|frase digitada").run()
legenda = [str(c.value) for c in at.caption if str(c.value).startswith("O app procura no documento:")]
checa(legenda == ["O app procura no documento: palavra1 palavra2; frase digitada"], f"legenda depois de editar: {legenda}")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOP), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOP)})")
(DADOS / "pedido13j" / "resultado_parte_1.json").write_text(json.dumps(RES, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

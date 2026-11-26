"""v4h, Pedido 13J, PARTE 2 – campos "Tokens lidos (opcional)" e "Janela da IA (tokens)" na Etapa 5, nos DOIS modos. SEM rede (socket bloqueado), rede SIMULADA, só leitura dos catálogos.
Prova: rótulos curtos de uma linha; os dois campos lado a lado na mesma linha, colunas iguais e as duas com ajuda; texto explicativo VISÍVEL (caption), exatamente o pedido; janela inicial lida de
config\\orcamento_tokens.csv (sem o arquivo: em branco + aviso e sem checagem de corte); tokens em branco: mensagem clara e a conferência segue sem a checagem; a regra do corte medida
(prompt_eval_count entre janela/2 e janela/2+16) continua valendo. O AppTest não mede o desenho no navegador.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13j_tokens.py   (na pasta do app)"""
import datetime as dt, json, re, socket, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "tests")); sys.dont_write_bytecode = True
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
from estrutura_util import rotulo_de
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
TMP = DADOS / "tmp_teste_fase4" / f"p13j_t_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat(); ESTADO = {"ligar": False}
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "TR", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]
def get(url, params=None, binario=False):
    params = params or {}
    if "3_consultarServico" in url:
        lote = [{"idCompra": f"92515806001192{i:03d}", "numeroItemCompra": i + 1, "descricaoItem": f"SERVICO SIMULADO {i}", "codigoItemCatalogo": 5606, "siglaUnidadeMedida": "UN", "quantidade": 1.0,
                 "precoUnitario": 1000.0 + i, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF", "dataCompra": HOJE, "dataResultado": HOJE} for i in range(8)]
        return 200, {"totalRegistros": 8, "paginasRestantes": 0, "resultado": lote}, {}
    if "1_consultarMaterial" in url:
        pag = params.get("pagina", 1)
        lote = [{"idCompra": f"9{(pag - 1) * 100 + i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF",
                 "descricaoItem": "NOTEBOOK i5 16 GB RAM SSD 512 GB tela 15,6 polegadas garantia 12 meses", "numeroItemCompra": i + 1, "nomePdm": "NOTEBOOK", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(100)]
        return 200, {"totalRegistros": 300, "resultado": lote, "paginasRestantes": 0 if pag >= 3 else 1}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url: return 200, {"resultado": [REG] if ESTADO["ligar"] else []}, {}
    if url.endswith("/arquivos"): return 200, LISTA, {}
    if re.search(r"/arquivos/(\d+)$", url): return 200, b"%PDF-1.4 conteudo simulado", {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
P1 = DADOS / "noite_2026-11-18" / "produto_p1"
PAGS_N03 = json.loads((next((P1 / "fase2" / "trabalho" / "recortes").glob("N03*")) / "paginas.json").read_text(encoding="utf-8"))
FICHA = (P1 / "fase2" / "saidas" / "N03.txt").read_text(encoding="utf-8")
f.extrair_paginas = lambda caminho: (PAGS_N03, "")
botao = lambda at, r: next(b for b in at.button if b.label == r)
def fluxo(modo):
    """Abre a tela, faz a busca, baixa o documento (simulado) e gera o texto: deixa a Etapa 5 pronta."""
    ESTADO["ligar"] = False
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
    if modo == "Produto":
        at.text_input(key="codigo_av").set_value("8435").run(); at.text_input(key="at_notebook_RAM").set_value("16")
        botao(at, "Buscar").click().run()
    else:
        at.radio(key="tipo_busca").set_value("Serviço").run(); at.text_input(key="serv_termo").set_value("instalação elétrica").run()
        ordem = [str(r["codigoServico"]) for r in sv.procurar("instalação elétrica", sv.ler_catalogo())]
        at.session_state["tab_serv_instalação elétrica"] = {"edited_rows": {ordem.index("5606"): {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
        botao(at, "Buscar compras do serviço").click().run()
    ESTADO["ligar"] = True; botao(at, "Baixar documentos da linha").click().run(); botao(at, "Gerar texto para IA").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at
def campos(at):
    pec = next(t for t in at.text_input if t.key == "ficha_pec"); ctx = next(t for t in at.text_input if t.key == "ficha_ctx"); return pec, ctx
def conferir(at, tokens, janela=None):
    at.text_area(key="ficha_resposta").set_value(FICHA)
    at.text_input(key="ficha_pec").set_value(tokens)
    if janela is not None: at.text_input(key="ficha_ctx").set_value(janela)
    at.run(); botao(at, "Conferir ficha").click().run()
    return at.session_state["ficha_conferida"]["res"]
def linha_dos_campos(at):
    """Procura o contêiner horizontal que tem os dois campos, cada um numa coluna: devolve [(peso da coluna, rótulo)]."""
    def anda(no):
        for c in no.children.values():
            if c.type == "flex_container" and [k.type for k in c.children.values()] == ["column", "column"]:
                inf = [(getattr(k.proto, "weight", None), [rotulo_de(x) for x in k.children.values() if x.type == "text_input"]) for k in c.children.values()]
                if any("Tokens lidos (opcional)" in r for _, r in inf): return inf
            if getattr(c, "children", None):
                r = anda(c)
                if r: return r
        return None
    return anda(at.main)

EXPL = ("Tokens lidos: número que o Open WebUI/Ollama mostra depois de a IA ler o texto (prompt_eval_count). Com ele o app confere se o texto foi cortado. "
        "Janela: o tamanho de contexto em que o Ollama está rodando.")
CONFIG_JANELA = str(f.orcamento_tokens.ler_config(f.ORCAMENTO_CSV)["contexto_tokens"])
res_modos = {}
for modo in ("Produto", "Serviço"):
    print(f"\n=== {modo.upper()} ===")
    at = fluxo(modo); pec, ctx = campos(at)
    checa(pec.label == "Tokens lidos (opcional)" and ctx.label == "Janela da IA (tokens)" and "\n" not in pec.label + ctx.label and len(pec.label) <= 30 and len(ctx.label) <= 30, f"rótulos curtos de uma linha: {pec.label!r} e {ctx.label!r}")
    checa(bool(pec.help) and bool(ctx.help), "os dois campos têm ajuda (mesma estrutura: a ajuda aberta não muda a altura nem o alinhamento)")
    lin = linha_dos_campos(at)
    checa(lin is not None and len(lin) == 2 and lin[0][0] == lin[1][0] and len(lin[0][1]) == 1 and len(lin[1][1]) == 1 and lin[0][1][0] == "Tokens lidos (opcional)" and lin[1][1][0] == "Janela da IA (tokens)", f"os dois campos lado a lado: duas colunas de peso igual {lin}")
    checa(any(str(c.value) == EXPL for c in at.caption), "texto explicativo VISÍVEL (caption), exatamente o pedido")
    checa(CONFIG_JANELA.isdigit() and ctx.value == CONFIG_JANELA, f"janela inicial = a de config\\orcamento_tokens.csv ({CONFIG_JANELA})")
    checa(pec.value == "" and any("Sem os tokens lidos, o app não consegue conferir se o texto foi cortado" in str(i.value) for i in at.info), "tokens em branco: mensagem clara na tela")
    checa(not any("Não achei a janela" in str(w.value) for w in at.warning), "com a janela vinda do config: nenhum aviso de janela")
    r = conferir(at, "")
    checa(r["ficha_encontrada"] and r["verificacao"] == "SEM DADO" and not r["possivel_corte"] and not at.exception and not any("POSSÍVEL CORTE" in str(e.value) for e in at.error)
          and any("Sem prompt_eval_count" in str(c.value) for c in at.caption), f"tokens em branco: a conferência SEGUE ({r['resumo']['literais']} de {r['resumo']['citacoes']} citações literais), sem checagem de corte (verificação {r['verificacao']})")
    metade = int(CONFIG_JANELA) // 2
    for tok, esperado in ((metade - 1, False), (metade, True), (metade + 8, True), (metade + 16, True), (metade + 17, False)):
        r = conferir(at, str(tok))
        tela = any("POSSÍVEL CORTE" in str(e.value) for e in at.error)
        checa(r["possivel_corte"] is esperado and tela is esperado, f"regra do corte, janela {CONFIG_JANELA}: tokens lidos {tok} -> {'POSSÍVEL CORTE' if esperado else 'sem corte'} (verificação {r['verificacao']}; mensagem na tela: {tela})")
    r = conferir(at, "8200", "8000")
    checa(r["num_ctx"] == 8000 and r["verificacao"] != "POSSÍVEL CORTE", f"janela editada para 8000: 8200 tokens já não é corte (limites 4000 a 4016); verificação {r['verificacao']}")
    r = conferir(at, "4005", "8000")
    checa(r["possivel_corte"], "janela editada para 8000: 4005 tokens é POSSÍVEL CORTE (4000 a 4016)")
    res_modos[modo] = {"labels": [pec.label, ctx.label], "linha_dos_campos": lin}

checa(res_modos["Produto"] == res_modos["Serviço"], f"Produto e Serviço: mesmos campos, mesmos rótulos e mesma linha: {res_modos['Produto']['labels']}")

print("\n=== config\\orcamento_tokens.csv AUSENTE (serviço) ===")
orig = f.ORCAMENTO_CSV
f.ORCAMENTO_CSV = TMP / "nao_existe_orcamento_tokens.csv"
try:
    at = fluxo("Serviço"); pec, ctx = campos(at)
    checa(ctx.value == "" and any("Não achei a janela da IA em config" in str(w.value) for w in at.warning), f"sem o arquivo: janela em BRANCO e aviso na tela (valor {ctx.value!r})")
    r = conferir(at, "8200")
    checa(r["verificacao"] == "SEM DADO" and not r["possivel_corte"] and not at.exception and not any("POSSÍVEL CORTE" in str(e.value) for e in at.error), "sem janela, mesmo com 8200 tokens: nenhuma checagem de corte (não usa janela inventada) e a conferência segue")
    r = conferir(at, "8200", "16384")
    checa(r["possivel_corte"], "a pessoa escreve a janela 16384: com 8200 tokens a checagem volta (POSSÍVEL CORTE)")
finally:
    f.ORCAMENTO_CSV = orig
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOP), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOP)})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

"""v4h, Pedido 13I, PARTE A – PAINEL DE PROGRESSO sempre visível em toda ação demorada, nos DOIS modos (Produto e Serviço). OFFLINE: socket bloqueado, rede trocada por respostas
SIMULADAS (dados simulados só aqui). O AppTest não mede o desenho no navegador: o que se prova é o conteúdo da tela e do st.session_state.
Prova: (1) o app não usa st.status nem st.spinner; as barras só nascem dentro do helper Painel; o painel é um container (nada recolhível); (2) cada ação deixa o painel com o estado FINAL
('Concluída em N s: ...', 'Conferida em N s: ...' ou 'Falhou: ...') na tela e em session_state; (3) o painel continua na tela depois de reruns; (4) as regras de limpeza (termo novo,
Nova busca) apagam os painéis. O que é gravado em config\\ (catálogos) é redirecionado para CÓPIAS em pasta de teste; o hash dos reais é conferido no fim.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13i_painel.py   (na pasta do app)"""
import ast, datetime as dt, hashlib, json, re, shutil, socket, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
LOOPBACK_INTERNO = []
_connect_original = socket.socket.connect
def _sem_rede(self, endereco, *a, **k):
    host, porta = (endereco[0], endereco[1]) if isinstance(endereco, tuple) else (str(endereco), None)
    if host in ("127.0.0.1", "::1") and porta != 11434:
        LOOPBACK_INTERNO.append((host, porta)); return _connect_original(self, endereco, *a, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {endereco!r}")
socket.socket.connect = _sem_rede
from streamlit.testing.v1 import AppTest
import ferramenta as f
import servicos as sv

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
REAIS = {n: RAIZ / "config" / n for n in ("catalogo_servicos.csv", "catalogo_pdm.csv")}; SHA0 = {n: sha(p) for n, p in REAIS.items()}
TMP = DADOS / "tmp_teste_fase4" / f"p13i_{int(time.time())}"; TMP.mkdir(parents=True)
f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
# catálogos: o app grava em CÓPIAS
CAT_S = TMP / "catalogo_servicos.csv"; shutil.copyfile(REAIS["catalogo_servicos.csv"], CAT_S); sv.CATALOGO_SERVICOS = CAT_S
CAT_P = TMP / "catalogo_pdm.csv"; shutil.copyfile(REAIS["catalogo_pdm.csv"], CAT_P); f.CATALOGO_PDM = CAT_P

# ------------------------------------------------------------------ rede SIMULADA
HOJE = dt.date.today().isoformat()
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "TR", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]
ESTADO = {"chamadas": [], "catalogo_serv": "ok", "total_serv": 3108, "ligar": False}
def itens_serv(n):
    return [{"codigoSecao": 1, "nomeSecao": "S", "codigoDivisao": 10, "nomeDivisao": "D", "codigoGrupo": 100, "nomeGrupo": "G", "codigoClasse": 1000, "nomeClasse": "C", "codigoSubclasse": None, "nomeSubclasse": None,
             "codigoServico": 20000 + i, "nomeServico": f"SERVICO SIMULADO {i}", "codigoCpc": 1, "exclusivoCentralCompras": False, "statusServico": True, "dataHoraAtualizacao": "2026-11-20T00:00:00"} for i in range(n)]
def get(url, params=None, binario=False):          # qualname 'get': o app o trata como a função original
    params = params or {}; ESTADO["chamadas"].append(url)
    if "modulo-servico/6_consultarItemServico" in url:
        if ESTADO["catalogo_serv"] == "http500": return 500, None, {}
        n, pag = ESTADO["total_serv"], params.get("pagina", 1); lote = itens_serv(n)[(pag - 1) * 500: pag * 500]
        tp = (n + 499) // 500
        return 200, {"resultado": lote, "totalRegistros": n, "totalPaginas": tp, "paginasRestantes": tp - pag}, {}
    if "modulo-material/3_consultarPdmMaterial" in url:
        return 200, {"resultado": [{"codigoPdm": 8435, "nomePdm": "NOTEBOOK", "statusPdm": True, "codigoClasse": 1, "nomeClasse": "X", "codigoGrupo": 1, "nomeGrupo": "Y"}], "totalPaginas": 1}, {}
    if "3_consultarServico" in url:
        lote = [{"idCompra": f"92515806001192{i:03d}", "numeroItemCompra": i + 1, "descricaoItem": f"SERVICO SIMULADO {i}", "codigoItemCatalogo": 5606, "siglaUnidadeMedida": "UN", "quantidade": 1.0,
                 "precoUnitario": 1000.0 + i, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF", "dataCompra": HOJE, "dataResultado": HOJE} for i in range(8)]
        return 200, {"totalRegistros": 8, "paginasRestantes": 0, "resultado": lote}, {}
    if "1_consultarMaterial" in url:
        pag = params.get("pagina", 1)
        lote = [{"idCompra": f"9{(pag - 1) * 100 + i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF",
                 "descricaoItem": "NOTEBOOK i5 16 GB RAM SSD 512 GB tela 15,6 polegadas garantia 12 meses", "numeroItemCompra": i + 1, "nomePdm": "NOTEBOOK", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(100)]
        return 200, {"totalRegistros": 300, "resultado": lote, "paginasRestantes": 0 if pag >= 3 else 1}, {}
    if "4_consultarItemMaterial" in url:
        return 200, {"resultado": [{"codigoItem": 111, "descricaoItem": "NOTEBOOK SIMULADO", "statusItem": True}], "totalRegistros": 1}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        return 200, {"resultado": [REG] if ESTADO["ligar"] else []}, {}
    if url.endswith("/arquivos"): return 200, LISTA, {}
    if re.search(r"/arquivos/(\d+)$", url): return 200, b"%PDF-1.4 conteudo simulado", {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
P1 = DADOS / "noite_2026-11-18" / "produto_p1"
PAGS_N03 = json.loads((next((P1 / "fase2" / "trabalho" / "recortes").glob("N03*")) / "paginas.json").read_text(encoding="utf-8"))
f.extrair_paginas = lambda caminho: (PAGS_N03, "")

def textos(at):
    s = []
    for lista in (at.warning, at.success, at.error, at.info, at.markdown, at.caption, at.subheader):
        s += [str(e.value) for e in lista]
    return s
def botao(at, rotulo): return next(b for b in at.button if b.label == rotulo)
def sem_excecao(at, onde): checa(len(at.exception) == 0, f"{onde}: sem exceção" + ("" if not at.exception else f" -> {[e.value for e in at.exception]}"))
CHAVES = ("e1_procurar", "e1_catalogo", "e1_config", "e1_conferir", "e2_buscar", "e3_baixar", "e3_recorte", "e5_conferir")
def paineis(at): return [c for c in CHAVES if f"painel_{c}" in at.session_state]
def estado(at, chave): return at.session_state[f"painel_{chave}"] if f"painel_{chave}" in at.session_state else None
def painel_ok(at, chave, titulo, verbo, contem, onde):
    """O estado guardado e a tela dizem '<verbo> em N s: <contem>' no painel 'titulo'."""
    e = estado(at, chave)
    esperado = re.compile(rf"{verbo} em [\d,]+( s| min \d\d s): .*{re.escape(contem)}")
    na_tela = any(esperado.match(t) for t in textos(at)) and any(t == f"**{titulo}**" for t in textos(at))
    checa(bool(e) and e["ok"] is True and bool(esperado.match(e["texto"])) and na_tela, f"{onde}: painel '{titulo}' com estado final na tela e em session_state: {(e or {}).get('texto', '(sem estado)')[:110]!r}")
def painel_falhou(at, chave, titulo, contem, onde):
    e = estado(at, chave)
    na_tela = any(t.startswith("Falhou: ") and contem in t for t in textos(at))
    checa(bool(e) and e["ok"] is False and e["texto"].startswith("Falhou: ") and contem in e["texto"] and na_tela, f"{onde}: painel '{titulo}' com 'Falhou: ...' na tela e em session_state: {(e or {}).get('texto', '(sem estado)')[:110]!r}")

print("=== A1. o código: nada de st.status nem st.spinner; barras só no helper; painel sem componente recolhível ===")
fonte = (RAIZ / "app.py").read_text(encoding="utf-8"); arv = ast.parse(fonte)
usos = [(n.lineno, n.func.attr) for n in ast.walk(arv) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "st" and n.func.attr in ("status", "spinner")]
checa(not usos, f"nenhuma chamada a st.status nem st.spinner no app.py {usos}")
def dentro(no, nomes): return any(isinstance(a, (ast.FunctionDef, ast.ClassDef)) and a.name in nomes for a in ast.walk(no) if a is not no) and False
prog = []
for cls in [n for n in arv.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]:
    for n in ast.walk(cls):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "st" and n.func.attr == "progress":
            prog.append((cls.name, n.lineno))
checa(prog and {c for c, _ in prog} <= {"Painel", "_desenha_painel"}, f"st.progress só dentro do helper do painel: {sorted({c for c, _ in prog})}")
src_painel = fonte[fonte.index("class Painel:"):fonte.index("def tempo_fmt") if fonte.index("def tempo_fmt") > fonte.index("class Painel:") else None] if False else ""
corpo_painel = next(n for n in arv.body if isinstance(n, ast.ClassDef) and n.name == "Painel")
checa(not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("expander", "status") for n in ast.walk(corpo_painel)) and
      any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "container" for n in ast.walk(corpo_painel)), "o Painel usa container com borda (sem expander nem status): aberto sem clique e sem recolher")

print("\n=== P. PRODUTO ===")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); sem_excecao(at, "abertura")
checa(not paineis(at), "sem busca nenhuma: nenhum painel na tela")
# Etapa 1: conferir código avançado
at.text_input(key="codigo_av").set_value("8435").run(); sem_excecao(at, "código 8435")
painel_ok(at, "e1_conferir", "Etapa 1 · Conferir o código digitado", "Concluída", "8435", "produto, conferir código")
at.text_input(key="at_notebook_RAM").set_value("16").run()
painel_ok(at, "e1_conferir", "Etapa 1 · Conferir o código digitado", "Concluída", "8435", "produto, conferir código, DEPOIS de outro rerun")
# Etapa 1: procurar
at.text_input(key="codigo_av").set_value("").run()
checa(estado(at, "e1_conferir") is None, "produto: apagou o código digitado: o painel da conferência some")
at.text_input(key="termo").set_value("notebook").run(); sem_excecao(at, "procurar notebook (Enter)")
painel_ok(at, "e1_procurar", "Etapa 1 · Procurar no catálogo", "Concluída", "código(s) encontrado(s)", "produto, procurar")
at.text_input(key="uf_busca").set_value("DF").run()
painel_ok(at, "e1_procurar", "Etapa 1 · Procurar no catálogo", "Concluída", "código(s) encontrado(s)", "produto, procurar, depois de rerun")
# Etapa 1: atualizar catálogo (cópia)
sha_cop = sha(CAT_P); botao(at, "Atualizar catálogo").click().run(); sem_excecao(at, "produto: atualizar catálogo")
painel_ok(at, "e1_catalogo", "Etapa 1 · Atualizar o catálogo de materiais", "Concluída", "atualizado", "produto, atualizar catálogo (depois do rerun do app)")
checa(sha(CAT_P) != sha_cop and sha(REAIS["catalogo_pdm.csv"]) == SHA0["catalogo_pdm.csv"], "produto: a CÓPIA do catálogo mudou; o real não")
# refaz a procura (o botão Atualizar limpou o resultado) e carrega configurações
at.text_input(key="termo").set_value("notebook").run(); botao(at, "Procurar no catálogo").click().run()
botao(at, "Ver configurações").click().run(); sem_excecao(at, "produto: ver configurações")
painel_ok(at, "e1_config", "Etapa 1 · Carregar as configurações do código", "Concluída", "configuração(ões)", "produto, carregar configurações")
# Etapa 2: buscar
at.text_input(key="codigo_av").set_value("8435").run(); at.text_input(key="at_notebook_RAM").set_value("16")
botao(at, "Buscar").click().run(); sem_excecao(at, "produto: Buscar")
painel_ok(at, "e2_buscar", "Etapa 2 · Buscar compras", "Concluída", "na API", "produto, buscar")
e2 = estado(at, "e2_buscar"); nomes = [b[0] for b in e2["barras"]]
checa(nomes[0].startswith("Passo 0") and all(b[1] == 1.0 for b in e2["barras"]) and len(nomes) == 4, f"produto: o passo 0 é a 1ª barra do painel e todas terminam em 100%: {nomes}")
at.radio(key="serv_modo" if False else "tipo_busca"); at.run(); sem_excecao(at, "rerun qualquer")
painel_ok(at, "e2_buscar", "Etapa 2 · Buscar compras", "Concluída", "na API", "produto, buscar, depois de rerun")
# Etapa 3: baixar e recortar (a compra só é ligada ao PNCP na hora do download)
ESTADO["ligar"] = True
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "produto: baixar")
painel_ok(at, "e3_baixar", "Etapa 3 · Baixar os documentos da compra", "Concluída", "download concluído (2 arquivo(s))", "produto, baixar documentos")
botao(at, "Gerar texto para IA").click().run(); sem_excecao(at, "produto: gerar texto")
painel_ok(at, "e3_recorte", "Etapa 3 · Gerar o texto para a IA", "Concluída", "texto pronto", "produto, gerar texto para IA")
painel_ok(at, "e3_baixar", "Etapa 3 · Baixar os documentos da compra", "Concluída", "download concluído (2 arquivo(s))", "produto, o painel do download continua depois do outro painel")
# Nova busca limpa
botao(at, "Nova busca").click().run(); sem_excecao(at, "Nova busca")
checa(not paineis(at), "produto: 'Nova busca' apagou todos os painéis")
# Falhas
f_autoteste = f.autoteste; f.autoteste = lambda: ["erro simulado do passo 0"]
at.text_input(key="codigo_av").set_value("8435").run(); botao(at, "Buscar").click().run()
painel_falhou(at, "e2_buscar", "Etapa 2 · Buscar compras", "a conferência offline falhou", "produto, passo 0 falhando"); f.autoteste = f_autoteste

print("\n=== S. SERVIÇO ===")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run(); sem_excecao(at, "troca para Serviço")
at.text_input(key="serv_termo").set_value("instalação elétrica").run(); sem_excecao(at, "procurar serviço (Enter)")
painel_ok(at, "e1_procurar", "Etapa 1 · Procurar no catálogo", "Concluída", "serviço(s) encontrado(s)", "serviço, procurar")
at.text_input(key="serv_uf").set_value("DF").run()
painel_ok(at, "e1_procurar", "Etapa 1 · Procurar no catálogo", "Concluída", "serviço(s) encontrado(s)", "serviço, procurar, depois de rerun")
at.text_input(key="serv_codigo_av").set_value("5606").run(); sem_excecao(at, "código digitado do serviço")
painel_ok(at, "e1_conferir", "Etapa 1 · Conferir o código digitado", "Concluída", "código(s) no catálogo local", "serviço, conferir código")
at.text_input(key="serv_codigo_av").set_value("99999999").run()
painel_falhou(at, "e1_conferir", "Etapa 1 · Conferir o código digitado", "fora do catálogo local", "serviço, código fora do catálogo")
at.text_input(key="serv_codigo_av").set_value("").run()
checa(estado(at, "e1_conferir") is None, "serviço: apagou o código digitado: o painel da conferência some")
sha_cop = sha(CAT_S); botao(at, "Atualizar catálogo").click().run(); sem_excecao(at, "serviço: atualizar catálogo")
painel_ok(at, "e1_catalogo", "Etapa 1 · Atualizar o catálogo de serviços", "Concluída", "atualizado", "serviço, atualizar catálogo (depois do rerun do app)")
checa(sha(CAT_S) != sha_cop and sha(REAIS["catalogo_servicos.csv"]) == SHA0["catalogo_servicos.csv"], "serviço: a CÓPIA do catálogo mudou; o real não")
ESTADO["catalogo_serv"] = "http500"; botao(at, "Atualizar catálogo").click().run()
painel_falhou(at, "e1_catalogo", "Etapa 1 · Atualizar o catálogo de serviços", "o atual foi mantido", "serviço, portal fora (HTTP 500)"); ESTADO["catalogo_serv"] = "ok"
ESTADO["ligar"] = True
# fluxo completo do serviço: usa serviços do catálogo ORIGINAL (a cópia acabou de ser trocada por itens simulados)
shutil.copyfile(REAIS["catalogo_servicos.csv"], CAT_S)
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
at.text_input(key="serv_termo").set_value("instalação elétrica").run()
ordem = [str(r["codigoServico"]) for r in sv.procurar("instalação elétrica", sv.ler_catalogo(CAT_S))]
at.session_state["tab_serv_instalação elétrica"] = {"edited_rows": {ordem.index("5606"): {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
botao(at, "Buscar compras do serviço").click().run(); sem_excecao(at, "serviço: Buscar")
painel_ok(at, "e2_buscar", "Etapa 2 · Buscar compras do serviço", "Concluída", "na API", "serviço, buscar")
e2 = estado(at, "e2_buscar"); nomes = [b[0] for b in e2["barras"]]
checa(nomes[0].startswith("Passo 0") and all(b[1] == 1.0 for b in e2["barras"]) and len(nomes) == 3, f"serviço: o passo 0 é a 1ª barra do painel e todas terminam em 100%: {nomes}")
at.text_input(key="serv_uf").set_value("DF").run()
painel_ok(at, "e2_buscar", "Etapa 2 · Buscar compras do serviço", "Concluída", "na API", "serviço, buscar, depois de rerun")
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "serviço: baixar")
painel_ok(at, "e3_baixar", "Etapa 3 · Baixar os documentos da compra", "Concluída", "download concluído (2 arquivo(s))", "serviço, baixar documentos")
botao(at, "Gerar texto para IA").click().run(); sem_excecao(at, "serviço: gerar texto")
painel_ok(at, "e3_recorte", "Etapa 3 · Gerar o texto para a IA", "Concluída", "Recorte: ", "serviço, gerar texto para IA")
at.text_area(key="ficha_resposta").set_value((P1 / "fase2" / "saidas" / "N03.txt").read_text(encoding="utf-8")); at.text_input(key="ficha_pec").set_value("")
botao(at, "Conferir ficha").click().run(); sem_excecao(at, "serviço: conferir ficha")
painel_ok(at, "e5_conferir", "Etapa 5 · Conferir a ficha", "Conferida", "6 de 6 citações literais", "serviço, conferir ficha")
at.text_input(key="serv_uf").set_value("SP").run()
painel_ok(at, "e5_conferir", "Etapa 5 · Conferir a ficha", "Conferida", "6 de 6 citações literais", "serviço, conferir ficha, depois de rerun")
painel_ok(at, "e3_recorte", "Etapa 3 · Gerar o texto para a IA", "Concluída", "Recorte: ", "serviço, o painel do recorte continua")
# termo novo limpa os painéis do resultado (mesma regra da busca anterior)
at.text_input(key="serv_termo").set_value("limpeza").run(); botao(at, "Procurar no catálogo").click().run()
checa(all(estado(at, c) is None for c in ("e2_buscar", "e3_baixar", "e3_recorte", "e5_conferir")), "serviço: termo novo limpou os painéis das etapas 2, 3 e 5 (e o da procura é o novo)")
painel_ok(at, "e1_procurar", "Etapa 1 · Procurar no catálogo", "Concluída", "serviço(s) encontrado(s)", "serviço, procurar o termo novo")
botao(at, "Nova busca").click().run()
checa(not paineis(at), "serviço: 'Nova busca' apagou todos os painéis")

print("\n=== Z. contenção ===")
checa(all(sha(p) == SHA0[n] for n, p in REAIS.items()), f"catalogo_servicos.csv e catalogo_pdm.csv reais intactos ({', '.join(f'{n} {SHA0[n][:8]}' for n in SHA0)})")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

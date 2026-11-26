"""v4h, Pedido 9 – a TELA (streamlit.testing.v1.AppTest) com o seletor Produto/Serviço, as etapas numeradas, a caixa de limites, o preço de serviço, o preço do
canal oficial, a lista de TR por compra e o CONTEÚDO do CSV baixado. SEM rede (socket bloqueado; só o loopback do asyncio passa e é contado), SEM Ollama.
A rede é trocada por respostas SIMULADAS (dados simulados só aqui): tudo que depende da API real fica 'NÃO TESTADO COM REDE'.
O CSV do botão 'Baixar CSV (ordem desta tela)' é capturado no momento em que o app chama st.download_button (o AppTest não guarda o conteúdo).
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido9_tela.py   (na pasta do app)"""
import csv, datetime as dt, io, json, re, socket, sys, time
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
import streamlit as st
from streamlit.testing.v1 import AppTest
import ferramenta as f
# Pedido 16 (M1): este teste guarda o comportamento de 16.384. Usa uma CÓPIA TEMPORÁRIA do config com contexto_tokens=16384; o config real (hoje 32.768) não é tocado.
import atexit as _at, os as _os, re as _re, shutil as _sh
_CFG16 = DADOS / "pedido16" / f"_tmp_cfg16384_{_os.getpid()}"; _CFG16.mkdir(parents=True, exist_ok=True); _at.register(_sh.rmtree, _CFG16, ignore_errors=True)
(_CFG16 / "orcamento_tokens.csv").write_text(_re.sub(r";\d+;1500;", ";16384;1500;", f.ORCAMENTO_CSV.read_text(encoding="utf-8-sig"), count=1), encoding="utf-8-sig"); f.ORCAMENTO_CSV = _CFG16 / "orcamento_tokens.csv"

CAPT = []
_orig_dl = st.download_button
def _spy(label, data, *a, **k):
    CAPT.append({"label": label, "data": data, "file_name": k.get("file_name")}); return _orig_dl(label, data, *a, **k)
st.download_button = _spy

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

P1 = DADOS / "noite_2026-11-18" / "produto_p1"
PAGS_N03 = json.loads((next((P1 / "fase2" / "trabalho" / "recortes").glob("N03*")) / "paginas.json").read_text(encoding="utf-8"))
TMP = DADOS / "tmp_teste_fase4"; TMP.mkdir(exist_ok=True)
RODADA = TMP / f"p9_{int(time.time())}"; RODADA.mkdir(); f.PASTA = RODADA

# ------------------------------------------------------------------ rede SIMULADA
HOJE = dt.date.today().isoformat()
PRECOS = [1000.0, 1100.0, 1200.0, 1300.0, 1150.0, 1250.0, 90000.0, 1.0]
IDS = ["9251580600119202" if i < 3 else f"{92515806001192025 + i}" for i in range(8)]
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
ESTADO = {"chamadas": [], "ligar": [], "inesperadas": []}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "TR assinado", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2},
         {"titulo": "Proposta da empresa", "tipoDocumentoNome": "Proposta", "sequencialDocumento": 3}]
def get(url, params=None, binario=False):          # qualname 'get': o app o trata como a função original
    params = params or {}; ESTADO["chamadas"].append(url); f.contar("chamadas")
    if "3_consultarServico" in url:
        lote = [{"idCompra": IDS[i], "numeroItemCompra": i + 1, "descricaoItem": f"SERVICO SIMULADO {i}", "codigoItemCatalogo": 5606, "siglaUnidadeMedida": "UN", "quantidade": float(i + 1),
                 "precoUnitario": PRECOS[i], "nomeOrgao": f"ORGAO SIMULADO {i}", "estado": "DF", "dataCompra": HOJE, "dataResultado": HOJE} for i in range(8)]
        return 200, {"totalRegistros": 8, "paginasRestantes": 0, "resultado": lote}, {}
    if "1_consultarMaterial" in url:
        pag = params.get("pagina", 1)
        lote = [{"idCompra": f"9{(pag - 1) * 100 + i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO SIMULADO {i}", "estado": "DF",
                 "descricaoItem": "NOTEBOOK i5 16 GB RAM SSD 512 GB tela 15,6 polegadas garantia 12 meses", "numeroItemCompra": i + 1, "nomePdm": "NOTEBOOK", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(100)]
        return 200, {"totalRegistros": 300, "resultado": lote, "paginasRestantes": 0 if pag >= 3 else 1}, {}
    if "4_consultarItemMaterial" in url:
        return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        ESTADO["ligar"].append(params.get("codigo", ""))
        if ESTADO.get("produto"): return 200, {"resultado": []}, {}      # produto: sem ligação, como no teste da fase 4 (não pede /itens)
        return 200, {"resultado": [REG] if str(params.get("codigo", "")).endswith(("2", "9", "1", "0")) else []}, {}
    if url.endswith("/arquivos"):
        return 200, LISTA, {}
    m = re.search(r"/arquivos/(\d+)$", url)
    if m:
        return 200, b"%PDF-1.4 conteudo simulado", {}
    ESTADO["inesperadas"].append(url); raise AssertionError(f"URL inesperada no teste: {url}")
f.get = get

import servicos as _sv_teste
def marca_servicos(at_, termo, codigos):
    """O AppTest não clica no st.data_editor: grava as linhas marcadas (coluna 'usar') no estado da tabela do serviço (chave tab_serv_<termo>)."""
    ordem = [str(r["codigoServico"]) for r in _sv_teste.procurar(termo, _sv_teste.ler_catalogo())]
    at_.session_state[f"tab_serv_{termo}"] = {"edited_rows": {ordem.index(str(c)): {"usar": True} for c in codigos}, "added_rows": [], "deleted_rows": []}
    at_.run()
    return at_
def codigos_marcados(at_):
    t = [str(m.value) for m in at_.markdown if str(m.value).startswith("Códigos marcados:")]
    return t[-1].split(":", 1)[1].strip() if t else ""

def textos(at):
    s = []
    for lista in (at.warning, at.success, at.error, at.info, at.markdown, at.caption, at.text, at.text_area, at.subheader, at.title):
        s += [str(e.value) for e in lista]
    return s
def tem(at, trecho): return any(trecho in t for t in textos(at))
def botao(at, rotulo): return next(b for b in at.button if b.label == rotulo)
def sem_excecao(at, onde_): checa(len(at.exception) == 0, f"{onde_}: sem exceção na tela" + ("" if not at.exception else f" -> {[e.value for e in at.exception]}"))
def tabela(at, coluna):
    return next((d.value for d in at.dataframe if coluna in d.value.columns), None)
def csv_capturado(rotulo):
    c = [x for x in CAPT if x["label"] == rotulo]
    if not c: return None, None
    txt = c[-1]["data"].decode("utf-8-sig") if isinstance(c[-1]["data"], bytes) else str(c[-1]["data"])
    linhas = list(csv.DictReader(io.StringIO(txt, newline=""), delimiter=";")); return (list(linhas[0]) if linhas else []), linhas

print("=== P0. topo da tela: caixa de limites, seletor e etapas ===")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); sem_excecao(at, "abertura")
checa(any(i.value == "Limites: a IA apoia, quem decide é a seção; a busca não usa IA." for i in at.info), "caixa 'Limites: a IA apoia, quem decide é a seção; a busca não usa IA.' visível")
checa(at.radio(key="tipo_busca").options == ["Produto", "Serviço"] and at.radio(key="tipo_busca").value == "Produto", f"seletor no topo: {at.radio(key='tipo_busca').options}, padrão 'Produto'")
checa(tem(at, "Etapa 1 · Buscar") and any(t.label.startswith("O que você procura?") for t in at.text_input), "Produto: título 'Etapa 1 · Buscar' e o campo 'O que você procura?' (Pedido 13B: um título só)")

print("\n=== P1. Serviço: catálogo local e procura por palavra ===")
at.radio(key="tipo_busca").set_value("Serviço").run(); sem_excecao(at, "troca para Serviço")
checa(tem(at, "Etapa 1 · Buscar") and any(t.label.startswith("Palavra do serviço") for t in at.text_input) and not any(t.label.startswith("O que você procura?") for t in at.text_input), "Serviço: mesmo título 'Etapa 1 · Buscar', campo 'Palavra do serviço' e some o campo de produto")
checa(any("3.108 serviços" in str(c.value) and "atualizado em " + (lambda _c: max(r["baixado_em"] for r in _c if r.get("baixado_em")))(__import__("servicos").ler_catalogo())[:10] in str(c.value) and "catalogo_servicos.csv" in str(c.value) and "o app não o baixa" not in str(c.value) for c in at.caption), "legenda do catálogo (Pedido 13F): 3.108 serviços, atualizado em 2026-11-17, arquivo citado, sem 'o app não o baixa' (a data é a do próprio arquivo)")
checa(not any("Testado com rede" in str(c.value) or "NÃO testado com rede" in str(c.value) or "tamanhoPagina" in str(c.value) for c in at.caption), "Pedido 13G: nenhum texto de status de teste na tela do serviço (o parágrafo 'Testado com rede' saiu; o conteúdo fica só no CONTROLE_VERSOES.txt)")
at.text_input(key="serv_termo").set_value("zzzxxx").run()
checa(any("Nenhum serviço ativo" in str(w.value) for w in at.warning), "palavra sem resultado: aviso claro (sem erro)")
at.text_input(key="serv_termo").set_value("instalação elétrica").run(); sem_excecao(at, "procura 'instalação elétrica'")
checa(any("serviço(s) encontrado(s)" in str(c.value) for c in at.caption) and "5606" in [str(r["codigoServico"]) for r in _sv_teste.procurar("instalação elétrica", _sv_teste.ler_catalogo())], "a lista de serviços aparece e inclui o código 5606")
botao(at, "Buscar compras do serviço").click().run()
checa(any("escolha pelo menos 1 código de serviço" in str(e.value) for e in at.error), "Buscar sem marcar código: mensagem de erro clara e nenhuma chamada de rede")
checa(not ESTADO["chamadas"], f"nenhuma chamada de rede ainda ({len(ESTADO['chamadas'])})")

print("\n=== P2. Serviço: busca (respostas SIMULADAS), etapas 2 e preço de serviço ===")
marca_servicos(at, "instalação elétrica", ["5606"])
checa(codigos_marcados(at) == "5606", "marcado na coluna 'usar': Códigos marcados: 5606")
botao(at, "Buscar compras do serviço").click().run(); sem_excecao(at, "busca de serviço")
rec = at.session_state["busca_atual"] if "busca_atual" in at.session_state else None
checa(rec is not None and rec.get("tipo") == "serviço" and rec["resumo"].get("tipo_busca") == "serviço", "a busca ficou na sessão com tipo 'serviço'")
checa(tem(at, "Etapa 2 · Escolher a compra: resumo da busca") and tem(at, "Etapa 2 · Escolher a compra: resultados") and tem(at, "Etapa 3 · Recorte") and tem(at, "Etapa 5 · Conferir ficha (sem IA)"), "etapas 2, 3 e 5 numeradas na tela")
checa(any("Preços de serviço podem não ser comparáveis (unidade, prazo, quantidade)." in str(w.value) for w in at.warning), "aviso 'preços de serviço podem não ser comparáveis (unidade, prazo, quantidade)'")
todos = " ".join(textos(at)).lower()
checa("mediana" not in todos.replace("nenhuma média nem mediana", "") and "média" not in todos.replace("nenhuma média nem mediana", ""), "a tela não mostra média nem mediana de preço de serviço (só a frase que diz que não são calculadas)")
df = tabela(at, "preco_unitario_homologado")
checa(df is not None and len(df) == 8 and {"unidade", "quantidade", "observacao_preco"} <= set(df.columns), f"tabela com as 8 linhas e as colunas unidade, quantidade, observacao_preco: {None if df is None else list(df.columns)}")
checa(df is not None and sorted(df.loc[df["observacao_preco"] == "suspeito", "preco_unitario_homologado"].astype(float).tolist()) == [1.0, 90000.0], "linhas de 1,00 e 90.000 marcadas 'suspeito' e continuam na tabela")
checa(any(m.label.startswith("Preço suspeito") and str(m.value) == "2" for m in at.metric), "métrica 'Preço suspeito (marcado, não apagado)' = 2")
checa(df is not None and "canal_oficial_comparacao" in df.columns and not df["canal_oficial_comparacao"].astype(str).str.contains("canal oficial").any() and not tem(at, "abaixo do canal oficial"), "sem o campo do canal oficial: nenhum rótulo 'abaixo do canal oficial' na tela nem na tabela")
cols_csv, lin_csv = csv_capturado("Baixar CSV (ordem desta tela)")
checa(cols_csv is not None and len(lin_csv) == 8 and {"versao_app", "tipo_busca", "modo", "chamadas", "falhas", "tempo_s"} <= set(cols_csv), f"CSV do botão 'Baixar CSV' capturado: 8 linhas e as colunas de versão presentes")
checa(lin_csv and all(l["versao_app"] == "v4h" and l["tipo_busca"] == "serviço" and l["modo"] == "rápido" and l["chamadas"] == str(rec["resumo"]["chamadas"]) and l["falhas"] == "0" for l in lin_csv),
      f"CSV baixado: versao_app=v4h, tipo_busca=serviço, modo=rápido, chamadas={rec['resumo']['chamadas']}, falhas=0 em todas as linhas")
checa(ESTADO["ligar"] and all(len(c) == 17 for c in ESTADO["ligar"]), f"ligação ao PNCP com 17 dígitos (zfill) também pela tela ({ESTADO['ligar'][:2]})")
checa(any("Preço suspeito" in m.label for m in at.metric) and any(e for e in at.expander if "site oficial" in str(e.label)), "bloco opcional 'preço do site oficial do fornecedor' presente")

print("\n=== P3. preço do site oficial (digitado) ===")
linha_1000 = str(df.loc[df["preco_unitario_homologado"].astype(float) == 1000.0, "linha"].iloc[0])
at.selectbox(key="canal_linha").set_value(linha_1000).run()
at.text_input(key="canal_preco").set_value("1.250,00").run(); botao(at, "Registrar para esta linha").click().run()
checa(any("Não registrei" in str(w.value) and "link" in str(w.value) and "data e a hora" in str(w.value) for w in at.warning) and not tem(at, "abaixo do canal oficial"), "só o preço digitado: o app pede link e data/hora e NÃO mostra o rótulo")
at.text_input(key="canal_link").set_value("https://exemplo.invalido/servico").run(); at.text_input(key="canal_acesso").set_value("20/11/2026 14:30").run()
botao(at, "Registrar para esta linha").click().run(); sem_excecao(at, "registro do canal oficial")
df2 = tabela(at, "preco_unitario_homologado")
checa(tem(at, f"Linha {linha_1000}: abaixo do canal oficial: pago R$ 1.000,00 × canal oficial R$ 1.250,00 (-20%)") and "https://exemplo.invalido/servico" in " ".join(textos(at)), "com os 3 campos: 'abaixo do canal oficial' com a diferença (-20%), o link e a hora")
checa(df2 is not None and df2.loc[df2["linha"].astype(str) == linha_1000, "canal_oficial_comparacao"].iloc[0] == "abaixo do canal oficial" and (df2["canal_oficial_comparacao"] == "abaixo do canal oficial").sum() == 1, "tabela: o rótulo só aparece na linha em que a pessoa digitou o campo")
cols2, lin2 = csv_capturado("Baixar CSV (ordem desta tela)")
l2 = next(l for l in lin2 if l["linha"] == linha_1000)
checa(l2["canal_oficial_preco"] == "1.250,00" and l2["canal_oficial_link"] == "https://exemplo.invalido/servico" and l2["canal_oficial_acesso"] == "20/11/2026 14:30" and l2["canal_oficial_comparacao"] == "abaixo do canal oficial" and all(l["canal_oficial_comparacao"] == "" for l in lin2 if l is not l2),
      "CSV baixado: preço, link, data/hora e rótulo só na linha registrada")
checa(not [u for u in ESTADO["chamadas"] if "exemplo.invalido" in u], "nenhuma chamada foi feita ao link do fornecedor (o app nunca acessa o site)")

print("\n=== P4. lista de TR por compra (resposta SIMULADA; NÃO TESTADO COM REDE) ===")
linhas_csv = list(csv.DictReader(io.StringIO(rec["csv"].decode("utf-8-sig"), newline=""), delimiter=";"))
com_link = next(l["linha"] for l in linhas_csv if l["link_publico"].startswith("http")); sem_link = next(l["linha"] for l in linhas_csv if not l["link_publico"].startswith("http"))
sel_doc = next(s for s in at.selectbox if s.label == "Linha" and s.key != "canal_linha")
sel_doc.set_value(sem_link).run(); botao(at, "Listar os TR e documentos principais desta compra (1 consulta ao PNCP, nada é baixado)").click().run()
checa(any("não está ligada ao PNCP" in str(w.value) for w in at.warning), "linha sem PNCP: aviso claro, sem consulta")
n_antes = len(ESTADO["chamadas"])
next(s for s in at.selectbox if s.label == "Linha" and s.key != "canal_linha").set_value(com_link).run()
botao(at, "Listar os TR e documentos principais desta compra (1 consulta ao PNCP, nada é baixado)").click().run(); sem_excecao(at, "lista de TR")
dft = tabela(at, "é TR")
checa(dft is not None and len(dft) == 3 and dft["é TR"].tolist() == [False, True, False] and len(ESTADO["chamadas"]) == n_antes + 1 and ESTADO["chamadas"][-1].endswith("/arquivos"), "lista de TR da compra: 3 documentos, só 1 é TR, 1 consulta GET /arquivos (simulada), nada baixado")

print("\n=== P5. etapas 3, 4 e 5 com o recorte de serviço (PDF simulado, páginas reais de N03) ===")
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "download simulado")
f.extrair_paginas = lambda caminho: (PAGS_N03, "")
botao(at, "Gerar texto para IA").click().run(); sem_excecao(at, "texto para IA (serviço)")
linha_rec = [i.value for i in at.info if str(i.value).startswith("Recorte: ")]
checa(len(linha_rec) == 1 and re.fullmatch(r"Recorte: \d+ de \d+ páginas relevantes · estimativa [\d.]+ tokens \(limite 70% = 11\.468,8\)", linha_rec[0]), f"linha do recorte (serviço): {linha_rec}")
infos = list(RODADA.glob("**/recortes/*/recorte.txt"))
cab = infos[0].read_text(encoding="utf-8").splitlines()[0] if infos else ""
checa("item pedido: simulado |" in cab, f"Pedido 13I: o seletor de páginas recebeu as palavras da DESCRIÇÃO da linha (sem as do nome do serviço): {cab[:110]!r}")
checa(tem(at, "Etapa 4 · IA:"), "Etapa 4 · IA aparece junto do texto para colar")
at.text_area(key="ficha_resposta").set_value((P1 / "fase2" / "saidas" / "N03.txt").read_text(encoding="utf-8")); at.text_input(key="ficha_pec").set_value("")
botao(at, "Conferir ficha").click().run(); sem_excecao(at, "conferir ficha (serviço)")
checa(tem(at, "6 de 6 citações literais"), "Etapa 5 funciona no fluxo de serviço (N03 da fase 2: 6 de 6 literais)")

print("\n=== P6. Produto: CSV baixado com as colunas de versão ===")
at2 = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at2.run()
at2.text_input(key="codigo_av").set_value("8435").run()
checa(any("Código 8435: NOTEBOOK" in t for t in textos(at2)), "produto: código 8435 conferido (resposta simulada)")
at2.text_input(key="at_notebook_RAM").set_value("16")
CAPT.clear(); ESTADO["chamadas"].clear(); ESTADO["produto"] = True
botao(at2, "Buscar").click().run(); sem_excecao(at2, "busca de produto")
rec2 = at2.session_state["busca_atual"]
linhas_p = list(csv.DictReader(io.StringIO(rec2["csv"].decode("utf-8-sig"), newline=""), delimiter=";")); cab_p = list(linhas_p[0])
checa(cab_p[-6:] == ["versao_app", "tipo_busca", "modo", "chamadas", "falhas", "tempo_s"], f"CSV do produto: 6 colunas AO FINAL: {cab_p[-6:]}")
checa(all(l["versao_app"] == "v4h" and l["tipo_busca"] == "produto" and l["modo"] == "rápido" and l["chamadas"] == str(rec2["resumo"]["chamadas"]) and l["tempo_s"].isdigit() for l in linhas_p), f"CSV do produto: v4h, produto, rápido, chamadas={rec2['resumo']['chamadas']}, tempo_s numérico (todas as {len(linhas_p)} linhas)")
cols_p, lin_p = csv_capturado("Baixar CSV (ordem desta tela)")
checa(cols_p is not None and len(lin_p) == len(linhas_p) and {"versao_app", "tipo_busca", "modo", "chamadas", "falhas", "tempo_s"} <= set(cols_p) and lin_p[0]["tipo_busca"] == "produto" and lin_p[0]["modo"] == "rápido",
      f"CSV do botão 'Baixar CSV' (produto) capturado: {len(lin_p)} linhas, versao_app={lin_p[0]['versao_app']!r}, modo={lin_p[0]['modo']!r}")
checa(tem(at2, "Etapa 2 · Escolher a compra: resultados (primeiro quem não tem 'não atende')"), "produto: o título da etapa 2 mantém '(primeiro quem não tem \"não atende\")'")

print("\n=== fechamento ===")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect a destino externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
checa(not ESTADO["inesperadas"], f"nenhuma URL inesperada pedida à rede simulada ({len(ESTADO['inesperadas'])})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

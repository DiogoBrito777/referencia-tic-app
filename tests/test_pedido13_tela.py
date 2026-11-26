"""v4h, Pedido 13 – config.toml, larguras/alturas dos campos, Etapa 1 do serviço alinhada à do produto (botão, Enter, arquivar e limpar só com termo novo) e a regra de
limpeza do produto SEM mudança. SEM rede (socket bloqueado, só o loopback do asyncio passa), rede trocada por respostas SIMULADAS (dados simulados só aqui), SEM Ollama.
O AppTest não expõe largura/altura dos campos; por isso as chamadas do app a text_input/text_area/columns são GRAVADAS (espião) e se confere o que o app PEDIU ao Streamlit
(width, height). Como o navegador desenha isso, NÃO dá para provar aqui: o tema, o navegador abrindo uma vez e o tamanho visual ficam NÃO VERIFICADOS sem abrir a tela.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13_tela.py   (na pasta do app)"""
import datetime as dt, json, re, socket, sys, time, tomllib
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
from streamlit.delta_generator import DeltaGenerator
from streamlit.testing.v1 import AppTest
import ferramenta as f

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

# ------------------------------------------------------------------ espião das chamadas de layout
CHAMADAS = []
def _envolve(nome, orig):
    def espia(self_ou_primeiro, *a, **k):
        CHAMADAS.append({"fn": nome, "args": a, "kw": dict(k), "primeiro": a[0] if (nome == "columns" and False) else None})
        return orig(self_ou_primeiro, *a, **k)
    return espia
for nome in ("text_input", "text_area", "columns"):
    setattr(DeltaGenerator, nome, _envolve(nome, getattr(DeltaGenerator, nome)))
def _modulo(nome):
    orig = getattr(st, nome)
    def espia(*a, **k):
        CHAMADAS.append({"fn": nome, "args": a, "kw": dict(k)}); return orig(*a, **k)
    setattr(st, nome, espia)
for nome in ("text_input", "text_area", "columns"): _modulo(nome)
def chamadas(fn, rotulo=None):
    out = []
    for c in CHAMADAS:
        if c["fn"] != fn: continue
        lab = c["args"][0] if (c["args"] and isinstance(c["args"][0], str)) else (c["args"][1] if len(c["args"]) > 1 and isinstance(c["args"][1], str) else "")
        if rotulo is None or str(lab).startswith(rotulo) or (fn == "columns" and rotulo == "*"): out.append(c)
    return out

# ------------------------------------------------------------------ config.toml
print("=== C1. .streamlit\\config.toml ===")
cfg_txt = (RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8"); cfg = tomllib.loads(cfg_txt)
checa(set(cfg.get("theme", {})) >= {"light", "dark"} and "[theme]" not in cfg_txt, "Pedido 36: tema com [theme.light] e [theme.dark] (sem bloco [theme] genérico)")
checa("browser" in cfg and set(cfg.get("theme", {})) >= {"light", "dark"}, "Pedido 36: [browser] + [theme.light]/[theme.dark] presentes ([server] não é obrigatório)")
checa(cfg.get("browser", {}).get("gatherUsageStats") is False, "[browser] gatherUsageStats = false mantido")
checa("port" not in cfg.get("server", {}) and "port" not in cfg_txt.lower(), "nenhuma porta definida no arquivo")
checa(set(cfg) - {"server"} == {"browser", "theme"}, f"Pedido 36: só [browser] e [theme] (e [server], se existir): {sorted(cfg)}")
checa(cfg_txt != (DADOS / "backups" / "config.toml__antes_pedido13").read_text(encoding="utf-8") and "[theme]" in (DADOS / "backups" / "config.toml__antes_pedido13").read_text(encoding="utf-8"), "o backup config.toml__antes_pedido13 guarda a versão com [theme]")

# ------------------------------------------------------------------ rede simulada
HOJE = dt.date.today().isoformat()
IDS = [f"92515806001192{i:03d}" for i in range(8)]
PRECOS = [1000.0, 1100.0, 1200.0, 1300.0, 1150.0, 1250.0, 1050.0, 1075.0]
ESTADO = {"chamadas": [], "inesperadas": []}
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
def get(url, params=None, binario=False):
    params = params or {}; ESTADO["chamadas"].append(url)
    if "3_consultarServico" in url:
        ESTADO.setdefault("cods", []).append(params.get("codigoItemCatalogo"))
        lote = [{"idCompra": IDS[i], "numeroItemCompra": i + 1, "descricaoItem": f"SERVICO SIMULADO {i}", "codigoItemCatalogo": 5606, "siglaUnidadeMedida": "UN", "quantidade": 1.0, "precoUnitario": PRECOS[i],
                 "nomeOrgao": "ORGAO SIMULADO", "estado": "DF", "dataCompra": HOJE, "dataResultado": HOJE} for i in range(8)]
        return 200, {"totalRegistros": 8, "paginasRestantes": 0, "resultado": lote}, {}
    if "1_consultarMaterial" in url:
        pag = params.get("pagina", 1)
        lote = [{"idCompra": f"9{(pag - 1) * 100 + i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF",
                 "descricaoItem": "NOTEBOOK i5 16 GB RAM SSD 512 GB tela 15,6 polegadas garantia 12 meses", "numeroItemCompra": i + 1, "nomePdm": "NOTEBOOK", "codigoItemCatalogo": 1000 + i} for i in range(100)]
        return 200, {"totalRegistros": 300, "resultado": lote, "paginasRestantes": 0 if pag >= 3 else 1}, {}
    if "4_consultarItemMaterial" in url:
        return 200, {"resultado": [], "totalRegistros": 0}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        return 200, {"resultado": [REG]}, {}
    if url.endswith("/arquivos"):
        return 200, [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "TR", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}], {}
    if re.search(r"/arquivos/(\d+)$", url): return 200, b"%PDF-1.4 conteudo simulado", {}
    ESTADO["inesperadas"].append(url); raise AssertionError(f"URL inesperada: {url}")
f.get = get
P1 = DADOS / "noite_2026-11-18" / "produto_p1"
PAGS_N03 = json.loads((next((P1 / "fase2" / "trabalho" / "recortes").glob("N03*")) / "paginas.json").read_text(encoding="utf-8"))
TMP = DADOS / "tmp_teste_fase4"; TMP.mkdir(exist_ok=True)
RODADA = TMP / f"p13_{int(time.time())}"; RODADA.mkdir(); f.PASTA = RODADA

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
    for lista in (at.warning, at.success, at.error, at.info, at.markdown, at.caption, at.subheader):
        s += [str(e.value) for e in lista]
    return s
def tem(at, t): return any(t in x for x in textos(at))
def botao(at, rotulo): return next(b for b in at.button if b.label == rotulo)
def sem_excecao(at, onde): checa(len(at.exception) == 0, f"{onde}: sem exceção" + ("" if not at.exception else f" -> {[e.value for e in at.exception]}"))

print("\n=== L1. produto: larguras, UF, atributos (o que o app pede ao Streamlit) ===")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); sem_excecao(at, "abertura")
col_busca = [c for c in chamadas("columns", "*") if c["args"] and c["args"][0] == [2, 1] and c["kw"].get("vertical_alignment") == "bottom"]
checa(len(col_busca) >= 1, f"produto: linha do campo de busca + botão com colunas [2, 1] dentro da coluna da Etapa 1 ({len(col_busca)} chamada(s))")
at.text_input(key="codigo_av").set_value("8435").run()
at.text_input(key="at_notebook_RAM").set_value("16")
uf_p = [c for c in chamadas("text_input", "UF") if c["kw"].get("key") == "uf_busca"]
checa(uf_p and all(c["kw"].get("width") == 100 for c in uf_p), "produto: UF (rótulo curto \"UF\") com width=100")
col_uf = [c for c in chamadas("columns", "*") if c["args"] and c["args"][0] == [2, 1] and "vertical_alignment" not in c["kw"]]
checa(len(col_uf) >= 1, "produto: Modo + UF na mesma linha (colunas [2, 1])")
n_attr = len([k for k in at.text_input if k.key and k.key.startswith("at_notebook_")])
col_attr = [c for c in chamadas("columns", "*") if c["args"] and c["args"][0] == n_attr and c["kw"].get("width") == 170 * n_attr]
checa(n_attr >= 2 and len(col_attr) >= 1, f"produto: {n_attr} campos de atributo em colunas estreitas (width={170 * n_attr})")

print("\n=== S1. serviço: Etapa 1 alinhada à do produto ===")
at.radio(key="tipo_busca").set_value("Serviço").run(); sem_excecao(at, "troca para Serviço")
checa(any(b.label == "Procurar no catálogo" for b in at.button), "serviço: botão 'Procurar no catálogo' (mesmo texto do produto) ao lado do campo")
col_serv = [c for c in chamadas("columns", "*") if c["args"] and c["args"][0] == [2, 1] and c["kw"].get("vertical_alignment") == "bottom"]
checa(len(col_serv) >= 2, f"serviço: mesma linha campo + botão [2, 1] do produto (produto + serviço: {len(col_serv)} chamadas)")
uf_s = [c for c in chamadas("text_input", "UF") if c["kw"].get("key") == "serv_uf"]
checa(uf_s and all(c["kw"].get("width") == 100 for c in uf_s), "serviço: UF com width=100")
checa(not at.multiselect and not any("serviço(s) encontrado(s)" in str(c.value) for c in at.caption), "antes de procurar: nenhuma lista de serviços na tela (e não há multiselect no serviço)")
n0 = len(ESTADO["chamadas"])
at.text_input(key="serv_termo").set_value("instalação elétrica").run(); sem_excecao(at, "Enter no campo de serviço")
n_lista = next((int(re.match(r"(\d+) serviço", str(c.value)).group(1)) for c in at.caption if re.match(r"\d+ serviço\(s\) encontrado", str(c.value))), 0)
checa(0 < n_lista <= 40 and not at.multiselect, f"depois do Enter a lista aparece ({n_lista} serviços, no máximo 40), sem multiselect")
checa(tem(at, "Procurado: instalação elétrica"), "mostra 'Procurado: instalação elétrica'")
checa(len(ESTADO["chamadas"]) == n0, f"procurar no catálogo de serviços não faz chamada de rede nem conta compras ({len(ESTADO['chamadas']) - n0} chamadas)")
marca_servicos(at, "instalação elétrica", ["5606", "21687"])
checa(codigos_marcados(at) == "21687, 5606", f"marcou 2 códigos na coluna 'usar' ({codigos_marcados(at)})")
botao(at, "Buscar compras do serviço").click().run(); sem_excecao(at, "busca de serviço (simulada)")
checa("busca_atual" in at.session_state and at.session_state["busca_atual"].get("tipo") == "serviço", "busca de serviço ficou na tela (Etapas 2 a 5 seguem como antes)")
checa(len(at.session_state["historico"] if "historico" in at.session_state else []) == 0, "histórico vazio até agora")
# mesmo termo (botão): não limpa
botao(at, "Procurar no catálogo").click().run(); sem_excecao(at, "mesmo termo, botão")
checa("busca_atual" in at.session_state and len(at.session_state["historico"] if "historico" in at.session_state else []) == 0 and codigos_marcados(at) == "21687, 5606",
      "mesmo termo: NÃO arquiva, NÃO limpa os resultados e mantém os códigos marcados")
# (igual ao produto, a comparação usa ferramenta.norm: um espaço a mais no fim já conta como termo novo; o mesmo texto não gera nova procura)
# termo novo: arquiva e limpa
n1 = len(ESTADO["chamadas"])
at.text_input(key="serv_termo").set_value("limpeza").run(); sem_excecao(at, "termo novo + Enter")
hist = at.session_state["historico"] if "historico" in at.session_state else []
checa(len(hist) == 1 and hist[0].get("tipo") == "serviço" and "busca_atual" not in at.session_state, f"termo novo: a busca atual foi para 'Buscas anteriores' ({len(hist)} no histórico) e a tela ficou sem resultado")
checa(codigos_marcados(at) == "nenhum (marque na coluna usar)" and tem(at, "Procurado: limpeza"), "termo novo: os códigos marcados saíram e a nova lista é de 'limpeza'")
checa(len(ESTADO["chamadas"]) == n1, "termo novo: nenhuma chamada de rede")
checa("docs" not in at.session_state and "canal_oficial" not in at.session_state, "termo novo: documentos e canal oficial do serviço anterior saíram")

print("\n=== S2. Etapas 3 a 5 do serviço (inalteradas) e alturas das caixas ===")
at.text_input(key="serv_termo").set_value("instalação elétrica").run()
marca_servicos(at, "instalação elétrica", ["5606"]); botao(at, "Buscar compras do serviço").click().run(); sem_excecao(at, "2ª busca de serviço")
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "download simulado")
f.extrair_paginas = lambda caminho: (PAGS_N03, "")
botao(at, "Gerar texto para IA").click().run(); sem_excecao(at, "texto para IA")
checa(any(str(i.value).startswith("Recorte: ") for i in at.info) and tem(at, "Etapa 4 · IA:"), "Etapas 3 e 4 como antes (linha do recorte e marcador da IA)")
h_ia = [c["kw"].get("height") for c in chamadas("text_area", "Texto para colar na IA")]
h_resp = [c["kw"].get("height") for c in chamadas("text_area", "Cole aqui a resposta da IA")]
checa(h_ia and set(h_ia) == {150}, f"'Texto para colar na IA': height=150 em todas as chamadas {set(h_ia)}")
checa(h_resp and set(h_resp) == {120}, f"caixa da resposta da IA: height=120 em todas as chamadas {set(h_resp)}")
checa(tem(at, "Etapa 5 · Conferir ficha (sem IA)"), "Etapa 5 continua na tela")

print("\n=== S3. serviço (Pedido 13B): caixa azul, legenda de teste com rede e opção avançada (código digitado) ===")
at.text_input(key="serv_termo").set_value("vigilância").run(); sem_excecao(at, "termo novo (vigilância)")
checa(any("Nenhuma busca nesta sessão. Procure o serviço" in str(i.value) and "atributo" not in str(i.value) for i in at.info), "caixa azul do serviço tem texto próprio e NÃO menciona atributos")
checa(not any("Testado com rede" in str(c.value) or "NÃO testado com rede" in str(c.value) or "tamanhoPagina" in str(c.value) for c in at.caption), "Pedido 13G: nenhum texto de status de teste na tela do serviço (o parágrafo 'Testado com rede' saiu)")
checa(not any("NÃO TESTADO COM REDE" in str(c.value) and "Catálogo oficial de serviços" in str(c.value) for c in at.caption), "a legenda antiga 'NÃO TESTADO COM REDE' do catálogo saiu")
for txt, esperado in (("abc", "só números"), ("99999999", "fora do catálogo local"), ("1,2,3,4,5,6,7", "No máximo 6")):
    at.text_input(key="serv_codigo_av").set_value(txt).run()
    checa(any(esperado in str(e.value) for e in at.error), f"opção avançada do serviço, '{txt}': erro '{esperado}' (sem rede)")
at.text_input(key="serv_codigo_av").set_value("5606, 22977").run()
checa(any(str(m.value).startswith("Código(s) no catálogo local: 5606 –") and "22977 –" in str(m.value) for m in at.success), "opção avançada do serviço, '5606, 22977': confere contra o catálogo local e mostra os nomes")
ESTADO["cods"] = []
botao(at, "Buscar compras do serviço").click().run(); sem_excecao(at, "busca com código digitado")
checa(ESTADO["cods"] == ["5606", "22977"] and at.session_state["busca_atual"]["codigos"] == "5606, 22977", f"a busca usou os códigos digitados {ESTADO['cods']} (e não os marcados)")
at.text_input(key="serv_codigo_av").set_value("").run()

print("\n=== S4. serviço (Pedido 13C): limite de 6 marcados na tabela 'usar' e código digitado substitui os marcados ===")
at.text_input(key="serv_termo").set_value("manutenção elétrica").run(); sem_excecao(at, "termo novo (manutenção elétrica)")
sete = [str(r["codigoServico"]) for r in _sv_teste.procurar("manutenção elétrica", _sv_teste.ler_catalogo())][:7]
marca_servicos(at, "manutenção elétrica", sete)
ordem_tab = [c for c in [str(r["codigoServico"]) for r in _sv_teste.procurar("manutenção elétrica", _sv_teste.ler_catalogo())] if c in sete][:6]
checa(codigos_marcados(at) == ", ".join(ordem_tab) and len(sete) == 7, f"7 marcados: 'Códigos marcados' mostra só os 6 primeiros ({codigos_marcados(at)})")
checa(any("Você marcou 7 códigos; o limite é 6" in str(w.value) for w in at.warning), "mensagem ao passar de 6: 'Você marcou 7 códigos; o limite é 6...'")
ESTADO["cods"] = []
botao(at, "Buscar compras do serviço").click().run(); sem_excecao(at, "busca com 7 marcados")
checa(ESTADO["cods"] == ordem_tab, f"a busca usou só os 6 primeiros marcados {ESTADO['cods']}")
at.text_input(key="serv_codigo_av").set_value("5606").run(); ESTADO["cods"] = []
botao(at, "Buscar compras do serviço").click().run(); sem_excecao(at, "código digitado + marcados")
checa(ESTADO["cods"] == ["5606"], f"o código digitado substitui os marcados (como no produto): {ESTADO['cods']}")
at.text_input(key="serv_codigo_av").set_value("").run()

print("\n=== P1. produto: a regra de limpeza NÃO mudou (termo novo arquiva e limpa; mesmo termo não) ===")
at2 = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at2.run()
def semeia(at_, rotulo):
    cab_ = "linha;orgao;uf;data_publicacao;data_resultado;data_usada_no_filtro;controle_pncp;numero_item;descricao_item;preco_unitario_homologado;atributos_atendidos;observacao_preco;situacao_pncp;status_item_pncp;valor_estimado_pncp;link_publico;fonte_api_resultado;cnpj;ano;sequencial;id_compra"
    lin_ = "1;ORGAO SIMULADO;DF;2026-11-01;2026-11-02;data do resultado;;1;ITEM SIMULADO;100.0;0 de 0;;sem PNCP;;;;;;;;123"
    at_.session_state["busca_atual"] = {"resumo": {"arquivo": "x.csv", "pedidos": {}}, "csv": (cab_ + "\n" + lin_ + "\n").encode("utf-8"), "quando": rotulo, "aceitar": False, "fim_txt": "", "log": "", "tempo": 0.0, "codigos": "0", "termo": "t", "eh_item": True}
checa(any("Nenhuma busca nesta sessão. Procure, marque um código, preencha os atributos" in str(i.value) for i in at2.info), "caixa azul do produto continua mencionando os atributos")
semeia(at2, "busca A")
at2.text_input(key="termo").set_value("notebook").run()
botao(at2, "Procurar no catálogo").click().run(); sem_excecao(at2, "produto: procurar 'notebook'")
h2 = at2.session_state["historico"] if "historico" in at2.session_state else []
checa(len(h2) == 1 and "busca_atual" not in at2.session_state and "pdms" in at2.session_state, f"produto: termo novo arquivou a busca atual ({len(h2)} no histórico) e procurou")
semeia(at2, "busca B")
botao(at2, "Procurar no catálogo").click().run(); sem_excecao(at2, "produto: mesmo termo")
checa("busca_atual" in at2.session_state and len(at2.session_state["historico"]) == 1, "produto: mesmo termo NÃO arquivou nem limpou (a busca B continua na tela)")
at2.text_input(key="termo").set_value("monitor").run(); botao(at2, "Procurar no catálogo").click().run(); sem_excecao(at2, "produto: termo novo")
checa("busca_atual" not in at2.session_state and len(at2.session_state["historico"]) == 2, "produto: termo novo de novo arquivou (2 no histórico) e limpou")

print("\n=== fechamento ===")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
checa(not ESTADO["inesperadas"], f"nenhuma URL inesperada na rede simulada ({len(ESTADO['inesperadas'])})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

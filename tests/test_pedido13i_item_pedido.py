"""v4h, Pedido 13I, PARTE B – "Item pedido" por item (Windows ≠ Office, mesmo código de serviço). OFFLINE: socket bloqueado, rede trocada por respostas SIMULADAS.
Prova: (1) funções puras (servicos.item_pedido_inicial / item_para_recorte); (2) na TELA do serviço, duas linhas da MESMA compra e do MESMO código (27499) com descrições
diferentes (Windows 11 Pro / Office LTSC Standard 2024) mostram 'Item pedido' diferente e geram PRIMEIRA LINHA do texto diferente; (3) o recorte REAL (seletor de páginas + guarda
de 70% da janela) com o TR local 4_137_2026 (CÓPIA só leitura) e com um texto SIMULADO de páginas separadas: páginas incluídas, tokens estimados e posição de cada página no ranking;
(4) sem descrição própria: avisa e usa as palavras do catálogo; (5) produto: o campo existe e passa o valor de sempre; (6) o que a pessoa digita com '|' vai como digitado.
Grava pedido13i\\resultado_parte_b.json (números do relatório). Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13i_item_pedido.py   (na pasta do app)"""
import csv, datetime as dt, hashlib, io, json, re, shutil, socket, sys, time, unicodedata
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
norm = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
TMP = DADOS / "tmp_teste_fase4" / f"p13i_b_{int(time.time())}"; TMP.mkdir(parents=True)
f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
RESULTADO = {}

# ------------------------------------------------------------------ o TR real (CÓPIA, só leitura)
TR_ORIG = next(DADOS.glob("saida/sessoes/*/recortes/4_137_2026/paginas.json"), None)
PAGS_REAL = None
if TR_ORIG:
    copia = TMP / "TR_4_137_2026_paginas.json"; shutil.copyfile(TR_ORIG, copia); sha_orig = sha(TR_ORIG)
    PAGS_REAL = json.loads(copia.read_text(encoding="utf-8"))
print(f"TR 4_137_2026 local: {'achado (' + str(len(PAGS_REAL)) + ' páginas, cópia em pasta de teste)' if PAGS_REAL else 'NÃO ACHADO: só o texto simulado'}")

# ------------------------------------------------------------------ rede SIMULADA: 8 linhas do código 27499; as 2 primeiras são os dois itens da mesma compra
HOJE = dt.date.today().isoformat()
DESC_W = "Licença Microsoft Windows 11 PRO ou superior (licenciamento perpétuo) fornecido em mídia digital, para estações de trabalho"
DESC_O = "Programas de computador - Microsoft Office LTSC Standard 2024 para Windows, 64 bits, em português (Brasil)"
ESTADO = {"descricoes": {0: DESC_W, 1: DESC_O}, "ligar": False}
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "TR", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]
def get(url, params=None, binario=False):          # qualname 'get'
    params = params or {}
    if "3_consultarServico" in url:
        lote = [{"idCompra": "92515806001192025" if i < 2 else f"9251580600119{i:04d}", "numeroItemCompra": i + 1, "descricaoItem": ESTADO["descricoes"].get(i, f"SERVICO SIMULADO {i}"),
                 "codigoItemCatalogo": 27499, "siglaUnidadeMedida": "UN", "quantidade": 10.0, "precoUnitario": 800.0 + 100 * i, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF",
                 "dataCompra": HOJE, "dataResultado": HOJE} for i in range(8)]
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

def textos(at):
    s = []
    for lista in (at.warning, at.success, at.error, at.info, at.markdown, at.caption, at.subheader):
        s += [str(e.value) for e in lista]
    return s
def botao(at, rotulo): return next(b for b in at.button if b.label == rotulo)
def sem_excecao(at, onde): checa(len(at.exception) == 0, f"{onde}: sem exceção" + ("" if not at.exception else f" -> {[e.value for e in at.exception]}"))
def campo_item(at): return next(t for t in at.text_input if t.label.startswith("Item pedido"))
def linha_de(at, trecho):
    rec = at.session_state["busca_atual"]
    return int(next(r["linha"] for r in csv.DictReader(io.StringIO(rec["csv"].decode("utf-8-sig")), delimiter=";") if trecho in r["descricao_item"]))

# ------------------------------------------------------------------ B1. funções puras
print("\n=== B1. funções puras ===")
NOME_27499 = [r["nomeServico"] for r in sv.ler_catalogo() if r["codigoServico"] == "27499"]
ini_w, ini_o = sv.item_pedido_inicial(DESC_W, NOME_27499), sv.item_pedido_inicial(DESC_O, NOME_27499)
no_nome = {t for n in NOME_27499 for t in sv._tokens(n)}
pal = lambda s: [w for w in re.findall(r"[a-zà-ÿ0-9]+", s.lower())]
checa(ini_w != ini_o and "windows 11 pro" in ini_w and "office ltsc standard 2024" in ini_o, f"iniciais diferentes: Windows {ini_w!r} | Office {ini_o!r}")
checa(not any(sv.f.singular(norm(w)) in no_nome or norm(w) in no_nome for w in pal(ini_w) + pal(ini_o)), f"nenhuma palavra do nome do serviço do catálogo ({NOME_27499[0][:40]}...) sobrou")
checa(len(pal(ini_w)) <= 12 and len(pal(ini_o)) <= 12, f"até 12 palavras ({len(pal(ini_w))} e {len(pal(ini_o))})")
checa(sv.item_pedido_inicial("", NOME_27499) == "" and sv.item_pedido_inicial("LICENCIAMENTO DE OUTROS DIREITOS PERMANENTES SOBRE PROGRAMASDE COMPUTADOR", NOME_27499) == "", "sem descrição, ou descrição que só repete o nome do serviço: '' (o app usa o catálogo e avisa)")
rw, ro = sv.item_para_recorte(ini_w, ["Notebook"]), sv.item_para_recorte(ini_o, ["Notebook"])
checa(rw != ro and rw.split("|")[0] == "windows 11 pro" and "office" in ro.split("|") and "ltsc" in ro.split("|") and " |" not in rw + ro and "windows 11 pro" not in ro.split("|"), f"para o seletor: Windows {rw!r} | Office {ro!r}")
checa(sv.item_para_recorte("Notebook", ["Notebook"]) == "Notebook" and sv.item_para_recorte("windows 11 pro|office ltsc", []) == "windows 11 pro|office ltsc" and sv.item_para_recorte("", []) == "",
      "produto igual ao de config\\produtos.csv passa como estava; com '|' vai como digitado; vazio = vazio")
RESULTADO["iniciais"] = {"windows": ini_w, "office": ini_o}; RESULTADO["para_o_seletor"] = {"windows": rw, "office": ro}

# ------------------------------------------------------------------ recorte: ranking e números
def carrega_apoio():
    import importlib.util
    spec = importlib.util.spec_from_file_location("recorte_teste_ia_b", f.RECORTE_PY); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m.APOIO
APOIO = carrega_apoio()
def numeros(paginas, item, pasta_recorte):
    """Posição de cada página no ranking (mesma ordem de inclusão do seletor) + o que o app manteve (recorte_info.json)."""
    alts = [w.strip() for w in item.split("|") if w.strip()] if "|" in item else [item]
    rx = "|".join(re.escape(norm(w)) for w in alts if len(norm(w)) >= 2)
    ordem = f.ranking_recorte.ordem_de_inclusao(paginas, rx, APOIO)
    info = json.loads((pasta_recorte / "recorte_info.json").read_text(encoding="utf-8"))
    return {"item": item, "ordem_de_inclusao": ordem, "posicao": {p: i + 1 for i, p in enumerate(ordem)}, "relevantes": info["relevantes"], "mantidas": info["mantidas"], "fora": info["fora"],
            "tokens_estimados": info["estimativa"], "limite_tokens": info["limite"], "acima_do_limite": info["acima_do_limite"], "reduzido": info["reduzido"]}

def roda_linha(paginas, trecho_descricao, item_digitado=None):
    """Abre a tela do serviço, busca o código 27499, escolhe a linha cuja descrição tem 'trecho', baixa o documento (simulado) e gera o texto. Devolve (at, item_do_campo, cabeçalho, pasta)."""
    f.extrair_paginas = lambda caminho: (paginas, "")
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
    at.text_input(key="serv_codigo_av").set_value("27499").run()
    botao(at, "Buscar compras do serviço").click().run(); sem_excecao(at, "busca do código 27499")
    sel = [s for s in at.selectbox if s.label == "Linha" and s.key != "canal_linha"][0]
    k = next(i for i, o in enumerate(sel.options) if norm(trecho_descricao) in norm(o))      # a opção mostra "N – órgão – descrição" (60 primeiros caracteres)
    sel.select_index(k).run()
    n = int(re.match(r"\d+", sel.options[k]).group(0))
    ESTADO["ligar"] = True; botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, f"baixar documentos da linha {n}")
    item_campo = campo_item(at).value
    if item_digitado is not None:
        campo_item(at).set_value(item_digitado).run()
    botao(at, "Gerar texto para IA").click().run(); sem_excecao(at, f"gerar texto da linha {n}")
    pasta = max((p.parent for p in f.PASTA.glob("**/recortes/*/recorte.txt")), key=lambda p: (p / "recorte.txt").stat().st_mtime)
    cab = (pasta / "recorte.txt").read_text(encoding="utf-8").splitlines()[0]
    ia = max(f.PASTA.glob("**/para_ia/*_PARA_IA.txt"), key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")
    return at, item_campo, cab, pasta, ia, n

PAGS_SIM = None
def monta_simulado():
    """Texto SIMULADO. As páginas dos itens NÃO têm 'garantia' nem 'prazo de entrega' (o seletor reserva as páginas com mais garantia e prazo, desempatando pela maior, sem olhar o item):
    essas cláusulas ficam em páginas gerais, para o que decide a ordem das páginas dos itens ser o item pedido."""
    base = "Texto de apoio do documento simulado, sem relação com os itens pedidos. " * 3
    pag = [base + "Página inicial com o objeto da contratação."]
    pag += [f"Item 1 – Licença do sistema operacional Microsoft Windows 11 Pro de 64 bits. Descrição: licença perpétua do Windows 11 Pro, mídia digital, para estações de trabalho. {base}" for _ in range(3)]
    pag += [f"Item 2 – Microsoft Office LTSC Standard 2024 para Windows. Descrição: pacote Office LTSC Standard 2024, licença perpétua, em português do Brasil. {base}" for _ in range(3)]
    pag += [f"Garantia: 12 (doze) meses para todos os itens. {base}", f"Prazo de entrega: 30 dias após a ordem de serviço. {base}"]
    pag += [f"Cláusula geral {i}. {base}" for i in range(4)]
    return pag
PAGS_SIM = monta_simulado()
W_SIM, O_SIM = {2, 3, 4}, {5, 6, 7}

print("\n=== B2. TELA do serviço, TEXTO SIMULADO de páginas (Windows nas pgs 2-4, Office nas pgs 5-7) ===")
at_w, item_w, cab_w, pasta_w, ia_w, n_w = roda_linha(PAGS_SIM, "Windows 11")
num_w = numeros(PAGS_SIM, sv.item_para_recorte(item_w, []), pasta_w)
at_o, item_o, cab_o, pasta_o, ia_o, n_o = roda_linha(PAGS_SIM, "Office LTSC")
num_o = numeros(PAGS_SIM, sv.item_para_recorte(item_o, []), pasta_o)
checa(n_w != n_o, f"duas linhas da mesma compra e do mesmo código: linhas {n_w} (Windows) e {n_o} (Office)")
checa(item_w == ini_w and item_o == ini_o and item_w != item_o, f"campo 'Item pedido' mostra a descrição própria sem as palavras do catálogo: {item_w!r} | {item_o!r}")
l1w, l1o = ia_w.splitlines()[0] if ia_w else "", ia_o.splitlines()[0] if ia_o else ""
cab_ia = lambda t: next((l for l in t.splitlines() if "item pedido:" in l), "")
checa(cab_w != cab_o and "item pedido: windows 11 pro|" in cab_w and "item pedido: microsoft|office|ltsc" in cab_o.replace("programas|", ""), f"PRIMEIRA LINHA do recorte diferente: {cab_w[:90]!r} | {cab_o[:90]!r}")
checa(cab_ia(ia_w) != cab_ia(ia_o) and "item pedido: windows 11 pro / " in cab_ia(ia_w), f"a linha 'item pedido' do TEXTO PARA A IA também difere: {cab_ia(ia_w)[:70]!r} | {cab_ia(ia_o)[:70]!r}")   # Pedido 28: no texto da IA o '|' do item vira ' / '
item_guardado_w = (re.search(r"item pedido: (.+?) \|", cab_w) or [None, ""])[1]
checa(item_guardado_w.startswith("windows 11 pro|") and " / " not in item_guardado_w and "item pedido: windows 11 pro|" in (pasta_w / "recorte.txt").read_text(encoding="utf-8"), f"Pedido 28: o item GUARDADO (cabeçalho do recorte.txt, o que conferir_tela.ler_recorte lê) continua com '|' e sem ' / ': {item_guardado_w[:60]!r}")
checa(any(t.startswith("Item pedido: windows 11 pro|") for t in textos(at_w)) and any(t.startswith("Item pedido: ") and "ltsc" in t for t in textos(at_o)), "'Item pedido: …' aparece no resumo do recorte (tela)")
pos = lambda num, pgs: sorted(num["posicao"][p] for p in pgs if p in num["posicao"])
print("  Windows:", {k: num_w[k] for k in ("item", "ordem_de_inclusao", "relevantes", "mantidas", "tokens_estimados")})
print("  Office :", {k: num_o[k] for k in ("item", "ordem_de_inclusao", "relevantes", "mantidas", "tokens_estimados")})
checa(max(pos(num_w, W_SIM)) < min(pos(num_w, O_SIM) or [99]) and max(pos(num_o, O_SIM)) < min(pos(num_o, W_SIM) or [99]),
      f"no ranking, as páginas do item vêm antes das do outro item nos dois recortes: Windows (pgs 2-4 nas posições {pos(num_w, W_SIM)}, pgs 5-7 nas {pos(num_w, O_SIM)}) | Office (pgs 5-7 nas {pos(num_o, O_SIM)}, pgs 2-4 nas {pos(num_o, W_SIM)})")
checa(set(num_w["mantidas"]) >= W_SIM and set(num_o["mantidas"]) >= O_SIM and not num_w["acima_do_limite"] and not num_o["acima_do_limite"], f"cada recorte mantém as páginas do seu item e fica dentro do limite de {num_w['limite_tokens']:,.1f} tokens (estimativas {num_w['tokens_estimados']} e {num_o['tokens_estimados']})".replace(",", "X").replace(".", ",").replace("X", "."))
RESULTADO["simulado"] = {"windows": num_w, "office": num_o, "paginas_windows": sorted(W_SIM), "paginas_office": sorted(O_SIM)}

print("\n=== B3. TELA do serviço, TR REAL 4_137_2026 (cópia) ===")
if PAGS_REAL:
    txt_pg = lambda pad: [i + 1 for i, p in enumerate(PAGS_REAL) if re.search(pad, norm(p))]
    pg_win, pg_off = txt_pg(r"windows ?11 ?pro"), txt_pg(r"office ?ltsc")
    print(f"  páginas do TR com 'windows 11 pro': {pg_win} | com 'office ltsc': {pg_off} (de {len(PAGS_REAL)})")
    at_w2, item_w2, cab_w2, pasta_w2, ia_w2, _ = roda_linha(PAGS_REAL, "Windows 11")
    at_o2, item_o2, cab_o2, pasta_o2, ia_o2, _ = roda_linha(PAGS_REAL, "Office LTSC")
    nw, no = numeros(PAGS_REAL, sv.item_para_recorte(item_w2, []), pasta_w2), numeros(PAGS_REAL, sv.item_para_recorte(item_o2, []), pasta_o2)
    checa(cab_w2 != cab_o2, f"TR real: primeira linha do recorte diferente: {cab_w2[:80]!r} | {cab_o2[:80]!r}")
    print("  Windows:", {k: nw[k] for k in ("item", "ordem_de_inclusao", "relevantes", "mantidas", "fora", "tokens_estimados", "limite_tokens")})
    print("  Office :", {k: no[k] for k in ("item", "ordem_de_inclusao", "relevantes", "mantidas", "fora", "tokens_estimados", "limite_tokens")})
    checa(not nw["acima_do_limite"] and not no["acima_do_limite"] and nw["tokens_estimados"] <= nw["limite_tokens"] and no["tokens_estimados"] <= no["limite_tokens"], f"TR real: estimativas dentro do limite de 70% (11.468,8): {nw['tokens_estimados']} e {no['tokens_estimados']}")
    ANTES = "licenciamento|direitos|permanentes|sobre|programasde|computador"      # o item de ANTES do Pedido 13I (palavras do nome do serviço, igual para todas as linhas do código)
    _, _, cab_a1, pasta_a1, _, _ = roda_linha(PAGS_REAL, "Windows 11", ANTES); na1 = numeros(PAGS_REAL, ANTES, pasta_a1)
    _, _, cab_a2, pasta_a2, _, _ = roda_linha(PAGS_REAL, "Office LTSC", ANTES); na2 = numeros(PAGS_REAL, ANTES, pasta_a2)
    checa(cab_a1.split("|", 2)[1] == cab_a2.split("|", 2)[1] and na1["mantidas"] == na2["mantidas"], f"controle (jeito de ANTES): as duas linhas geram a MESMA primeira linha e as MESMAS páginas {na1['mantidas']} (tokens {na1['tokens_estimados']})")
    print("  ANTES  :", {k: na1[k] for k in ("item", "ordem_de_inclusao", "relevantes", "mantidas", "fora", "tokens_estimados")})
    RESULTADO["tr_real_antes"] = na1
    # a pessoa edita o campo (separando com |) para o que identifica o item: o que muda no recorte
    _, _, cab_e1, pasta_e1, _, _ = roda_linha(PAGS_REAL, "Windows 11", "windows 11 pro"); ne1 = numeros(PAGS_REAL, sv.item_para_recorte("windows 11 pro", []), pasta_e1)
    _, _, cab_e2, pasta_e2, _, _ = roda_linha(PAGS_REAL, "Office LTSC", "office ltsc"); ne2 = numeros(PAGS_REAL, sv.item_para_recorte("office ltsc", []), pasta_e2)
    print("  EDITADO Windows ('windows 11 pro'):", {k: ne1[k] for k in ("ordem_de_inclusao", "relevantes", "mantidas", "fora", "tokens_estimados")})
    print("  EDITADO Office  ('office ltsc')   :", {k: ne2[k] for k in ("ordem_de_inclusao", "relevantes", "mantidas", "fora", "tokens_estimados")})
    checa(not ne1["acima_do_limite"] and not ne2["acima_do_limite"] and "item pedido: windows 11 pro|windows |" in cab_e1 and "item pedido: office|ltsc |" in cab_e2, f"TR real, item editado pela pessoa: primeira linha leva o que foi digitado; estimativas {ne1['tokens_estimados']} e {ne2['tokens_estimados']} dentro do limite")
    RESULTADO["tr_real_editado"] = {"windows_11_pro": ne1, "office_ltsc": ne2}
    checa(sha(TR_ORIG) == sha_orig, "o TR original em saida\\sessoes não foi tocado (hash igual; o teste só leu uma cópia)")
    RESULTADO["tr_real"] = {"paginas_no_tr": len(PAGS_REAL), "paginas_com_windows_11_pro": pg_win, "paginas_com_office_ltsc": pg_off, "windows": nw, "office": no}
else:
    print("  (sem TR local: NÃO VERIFICADO com PDF real)"); RESULTADO["tr_real"] = "NÃO VERIFICADO: TR local não encontrado"

print("\n=== B4. linha SEM descrição própria: avisa e usa as palavras do catálogo ===")
ESTADO["descricoes"] = {i: "" for i in range(8)}      # nenhuma linha traz descrição própria
at_v, item_v, cab_v, _, _, n_v = roda_linha(PAGS_SIM, "")
txt_v = textos(at_v)
checa(any("não traz descrição própria" in t for t in txt_v), "aviso na tela: a linha não traz descrição própria do item (usei as palavras do nome do serviço)")
checa(item_v and "programasde" in norm(item_v) or "licenciamento" in norm(item_v), f"valor inicial = palavras do nome do serviço do catálogo: {item_v!r}")
RESULTADO["sem_descricao"] = {"item": item_v, "primeira_linha": cab_v[:120]}
ESTADO["descricoes"] = {0: DESC_W, 1: DESC_O}

print("\n=== B5. o que a pessoa digita com '|' vai como digitado ===")
f.extrair_paginas = lambda caminho: (PAGS_SIM, "")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
at.text_input(key="serv_codigo_av").set_value("27499").run(); botao(at, "Buscar compras do serviço").click().run()
ESTADO["ligar"] = True; botao(at, "Baixar documentos da linha").click().run()
campo_item(at).set_value("windows 11 pro|licença perpétua").run()
botao(at, "Gerar texto para IA").click().run(); sem_excecao(at, "gerar com item digitado")
pasta = max((p.parent for p in f.PASTA.glob("**/recortes/*/recorte.txt")), key=lambda p: (p / "recorte.txt").stat().st_mtime)
cab = (pasta / "recorte.txt").read_text(encoding="utf-8").splitlines()[0]
checa("item pedido: windows 11 pro|licenca perpetua |" in norm(cab).replace("licença", "licenca").replace("perpétua", "perpetua") or "item pedido: windows 11 pro|licença perpétua |" in cab, f"item com '|': {cab[:100]!r}")
campo_item(at).set_value("").run(); botao(at, "Gerar texto para IA").click().run()
checa(any("item pedido está vazio" in str(e.value) for e in at.error), "item vazio: mensagem pedindo para escrever o item (e o painel diz 'Falhou')")

print("\n=== B6. PRODUTO: o campo existe e o valor inicial é o que já era ===")
ESTADO["ligar"] = False
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
at.text_input(key="codigo_av").set_value("8435").run(); at.text_input(key="at_notebook_RAM").set_value("16")
botao(at, "Buscar").click().run(); sem_excecao(at, "produto: buscar")
rec = at.session_state["busca_atual"]; esperado = rec.get("item_recorte") or rec["resumo"].get("produto") or rec["resumo"].get("nome_no_catalogo") or "notebook"
ESTADO["ligar"] = True; botao(at, "Baixar documentos da linha").click().run()
checa(campo_item(at).value == esperado, f"produto: 'Item pedido' inicial = o que já era ({esperado!r})")
botao(at, "Gerar texto para IA").click().run(); sem_excecao(at, "produto: gerar texto")
pasta = max((p.parent for p in f.PASTA.glob("**/recortes/*/recorte.txt")), key=lambda p: (p / "recorte.txt").stat().st_mtime)
cab = (pasta / "recorte.txt").read_text(encoding="utf-8").splitlines()[0]
checa(f"item pedido: {esperado} |" in cab, f"produto: a 1ª linha do recorte leva o item de sempre: {cab[:90]!r}")
RESULTADO["produto"] = {"item_inicial": esperado, "primeira_linha": cab[:120]}

checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
(DADOS / "pedido13i").mkdir(exist_ok=True)
(DADOS / "pedido13i" / "resultado_parte_b.json").write_text(json.dumps(RESULTADO, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

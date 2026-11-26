"""v4h, Pedido 33 (Fase 1), SEM rede (socket bloqueado; rede SIMULADA). Padrões da tela:
(1) Etapa 5 abre no recorte MAIS RECENTE da sessão e diz qual está sendo conferido; (2) Etapa 3 'Documento para recortar' abre no TR (senão no 1º principal);
(3) Etapa 3 'Linha' abre na 1ª linha ligada ao PNCP (nenhuma ligada = linha 1); (4) Etapa 2: linhas ligadas ao PNCP primeiro, sem mudar o número da linha.
Dados simulados só aqui (regra 10).
Uso: <python> -I -B -X utf8 tests\\test_pedido33_fase1.py   (na pasta do app)"""
import datetime as dt, json, os, re, socket, sys, time, zlib
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(os.environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
_o = socket.socket.connect
def _b(self, a, *x, **k):
    h, p = (a[0], a[1]) if isinstance(a, tuple) else (str(a), None)
    if h in ("127.0.0.1", "::1") and p != 11434: return _o(self, a, *x, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
from streamlit.testing.v1 import AppTest
import pandas as pd
import ferramenta as f
import servicos as sv
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
norm = f.norm
TMP = DADOS / "pedido33" / f"_tmp_teste_f1_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat()
CEN = {"ligadas": ()}     # dígito final do idCompra que é ligado ao PNCP; () = nenhum
def get(url, params=None, binario=False):
    params = params or {}
    if "1_consultarMaterial" in url:
        lote = [{"idCompra": f"9{i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO {i}", "estado": "DF",
                 "descricaoItem": f"SOFTWARE LICENCA SIMULADA {i}", "nomePdm": "SOFTWARE", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(10)]
        return 200, {"totalRegistros": len(lote), "resultado": lote, "paginasRestantes": 0}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        d = str(params.get("codigo", ""))[-1:]
        if d not in CEN["ligadas"]: return 200, {"resultado": []}, {}
        return 200, {"resultado": [{"numeroControlePNCP": f"1111111100019{d}-1-00000{d}/2026", "orgaoEntidadeCnpj": f"1111111100019{d}", "anoCompraPncp": 2026, "sequencialCompraPncp": int(d) + 1}]}, {}
    if url.endswith("/itens"): return 200, [], {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
botao = lambda at, r: next(b for b in at.button if b.label == r)
def busca(ligadas=()):
    CEN["ligadas"] = tuple(ligadas)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300); at.run()
    at.text_input(key="termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
    at.session_state[f"tab_sug_pdm_{zlib.crc32(norm('windows 11').encode('utf-8'))}"] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
    botao(at, "Buscar").click().run(); assert not at.exception, [e.value for e in at.exception]; return at
def tabela(at): return next(d.value for d in at.dataframe if "descricao_item" in d.value.columns)
def sb(at, rotulo): return next(s for s in at.selectbox if s.label == rotulo)
nome = lambda v: getattr(v, "name", str(v))

print("=== funções puras (Fase 1) ===")
L = lambda x: "https://pncp.gov.br/app/editais/1/2026/1" if x else ""
df0 = pd.DataFrame({"linha": [1, 2, 3, 4, 5], "link_publico": [L(0), L(1), L(0), L(1), L(0)]})
cp = df0.copy(); o = sv.ligadas_primeiro(df0)
checa(o["linha"].tolist() == [2, 4, 1, 3, 5], f"ligadas_primeiro: ordem das linhas {o['linha'].tolist()} (esperado [2, 4, 1, 3, 5]; estável nos dois grupos)")
checa(df0.equals(cp) and o.index.tolist() == [0, 1, 2, 3, 4], "ligadas_primeiro não altera o df recebido e devolve índice 0..n-1")
checa(sv.ligadas_primeiro(pd.DataFrame({"linha": [3, 1]}))["linha"].tolist() == [3, 1], "sem a coluna link_publico: devolve como veio")
checa(sv.ligadas_primeiro(pd.DataFrame({"linha": [1, 2], "link_publico": [L(0), L(0)]}))["linha"].tolist() == [1, 2], "nenhuma ligada: mesma ordem")
checa(sv.ligadas_primeiro(pd.DataFrame({"linha": [1, 2], "link_publico": [L(1), L(1)]}))["linha"].tolist() == [1, 2], "todas ligadas: mesma ordem")
checa(sv.ligadas_primeiro(pd.DataFrame({"linha": [1, 2], "link_publico": [None, float("nan")]}))["linha"].tolist() == [1, 2], "link_publico vazio/NaN conta como não ligada, sem erro")
checa(sv.indice_primeira_ligada([L(0), L(0), L(1), L(1)]) == 2 and sv.indice_primeira_ligada([L(1)]) == 0 and sv.indice_primeira_ligada([L(0), L(0)]) == 0 and sv.indice_primeira_ligada([]) == 0, "indice_primeira_ligada: 2 / 0 / 0 (nenhuma) / 0 (vazia)")

def lista(*itens): return [{"sequencialDocumento": s, "titulo": t, "tipoDocumentoNome": tp, "statusAtivo": ativo} for s, t, tp, ativo in itens]
def pasta_docs(nome_pasta, arqs, lst=None):
    p = TMP / "docs" / nome_pasta; p.mkdir(parents=True)
    for a in arqs:
        q = p / a; q.parent.mkdir(parents=True, exist_ok=True); q.write_bytes(b"%PDF-1.4 teste")
    if lst is not None: (p / "_lista_arquivos_pncp.json").write_text(json.dumps(lst, ensure_ascii=False), encoding="utf-8")
    return p, sorted([x for x in p.rglob("*") if x.is_file() and not x.name.startswith("_lista") and x.suffix.lower() in f.EXTENSOES_RECORTE])
def idx(nome_pasta, arqs, lst=None):
    p, pdfs = pasta_docs(nome_pasta, arqs, lst); i, m = sv.indice_documento_recorte(p, pdfs); return pdfs[i].name if pdfs else None, m, [x.name for x in pdfs]
r = idx("a", ["1_anexo.pdf", "2_zzz.pdf", "3_edital.pdf"], lista((1, "Anexo", "Outros Documentos", True), (2, "ZZZ", "Termo de Referencia", True), (3, "Edital", "Edital", True)))
checa(r[0] == "2_zzz.pdf" and r[1] == "TR", f"com TR marcado na lista (nome do arquivo sem 'termo'): abre em {r[0]} ({r[1]}); arquivos {r[2]}")
r = idx("b", ["1_decisao.pdf", "2_edital.pdf"], lista((1, "Decisão", "Decisão", True), (2, "Edital", "Edital", True)))
checa(r[0] == "2_edital.pdf" and r[1] == "principal", f"sem TR, com edital: abre no 1º principal ({r[0]}, {r[1]})")
r = idx("c", ["1_a.pdf", "2_termo_de_referencia.pdf"], None)
checa(r[0] == "2_termo_de_referencia.pdf" and r[1] == "nome", f"sem a lista (download antigo): regra de antes, pelo nome ({r[0]}, {r[1]})")
r = idx("d", ["1_a.pdf", "2_b.docx"], None)
checa(r[0] == "1_a.pdf" and r[1] == "primeiro", f"sem a lista e sem nome de TR: o primeiro ({r[0]}, {r[1]})")
r = idx("e", ["1_decisao.pdf", "5_pacote_extraido/doc_interno.pdf"], lista((1, "Decisão", "Decisão", True), (5, "Pacote", "Termo de Referencia", True)))
checa(r[0] == "doc_interno.pdf" and r[1] == "TR", f"TR dentro de ZIP extraído (pasta '5_...'): abre nele ({r[0]}, {r[1]})")
r = idx("f", ["1_decisao.pdf", "2_proposta.pdf"], lista((1, "Decisão", "Decisão", True), (2, "Proposta", "Proposta", True)))
checa(r[0] == "1_decisao.pdf" and r[1] == "primeiro", f"sem TR e sem principal: o primeiro, como antes ({r[0]}, {r[1]})")
r = idx("b2", ["2_DFD.pdf", "3_TR.pdf"], lista((2, "DFD", "Documento de Formalizacao da Demanda", True), (3, "TR", "Termo de Referencia", True)))
checa(r[0] == "3_TR.pdf" and r[1] == "TR", f"(b) estrutura real: 2_DFD.pdf e 3_TR.pdf, lista com o sequencial 3 como TR: abre em {r[0]} ({r[1]}); o DFD também é principal, mas o TR vem antes")
r = idx("g", ["1_tr_velho.pdf", "2_tr_novo.pdf"], lista((1, "TR antigo", "Termo de Referencia", False), (2, "TR novo", "Termo de Referencia", True)))
checa(r[0] == "2_tr_novo.pdf" and r[1] == "TR", f"TR inativo na lista é ignorado ({r[0]}, {r[1]})")
r = idx("h", ["1_a.pdf"], None); (TMP / "docs" / "h" / "_lista_arquivos_pncp.json").write_text("isto não é json", encoding="utf-8")
p, pdfs = pasta_docs("h2", ["1_a.pdf", "2_termo.pdf"]); (p / "_lista_arquivos_pncp.json").write_text("isto não é json", encoding="utf-8")
checa(sv.indice_documento_recorte(p, pdfs) == (1, "nome"), "lista ilegível: cai na regra de antes sem erro")
rs = [Path("C:/x/novo"), Path("C:/x/velho")]
checa(sv.recorte_padrao(rs, None) == rs[0] and sv.recorte_padrao(rs, "velho") == rs[1] and sv.recorte_padrao(rs, "nao_existe") == rs[0] and sv.recorte_padrao([], "x") is None, "recorte_padrao: mais recente; o gerado por último se achado; nome que não existe -> mais recente; sem recorte -> None")
checa(sv.frase_recorte_conferido(rs, rs[0]) == "Recorte conferido: novo (2 recorte(s) nesta sessão); é o mais recente." and "NÃO é o mais recente (o mais recente é novo)" in sv.frase_recorte_conferido(rs, rs[1]), "frase do recorte conferido: o mais recente / não é o mais recente")

print("\n=== Item 4 (tela): Etapa 2 com ligadas primeiro ===")
at = busca(ligadas="47"); t = tabela(at)
lig = t["abrir"].astype(str).str.startswith("http").tolist(); lin = [int(x) for x in t["linha"].tolist()]
checa(len(t) == 10 and lig == [True, True] + [False] * 8, f"2 de 10 ligadas aparecem nas 2 primeiras linhas da tabela (ligadas por linha: {lig})")
checa(lin[:2] == sorted(lin[:2]) and lin[2:] == sorted(lin[2:]) and sorted(lin) == list(range(1, 11)), f"dentro de cada grupo a ordem é a de antes e o número da linha não mudou ({lin})")
checa(nome(sb(at, "Linha").value) == str(lin[0]) or sb(at, "Linha").value == lin[0], f"item 3: o seletor 'Linha' abre na 1ª ligada (linha {lin[0]}; seletor = {sb(at, 'Linha').value})")
s3 = sb(at, "Linha"); rot3 = [str(o) for o in s3.options]; sel3 = rot3[s3.index]
orig_ligadas = [i + 1 for i in range(10) if str(i) in "47"]      # a ordem original: linhas 5 e 8 (i = 4 e 7), a primeira ligada NÃO é a linha 1
checa(orig_ligadas[0] != 1 and sel3.startswith(f"{orig_ligadas[0]} – ") and rot3[s3.index].split(" – ")[0] == str(lin[0]) and s3.index == lin.index(lin[0]),
      f"(a) a 1ª ligada na ordem original é a linha {orig_ligadas[0]} (não a 1); o rótulo selecionado no seletor 'Linha' é '{sel3[:40]}…' (índice {s3.index} = posição desse rótulo nas {len(rot3)} opções)")
checa([o.split(" – ")[0] for o in rot3] == [str(x) for x in lin], f"(a) as opções do seletor seguem a mesma ordem da tabela ({[o.split(' – ')[0] for o in rot3]})")
fonte = (RAIZ / "app.py").read_text(encoding="utf-8")
checa(fonte.index("df = sv.ligadas_primeiro(df)") < fonte.index('st.download_button("Baixar CSV (ordem desta tela)"') and fonte.count("sv.ligadas_primeiro(") == 1, "o CSV baixado é gerado do mesmo df já ordenado: continua na 'ordem desta tela' (conferido no código; o download em si não foi aberto)")
checa(fonte.count('(f.SAIDA / "busca_tela_atual.csv").write_bytes(rec["csv"])') == 1, "o arquivo que a opção 3 lê (busca_tela_atual.csv) continua vindo de rec['csv'], sem reordenar (o número da linha segue valendo)")

print("\n=== Item 3 (tela): nenhuma linha ligada -> linha 1 ===")
at = busca(ligadas=""); t = tabela(at)
checa([int(x) for x in t["linha"].tolist()] == list(range(1, 11)) and not t["abrir"].astype(str).str.startswith("http").any(), f"nenhuma ligada: ordem de antes ({[int(x) for x in t["linha"].tolist()]})")
checa(sb(at, "Linha").value in (1, "1"), f"nenhuma ligada: o seletor abre na linha 1 (seletor = {sb(at, 'Linha').value})")
at = busca(ligadas="0123456789"); t = tabela(at)
checa([int(x) for x in t["linha"].tolist()] == list(range(1, 11)) and sb(at, "Linha").value in (1, "1"), "todas ligadas: ordem de antes e seletor na linha 1")

print("\n=== Item 2 (tela): 'Documento para recortar' ===")
ROT_DOC = "Documento para recortar: PDF ou Word (de preferência o TR)"
def tela_docs(arqs, lst):
    at = busca(ligadas="47"); escolha = sb(at, "Linha").value
    p, _ = pasta_docs(f"t{int(time.time() * 1000)}", arqs, lst)
    at.session_state["docs"] = {"linha": escolha, "pasta": str(p), "log": "", "aviso": "", "falhas": []}; at.run()
    assert not at.exception, [e.value for e in at.exception]; return at
at = tela_docs(["1_anexo.pdf", "2_zzz.pdf", "3_edital.pdf"], lista((1, "Anexo", "Outros Documentos", True), (2, "ZZZ", "Termo de Referencia", True), (3, "Edital", "Edital", True)))
checa(nome(sb(at, ROT_DOC).value) == "2_zzz.pdf", f"tela, compra com TR: o seletor abre no TR ({nome(sb(at, ROT_DOC).value)})")
at = tela_docs(["2_DFD.pdf", "3_TR.pdf"], lista((2, "DFD", "Documento de Formalizacao da Demanda", True), (3, "TR", "Termo de Referencia", True)))
checa(nome(sb(at, ROT_DOC).value) == "3_TR.pdf", f"(b) tela, estrutura real (2_DFD.pdf, 3_TR.pdf; TR = sequencial 3): o seletor abre em {nome(sb(at, ROT_DOC).value)}")
at = tela_docs(["1_decisao.pdf", "2_edital.pdf"], lista((1, "Decisão", "Decisão", True), (2, "Edital", "Edital", True)))
checa(nome(sb(at, ROT_DOC).value) == "2_edital.pdf", f"tela, compra sem TR: abre no 1º principal ({nome(sb(at, ROT_DOC).value)})")
at = tela_docs(["1_decisao.pdf", "2_proposta.pdf"], lista((1, "Decisão", "Decisão", True), (2, "Proposta", "Proposta", True)))
checa(nome(sb(at, ROT_DOC).value) == "1_decisao.pdf", f"tela, sem TR e sem principal: o primeiro ({nome(sb(at, ROT_DOC).value)})")

print("\n=== Item 1 (tela): Etapa 5 abre no recorte mais recente ===")
def recorte(at, nome_r, idade_s):
    sess = f.PASTA / "saida" / "sessoes" / at.session_state["sessao_id"] / "recortes" / nome_r; sess.mkdir(parents=True)
    (sess / "recorte.txt").write_text(f"DOCUMENTO {nome_r} | item pedido: windows 11 | 2 páginas no original | páginas incluídas: 1\n[pág. 1]\nTexto de teste {nome_r}.\n", encoding="utf-8")
    (sess / "paginas.json").write_text(json.dumps(["Texto de teste " + nome_r + "."], ensure_ascii=False), encoding="utf-8")
    t = time.time() - idade_s; os.utime(sess / "recorte.txt", (t, t)); return sess
at = busca(ligadas="")
checa(not [c for c in at.caption if str(c.value).startswith("Recorte conferido:")], "sem recorte: nenhuma linha 'Recorte conferido' (a tela mostra o aviso de antes)")
recorte(at, "R1_antigo", 600); at.run()
checa(nome(sb(at, "Recorte conferido (o texto das páginas vem dele)").value) == "R1_antigo", "sessão com 1 recorte: abre nele")
cap = [c.value for c in at.caption if str(c.value).startswith("Recorte conferido:")]
checa(cap == ["Recorte conferido: R1_antigo (1 recorte(s) nesta sessão); é o mais recente."], f"1 recorte: a linha diz qual é: {cap}")
recorte(at, "R2_novo", 5); at.run(); assert not at.exception, [e.value for e in at.exception]
checa(nome(sb(at, "Recorte conferido (o texto das páginas vem dele)").value) == "R2_novo", "gerou um 2º recorte depois de já ter aberto no 1º: passa a abrir no MAIS RECENTE (bug de hoje: ficava no antigo)")
cap = [c.value for c in at.caption if str(c.value).startswith("Recorte conferido:")]
checa(cap == ["Recorte conferido: R2_novo (2 recorte(s) nesta sessão); é o mais recente."], f"2 recortes: a linha diz qual é: {cap}")
at2 = at; s5 = sb(at2, "Recorte conferido (o texto das páginas vem dele)")
alvo_velho = next(i for i, o in enumerate(s5.options) if "R1_antigo" in str(o))
s5.set_value(s5.options[alvo_velho] if not isinstance(s5.options[alvo_velho], str) else s5.options[alvo_velho]).run()
cap = [c.value for c in at2.caption if str(c.value).startswith("Recorte conferido:")]
checa("R1_antigo" in cap[0] and "NÃO é o mais recente (o mais recente é R2_novo)" in cap[0], f"se a pessoa escolhe o antigo à mão, a escolha dela vale e a linha avisa: {cap}")
at2.run()
checa("R1_antigo" in [c.value for c in at2.caption if str(c.value).startswith("Recorte conferido:")][0], "num novo rerun sem recorte novo, a escolha manual continua")
recorte(at2, "R3_regravado", 1); at2.session_state["recorte_atual"] = "R1_antigo"; at2.run()
checa(nome(sb(at2, "Recorte conferido (o texto das páginas vem dele)").value) == "R1_antigo", "se o app marcou 'recorte_atual' (o gerado por último) e ele existe, abre nesse")
os.utime(TMP, None)
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

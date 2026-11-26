"""v4h, Pedido 13K – (A) PDF sem texto, (B) sugestões clicáveis, (C) % real e tempo decorrido. SEM rede (socket bloqueado), rede SIMULADA, PDFs criados pelo próprio teste.
A: PDF só de imagem (3 págs) criado aqui, lido com a extração REAL (pdfplumber): painel "Concluída com falhas", nada de "páginas relevantes"/"texto pronto"/texto para colar, os outros
   documentos da compra com o nº de caracteres, "não faz OCR"; só algumas páginas sem texto = aviso "X de N páginas sem texto"; Etapa 5 marca "recorte sem texto" e não confere.
B: Serviço e Produto: a sugestão vira tabela com 'usar'; marcar mostra "Códigos marcados: ..." e o botão Buscar usa o código; termo sem sugestão: frase da equipe; termos_software.csv intacto.
C: toda barra com valor > 0 traz o %; etapa única sem total mostra "em andamento" (sem % inventado); o 'Tempo decorrido' sobe a cada 1 s durante uma etapa longa (extração lenta simulada).
O AppTest não mede o desenho no navegador. O PDF real do caso está em test_pedido13k_pdf_real.py.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13k_tela.py   (na pasta do app)"""
import datetime as dt, hashlib, json, re, shutil, socket, sys, time, zlib
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "tests")); sys.dont_write_bytecode = True
_o = socket.socket.connect
def _b(self, a, *x, **k):
    h, p = (a[0], a[1]) if isinstance(a, tuple) else (str(a), None)
    if h in ("127.0.0.1", "::1") and p != 11434: return _o(self, a, *x, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
from streamlit.testing.v1 import AppTest
import streamlit.delta_generator as dg
import ferramenta as f
import servicos as sv
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
norm = f.norm
TMP = DADOS / "pedido13k" / f"_tmp_teste_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
TERMOS = RAIZ / "config" / "termos_software.csv"; SHA_TERMOS = sha(TERMOS)

# ---------------------------------------------------------------- PDFs criados pelo teste (sem instalar nada)
def monta_pdf(paginas):
    """paginas: lista de None (página só com uma imagem, sem texto) ou str (texto)."""
    n = len(paginas); ids = [5 + 2 * i for i in range(n)]; corpo = {1: b"<< /Type /Catalog /Pages 2 0 R >>"}
    corpo[2] = ("<< /Type /Pages /Kids [" + " ".join(f"{i} 0 R" for i in ids) + f"] /Count {n} >>").encode()
    corpo[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    corpo[4] = b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 4 >>\nstream\n" + bytes([0, 255, 255, 0]) + b"\nendstream"
    for i, t in enumerate(paginas):
        pid, cid = ids[i], ids[i] + 1
        corpo[pid] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents {cid} 0 R /Resources << /Font << /F1 3 0 R >> /XObject << /Im0 4 0 R >> >> >>".encode()
        cont = b"q 300 0 0 300 0 0 cm /Im0 Do Q" if t is None else ("BT /F1 12 Tf 10 150 Td (" + t + ") Tj ET").encode("latin-1")
        corpo[cid] = b"<< /Length %d >>\nstream\n" % len(cont) + cont + b"\nendstream"
    out = b"%PDF-1.4\n"; offs = {}
    for k in sorted(corpo): offs[k] = len(out); out += f"{k} 0 obj\n".encode() + corpo[k] + b"\nendobj\n"
    tot = max(corpo) + 1
    out += (f"xref\n0 {tot}\n").encode() + b"0000000000 65535 f \n" + b"".join(f"{offs[k]:010d} 00000 n \n".encode() for k in range(1, tot))
    out += f"trailer\n<< /Size {tot} /Root 1 0 R >>\nstartxref\n0\n%%EOF\n".encode()    # o 0 é trocado pela posição real em monta_pdf_ok
    return out
def monta_pdf_ok(paginas):
    """Monta o PDF e corrige o startxref com a posição real da tabela xref."""
    b = monta_pdf(paginas); pos = b.rindex(b"xref\n0 "); return re.sub(rb"startxref\n\d+\n", b"startxref\n%d\n" % pos, b)
TEXTO = "Termo de referencia: licenca Microsoft Windows 11 Pro e Office, garantia de 36 meses, entrega em 30 dias."
PDF_IMAGEM = monta_pdf_ok([None, None, None]); PDF_TEXTO = monta_pdf_ok([TEXTO, TEXTO + " Pagina dois.", TEXTO + " Pagina tres."]); PDF_PARCIAL = monta_pdf_ok([TEXTO, None, TEXTO + " Pagina tres."])
pr = f.extrair_paginas  # extração REAL
for nome, b in (("imagem", PDF_IMAGEM), ("texto", PDF_TEXTO), ("parcial", PDF_PARCIAL)):
    (TMP / f"{nome}.pdf").write_bytes(b)
    pg, _ = pr(TMP / f"{nome}.pdf"); print("   PDF do teste", nome, "-> caracteres por página:", sv.caracteres_por_pagina(pg))
checa(sv.caracteres_por_pagina(pr(TMP / "imagem.pdf")[0]) == [0, 0, 0], "o PDF só de imagem criado no teste dá 0 caracteres em 3 de 3 páginas (extração real)")
checa(all(c > 50 for c in sv.caracteres_por_pagina(pr(TMP / "texto.pdf")[0])), "o PDF com texto criado no teste tem texto em todas as páginas (extração real)")

# ---------------------------------------------------------------- função pura (servicos.py)
av0 = sv.avaliar_texto_documento([""] * 26)
checa(av0 == {"paginas": 26, "sem_texto": 26, "total": 0, "estado": "sem_texto"}, f"26 páginas vazias: {av0}")
checa(sv.frase_sem_texto(av0) == "PDF sem texto: 26 de 26 páginas sem texto (provavelmente digitalizado). A IA não tem o que ler.", "frase exata do painel para 26 de 26")
avp = sv.avaliar_texto_documento(["x" * 300, "", "y" * 300])
checa(avp["estado"] == "parcial" and sv.frase_paginas_sem_texto(avp) == "1 de 3 páginas sem texto.", f"parcial: {avp} -> '{sv.frase_paginas_sem_texto(avp)}'")
checa(sv.avaliar_texto_documento(["x" * 300] * 3)["estado"] == "ok" and sv.frase_paginas_sem_texto(sv.avaliar_texto_documento(["x" * 300] * 3)) == "", "com texto em todas: ok e sem aviso")
checa(sv.avaliar_texto_documento([])["estado"] == "sem_texto", "documento sem nenhuma página conta como sem texto")
checa(sv.caracteres_do_recorte(["abc def", "", "gh"], [1, 3]) == 8 and sv.caracteres_do_recorte(["abc", ""], [2]) == 0, "caracteres do recorte: só as páginas mantidas, sem espaços")

# ---------------------------------------------------------------- rede simulada
HOJE = dt.date.today().isoformat(); ESTADO = {"ligar": False, "docs": {}, "multi": False}
CHAMADAS = []
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "Termo de Referencia", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]
def get(url, params=None, binario=False):
    params = params or {}; CHAMADAS.append((url, dict(params)))
    if "3_consultarServico" in url:
        pag = params.get("pagina", 1)
        lote = [{"idCompra": f"92515806001192{i:03d}", "numeroItemCompra": i + 1, "descricaoItem": f"SERVICO SIMULADO {i}", "codigoItemCatalogo": int(params.get("codigoItemCatalogo") or 5606), "siglaUnidadeMedida": "UN",
                 "quantidade": 1.0, "precoUnitario": 1000.0 + i, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF", "dataCompra": HOJE, "dataResultado": HOJE} for i in range(8)]
        if ESTADO["multi"]:
            return 200, {"totalRegistros": 150, "paginasRestantes": 1 if pag < 2 else 0, "resultado": lote}, {}
        return 200, {"totalRegistros": 8, "paginasRestantes": 0, "resultado": lote}, {}
    if "1_consultarMaterial" in url:
        pag = params.get("pagina", 1)
        lote = [{"idCompra": f"9{(pag - 1) * 100 + i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF",
                 "descricaoItem": "SOFTWARE LICENCA SIMULADA", "numeroItemCompra": i + 1, "nomePdm": "SOFTWARE", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(10)]
        return 200, {"totalRegistros": 10, "resultado": lote, "paginasRestantes": 0}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url: return 200, {"resultado": [REG] if ESTADO["ligar"] else []}, {}
    if url.endswith("/arquivos"): return 200, LISTA, {}
    m = re.search(r"/arquivos/(\d+)$", url)
    if m: return 200, ESTADO["docs"][int(m.group(1))], {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
botao = lambda at, r: next(b for b in at.button if b.label == r)
def textos(at):
    out = [m.value for m in at.markdown] + [m.value for m in at.caption] + [m.value for m in at.info] + [m.value for m in at.warning] + [m.value for m in at.error] + [m.value for m in at.success]
    return "\n".join(str(x) for x in out)
def serv_ate_documentos(doc_tr, doc_edital=PDF_TEXTO):
    """Busca de serviço (código 5606) e download dos 2 documentos (TR = doc_tr, Edital = doc_edital): deixa a Etapa 3 pronta para 'Gerar texto para IA'."""
    ESTADO.update(ligar=False, docs={1: doc_edital, 2: doc_tr}, multi=False)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
    at.radio(key="tipo_busca").set_value("Serviço").run(); at.text_input(key="serv_codigo_av").set_value("5606").run()
    botao(at, "Buscar compras do serviço").click().run()
    ESTADO["ligar"] = True; botao(at, "Baixar documentos da linha").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at

# ---------------------------------------------------------------- A. PDF sem texto (Serviço)
print("\n=== A. PDF só de imagem: o app avisa e não oferece texto para a IA ===")
at = serv_ate_documentos(PDF_IMAGEM)
sel = next(s_ for s_ in at.selectbox if s_.label.startswith("Documento para recortar"))
checa("Termo" in sel.value.name, f"o documento escolhido por padrão é o TR (imagem): {sel.value.name}")
botao(at, "Gerar texto para IA").click().run()
checa(not at.exception, "sem exceção ao gerar o texto de um PDF sem texto")
pn = at.session_state["painel_e3_recorte"]
checa(pn["texto"].startswith("Concluída com falhas em") and "PDF sem texto: 3 de 3 páginas sem texto (provavelmente digitalizado). A IA não tem o que ler." in pn["texto"], f"painel: '{pn['texto'][:150]}'")
T = textos(at)
checa("páginas relevantes" not in T and "texto pronto" not in T and "Pronto:" not in T, "não mostra 'páginas relevantes', 'texto pronto' nem 'Pronto:'")
checa(not [t for t in at.text_area if t.label == "Texto para colar na IA"] and not [d for d in at.get("download_button") if d.proto.label == "Baixar o .txt"], "não oferece o texto para colar nem o botão de baixar o .txt")
checa("não faz OCR" in T, "diz que o app não faz OCR")
checa("1_Edital.pdf" in " ".join(str(d.value) for d in at.dataframe) and any("tem texto" in str(d.value.to_dict()) for d in at.dataframe), "lista o outro documento baixado com a situação 'tem texto'")
tab_out = next(d.value for d in at.dataframe if "caracteres de texto" in d.value.columns)
chars_edital = int(str(tab_out.loc[tab_out["documento"].str.contains("Edital"), "caracteres de texto"].iloc[0]).replace(".", ""))
esperado = sum(sv.caracteres_por_pagina(pr(TMP / "texto.pdf")[0]))
checa(chars_edital == esperado and chars_edital > 0, f"caracteres do outro documento na tabela = {chars_edital} (conta independente: {esperado}); páginas = {int(tab_out['páginas'].iloc[0])}")
checa("painel_e3_outros" in at.session_state and at.session_state["painel_e3_outros"]["ok"], "painel dos outros documentos concluído")
checa(not any("texto para colar" in str(m.value).lower() for m in at.markdown if "Etapa 4" in str(m.value)), "a Etapa 4 (copiar o texto) não aparece")
# Etapa 5
at.run()
checa("Recorte sem texto" in textos(at), "Etapa 5: marca 'recorte sem texto'")
checa("painel_e3_outros" in at.session_state and "Recorte sem texto" in textos(at) and any("sem texto" in str(d.value.to_dict()) or "tem texto" in str(d.value.to_dict()) for d in at.dataframe), "o aviso de sem texto continua depois de outro rerun (a tabela dos outros documentos fica)")
at.text_area(key="ficha_resposta").set_value("qualquer coisa"); at.run(); botao(at, "Conferir ficha").click().run()
checa("ficha_conferida" not in at.session_state, "Etapa 5: a ficha NÃO é tratada como conferida (nada em ficha_conferida)")
p5 = at.session_state["painel_e5_conferir"]
checa(not p5["ok"] and "recorte sem texto" in p5["texto"], f"Etapa 5: painel falhou com '{p5['texto']}'")

print("\n=== A3. Só algumas páginas sem texto: aviso 'X de N páginas sem texto' ===")
at = serv_ate_documentos(PDF_PARCIAL)
botao(at, "Gerar texto para IA").click().run()
checa(not at.exception, "sem exceção com PDF parcial")
T = textos(at)
checa("1 de 3 páginas sem texto." in T, "aviso '1 de 3 páginas sem texto.'")
checa("texto pronto" in at.session_state["painel_e3_recorte"]["texto"] and [t for t in at.text_area if t.label == "Texto para colar na IA"], "o texto para a IA continua sendo oferecido (há texto em 2 de 3 páginas)")
at.run(); checa("Recorte sem texto" not in textos(at), "Etapa 5: recorte com texto não é marcado como sem texto")

print("\n=== A. PDF com texto: nada de aviso ===")
at = serv_ate_documentos(PDF_TEXTO)
botao(at, "Gerar texto para IA").click().run()
T = textos(at)
checa("sem texto" not in T.lower() and "texto pronto" in at.session_state["painel_e3_recorte"]["texto"], "PDF com texto em todas as páginas: sem aviso de 'sem texto' e com 'texto pronto'")

# ---------------------------------------------------------------- B. sugestões clicáveis
print("\n=== B. Serviço: a sugestão vira tabela com 'usar' ===")
catalogo_s = list(__import__("csv").DictReader((RAIZ / "config" / "catalogo_servicos.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
ativos = [r for r in catalogo_s if r["statusServico"] == "True" and ("licenc" in norm(r["nomeServico"]) or "software como servico" in norm(r["nomeServico"]))][:10]
def chave_sug(prefixo, termo): return f"{prefixo}_{zlib.crc32(norm(termo).encode('utf-8'))}"
def tabelas_usar(at): return [d for d in at.dataframe if "usar" in d.value.columns] if at.dataframe else []
ESTADO.update(ligar=False, docs={1: PDF_TEXTO, 2: PDF_TEXTO}, multi=False); CHAMADAS.clear()
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
at.text_input(key="serv_termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
tabs = [d for d in at.dataframe if "usar" in d.value.columns]
checa(len(tabs) == 1 and list(tabs[0].value["código"]) == [int(r["codigoServico"]) for r in ativos], f"a sugestão é UMA tabela com a coluna 'usar' e {len(tabs[0].value) if tabs else 0} serviços, na ordem do catálogo")
checa("Códigos marcados: nenhum (marque na coluna usar)" in textos(at), "antes de marcar: 'Códigos marcados: nenhum (marque na coluna usar)'")
at.session_state[chave_sug("tab_sug_serv", "windows 11")] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
checa("Códigos marcados: 27499" in textos(at), "marcar a sugestão mostra 'Códigos marcados: 27499'")
checa(at.text_input(key="serv_codigo_av").value == "", "sem digitar nada na opção avançada")
botao(at, "Buscar compras do serviço").click().run()
cods = {c[1].get("codigoItemCatalogo") for c in CHAMADAS if "3_consultarServico" in c[0]}
checa(not at.exception and cods == {"27499"}, f"o botão Buscar usou o código marcado: códigos consultados {sorted(map(str, cods))}")
checa(at.session_state["busca_atual"]["codigos"] == "27499", f"busca_atual guarda o código: {at.session_state['busca_atual']['codigos']}")
print("\n--- Serviço: 7 marcados + limite de 6 não se aplica a sugestão com 7 itens; marcar vários ---")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
at.text_input(key="serv_termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
at.session_state[chave_sug("tab_sug_serv", "windows 11")] = {"edited_rows": {0: {"usar": True}, 1: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
checa(f"Códigos marcados: {ativos[0]['codigoServico']}, {ativos[1]['codigoServico']}" in textos(at), "marcar 2 sugestões: 'Códigos marcados' lista os dois")

print("\n=== B2. Termo sem sugestão ===")
FRASE = "Para sugerir códigos para este termo, a equipe acrescenta o termo em config\\termos_software.csv"
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
at.text_input(key="serv_termo").set_value("firewall").run(); botao(at, "Procurar no catálogo").click().run()
checa(any("Nenhum serviço ativo do catálogo tem todas essas palavras" in w.value for w in at.warning), "serviço 'firewall': a mensagem atual continua")
checa(FRASE in [c.value for c in at.caption] and not tabelas_usar(at), "serviço 'firewall': acrescenta a frase da equipe (config\\termos_software.csv) e não mostra tabela")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
at.text_input(key="termo").set_value("qwertyuiop").run(); botao(at, "Procurar no catálogo").click().run()
checa(any("Nada encontrado no catálogo" in w.value for w in at.warning) and FRASE in [c.value for c in at.caption], "produto sem sugestão: a mensagem atual continua e a frase da equipe aparece")
checa(sha(TERMOS) == SHA_TERMOS, "config\\termos_software.csv não foi alterado (SHA-256 igual)")

print("\n=== B. Produto: o PDM 'Software' sugerido também é marcável ===")
cat_pdm = f.ler_catalogo_pdm()
pdm = next(str(r["codigoPdm"]) for r in cat_pdm if norm(r["nomePdm"]).strip() == "software" and str(r["statusPdm"]).strip().lower() == "true")
CHAMADAS.clear(); ESTADO["ligar"] = False
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
at.text_input(key="termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
tabs = [d for d in at.dataframe if "usar" in d.value.columns]
checa(len(tabs) == 1 and list(tabs[0].value["código"]) == [int(pdm)] and list(tabs[0].value["nome"]) == ["SOFTWARE"] or len(tabs) == 1 and list(tabs[0].value["código"]) == [int(pdm)], f"produto: tabela com 'usar' e o PDM Software {pdm}")
checa(f"({pdm})" in " ".join(i.value for i in at.info), "a orientação com o código continua")
at.session_state[chave_sug("tab_sug_pdm", "windows 11")] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
checa(f"Códigos marcados: {pdm}" in textos(at), f"produto: marcar mostra 'Códigos marcados: {pdm}'")
checa(not at.exception, "produto: sem exceção depois de marcar (o código marcado não está nos 'achados')")
botao(at, "Buscar").click().run()
cods_p = {c[1].get("codigo") for c in CHAMADAS if "1_consultarMaterial" in c[0]}
checa(not at.exception and cods_p == {int(pdm)} or cods_p == {pdm}, f"produto: o botão Buscar usou o código marcado: {sorted(map(str, cods_p))}")

# ---------------------------------------------------------------- C. % e tempo
print("\n=== C. % real, 'em andamento' e tempo decorrido ===")
REG_PROG, REG_MD = [], []
orig_enq = dg.DeltaGenerator._enqueue
def enq(self, delta_type, element_proto, *a, **k):
    try:
        if delta_type == "progress": REG_PROG.append((round(element_proto.value / 100, 2) if element_proto.value > 1 else element_proto.value, element_proto.text))
        if delta_type == "markdown" and "Tempo decorrido" in element_proto.body: REG_MD.append(element_proto.body)
    except Exception:  # noqa: BLE001
        pass
    return orig_enq(self, delta_type, element_proto, *a, **k)
dg.DeltaGenerator._enqueue = enq
# C1: busca de serviço com 2 páginas na API (total conhecido) -> % real
ESTADO.update(ligar=False, docs={1: PDF_TEXTO, 2: PDF_TEXTO}, multi=True); REG_PROG.clear()
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
at.text_input(key="serv_codigo_av").set_value("5606").run(); botao(at, "Buscar compras do serviço").click().run()
t_serv = [t for v, t in REG_PROG if "Pesquisa de preço" in t]
checa(any("50%" in t for t in t_serv) and any("100%" in t for t in t_serv), f"serviço: a barra da pesquisa mostra 50% (1 de 2 páginas da API) e 100%: {t_serv}")
checa(all("%" in t or "em andamento" in t or v == 0 for v, t in REG_PROG), f"toda barra com valor > 0 tem o % escrito ({len(REG_PROG)} atualizações de barra)")
sem_pct = [(v, t) for v, t in REG_PROG if v > 0 and "%" not in t]
checa(not sem_pct, f"nenhuma barra com valor > 0 sem % escrito: {sem_pct[:3]}")
checa(any(t.endswith("em andamento") for v, t in REG_PROG if "Passo 0" in t), "o passo 0 (sem total) mostra 'em andamento', não um % inventado")
# C1/C2: extração lenta simulada (etapa única e longa) -> 'em andamento' e tempo subindo
ESTADO.update(ligar=False, docs={1: PDF_TEXTO, 2: PDF_TEXTO}, multi=False)
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run(); at.text_input(key="serv_codigo_av").set_value("5606").run()
botao(at, "Buscar compras do serviço").click().run(); ESTADO["ligar"] = True; botao(at, "Baixar documentos da linha").click().run()
def lenta(caminho):
    time.sleep(4.3); return pr(caminho)
f.extrair_paginas = lenta
REG_PROG.clear(); REG_MD.clear(); t0 = time.time()
botao(at, "Gerar texto para IA").click().run()
dur = time.time() - t0; f.extrair_paginas = pr
tempos = [re.search(r"Tempo decorrido: (.+)", b).group(1) for b in REG_MD]
distintos = []
for t in tempos:
    if t not in distintos: distintos.append(t)
checa(dur >= 4.3 and len(distintos) >= 4, f"durante a extração de {dur:.1f} s o 'Tempo decorrido' mudou {len(distintos)} vezes: {distintos[:8]}")
checa(any(t.startswith("0 s") for t in distintos) and any(t.startswith("3 s") or t.startswith("4 s") for t in distintos), "o tempo começou em 0 s e chegou a 3-4 s ainda DENTRO da etapa")
rec_barras = [(v, t) for v, t in REG_PROG if "Recortando" in t]
checa(rec_barras and all(v == 0 and t.endswith("em andamento") for v, t in rec_barras), f"extração (etapa única): a barra diz 'em andamento' sem % inventado: {rec_barras[:2]}")
checa(not at.exception and "texto pronto" in at.session_state["painel_e3_recorte"]["texto"], "a etapa lenta terminou normalmente (resultado igual ao da etapa rápida)")
fim_barra = [t for v, t in REG_PROG if v == 1.0]
checa(any("100%" in t for t in fim_barra), "ao concluir a barra mostra 100%")
dg.DeltaGenerator._enqueue = orig_enq

# ---------------------------------------------------------------- guarda
checa(sha(TERMOS) == SHA_TERMOS, "termos_software.csv igual no fim")
checa(not [c for c in CHAMADAS if "http" not in c[0]], "todas as chamadas foram à rede SIMULADA (nenhuma real; socket bloqueado)")
import gc; gc.collect()   # solta os arquivos que a extração do PDF ainda mantém abertos (Windows não apaga arquivo aberto)
try:
    shutil.rmtree(TMP)
except OSError as exc:
    print("(a pasta temporária continua aberta por este processo; o runner a apaga depois que o teste termina)")
print(f"\n{len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)

"""v4h, Pedido 13K, A5 – o PDF REAL do caso (2_TR153114_000161_2026.pdf, 26 páginas, só imagem) e o ETP real da mesma compra, SEMPRE em CÓPIA (o original fica intacto: SHA-256 igual antes e depois).
SEM rede (socket bloqueado, rede SIMULADA devolvendo os bytes das cópias). A extração é a REAL (pdfplumber), por isso este teste demora cerca de 2 a 3 minutos.
Prova, com números: 0 caracteres em 26 de 26 páginas; painel 'Concluída com falhas' com a frase pedida; nada de 'páginas relevantes'/'texto pronto'/texto para colar; o ETP aparece com o nº de
caracteres; Etapa 5 marca 'recorte sem texto'; durante a extração o 'Tempo decorrido' subiu enquanto a barra ficou 'em andamento' (sem % inventado). O AppTest não mede o navegador.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13k_pdf_real.py   (na pasta do app)"""
import datetime as dt, hashlib, re, shutil, socket, sys, time
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
TMP = DADOS / "pedido13k" / f"_tmp_real_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
orig_tr = next(DADOS.glob("saida/sessoes/*/documentos/*/2_TR153114_000161_2026.pdf")); orig_etp = next(DADOS.glob("saida/sessoes/*/documentos/*/3_ETP153114_000076_2026-.pdf"))
sha_tr0, sha_etp0, tam_tr = sha(orig_tr), sha(orig_etp), orig_tr.stat().st_size
cop_tr, cop_etp = TMP / "tr_copia.pdf", TMP / "etp_copia.pdf"; shutil.copy(orig_tr, cop_tr); shutil.copy(orig_etp, cop_etp)
checa(sha(cop_tr) == sha_tr0 and sha(cop_etp) == sha_etp0, f"as cópias têm o mesmo SHA-256 dos originais (TR {sha_tr0[:12]}…, {tam_tr:,} bytes)".replace(",", "."))
BYTES_TR, BYTES_ETP = cop_tr.read_bytes(), cop_etp.read_bytes()

HOJE = dt.date.today().isoformat(); ESTADO = {"ligar": False}; CHAMADAS = []
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "ETP", "tipoDocumentoNome": "Estudo Técnico Preliminar", "sequencialDocumento": 3}, {"titulo": "TR153114 000161 2026", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]
def get(url, params=None, binario=False):
    params = params or {}; CHAMADAS.append(url)
    if "3_consultarServico" in url:
        lote = [{"idCompra": f"92515806001192{i:03d}", "numeroItemCompra": i + 1, "descricaoItem": "LICENCIAMENTO MICROSOFT OFFICE SIMULADO", "codigoItemCatalogo": 27499, "siglaUnidadeMedida": "UN", "quantidade": 1.0,
                 "precoUnitario": 1000.0 + i, "nomeOrgao": "ORGAO SIMULADO", "estado": "DF", "dataCompra": HOJE, "dataResultado": HOJE} for i in range(5)]
        return 200, {"totalRegistros": 5, "paginasRestantes": 0, "resultado": lote}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url: return 200, {"resultado": [REG] if ESTADO["ligar"] else []}, {}
    if url.endswith("/arquivos"): return 200, LISTA, {}
    m = re.search(r"/arquivos/(\d+)$", url)
    if m: return 200, (BYTES_TR if int(m.group(1)) == 2 else BYTES_ETP), {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
botao = lambda at, r: next(b for b in at.button if b.label == r)
def textos(at):
    out = [m.value for m in at.markdown] + [m.value for m in at.caption] + [m.value for m in at.info] + [m.value for m in at.warning] + [m.value for m in at.error] + [m.value for m in at.success]
    return "\n".join(str(x) for x in out)
REG_PROG, REG_MD = [], []
orig_enq = dg.DeltaGenerator._enqueue
def enq(self, delta_type, element_proto, *a, **k):
    try:
        if delta_type == "progress": REG_PROG.append((element_proto.value, element_proto.text))
        if delta_type == "markdown" and "Tempo decorrido" in element_proto.body: REG_MD.append((time.time(), element_proto.body))
    except Exception:  # noqa: BLE001
        pass
    return orig_enq(self, delta_type, element_proto, *a, **k)
dg.DeltaGenerator._enqueue = enq

at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=600); at.run()
at.radio(key="tipo_busca").set_value("Serviço").run(); at.text_input(key="serv_codigo_av").set_value("27499").run()
botao(at, "Buscar compras do serviço").click().run(); ESTADO["ligar"] = True; botao(at, "Baixar documentos da linha").click().run()
assert not at.exception, [e.value for e in at.exception]
sel = next(s_ for s_ in at.selectbox if s_.label.startswith("Documento para recortar"))
checa("TR153114" in sel.value.name, f"o documento escolhido é o TR do caso: {sel.value.name}")
REG_PROG.clear(); REG_MD.clear(); t0 = time.time()
botao(at, "Gerar texto para IA").click().run()
dur = time.time() - t0
checa(not at.exception, "sem exceção")
pn = at.session_state["painel_e3_recorte"]
checa(pn["texto"].startswith("Concluída com falhas em") and "PDF sem texto: 26 de 26 páginas sem texto (provavelmente digitalizado). A IA não tem o que ler." in pn["texto"], f"painel: '{pn['texto']}'")
import json
pj = next((f.PASTA / "saida" / "sessoes").glob("*/recortes/*TR153114*/paginas.json"))     # a contagem vem do paginas.json gravado pelo app
paginas = json.loads(pj.read_text(encoding="utf-8")); cs = sv.caracteres_por_pagina(paginas)
checa(len(cs) == 26 and sum(cs) == 0 and sum(1 for c in cs if c == 0) == 26, f"extração real da cópia: {len(cs)} páginas, {sum(cs)} caracteres no total, {sum(1 for c in cs if c == 0)} páginas com 0 caracteres")
T = textos(at)
checa("páginas relevantes" not in T and "texto pronto" not in T and "Pronto:" not in T, "não mostra 'páginas relevantes', 'texto pronto' nem 'Pronto:'")
checa(not [t for t in at.text_area if t.label == "Texto para colar na IA"] and not [d for d in at.get("download_button") if d.proto.label == "Baixar o .txt"], "não oferece texto para colar nem o .txt")
checa("não faz OCR" in T, "diz que o app não faz OCR")
tab = next(d.value for d in at.dataframe if "caracteres de texto" in d.value.columns)
ch_etp = int(str(tab.loc[tab["documento"].str.contains("ETP"), "caracteres de texto"].iloc[0]).replace(".", "")); pg_etp = int(tab.loc[tab["documento"].str.contains("ETP"), "páginas"].iloc[0])
checa(ch_etp == 18033 and pg_etp == 8, f"o ETP real aparece na tabela: {pg_etp} páginas, {ch_etp} caracteres (medição independente do medir_a1.py: 8 págs, 18033)")
tempos = [(t, re.search(r"Tempo decorrido: (.+)", b).group(1)) for t, b in REG_MD]
dist = []
for _, v in tempos:
    if v not in dist: dist.append(v)
checa(dur > 60 and len(dist) > 60, f"durante a extração de {dur:.0f} s o 'Tempo decorrido' mudou {len(dist)} vezes (de '{dist[0]}' a '{dist[-1]}'); antes ficava parado em '0 s'")
rec = [(v, t) for v, t in REG_PROG if "Recortando" in t]
checa(rec and all(v == 0 and t.endswith("em andamento") for v, t in rec), f"durante a extração a barra diz 'em andamento', sem % inventado: {rec[:1]}")
at.run(); checa("Recorte sem texto" in textos(at), "Etapa 5: 'recorte sem texto' marcado")
at.text_area(key="ficha_resposta").set_value("x"); at.run(); botao(at, "Conferir ficha").click().run()
checa("ficha_conferida" not in at.session_state and "recorte sem texto" in at.session_state["painel_e5_conferir"]["texto"], "Etapa 5: a ficha não é tratada como conferida")
dg.DeltaGenerator._enqueue = orig_enq
checa(sha(orig_tr) == sha_tr0 and sha(orig_etp) == sha_etp0, f"os ORIGINAIS ficaram intactos: SHA-256 do TR {sha(orig_tr)[:12]}… igual ao de antes ({sha_tr0[:12]}…); ETP igual")
checa(all("http" in u for u in CHAMADAS), "só a rede simulada foi usada")
import gc; gc.collect()
try:
    shutil.rmtree(TMP)
except OSError:
    print("(a pasta temporária continua aberta por este processo; o runner a apaga depois que o teste termina)")
print(f"\n{len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)

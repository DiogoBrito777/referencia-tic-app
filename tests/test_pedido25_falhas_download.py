"""v4h, Pedido 28 (Fase 3), SEM rede (rede e respostas do PNCP SIMULADAS; socket bloqueado). Download com falha: a tela mostra, por arquivo, o código HTTP e uma frase curta em português
(422, 404, 503, timeout) e NUNCA o corpo da resposta, o caminho interno do armazenamento nem a URL (conferido na tela e em todos os arquivos da sessão). O painel de download não muda.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido25_falhas_download.py   (na pasta do app)"""
import datetime as dt, socket, sys, time, zlib
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
_o = socket.socket.connect
def _b(self, a, *x, **k):
    h, p = (a[0], a[1]) if isinstance(a, tuple) else (str(a), None)
    if h in ("127.0.0.1", "::1") and p != 11434: return _o(self, a, *x, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
from streamlit.testing.v1 import AppTest
import ferramenta as f
import servicos as sv
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
norm = f.norm
TMP = DADOS / "pedido25" / f"_tmp_teste_falhas_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat(); CHAMADAS = []
ESTADO = {"ligar": True, "lista": [], "status_lista": 200}
CNPJ_TESTE = "11111111000191"   # inventado, só do teste
def get(url, params=None, binario=False):
    params = params or {}; CHAMADAS.append(url)
    if "1_consultarMaterial" in url:
        lote = [{"idCompra": f"9{i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO {i}", "estado": "DF", "descricaoItem": f"SOFTWARE LICENCA SIMULADA {i}",
                 "nomePdm": "SOFTWARE", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(10)]
        return 200, {"totalRegistros": len(lote), "resultado": lote, "paginasRestantes": 0}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        if not ESTADO["ligar"]: return 200, {"resultado": []}, {}
        return 200, {"resultado": [{"numeroControlePNCP": f"{CNPJ_TESTE}-1-000001/2026", "orgaoEntidadeCnpj": CNPJ_TESTE, "anoCompraPncp": 2026, "sequencialCompraPncp": 1}]}, {}
    if url.endswith("/itens"): return 200, [], {}
    if url.endswith("/arquivos"):
        return ESTADO["status_lista"], (ESTADO["lista"] if ESTADO["status_lista"] == 200 else {}), {}
    if "/arquivos/" in url: return 200, b"%PDF-1.4 teste", {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
botao = lambda at, r: next(b for b in at.button if b.label == r)
def textos(at):
    out = [m.value for m in at.markdown] + [m.value for m in at.caption] + [m.value for m in at.info] + [m.value for m in at.warning] + [m.value for m in at.error] + [m.value for m in at.success]
    return "\n".join(str(x) for x in out)
def arq(seq, titulo, tipo="", ativo=True):
    return {"sequencialDocumento": seq, "titulo": titulo, "tipoDocumentoNome": tipo, "statusAtivo": ativo, "url": f"https://pncp.gov.br/pncp-api/v1/orgaos/{CNPJ_TESTE}/compras/2026/1/arquivos/{seq}"}
DECISAO = arq(1, "Decisão – Ato que autoriza a Contratação Direta", "Decisão")
def busca_produto():
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300); at.run()
    at.text_input(key="termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
    at.session_state[f"tab_sug_pdm_{zlib.crc32(norm('windows 11').encode('utf-8'))}"] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
    botao(at, "Buscar").click().run(); assert not at.exception, [e.value for e in at.exception]; return at
def clica(at, rotulo):
    botao(at, rotulo).click().run(); assert not at.exception, [e.value for e in at.exception]
BTN_LISTAR = "Listar os TR e documentos principais desta compra (1 consulta ao PNCP, nada é baixado)"
BTN_BAIXAR = "Baixar documentos da linha"

import re, json as _json
SEGREDO = "ARMAZENAMENTO_INTERNO_bucket-xyz/objeto-9f8e7d6c5b4a39281706"       # o que o PNCP devolve no corpo do 422: não pode aparecer na tela nem em arquivo
URL_SEG = "ARMAZENAMENTO_SECRETO_ID_123456789"
_get_base = f.get
ARQ_TR = arq(2, "Termo de Referência", "Termo de Referencia")
ARQ_DFD = arq(1, "1_1. DFD - DESPACHO DA CONTRATACAO EMERGENCIAL", "Documento de Formalizacao da Demanda")
MODO = {"arq": {}}            # seq -> ("status", codigo) | ("portal_fora", mensagem) | ("ok",)
def get3(url, params=None, binario=False):
    m = re.search(r"/arquivos/(\d+)$", url)
    if not m: return _get_base(url, params, binario)
    CHAMADAS.append(url)
    caso = MODO["arq"].get(int(m.group(1)), ("ok",))
    if caso[0] == "status": return caso[1], _json.dumps({"message": "Erro ao carregar arquivo no armazenamento", "path": SEGREDO}).encode("utf-8"), {}
    if caso[0] == "portal_fora": raise f.PortalFora(caso[1] + " " + url + "?x=" + URL_SEG)
    return 200, b"%PDF-1.4 teste", {}
f.get = get3

print("=== funções puras ===")
checa(sv.frase_falha_http(422) == "PNCP respondeu 422: erro do lado do PNCP ao carregar o arquivo; tente de novo mais tarde", "422: a frase pedida")
checa(sv.frase_falha_http("404").startswith("PNCP respondeu 404: arquivo não encontrado") and sv.frase_falha_http(403).startswith("PNCP respondeu 403: acesso bloqueado"), "404 e 403: uma frase cada")
checa(sv.frase_falha_http(429).startswith("PNCP respondeu 429: limite") and sv.frase_falha_http(500).startswith("PNCP respondeu 500: servidor do PNCP") and sv.frase_falha_http(503).startswith("PNCP respondeu 503: servidor do PNCP"), "429, 500 e 503: uma frase cada (5xx: servidor)")
checa(sv.frase_falha_http(418).startswith("PNCP respondeu 418: o PNCP recusou o pedido"), "outro 4xx (418): frase genérica com o código")
checa(sv.frase_falha_rede("ReadTimeout").startswith("Sem resposta do PNCP (tempo esgotado)") and sv.frase_falha_rede("ConnectionError").startswith("Sem conexão") and sv.frase_falha_rede("X").startswith("Falha de rede"), "timeout, conexão e outro erro de rede: uma frase cada")
LOG = "  1 arquivos ativos: 1 principais (edital, TR, ETP, DFD, aviso) e 0 outros (propostas, atas, despachos...).\n  Termo de Referência: HTTP 422, não baixado\n  1_1. DFD: HTTP 404, não baixado\nDocumentos em: C:\\x\\y\n"
fl = sv.falhas_do_download(LOG)
checa([(x["arquivo"], x["codigo"]) for x in fl] == [("Termo de Referência", "422"), ("1_1. DFD", "404")], f"falhas_do_download lê 2 arquivos e os códigos: {[(x['arquivo'], x['codigo']) for x in fl]}")
fl = sv.falhas_do_download("*** PORTAL FORA OU BLOQUEADO: o portal não respondeu após 3 tentativas (HTTP 503): https://pncp.gov.br/x/" + URL_SEG + "\n")
fl = sv.falhas_do_download("*** PORTAL FORA OU BLOQUEADO: o portal não respondeu após 3 tentativas (HTTP 503): https://pncp.gov.br/x/" + URL_SEG + "\n")
checa(len(fl) == 1 and fl[0]["codigo"] == "503" and URL_SEG not in _json.dumps(fl) and "https" not in _json.dumps(fl), f"PORTAL FORA com HTTP 503: só o código, sem a URL: {fl[0]['frase'][:60] if fl else None}")
fl = sv.falhas_do_download("*** PORTAL FORA OU BLOQUEADO: o portal não respondeu após 3 tentativas (ReadTimeout): https://pncp.gov.br/x/" + URL_SEG + "\n")
checa(len(fl) == 1 and fl[0]["codigo"] == "ReadTimeout" and URL_SEG not in _json.dumps(fl) and fl[0]["frase"].startswith("Sem resposta do PNCP"), "PORTAL FORA com ReadTimeout: frase de tempo esgotado, sem a URL")
checa(sv.falhas_do_download("") == [] and sv.falhas_do_download(None) == [] and sv.falhas_do_download("  baixado: a.pdf (pdf, 10 bytes)\nDocumentos em: x\n") == [], "sem falha: lista vazia")
checa(sv.resumo_falhas([{"codigo": "422"}, {"codigo": "422"}, {"codigo": "ReadTimeout"}]) == "HTTP 422 em 2 arquivo(s); ReadTimeout em 1" and sv.resumo_falhas([]) == "", "resumo por código")
checa("(endereço omitido)" in sv.sem_enderecos("erro em https://pncp.gov.br/a/b/" + URL_SEG + " fim") and URL_SEG not in sv.sem_enderecos("erro em https://pncp.gov.br/a/b/" + URL_SEG + " fim"), "sem_enderecos tira a URL")

ESTADO.update(ligar=True, lista=[ARQ_TR], status_lista=200)
def vazou(at):
    t = textos(at).split("\n")
    todos = "\n".join(t)
    dentro = ""
    for p in f.PASTA.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".json", ".jsonl", ".txt", ".csv", ".md", ".log"):
            dentro += p.read_text(encoding="utf-8", errors="replace")
    return SEGREDO in todos or URL_SEG in todos or SEGREDO in dentro or URL_SEG in dentro
def avisos(at): return [w.value for w in at.warning]

print("\n=== tela: 422 (todos os arquivos falham) ===")
MODO["arq"] = {2: ("status", 422)}
at = busca_produto(); clica(at, BTN_BAIXAR); av = avisos(at)
checa("Termo de Referência: PNCP respondeu 422: erro do lado do PNCP ao carregar o arquivo; tente de novo mais tarde" in av, f"a tela mostra o arquivo, o código e a frase do 422: {[a for a in av if '422' in a][:1]}")
checa(any(t.startswith("Falhou: ") and t.endswith("download NÃO concluído: nenhum arquivo foi baixado") for t in textos(at).split("\n")), "o painel continua com a mensagem de antes (texto igual)")
checa(not vazou(at), "nenhum caminho interno, corpo do 422 ou URL na tela nem em arquivo da sessão")
_ctl = f.PASTA / "controle_vazamento.txt"; _ctl.write_text("x " + SEGREDO, encoding="utf-8")
checa(vazou(at) is True, "controle positivo: com o segredo gravado num arquivo da sessão, a verificação de vazamento diz 'vazou'")
_ctl.unlink()
checa(not vazou(at), "controle removido: a verificação volta a 'não vazou'")

print("\n=== tela: 404 ===")
MODO["arq"] = {2: ("status", 404)}
at = busca_produto(); clica(at, BTN_BAIXAR); av = avisos(at)
checa(any(a.startswith("Termo de Referência: PNCP respondeu 404: arquivo não encontrado") for a in av) and not vazou(at), "404: frase própria e nenhum vazamento")

print("\n=== tela: 503 (PORTAL FORA depois das tentativas) ===")
MODO["arq"] = {2: ("portal_fora", "o portal não respondeu após 3 tentativas (HTTP 503):")}
at = busca_produto(); clica(at, BTN_BAIXAR); av = avisos(at); tt = "\n".join(textos(at))
checa(any(a.startswith("(download interrompido): PNCP respondeu 503: servidor do PNCP") for a in av), f"503: 'download interrompido' com código e frase: {[a for a in av if '503' in a][:1]}")
checa(not vazou(at) and "https://" not in "\n".join(av), "503: a URL com identificadores não aparece (nem no aviso do log)")

print("\n=== tela: timeout ===")
MODO["arq"] = {2: ("portal_fora", "o portal não respondeu após 3 tentativas (ReadTimeout):")}
at = busca_produto(); clica(at, BTN_BAIXAR); av = avisos(at)
checa(any(a.startswith("(download interrompido): Sem resposta do PNCP (tempo esgotado)") for a in av) and not vazou(at), "timeout: frase de tempo esgotado e nenhum vazamento")

print("\n=== tela: um arquivo falha (422) e outro baixa ===")
ESTADO.update(lista=[ARQ_DFD, ARQ_TR])
MODO["arq"] = {1: ("status", 422)}
ESTADO["lista"] = [dict(ARQ_DFD, tipoDocumentoNome="Documento de Formalizacao da Demanda"), ARQ_TR]
at = busca_produto(); clica(at, BTN_BAIXAR); av = avisos(at); tt = textos(at).split("\n")
checa(any(a.startswith("1_1. DFD - DESPACHO DA CONTRATACAO EMERGENCIAL: PNCP respondeu 422") for a in av) and not any(a.startswith("Termo de Referência: PNCP respondeu") for a in av), "só o arquivo que falhou recebe frase (o que baixou não)")
checa(any(t.startswith("Concluída com falhas em ") and t.endswith("download PARCIAL: 1 arquivo(s) baixado(s), 1 falhou/falharam") for t in tt) and not vazou(at), "painel PARCIAL igual ao de antes e nenhum vazamento")

print("\n=== tela: tudo baixa ===")
ESTADO.update(lista=[ARQ_TR]); MODO["arq"] = {}
at = busca_produto(); clica(at, BTN_BAIXAR)
checa(not [a for a in avisos(at) if "PNCP respondeu" in a or "download interrompido" in a or "Sem resposta" in a] and any("download concluído (1 arquivo(s))" in t for t in textos(at).split("\n")), "sem falha: nenhuma frase de erro; 'download concluído (1 arquivo(s))'")
f.get = _get_base
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

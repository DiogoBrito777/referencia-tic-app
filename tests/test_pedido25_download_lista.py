"""v4h, Pedido 25 (Fases 1 e 2), SEM rede (socket bloqueado; rede SIMULADA). Fase 1: quando a lista do PNCP veio e nenhum arquivo é principal, a tela diz o motivo
(N arquivos, nenhum é edital/TR/ETP/DFD/aviso, nada baixado por regra) e lista os títulos, em vez de "download NÃO concluído"; falha real continua com a mensagem de falha;
quais arquivos são principais NÃO muda (f.eh_principal). Fase 2: o botão "Listar os TR e documentos principais desta compra" existe também em Produto (1 consulta, nada baixado;
linha sem PNCP mostra a mensagem que já existia). Dados simulados só aqui (regra 10: só dentro de testes).
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido25_download_lista.py   (na pasta do app)"""
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
TMP = DADOS / "pedido25" / f"_tmp_teste_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
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

print("=== Fase 1 (função pura): mensagem quando a lista veio e nenhum arquivo é principal ===")
LOG0 = f"  1 arquivos ativos: 0 principais (edital, TR, ETP, DFD, aviso) e 1 outros (propostas, atas, despachos...).\nDocumentos em: C:\\x\\y\n"
m = sv.mensagem_sem_principais(LOG0, ["Decisão – Ato que autoriza a Contratação Direta"])
checa(m is not None and m.startswith("A compra tem 1 arquivo(s) no PNCP, mas nenhum é edital, TR, ETP, DFD ou aviso; nada foi baixado por regra.") and "Decisão – Ato que autoriza a Contratação Direta" in m, f"1 arquivo, 0 principais: '{(m or '')[:120]}…'")
m3 = sv.mensagem_sem_principais(LOG0.replace("  1 arquivos ativos: 0 principais", "  3 arquivos ativos: 0 principais"), ["A", "B", "C"])
checa(m3 is not None and "3 arquivo(s)" in m3 and "A; B; C" in m3, "3 arquivos: conta e lista os 3 títulos")
m12 = sv.mensagem_sem_principais(LOG0.replace("  1 arquivos ativos: 0 principais", "  12 arquivos ativos: 0 principais"), [f"T{i}" for i in range(12)])
checa(m12 is not None and "T9" in m12 and "T10" not in m12 and "e mais 2" in m12, "12 arquivos: lista 10 títulos e diz 'e mais 2'")
checa(sv.mensagem_sem_principais(LOG0.replace("0 principais", "1 principais"), ["A"]) is None, "1 principal: sem mensagem nova (o fluxo é o de antes)")
checa(sv.mensagem_sem_principais("*** PORTAL FORA OU BLOQUEADO: x\n") is None and sv.mensagem_sem_principais("Lista de arquivos não veio (HTTP 503).\n") is None and sv.mensagem_sem_principais("") is None and sv.mensagem_sem_principais(None) is None, "portal fora, lista que não veio, texto vazio ou None: sem mensagem nova (falha de rede continua falha)")
checa(sv.mensagem_sem_principais(LOG0 + "  baixado: x.pdf (pdf, 10 bytes)\n", ["A"]) is None, "se algo foi baixado: sem mensagem nova")
checa(not f.eh_principal(DECISAO) and f.eh_principal(arq(2, "Termo de Referência", "Termo de Referencia")) and f.eh_principal(arq(3, "Edital", "Edital")), "quais arquivos são principais NÃO mudou: Decisão = não; TR e Edital = sim")
checa(f.texto_download({"estado": "falhou", "motivo": "nenhum arquivo foi baixado", "baixados": 0, "falhas": 0}) == "download NÃO concluído: nenhum arquivo foi baixado", "texto_download de ferramenta.py intacto")

print("\n=== Fase 1 (tela, Produto): só 'Decisão' na lista do PNCP ===")
ESTADO.update(ligar=True, lista=[DECISAO], status_lista=200)
at = busca_produto(); n0 = len(CHAMADAS)
clica(at, BTN_BAIXAR); t = textos(at)
nov = CHAMADAS[n0:]
checa("A compra tem 1 arquivo(s) no PNCP, mas nenhum é edital, TR, ETP, DFD ou aviso; nada foi baixado por regra." in t and "Decisão – Ato que autoriza a Contratação Direta" in t, "a tela mostra o motivo e o título do arquivo")
checa("download NÃO concluído" not in t and not [e.value for e in at.error], f"a tela NÃO mostra 'download NÃO concluído' nem erro (erros na tela: {len(at.error)})")
checa(sum(1 for u in nov if "/arquivos/" in u) == 0 and sum(1 for u in nov if u.endswith("/arquivos")) == 1, f"requisições no download: {len(nov)}; ao arquivo: 0; à lista: 1")

print("\n=== Fase 1 (tela): falha real e caso normal continuam como antes ===")
ESTADO.update(ligar=True, lista=[], status_lista=503)
at = busca_produto(); clica(at, BTN_BAIXAR); t = textos(at)
checa("download NÃO concluído: a lista de arquivos não veio do PNCP" in t and "nada foi baixado por regra" not in t, "lista que não veio (HTTP 503): continua 'download NÃO concluído: a lista de arquivos não veio do PNCP'")
ESTADO.update(ligar=True, lista=[DECISAO, arq(2, "Termo de Referência", "Termo de Referencia")], status_lista=200)
at = busca_produto(); n0 = len(CHAMADAS); clica(at, BTN_BAIXAR); t = textos(at); nov = CHAMADAS[n0:]
checa("download concluído (1 arquivo(s))" in t and "nada foi baixado por regra" not in t, "lista com TR: baixa o TR e diz 'download concluído (1 arquivo(s))'")
checa(sum(1 for u in nov if "/arquivos/2" in u) == 1 and sum(1 for u in nov if "/arquivos/1" in u) == 0, "só o TR foi pedido; a Decisão não (regra de principais intacta)")

print("\n=== Fase 2: botão 'Listar os TR e documentos principais' em Produto ===")
ESTADO.update(ligar=True, lista=[DECISAO, arq(2, "Termo de Referência", "Termo de Referencia"), arq(3, "Proposta da empresa", "Proposta"), arq(4, "Edital antigo", "Edital", ativo=False)], status_lista=200)
at = busca_produto()
checa(any(b.label == BTN_LISTAR for b in at.button), "Produto: o botão 'Listar os TR e documentos principais desta compra' está na tela")
n0 = len(CHAMADAS); clica(at, BTN_LISTAR); nov = CHAMADAS[n0:]
tab = next((d.value for d in at.dataframe if "principal" in d.value.columns), None)
checa(len(nov) == 1 and nov[0].endswith("/arquivos") and not any("/arquivos/" in u for u in nov), f"1 consulta ({len(nov)} requisição) e nada baixado")
checa(tab is not None and len(tab) == 3 and set(tab["titulo"]) == {"Decisão – Ato que autoriza a Contratação Direta", "Termo de Referência", "Proposta da empresa"}, f"a tabela lista os 3 arquivos ativos (o inativo fica de fora): {None if tab is None else len(tab)} linhas")
if tab is not None:
    pr = dict(zip(tab["titulo"], tab["principal"])); tr = dict(zip(tab["titulo"], tab["é TR"]))
    checa(pr["Termo de Referência"] and not pr["Proposta da empresa"] and not pr["Decisão – Ato que autoriza a Contratação Direta"] and tr["Termo de Referência"], "principal e 'é TR' marcados só no Termo de Referência")
ESTADO.update(ligar=False)
at = busca_produto(); n0 = len(CHAMADAS); clica(at, BTN_LISTAR); nov = CHAMADAS[n0:]
checa("Esta linha não está ligada ao PNCP: não há compra para listar." in textos(at) and len(nov) == 0, f"linha sem ligação ao PNCP: mensagem de antes e {len(nov)} requisição")
ESTADO.update(ligar=True, lista=[], status_lista=503)
at = busca_produto(); clica(at, BTN_LISTAR)
checa("O PNCP não devolveu a lista de documentos desta compra" in textos(at), "lista que não veio: aviso de antes ('não quer dizer que não existam')")

print("\n=== Serviço não mudou ===")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300); at.run(); at.radio(key="tipo_busca").set_value("Serviço").run()
checa(not at.exception, "a tela de Serviço abre sem erro")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

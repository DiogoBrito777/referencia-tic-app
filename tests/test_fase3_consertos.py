"""Fase 3 – um teste para cada conserto (OFFLINE: socket bloqueado; dados simulados só aqui).
 C1  'download concluído' só quando o download deu certo (ferramenta.opcao_3_baixar + resultado_download/texto_download)
 C2  'Preencha os atributos' não vaza para 'Mensagens da busca' (ferramenta.perguntar_atributos + limpar_log_busca)
 C3  aviso visível quando a busca é cortada (300 registros no modo rápido) (ferramenta.aviso_corte_busca)
 + checagem de que app.py chama as três funções (a tela em si NÃO foi executada).
Uso (na pasta do app): python -I -B -X utf8 tests\\test_fase3_consertos.py"""
import contextlib, io, json, socket, sys, shutil
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True

def _sem_rede(*a, **k): raise AssertionError("TENTOU ABRIR REDE")
socket.socket.connect = _sem_rede
import ferramenta as f

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

TMP = DADOS / "tmp_teste_fase3"; TMP.mkdir(exist_ok=True)
import time; RODADA = TMP / f"r{int(time.time())}"; RODADA.mkdir()

print("=== C1. 'download concluído' só quando o download der certo ===")
BUSCA = {"id_compra": "08031406000272026", "cnpj": "00000000000000", "ano": "2026", "sequencial": "1", "controle_pncp": "00000000000000-1-000001/2026"}
def roda_opcao_3(get_falso):
    saida = RODADA / f"s{len(list(RODADA.iterdir()))}"; saida.mkdir()
    f.SAIDA = saida
    f.ultima_busca = lambda: ("x.csv", [dict(BUSCA)]); f.escolher_numero = lambda msg, maximo: 1
    f.pergunta = lambda msg, padrao="": "n"; f.get = get_falso
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): f.opcao_3_baixar()
    return buf.getvalue()
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1, "url": "http://falso/a"}, {"titulo": "Termo de Referência", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2, "url": "http://falso/b"}]
def get_ok(url, params=None, binario=False):
    return (200, LISTA, {}) if url.endswith("/arquivos") else (200, b"%PDF-1.4 conteudo simulado", {})
def get_um_falha(url, params=None, binario=False):
    if url.endswith("/arquivos"): return 200, LISTA, {}
    return (200, b"%PDF-1.4 x", {}) if url.endswith("/a") else (500, b"", {})
def get_todos_falham(url, params=None, binario=False):
    return (200, LISTA, {}) if url.endswith("/arquivos") else (500, b"", {})
def get_lista_falha(url, params=None, binario=False): return 503, None, {}
def get_portal_fora(url, params=None, binario=False): raise f.PortalFora("simulado")
t_ok, t_um, t_todos, t_lista, t_fora = (roda_opcao_3(g) for g in (get_ok, get_um_falha, get_todos_falham, get_lista_falha, get_portal_fora))
r_ok, r_um, r_todos, r_lista, r_fora = (f.resultado_download(t) for t in (t_ok, t_um, t_todos, t_lista, t_fora))
print("  log do caso 'todos falham':", t_todos.strip().replace("\n", " | ")[:260])
checa(r_ok["estado"] == "concluido" and r_ok["baixados"] == 2 and r_ok["falhas"] == 0 and f.texto_download(r_ok).startswith("download concluído"), f"2 de 2 baixados -> 'download concluído': {f.texto_download(r_ok)}")
checa(r_um["estado"] == "parcial" and (r_um["baixados"], r_um["falhas"]) == (1, 1) and "concluído" not in f.texto_download(r_um), f"1 baixado e 1 falha -> NÃO diz 'concluído': {f.texto_download(r_um)}")
checa(r_todos["estado"] == "falhou" and r_todos["baixados"] == 0 and r_todos["falhas"] == 2 and "concluído" not in f.texto_download(r_todos).replace("NÃO concluído", ""), f"0 de 2 baixados (a opção ainda imprime 'Documentos em:') -> falhou: {f.texto_download(r_todos)}")
checa(r_lista["estado"] == "falhou" and "lista de arquivos" in r_lista["motivo"], f"lista de arquivos HTTP 503 -> falhou: {f.texto_download(r_lista)}")
checa(r_fora["estado"] == "falhou" and "portal" in r_fora["motivo"], f"portal fora -> falhou: {f.texto_download(r_fora)}")
checa(f.resultado_download("")["estado"] == "falhou", "log vazio -> falhou (nunca 'concluído' por falta de informação)")
checa(f.resultado_download("Esta compra não foi encontrada no PNCP (pode ser anterior à Lei 14.133). Sem documentos para baixar.")["estado"] == "falhou", "compra sem PNCP -> falhou")

print("\n=== C2. 'Preencha os atributos' não vai para 'Mensagens da busca' ===")
ATRS = [{"nome": "tela", "unidade": "pol", "regra": "x-2 a x+2"}, {"nome": "ram", "unidade": "GB", "regra": "x a x*4"}]
f.pergunta = lambda msg, padrao="": {"  tela": "24"}.get(msg.split(" (")[0], "")
buf = io.StringIO()
with contextlib.redirect_stdout(buf): ped = f.perguntar_atributos(ATRS)
bruto = buf.getvalue()
checa("Preencha os atributos" in bruto, "ANTES do conserto o texto impresso pela função tem a frase (é o que vazava): " + bruto.splitlines()[0])
limpo = f.limpar_log_busca(bruto + "  pesquisa de preço, página 1: HTTP 200, 100 registros (total informado: 250)\n")
checa("Preencha os atributos" not in limpo and "tela: aceita de" in limpo and "pesquisa de preço, página 1" in limpo, f"log limpo sem a frase e com as demais linhas ({len(limpo.splitlines())} linhas)")
checa(f.limpar_log_busca("") == "" and f.limpar_log_busca(None) == "" and f.limpar_log_busca("a\nb") == "a\nb", "log vazio, None e texto sem a frase ficam como estão")
checa(f.limpar_log_busca("  Preencha os atributos que quiser\nx") == "x", "linha com recuo também é removida")

print("\n=== C3. aviso visível quando a busca é cortada em 300 ===")
av = f.aviso_corte_busca({"registros_informados_pela_api": 1234, "registros_lidos": 300})
print("  aviso:", av)
checa(av.startswith("BUSCA CORTADA") and "1.234" in av and "300" in av and "934" in av, "informados 1.234, lidos 300: avisa o corte e diz os números (934 não analisados)")
checa(f.aviso_corte_busca({"registros_informados_pela_api": 300, "registros_lidos": 300}) == "", "300 de 300: sem aviso (não cortou)")
checa(f.aviso_corte_busca({"registros_informados_pela_api": 120, "registros_lidos": 120}) == "", "120 de 120: sem aviso")
checa(f.aviso_corte_busca({"registros_informados_pela_api": None, "registros_lidos": 0}) == "" and f.aviso_corte_busca({}) == "" and f.aviso_corte_busca(None) == "", "sem número (None/ausente): NÃO afirma corte")
checa("limite desta busca: 300" in f.aviso_corte_busca({"registros_informados_pela_api": 500, "registros_lidos": 300}, 300), "com limite informado, o aviso o cita")

print("\n=== W. app.py chama as três funções (leitura do texto; a tela NÃO foi executada) ===")
app = (RAIZ / "app.py").read_text(encoding="utf-8")
checa("f.resultado_download(texto)" in app and "f.texto_download(res_dl)" in app and "**Agora:** download concluído" not in app, "app.py: usa resultado_download/texto_download e não tem mais a frase fixa 'download concluído'")
checa("f.limpar_log_busca(log.getvalue())" in app, "app.py: o log da busca passa por limpar_log_busca")
checa("f.aviso_corte_busca(resumo)" in app and "st.warning(aviso_corte)" in app, "app.py: mostra st.warning(aviso_corte)")
import ast; ast.parse(app); ast.parse((RAIZ / "ferramenta.py").read_text(encoding="utf-8")); print("sintaxe ok: app.py, ferramenta.py")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

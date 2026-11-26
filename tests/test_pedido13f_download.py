"""v4h, Pedido 13F – download do catálogo de serviços (servicos.baixar_catalogo_servicos) e o botão 'Atualizar catálogo' do modo Serviço, OFFLINE.
Socket bloqueado; a rede é trocada por respostas SIMULADAS (dado simulado só existe aqui, dentro do teste automatizado). Tudo grava em pasta temporária de teste;
o config\\catalogo_servicos.csv real é só LIDO (o hash é conferido no fim). Cobre: download completo (7 páginas, 3.108 itens), página sem 'resultado', HTTP 500,
total diferente de totalRegistros, arquivo novo com menos de 80% (fronteira 2.486 x 2.487), histórico criado, colunas iguais às do arquivo atual, forcar=False sem rede,
e o botão na tela (sucesso e portal fora) com o catálogo atual mantido.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13f_download.py   (na pasta do app)"""
import csv, hashlib, shutil, socket, sys, time
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
REAL = RAIZ / "config" / "catalogo_servicos.csv"; SHA_REAL = sha(REAL)
TMP = DADOS / "tmp_teste_fase4" / f"p13f_{int(time.time())}"; TMP.mkdir(parents=True)
f.PASTA = TMP; f.SAIDA = TMP; f.LOG = TMP / "log_teste.jsonl"

def itens_simulados(n):
    return [{"codigoSecao": 1 + i % 9, "nomeSecao": "SEÇÃO SIMULADA", "codigoDivisao": 10 + i % 90, "nomeDivisao": "DIVISÃO", "codigoGrupo": 100 + i % 900, "nomeGrupo": "GRUPO",
             "codigoClasse": None if i % 4 == 0 else 1000 + i % 9000, "nomeClasse": None if i % 4 == 0 else "CLASSE", "codigoSubclasse": None, "nomeSubclasse": None,
             "codigoServico": 20000 + i, "nomeServico": f"SERVIÇO SIMULADO ÇÃO {i}", "codigoCpc": 9311, "exclusivoCentralCompras": False, "statusServico": i % 10 != 0,
             "dataHoraAtualizacao": "2026-11-20T09:09:59.689615"} for i in range(n)]

CHAMADAS = []
class Portal:
    """Resposta simulada do portal; modo escolhe o defeito."""
    def __init__(self, n=3108, modo="ok", total=None, pag=500):
        self.itens, self.modo, self.total, self.pag = itens_simulados(n), modo, (n if total is None else total), pag
    def __call__(self, url, params=None, binario=False):
        CHAMADAS.append((url, dict(params or {})))
        p = (params or {}).get("pagina", 1); tp = (len(self.itens) + self.pag - 1) // self.pag
        if self.modo == "http500" and p == 3: return 500, None, {}
        if self.modo == "sem_resultado" and p == 2: return 200, {"mensagem": "erro"}, {}
        if self.modo == "corpo_nulo" and p == 1: return 200, None, {}
        return 200, {"resultado": self.itens[(p - 1) * self.pag: p * self.pag], "totalRegistros": self.total, "totalPaginas": tp, "paginasRestantes": tp - p}, {}

def pasta(nome, com_atual=True):
    d = TMP / nome; d.mkdir(); alvo = d / "catalogo_servicos.csv"
    if com_atual: shutil.copyfile(REAL, alvo)
    return alvo

print("=== A. download completo ===")
alvo = pasta("completo", com_atual=False); CHAMADAS.clear(); f.get = Portal()
r = sv.baixar_catalogo_servicos(destino=alvo, referencia=REAL)
linhas = list(csv.DictReader(alvo.open(encoding="utf-8-sig", newline=""), delimiter=";"))
checa(len(CHAMADAS) == 7 and [c[1]["pagina"] for c in CHAMADAS] == list(range(1, 8)) and all(c[1]["tamanhoPagina"] == 500 for c in CHAMADAS) and all(c[0].endswith("/modulo-servico/6_consultarItemServico") for c in CHAMADAS),
      f"7 chamadas, páginas 1 a 7, tamanhoPagina=500, endpoint modulo-servico/6_consultarItemServico ({len(CHAMADAS)} chamadas)")
checa(len(linhas) == 3108 and len(r) == 3108 and len({l['codigoServico'] for l in linhas}) == 3108, f"3.108 itens gravados e devolvidos, códigos distintos ({len(linhas)})")
cab_real = REAL.read_text(encoding="utf-8-sig").splitlines()[0]; cab_novo = alvo.read_text(encoding="utf-8-sig").splitlines()[0]
checa(cab_novo == cab_real and cab_novo.split(";")[-1] == "baixado_em", f"cabeçalho igual ao do catalogo_servicos.csv atual (17 colunas, termina em baixado_em): {cab_novo == cab_real}")
b = alvo.read_bytes()
checa(b[:3] == b"\xef\xbb\xbf" and b.count(b"\r\n") == len(linhas) + 1 and b";" in b.split(b"\r\n")[0], f"utf-8 com BOM, separador ';', fim de linha CRLF como o atual ({b.count(bytes([13, 10]))} CRLF para {len(linhas) + 1} linhas)")
checa(REAL.read_bytes().count(b"\r\n") == len(list(csv.reader(REAL.open(encoding='utf-8-sig', newline=''), delimiter=';'))), "o arquivo atual real também é CRLF (mesmo formato)")
checa(all(l["baixado_em"] == linhas[0]["baixado_em"] and len(l["baixado_em"]) == 19 for l in linhas) and linhas[0]["exclusivoCentralCompras"] == "False" and {l["statusServico"] for l in linhas} == {"True", "False"}
      and linhas[0]["nomeServico"].startswith("SERVIÇO SIMULADO ÇÃO") and linhas[0]["codigoClasse"] == "", "baixado_em preenchido (AAAA-MM-DDTHH:MM:SS), booleanos como 'True'/'False', acentos preservados, None vira vazio")
checa(not (alvo.parent / "historico").exists() and not alvo.with_suffix(".tmp").exists(), "arquivo novo sem histórico (não havia atual) e sem .tmp sobrando")

print("\n=== B. histórico criado ao substituir ===")
alvo = pasta("historico"); antes = sha(alvo); CHAMADAS.clear(); f.get = Portal(n=3200)
sv.baixar_catalogo_servicos(forcar=True, destino=alvo)
h = list((alvo.parent / "historico").glob("catalogo_servicos__*.csv"))
import re
checa(len(h) == 1 and re.fullmatch(r"catalogo_servicos__\d{4}-\d\d-\d\d_\d{4}\.csv", h[0].name) and sha(h[0]) == antes, f"cópia do atual em historico\\{h[0].name if h else '?'} com o mesmo SHA-256 do atual de antes")
checa(sha(alvo) != antes and len(list(csv.DictReader(alvo.open(encoding='utf-8-sig', newline=''), delimiter=';'))) == 3200 and not alvo.with_suffix(".tmp").exists(), "o atual foi substituído pelo novo (3.200 linhas) e não sobrou .tmp")

print("\n=== C. sem forcar e com arquivo: usa o local, 0 chamadas ===")
alvo = pasta("local"); antes = sha(alvo); CHAMADAS.clear(); f.get = Portal()
r = sv.baixar_catalogo_servicos(destino=alvo)
checa(not CHAMADAS and len(r) == 3108 and sha(alvo) == antes, "forcar=False com arquivo existente: lê o local, 0 chamadas, arquivo igual")

print("\n=== D. abortos: o atual NÃO é substituído ===")
def aborta(nome, portal, esperado, descricao):
    alvo = pasta(nome); antes = sha(alvo); CHAMADAS.clear(); f.get = portal
    try:
        sv.baixar_catalogo_servicos(forcar=True, destino=alvo); exc = None
    except f.PortalFora as e:
        exc = e
    checa(exc is not None and isinstance(exc, esperado) and sha(alvo) == antes and not alvo.with_suffix(".tmp").exists() and not (alvo.parent / "historico").exists(),
          f"{descricao}: aborta ({type(exc).__name__}), atual intacto (mesmo SHA-256), sem .tmp e sem histórico. Mensagem: {str(exc)[:110]}")
aborta("sem_res", Portal(modo="sem_resultado"), f.PortalFora, "página 2 sem 'resultado'")
aborta("corpo_nulo", Portal(modo="corpo_nulo"), f.PortalFora, "página 1 com corpo nulo")
aborta("http500", Portal(modo="http500"), f.PortalFora, "HTTP 500 na página 3")
aborta("total", Portal(n=3108, total=3109), sv.CatalogoRejeitado, "itens baixados (3.108) diferente de totalRegistros (3.109)")
aborta("total_nulo", Portal(n=3108, total=0), sv.CatalogoRejeitado, "totalRegistros=0 com 3.108 itens")
aborta("menos80", Portal(n=2000), sv.CatalogoRejeitado, "arquivo novo com 2.000 linhas (< 80% de 3.108)")
aborta("fronteira_baixo", Portal(n=2486), sv.CatalogoRejeitado, "2.486 linhas (80% de 3.108 = 2.486,4): rejeitado")
alvo = pasta("fronteira_alto"); f.get = Portal(n=2487); sv.baixar_catalogo_servicos(forcar=True, destino=alvo)
checa(len(list(csv.DictReader(alvo.open(encoding='utf-8-sig', newline=''), delimiter=';'))) == 2487, "2.487 linhas (acima de 80%): aceito")
checa(sv.CatalogoRejeitado.__mro__[1] is f.PortalFora, "CatalogoRejeitado é um PortalFora (o app trata os dois do mesmo jeito)")

print("\n=== E. botão 'Atualizar catálogo' no modo Serviço (AppTest) ===")
real_dest = sv.CATALOGO_SERVICOS
alvo = pasta("tela"); sv.CATALOGO_SERVICOS = alvo; antes = sha(alvo)
def abre():
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
    at.radio(key="tipo_busca").set_value("Serviço").run(); return at
def botao(at): return next(b for b in at.button if b.label == "Atualizar catálogo")
try:
    at = abre(); legenda0 = next(str(c.value) for c in at.caption if "Catálogo oficial de serviços" in str(c.value))
    checa("3.108 serviços" in legenda0 and "atualizado em " + max(r["baixado_em"] for r in sv.ler_catalogo(REAL))[:16].replace("T", " ") in legenda0, f"legenda antes (data do próprio arquivo): {legenda0[:100]}")
    CHAMADAS.clear(); f.get = Portal(n=3200); botao(at).click().run()
    leg1 = next(str(c.value) for c in at.caption if "Catálogo oficial de serviços" in str(c.value))
    checa(not at.exception and len(CHAMADAS) == 7 and "3.200 serviços" in leg1 and sha(alvo) != antes and len(list((alvo.parent / "historico").glob("*.csv"))) == 1,
          f"clique: 7 chamadas simuladas, sem exceção, legenda passa a '3.200 serviços' ({leg1[:70]}), histórico criado")
    ap = sha(alvo); CHAMADAS.clear(); f.get = Portal(n=3200, modo="http500"); at = abre(); botao(at).click().run()
    erros = [str(e.value) for e in at.error]
    checa(not at.exception and any("Não atualizei o catálogo de serviços" in e for e in erros) and sha(alvo) == ap, f"portal fora (HTTP 500): mensagem na tela, o catálogo atual foi mantido e o app não caiu ({[e[:70] for e in erros]})")
    ap = sha(alvo); f.get = Portal(n=100); at = abre(); botao(at).click().run()
    checa(not at.exception and any("menos de 80%" in str(e.value) for e in at.error) and sha(alvo) == ap, "lista nova com 100 itens: rejeitada na tela, catálogo mantido")
    alvo.unlink(); at = abre()
    checa(not at.exception and any("Não achei o catálogo de serviços" in str(e.value) for e in at.error) and any(b.label == "Atualizar catálogo" for b in at.button), "sem o arquivo: erro explicado e o botão 'Atualizar catálogo' continua na tela")
    CHAMADAS.clear(); f.get = Portal(n=3108); botao(at).click().run()
    checa(not at.exception and alvo.exists() and len(CHAMADAS) == 7 and not at.error, "sem o arquivo, o botão baixa o catálogo (7 chamadas simuladas)")
finally:
    sv.CATALOGO_SERVICOS = real_dest
checa(sha(REAL) == SHA_REAL, f"config\\catalogo_servicos.csv real intacto (SHA-256 {SHA_REAL[:12]}… igual ao de antes)")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

"""v4h, Pedido 13E – orientação para termos de software e licença, OFFLINE (socket bloqueado, rede trocada por uma função que CONTA as chamadas: têm que ser 0). Cobre os Itens 4 a 8:
 - config\\termos_software.csv tem os 13 termos pedidos (lido pelo app; a equipe edita sem mexer no código);
 - produto: 'windows 11', 'office 365', 'microsoft' (nenhum PDM com o termo) mostram a orientação com o código do PDM 'Software' ativo CALCULADO pelo catálogo local;
 - serviço: o mesmo termo lista os serviços ativos com 'licenc' ou 'software como servico' (no máximo 10) e a frase de confirmação;
 - 'notebook' (produto) e 'instalação elétrica' (serviço) acham resultados e NÃO mostram a orientação; um termo fora do arquivo ('zzzprog') não mostra;
 - um termo NOVO no arquivo muda o comportamento; arquivo AUSENTE não derruba o app (sem orientação, sem erro). O arquivo real é movido/restaurado em try/finally e o hash conferido.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13e_software.py   (na pasta do app)"""
import csv, hashlib, socket, sys, time, unicodedata
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

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
CHAMADAS = []
def get(url, params=None, binario=False):
    CHAMADAS.append(url); return 200, {"resultado": [], "totalRegistros": 0, "paginasRestantes": 0}, {}
f.get = get
TMP = DADOS / "tmp_teste_fase4"; TMP.mkdir(exist_ok=True)
f.PASTA = TMP / f"p13e_{int(time.time())}"; f.PASTA.mkdir()
def norm(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
ARQ = RAIZ / "config" / "termos_software.csv"; ORIG = ARQ.read_bytes(); SHA0 = hashlib.sha256(ORIG).hexdigest()

def busca(modo, termo):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
    if modo == "Serviço": at.radio(key="tipo_busca").set_value("Serviço").run()
    at.text_input(key="termo" if modo == "Produto" else "serv_termo").set_value(termo).run()
    return at
def orient(at, modo):
    chave = "não é um tipo de produto no catálogo oficial" if modo == "Produto" else "Sugestão de onde procurar"
    return [str(i.value) for i in at.info if chave in str(i.value)]

print("=== A. o arquivo config\\termos_software.csv ===")
termos = [l["termo"] for l in csv.DictReader(ARQ.open(encoding="utf-8-sig", newline=""), delimiter=";")]
checa(termos == ["windows", "office", "microsoft", "365", "word", "excel", "antivirus", "licenca", "licencas", "software", "xdr", "edr", "endpoint"], f"13 termos do pedido, uma coluna 'termo': {termos}")

print("\n=== B. produto: termos de software sem PDM ===")
cat = list(csv.DictReader((RAIZ / "config" / "catalogo_pdm.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
cod_esperado = [r["codigoPdm"] for r in cat if norm(r["nomePdm"]).strip() == "software" and str(r["statusPdm"]).lower() == "true"]
checa(len(cod_esperado) == 1, f"o catálogo local tem 1 PDM 'Software' ativo (calculado agora pelo teste: {cod_esperado}); o app não escreve esse número no código")
fonte = (RAIZ / "app.py").read_text(encoding="utf-8")
checa(cod_esperado[0] not in fonte.split("def ler_termos_software")[1].split("def lista_resultados")[0], "o número do PDM não está escrito no código da orientação")
for termo in ("windows 11", "office 365", "microsoft"):
    at = busca("Produto", termo); o = orient(at, "Produto")
    checa(not at.exception and len(o) == 1 and f"'{termo}' não é um tipo de produto no catálogo oficial (os PDMs são tipos, não marcas nem versões)." in o[0] and f"({cod_esperado[0]})" in o[0]
          and "Procure 'software'" in o[0] and "'Ver configurações (itens CATMAT)'" in o[0] and f"filtro de texto '{termo}'" in o[0], f"produto, '{termo}': orientação com o código {cod_esperado[0]} e o filtro de texto")
checa(not CHAMADAS, f"produto: 0 chamadas de rede ({len(CHAMADAS)})")

print("\n=== C. serviço: termos de software sem serviço com o nome ===")
catalogo_s = list(csv.DictReader((RAIZ / "config" / "catalogo_servicos.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
ativos = [r for r in catalogo_s if r["statusServico"] == "True" and ("licenc" in norm(r["nomeServico"]) or "software como servico" in norm(r["nomeServico"]))]
checa(len(ativos) > 0, f"o catálogo local tem serviços ativos com 'licenc' ou 'software como servico' ({len(ativos)})")
for termo in ("windows 11", "office 365", "microsoft"):
    at = busca("Serviço", termo); o = orient(at, "Serviço")
    tab_sug = [d.value for d in at.dataframe if "usar" in d.value.columns]      # Pedido 13K: os serviços sugeridos agora estão numa tabela com a coluna "usar" (antes eram linhas "- código – nome" no st.info)
    linhas = [f"{c} – {n}" for c, n in zip(tab_sug[0]["código"], tab_sug[0]["serviço"])] if len(tab_sug) == 1 else []
    esperados = [f"{r['codigoServico']} – {r['nomeServico']}" for r in ativos[:10]]
    checa(len(o) == 1 and "Sugestão de onde procurar. A equipe e o órgão confirmam qual código usar." in o[0] and 1 <= len(linhas) <= 10 and linhas == esperados, f"serviço, '{termo}': frase de confirmação e {len(linhas)} serviços ativos do catálogo local (no máximo 10), na ordem do catálogo")
    checa(all("licenc" in norm(l) or "software como servico" in norm(l) for l in linhas) and "é o certo" not in o[0].lower(), f"serviço, '{termo}': só nomes com licenc/software como servico e nenhuma afirmação de qual é o certo")
checa(not CHAMADAS, f"serviço: 0 chamadas de rede ({len(CHAMADAS)})")

print("\n=== D. não aparece quando a busca achou resultados ou o termo não está no arquivo ===")
n_antes_nb = len(CHAMADAS)
at = busca("Produto", "notebook")
N_NB = len(CHAMADAS) - n_antes_nb   # as contagens de compras do produto que acha PDMs (comportamento que já existia; nada a ver com a orientação)
checa(not at.exception and not orient(at, "Produto") and any("código(s) encontrado(s)" in str(c.value) for c in at.caption), "produto 'notebook': achou PDMs e NÃO mostra a orientação")
at = busca("Serviço", "instalação elétrica")
checa(not at.exception and not orient(at, "Serviço") and any("serviço(s) encontrado(s)" in str(c.value) for c in at.caption), "serviço 'instalação elétrica': achou serviços e NÃO mostra a orientação")
at = busca("Produto", "zzzprog"); at2 = busca("Serviço", "zzzprog")
checa(not orient(at, "Produto") and not orient(at2, "Serviço") and not at.exception and not at2.exception, "termo fora do arquivo ('zzzprog'): nada achado e sem orientação, nos dois modos")

print("\n=== E. o arquivo manda: termo novo, arquivo ausente ===")
try:
    import servicos as sv      # Pedido 20: com o Pedido 18, um termo sem item no PDM Software vira a mensagem de serviço; o termo novo deste teste precisa existir nos itens
    _itens = sv.ler_itens_software(); N_ADOBE = sv.itens_que_citam_termo("adobe", _itens)
    checa(b"adobe" not in ORIG.lower() and N_ADOBE > 0, f"termo novo escolhido ('adobe'): fora do arquivo de termos e citado em {N_ADOBE} dos {len(_itens)} itens do PDM Software (palavra inteira)")
    ARQ.write_bytes(ORIG + b"adobe\r\n")
    a1 = busca("Produto", "adobe"); a2 = busca("Serviço", "adobe")
    checa(len(orient(a1, "Produto")) == 1 and len(orient(a2, "Serviço")) == 1, "termo NOVO no arquivo ('adobe', com itens no PDM Software): a orientação passa a aparecer nos dois modos (sem mexer no código)")
    ARQ.write_bytes(ORIG + b"zzzprog\r\n")
    c1 = busca("Produto", "zzzprog"); c2 = busca("Serviço", "zzzprog")
    checa(not orient(c1, "Produto") and sv.mensagem_software_sem_item("zzzprog", len(_itens)) in [str(i.value) for i in c1.info] and len(orient(c2, "Serviço")) == 1,
          "termo NOVO no arquivo SEM item no PDM Software ('zzzprog'): Produto mostra a mensagem de serviço (Pedido 18) e o Serviço continua com a orientação")
    ARQ.write_bytes(ORIG)
    ARQ.rename(ARQ.with_suffix(".csv.ausente"))
    b1 = busca("Produto", "windows 11"); b2 = busca("Serviço", "windows 11")
    checa(not b1.exception and not b2.exception and not orient(b1, "Produto") and not orient(b2, "Serviço"), "arquivo AUSENTE: o app não cai, sem orientação e sem erro (produto e serviço)")
    checa(not b1.error and not b2.error, f"arquivo ausente: nenhuma caixa de erro na tela ({[str(e.value)[:50] for e in b1.error]})")
finally:
    ausente = ARQ.with_suffix(".csv.ausente")
    if ausente.exists(): ausente.rename(ARQ)
    ARQ.write_bytes(ORIG)
checa(hashlib.sha256(ARQ.read_bytes()).hexdigest() == SHA0, f"o arquivo real foi restaurado (SHA-256 {SHA0[:12]}… igual ao de antes)")
checa(len(CHAMADAS) - N_NB == 0, f"chamadas de rede nas cenas da orientação: {len(CHAMADAS) - N_NB} (as {N_NB} restantes são as contagens de compras do produto 'notebook', que acha PDMs; já existiam)")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

"""Ferramenta MVP – Referência TIC (UnDF / PMDF).

Menu em texto para a equipe testar o fluxo: buscar compras no PNCP, ver a tabela, baixar documentos,
recortar as páginas do item e montar o texto para colar numa IA.

Regras seguidas aqui:
- Só dados públicos do PNCP, só GET, sem login e sem chave de API. Nenhuma IA participa da busca nem dos filtros.
- Pausa de 3 s entre chamadas, até 3 tentativas. Se o portal cair (ou responder 403/bloqueio), avisa na tela e para.
- Trabalha só na própria pasta: usa o recorte_teste_ia.py desta mesma pasta e grava em saida/.
- Roda no Windows e no Linux (Streamlit Community Cloud). A conversão de .doc pelo Word só existe no Windows com Word.
Menu em texto: python ferramenta.py. Tela: streamlit run app.py.
"""
import csv
import datetime as dt
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.parse
import zipfile
from pathlib import Path

# ----------------------------------------------------------------- caminhos e limites
PASTA = Path(__file__).resolve().parent
CONFIG = PASTA / "config"
SAIDA = PASTA / "saida"
SAIDA.mkdir(exist_ok=True)  # a pasta saida/ não vai para o repositório: é criada na primeira execução
PRODUTOS_CSV = CONFIG / "produtos.csv"
INSTRUCAO = CONFIG / "INSTRUCAO_FICHA.txt"
RECORTE_PY = PASTA / "recorte_teste_ia.py"  # cópia local, na mesma pasta
LOG = SAIDA / "log_requisicoes.jsonl"

BUSCA = "https://pncp.gov.br/api/search/"            # busca do portal (mesma usada nas rodadas 1, 2 e 5)
API = "https://pncp.gov.br/api/pncp/v1"              # API de integração (itens, resultados, arquivos)
CONSULTA = "https://pncp.gov.br/api/consulta/v1"     # API de Consultas (compras por data de publicação e modalidade)
COMPRAS = "https://dadosabertos.compras.gov.br"      # Compras.gov.br dados abertos (pesquisa de preço por código do catálogo)
MAX_PAGINAS_CATALOGO = 20 # até 20 páginas de 100 registros na pesquisa de preço por código
MAX_VINCULOS = 40        # até 40 compras convertidas para o nº de controle do PNCP por busca
FONTE_PADRAO = "1"       # 1 = API de Consultas; 2 = busca do portal (ver LEIA_ME: por que a 1 é a padrão)
MODALIDADES = (6, 8)     # 6 = Pregão Eletrônico, 8 = Dispensa (tabela /v1/modalidades)
MAX_PAGINAS_CONSULTA = 2 # páginas de 50 compras por mês e modalidade na API de Consultas
TERMOS_TI = r"informatica|tecnologia da informacao|\btic\b|computador|equipamentos de ti\b|microcomputador"
USER_AGENT = "ReferenciaTIC-Ferramenta/0.1 (pesquisa academica UnDF)"
PAUSA_S = 3              # pausa antes de cada chamada
TENTATIVAS = 3           # tentativas por chamada
MAX_PAGINAS_BUSCA = 3    # até 3 páginas de 100 editais na busca
MAX_COMPRAS = 40         # até 40 compras (com resultado) analisadas por busca
MAX_RESULTADOS = 60      # até 60 consultas de resultado de item por busca
MESES = 12               # janela da busca
OLLAMA_NUM_CTX = 8192    # quando a leitura com Ollama for implementada: num_ctx >= 8192, senão o recorte é cortado


class PortalFora(Exception):
    """O portal não respondeu depois das tentativas, ou respondeu com bloqueio (403)."""


# ----------------------------------------------------------------- utilidades
def norm(s):
    """Minúsculas e sem acentos (para comparar textos)."""
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def agora():
    return dt.datetime.now().isoformat(timespec="seconds")


def numero(txt):
    """'15,6' -> 15.6"""
    return float(txt.replace(".", "").replace(",", ".")) if re.fullmatch(r"\d{1,3}(\.\d{3})+", txt) else float(txt.replace(",", "."))


def ler_valor(txt):
    """Valor digitado pelo usuário: '16', '15,6', '960G', '512 GB', '1TB', '1 T' (T/TB = x1024, em GB)."""
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(tb|t|gb|g)?\s*", norm(txt))
    if not m:
        raise ValueError(txt)
    return numero(m.group(1)) * (1024 if (m.group(2) or "").startswith("t") else 1)


def pergunta(msg, padrao=""):
    r = input(msg).strip()
    return r or padrao


def escolher_numero(msg, maximo):
    r = input(msg).strip()
    if not r.isdigit() or not 1 <= int(r) <= maximo:
        print("Número inválido.")
        return None
    return int(r)


# ----------------------------------------------------------------- rede (GET público)
_sessao = None
STATS = {}  # contagem de chamadas e falhas da última busca


def contar(chave):
    STATS[chave] = STATS.get(chave, 0) + 1


def grupo(url):
    if "dadosabertos.compras.gov.br" in url:
        return "Compras.gov.br"
    return "busca do portal" if "/api/search" in url else "API de Consultas" if "/api/consulta" in url else "API de integração"


def get(url, params=None, binario=False):
    """GET com pausa, até 3 tentativas e log. Devolve (status, corpo, headers). Levanta PortalFora se não conseguir."""
    global _sessao
    import requests
    if _sessao is None:
        _sessao = requests.Session()
        _sessao.headers["User-Agent"] = USER_AGENT
    ultimo = ""
    for t in range(1, TENTATIVAS + 1):
        time.sleep(PAUSA_S)
        try:
            contar("chamadas")
            contar("grupo:" + grupo(url))
            r = _sessao.get(url, params=params, timeout=60)
            if r.status_code >= 400:
                contar("falhas")
                contar(f"falha:HTTP {r.status_code}")
                contar("falhagrupo:" + grupo(url))
            registro = {"ts": agora(), "url": r.url, "tentativa": t, "status": r.status_code, "bytes": len(r.content)}
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            if r.status_code == 403 or b"captcha" in r.content[:2000].lower():
                raise PortalFora(f"HTTP {r.status_code}: possível bloqueio do portal. Parei para não insistir.")
            if r.status_code >= 500 or r.status_code == 429:
                ultimo = f"HTTP {r.status_code}"
                time.sleep(5 * t)
                continue
            if r.status_code == 204:
                return 204, (b"" if binario else None), r.headers
            if binario:
                return r.status_code, r.content, r.headers
            try:
                return r.status_code, r.json(), r.headers
            except ValueError:
                return r.status_code, None, r.headers
        except requests.RequestException as e:
            ultimo = type(e).__name__
            contar("falhas")
            contar(f"falha:{ultimo}")
            contar("falhagrupo:" + grupo(url))
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": agora(), "url": url, "tentativa": t, "erro": ultimo}) + "\n")
            time.sleep(5 * t)
    raise PortalFora(f"o portal não respondeu após {TENTATIVAS} tentativas ({ultimo}): {url}")


# ----------------------------------------------------------------- produtos.csv e faixas
def ler_produtos():
    """Lê config\\produtos.csv -> {produto: [ {nome, apelidos, unidades{u: fator}, regra} ]}."""
    produtos = {}
    with PRODUTOS_CSV.open(encoding="utf-8-sig", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            if not (l.get("produto") or "").strip():
                continue
            apelidos = [a.strip() for a in l["atributo"].split("|") if a.strip()]
            unidades = {}
            for u in l["unidade"].split("|"):
                u = u.strip()
                if not u:
                    continue
                m = re.fullmatch(r"(.+?)\*(\d+(?:\.\d+)?)", u)  # ex.: TB*1024 = multiplica por 1024
                unidades[m.group(1) if m else u] = float(m.group(2)) if m else 1.0
            produtos.setdefault(l["produto"].strip(), []).append(
                {"nome": apelidos[0], "apelidos": apelidos, "unidades": unidades, "regra": l["regra_da_faixa"].strip(), "unidade": l["unidade"].split("|")[0].split("*")[0]})
    return produtos


def calcular(expr, x):
    """Avalia 'x', 'x+2', 'x-12', '2*x', '1.5*x', 'x*2' (só isso; nada de eval)."""
    e = expr.replace(" ", "")
    if e == "x":
        return x
    m = re.fullmatch(r"x([+\-*/])(\d+(?:\.\d+)?)", e) or re.fullmatch(r"(\d+(?:\.\d+)?)\*x", e)
    if not m:
        raise ValueError(f"regra_da_faixa não entendida: {expr}")
    if m.re.pattern.startswith("(\\d"):
        return float(m.group(1)) * x
    op, n = m.group(1), float(m.group(2))
    return {"+": x + n, "-": x - n, "*": x * n, "/": x / n}[op]


def faixa(regra, x):
    """'x-2 a x+2' com x=15 -> (13, 17)."""
    a, b = [p.strip() for p in regra.split(" a ")]
    return calcular(a, x), calcular(b, x)


def valores_no_texto(descricao, atributos):
    """Acha 'número + unidade' na descrição e entrega cada valor ao atributo cuja palavra-chave estiver mais perto.
    Devolve {atributo: [valores na unidade base, em ordem de aparição]}."""
    t = norm(descricao)
    achados = {a["nome"]: [] for a in atributos}
    posicoes = {a["nome"]: [(m.start(), m.end()) for ap in a["apelidos"] for m in re.finditer(r"(?<![a-z])" + re.escape(norm(ap)) + r"(?![a-z])", t)] for a in atributos}
    candidatos = []
    for a in atributos:
        for u, fator in a["unidades"].items():
            un = re.escape(norm(u))
            fim = "" if not un[-1:].isalpha() else r"(?![a-z])"
            rx = r"(?<![\d,.])(\d+(?:[.,]\d+)?)\s*(?:\([^)]{0,20}\)\s*)?" + un + fim
            for m in re.finditer(rx, t):
                if re.search(r"(ate|expansivel|maximo|max\.?)\s*(de\s*)?$", t[max(0, m.start() - 20):m.start()]):
                    continue  # 'expansível até 32 GB' é limite de expansão, não o valor do item
                candidatos.append((m.start(), m.end(), numero(m.group(1)) * fator, a["unidades"]))
    vistos = set()
    for ini, fim, valor, unids in sorted(candidatos, key=lambda c: (c[0], -c[1])):
        if (ini, valor) in vistos:
            continue
        vistos.add((ini, valor))
        melhor, dist = None, 41  # palavra-chave a no máximo 40 caracteres
        for a in atributos:
            if a["unidades"] is not unids and not (set(a["unidades"]) & set(unids)):
                continue
            for k_ini, k_fim in posicoes[a["nome"]]:
                d = ini - k_fim if k_fim <= ini else k_ini - fim if k_ini >= fim else 0  # caracteres entre a palavra e o número
                if d < dist:
                    melhor, dist = a["nome"], d
        if melhor:
            achados[melhor].append(valor)
    return achados


INFINITO = float("inf")


def faixas_do_catalogo(descricao, atributos):
    """Lê descrições no formato do catálogo de compras, 'chave: valor' sem unidade
    (ex.: 'memória ram: superior a 8', 'armazenamento ssd: 480 a 1.000 gb', 'tela: até 14', 'garantia on site: 12').
    O catálogo informa faixas, não um valor exato. Devolve {atributo: [(mínimo, máximo, texto)]}."""
    t = norm(descricao)
    achados = {a["nome"]: [] for a in atributos}
    for a in atributos:
        chaves = "|".join(re.escape(norm(ap)) for ap in a["apelidos"])
        for m in re.finditer(rf"(?<![a-z])(?:{chaves})(?![a-z])[a-z ]{{0,25}}:\s*([^,;]{{1,40}})", t):
            v = so_valor(m.group(1))
            faixa_item = faixa_do_valor(v, a)
            if faixa_item:
                achados[a["nome"]].append((*faixa_item, v))
    return achados


RX_VALOR = re.compile(r"^(?:(?:superior a|acima de|mais de|maior que|minimo de|minimo|no minimo|a partir de|pelo menos|ate|maximo de|maximo|inferior a|menor que)\s*)?\d+(?:[.,]\d+)*(?:\s*(?:a|-)\s*\d+(?:[.,]\d+)*)?(?:\s*(?:gb|tb|mb|polegadas|pol|\"|''|meses|mes|anos|ano|megapixels|mp|kva|va|w|metros|m|minutos|min|portas)(?![a-z])\.?)?")


def so_valor(v):
    """Corta o texto depois do valor: 'superior a 14 notebook core i5' -> 'superior a 14' (o resto não é do atributo)."""
    m = RX_VALOR.match(v.strip())
    return m.group(0).strip() if m else v.strip()


def faixa_do_valor(v, a):
    """Texto de valor do catálogo ('superior a 8', '480 a 1.000 gb', 'até 14', '12') -> (mínimo, máximo) na unidade base.
    None quando não há número (ex.: 'sem disco hdd', 'definido pelo fabricante')."""
    nums = re.findall(r"\d+(?:[.,]\d+)?", v)
    if not nums:
        return None
    fator = next((f for u, f in a["unidades"].items() if re.search(rf"\d\s*{re.escape(norm(u))}(?![a-z])", v)), 1.0)
    x = [numero(n) * fator for n in nums]
    if re.match(r"(superior a|acima de|mais de|maior que)\b", v):
        return (x[0] + 1e-9, INFINITO)
    if re.match(r"(minimo|no minimo|a partir de|pelo menos)\b", v):
        return (x[0], INFINITO)
    if re.match(r"(ate|maximo|inferior a|menor que)\b", v):
        return (0, x[0])
    if len(x) >= 2 and re.search(r"\d\s*(gb|tb|mp)?\s*a\s*\d", v):
        return (x[0], x[1])
    return (x[0], x[0])


# ----------------------------------------------------------------- armazenamento (tipo e classes comerciais)
CLASSES_ARMAZENAMENTO = [(120, 128, 128), (240, 256, 256), (480, 512, 512), (960, 1024, 1024)]  # (de, até, classe) em GB


def classe_armazenamento(gb):
    """Classe comercial: 120/128 -> 128; 240/250/256 -> 256; 480/500/512 -> 512; 960/1000/1024 (1 TB) -> 1024."""
    for de, ate, classe in CLASSES_ARMAZENAMENTO:
        if de <= gb <= ate:
            return classe
    return gb


def eh_armazenamento(a):
    return norm(a["nome"]) == "armazenamento"


def tipos_de_disco(descricao):
    """Que tipo de disco a descrição tem: {'ssd': bool, 'hdd': bool}. 'Sem disco SSD' / 'SSD: sem ...' conta como não ter."""
    t = norm(descricao)
    sem_ssd = re.search(r"ssd\s*:\s*(sem|nao)|sem\s+(disco\s+)?ssd", t)
    sem_hdd = re.search(r"hdd?\s*:\s*(sem|nao)|sem\s+(disco\s+)?hdd?\b", t)
    ssd = bool(re.search(r"\bssd\b|\bnvme\b|estado solido", t)) and not sem_ssd
    hdd = bool(re.search(r"\bhdd\b|disco rigido|\bhd\s*(:|de\s*\d|\d)", t)) and not sem_hdd
    return {"ssd": ssd, "hdd": hdd}


def avaliar_armazenamento(descricao, a, pedido, atributos=None):
    """Armazenamento: o pedido é de SSD. Só HDD -> 'não atende (só HDD)'. Valores e faixas comparados por classe comercial:
    valor exato na faixa aceita = atende; faixa do catálogo que contém a classe pedida (ou cruza a faixa aceita) = parcial."""
    t = norm(descricao)
    tipos = tipos_de_disco(descricao)
    if tipos["hdd"] and not tipos["ssd"]:
        m = re.search(r"hdd?[a-z ]{0,15}:\s*([^,;]{1,40})", t)
        return "não atende (só HDD)", (so_valor(m.group(1)) if m else "HDD")
    classe_pedida = classe_armazenamento(pedido)
    lo, hi = faixa(a["regra"], classe_pedida)
    m = re.search(r"ssd[a-z ]{0,15}:\s*([^,;]{1,40})", t)  # catálogo: 'armazenamento ssd: 480 a 1.000 gb'
    fx = faixa_do_valor(so_valor(m.group(1)), a) if m else None
    if fx:
        vmin, vmax, texto = fx[0], fx[1], so_valor(m.group(1))
    else:
        cat = faixas_do_catalogo(descricao, [a])[a["nome"]]
        livres = valores_no_texto(descricao, atributos or [a])[a["nome"]]  # todos: o número vai ao atributo mais perto
        if cat:
            vmin, vmax, texto = cat[0]
        elif livres:
            vmin = vmax = livres[0]
            texto = f"{livres[0]:g}"
        else:
            return "não informado", ""
    if vmin == vmax:  # valor exato: compara a classe comercial
        c = classe_armazenamento(vmin)
        return ("atende" if lo <= c <= hi else "não atende"), texto
    cmin = classe_armazenamento(vmin) if vmin < INFINITO else vmin
    cmax = classe_armazenamento(vmax) if vmax < INFINITO else vmax
    if cmin <= classe_pedida <= cmax or (cmin <= hi and cmax >= lo):
        return "parcial", texto
    return "não atende", texto


def avaliar(descricao, atributos, pedidos):
    """pedidos = {atributo: valor pedido}. Devolve ({atributo: (situação, valor achado)}, n atendidos).
    Atende quando o valor (ou a faixa do catálogo) cai dentro da faixa aceita."""
    catalogo = faixas_do_catalogo(descricao, atributos)
    achados = valores_no_texto(descricao, atributos)
    saida, n = {}, 0
    for a in atributos:
        if a["nome"] not in pedidos:
            continue
        if eh_armazenamento(a):  # tipo (SSD x só HDD) e classes comerciais
            situacao, texto = avaliar_armazenamento(descricao, a, pedidos[a["nome"]], atributos)
            saida[a["nome"]] = (situacao, texto)
            n += situacao == "atende"
            continue
        lo, hi = faixa(a["regra"], pedidos[a["nome"]])
        if catalogo[a["nome"]]:
            vmin, vmax, texto = catalogo[a["nome"]][0]  # formato do catálogo tem prioridade
        elif achados[a["nome"]]:
            v = achados[a["nome"]][0]  # o primeiro valor citado (evita 'expansível até 32 GB' contar como 32)
            vmin, vmax, texto = v, v, f"{v:g}"
        else:
            saida[a["nome"]] = ("não informado", "")
            continue
        cruza = vmin <= hi and vmax >= lo  # as faixas se cruzam
        if not cruza:
            situacao = "não atende"
        elif vmin >= lo and vmax <= hi:
            situacao = "atende"       # toda a faixa do catálogo cabe na faixa aceita
        else:
            situacao = "parcial"      # cruza, mas admite valores fora da faixa aceita (margem abaixo e/ou acima)
        saida[a["nome"]] = (situacao, texto)
        n += situacao == "atende"
    return saida, n


def autoteste():
    """Preflight offline (sem rede): confere faixas e leitura de atributos em frases fixas de teste."""
    p = {"notebook": ler_produtos()["notebook"]}["notebook"]
    erros = []
    if faixa("x a 2*x", 16) != (16, 32) or faixa("x-2 a x+2", 15) != (13, 17) or faixa("x-12 a x+24", 36) != (24, 60):
        erros.append("faixa")
    r, n = avaliar("Notebook memória RAM 16GB, SSD 512 GB, tela 15,6 polegadas, garantia 36 meses", p,
                   {"RAM": 16, "armazenamento": 512, "tela": 15, "garantia": 36})
    if n != 4:
        erros.append(f"avaliar frase 1: {r}")
    r, n = avaliar("Notebook 8 GB de RAM, armazenamento 1 TB SSD", p, {"RAM": 16, "armazenamento": 512, "tela": 15})
    if r["RAM"][0] != "não atende" or r["armazenamento"][0] != "atende" or r["tela"][0] != "não informado":
        erros.append(f"avaliar frase 2: {r}")
    r, n = avaliar("Notebook armazenamento hdd: sem disco hdd, armazenamento ssd: 480 a 1.000 gb, memória ram: superior a 8, tela: até 12", p,
                   {"RAM": 16, "armazenamento": 512, "tela": 15})
    if [r[k][0] for k in ("RAM", "armazenamento", "tela")] != ["parcial", "parcial", "não atende"]:
        erros.append(f"avaliar frase 3 (catálogo): {r}")
    for txt, esperado in (("tela: até 14", "parcial"), ("tela: superior a 14", "parcial"), ("tela: até 12", "não atende"),
                          ("tela: 15", "atende"), ("tela: 14 a 16", "atende")):
        r, n = avaliar("Notebook " + txt, p, {"tela": 15})
        if r["tela"][0] != esperado:
            erros.append(f"avaliar parcial bidirecional ({txt}): {r}")
    if eh_do_produto("Mochila material: nylon, aplicação: notebook", ["notebook"], item=True) or \
            not eh_do_produto("Computador tipo: notebook, tela 14", ["notebook"], item=True):
        erros.append("eh_do_produto (acessório)")
    # ajuste 1: tipo de disco, classes comerciais e entrada '960G' / '1TB' / '1 T'
    r, _ = avaliar("Notebook, armazenamento hdd: 1 tb., armazenamento ssd: sem disco ssd", p, {"armazenamento": 512})
    if r["armazenamento"][0] != "não atende (só HDD)":
        erros.append(f"armazenamento só HDD: {r}")
    r, _ = avaliar("Notebook SSD 480GB, memória 16GB", p, {"armazenamento": 512, "RAM": 16})
    if r["armazenamento"][0] != "atende" or r["RAM"][0] != "atende":
        erros.append(f"classe comercial 480 -> 512: {r}")
    r, _ = avaliar("Notebook, armazenamento ssd: 480 a 1.000 gb", p, {"armazenamento": 512})
    if r["armazenamento"][0] != "parcial":
        erros.append(f"faixa do catálogo com a classe pedida: {r}")
    if (ler_valor("960G"), ler_valor("1TB"), ler_valor("1 T")) != (960, 1024, 1024):
        erros.append("ler_valor")
    return erros


# ----------------------------------------------------------------- catálogo de materiais (PDM): palavra -> códigos (sem IA)
CATALOGO_PDM = CONFIG / "catalogo_pdm.csv"   # lista oficial de PDMs (Compras.gov.br, modulo-material/3_consultarPdmMaterial)
SINONIMOS_CSV = CONFIG / "sinonimos.csv"     # termo;equivale (editável)
CAMPOS_PDM = ["codigoPdm", "nomePdm", "statusPdm", "codigoClasse", "nomeClasse", "codigoGrupo", "nomeGrupo", "baixado_em"]


def baixar_catalogo_pdm(forcar=False):
    """Baixa uma vez a lista de PDMs de materiais (500 por página) e salva em config\\catalogo_pdm.csv, com a data.
    Se o arquivo já existir, usa o local (forcar=True baixa de novo)."""
    if CATALOGO_PDM.exists() and not forcar:
        return ler_catalogo_pdm()
    url = f"{COMPRAS}/modulo-material/3_consultarPdmMaterial"
    quando = agora()
    linhas, pagina, total_pag = [], 1, None
    while total_pag is None or pagina <= total_pag:
        st, js, _ = get(url, {"pagina": pagina, "tamanhoPagina": 500})
        if st != 200 or not isinstance(js, dict):
            raise PortalFora(f"catálogo de PDM: HTTP {st} na página {pagina}")
        total_pag = js.get("totalPaginas") or 1
        for r in js.get("resultado", []):
            linhas.append({"codigoPdm": r.get("codigoPdm"), "nomePdm": (r.get("nomePdm") or "").strip('" '),
                           "statusPdm": r.get("statusPdm"), "codigoClasse": r.get("codigoClasse"), "nomeClasse": r.get("nomeClasse"),
                           "codigoGrupo": r.get("codigoGrupo"), "nomeGrupo": r.get("nomeGrupo"), "baixado_em": quando})
        print(f"  catálogo de PDM: página {pagina} de {total_pag} ({len(linhas)} PDMs)")
        pagina += 1
    tmp = CATALOGO_PDM.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS_PDM, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    tmp.replace(CATALOGO_PDM)
    return ler_catalogo_pdm()


def ler_catalogo_pdm():
    with CATALOGO_PDM.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def singular(p):
    """Singular simples do português (para comparar 'notebooks' com 'notebook', 'monitores' com 'monitor')."""
    if len(p) <= 3 or p.isdigit():
        return p
    for fim, troca in (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("teis", "til"), ("ceis", "cil"), ("eis", "el"), ("ois", "ol"), ("ns", "m")):
        if p.endswith(fim):
            return p[: -len(fim)] + troca
    if re.search(r"(r|z|s)es$", p):
        return p[:-2]
    return p[:-1] if p.endswith("s") else p


def tokens(texto):
    """Sem acento, minúsculas, hífen e barra juntam as partes ('no-break' -> 'nobreak'), cada palavra no singular."""
    t = re.sub(r"(?<=[a-z0-9])[-/](?=[a-z0-9])", "", norm(texto))
    return [singular(w) for w in re.findall(r"[a-z0-9]+", t)]


def ler_sinonimos():
    """{termo normalizado: [equivalentes normalizados]} de config/sinonimos.csv (um termo pode ter várias linhas)."""
    if not SINONIMOS_CSV.exists():
        return {}
    sin = {}
    with SINONIMOS_CSV.open(encoding="utf-8-sig", newline="") as fh:
        for l in csv.DictReader(fh, delimiter=";"):
            if l.get("termo") and l.get("equivale"):
                sin.setdefault(" ".join(tokens(l["termo"])), []).append(" ".join(tokens(l["equivale"])))
    return sin


def procurar_pdm(consulta, catalogo=None, limite=15):
    """Palavra -> PDMs do catálogo. A consulta e cada sinônimo dela são alternativas: o PDM entra se todas as
    palavras (não numéricas) de alguma alternativa estiverem no nome dele.
    Devolve (PDMs ordenados, alternativas usadas, números ignorados)."""
    catalogo = catalogo if catalogo is not None else baixar_catalogo_pdm()
    sin = ler_sinonimos()
    tk = tokens(consulta)
    numeros = [w for w in tk if w.isdigit()]
    frase = " ".join(w for w in tk if not w.isdigit())
    if not frase:
        return [], "", numeros
    alternativas = [frase] + sin.get(frase, [])
    for alt in list(alternativas):  # um nível a mais: 'laptop' -> 'notebook'; 'ups' -> 'nobreak' -> 'fonte alimentacao ininterrupta'
        alternativas += [x for x in sin.get(alt, []) if x not in alternativas]
    alternativas = [a.split() for a in alternativas]
    achados = []
    for r in catalogo:
        nome_tk = tokens(r["nomePdm"])
        casadas = [a for a in alternativas if all(w in nome_tk for w in a)]
        if casadas:
            exato = any(nome_tk == a for a in casadas)
            comeca = any(nome_tk[: len(a)] == a for a in casadas)  # nome começa pelo termo ('MONITOR COMPUTADOR')
            ativo = str(r["statusPdm"]).lower() == "true"
            achados.append(((not exato, not comeca, not ativo, len(nome_tk), r["nomePdm"]), r))
    achados.sort(key=lambda x: x[0])
    return [r for _, r in achados[:limite]], " | ".join(" ".join(a) for a in alternativas), numeros


def sugerir_termos(consulta, catalogo=None, n=5):
    """Nada encontrado: palavras do catálogo parecidas com a consulta (difflib, sem IA)."""
    import difflib
    catalogo = catalogo if catalogo is not None else baixar_catalogo_pdm()
    vocab = sorted({w for r in catalogo for w in tokens(r["nomePdm"]) if len(w) >= 3 and not w.isdigit()})
    sug = []
    for w in tokens(consulta):
        sug += difflib.get_close_matches(w, vocab, n=n, cutoff=0.7)
    return list(dict.fromkeys(sug))[:n]


def contar_itens_pdm(codigo_pdm):
    """Quantos itens CATMAT o PDM tem (totalRegistros de modulo-material/4_consultarItemMaterial)."""
    st, js, _ = get(f"{COMPRAS}/modulo-material/4_consultarItemMaterial", {"pagina": 1, "tamanhoPagina": 10, "codigoPdm": codigo_pdm})
    return js.get("totalRegistros") if st == 200 and isinstance(js, dict) else None


# ----------------------------------------------------------------- opção 1
def opcao_1_buscar():
    """Busca compras (últimos 12 meses) pelo nome do produto ou pelo código do catálogo e marca os atributos."""
    erros = autoteste()
    if erros:
        print("Preflight offline FALHOU; nenhuma chamada de rede foi feita:", erros)
        return
    entrada = pergunta("Entrada: 1 = nome do produto, 2 = código do catálogo (CATMAT ou PDM) [Enter = 1]: ", "1")
    if entrada == "2":
        buscar_por_codigo()
    else:
        buscar_por_nome()


def perguntar_atributos(atributos):
    """Pergunta os atributos do produto (Enter deixa em branco) e mostra a faixa aceita de cada um."""
    pedidos = {}
    print("Preencha os atributos que quiser (Enter deixa em branco):")
    for a in atributos:
        v = pergunta(f"  {a['nome']} ({a['unidade']}; faixa {a['regra']}): ")
        if v:
            try:
                pedidos[a["nome"]] = ler_valor(v)
            except ValueError:
                print("   valor ignorado (não é número)")
    for nome, v in pedidos.items():
        a = next(x for x in atributos if x["nome"] == nome)
        lo, hi = faixa(a["regra"], v)
        print(f"  {nome}: aceita de {lo:g} a {hi:g} {a['unidade']}")
    return pedidos


def buscar_por_nome():
    """Entrada 1: nome do produto (fonte API de Consultas ou busca do portal) + itens e resultados do PNCP."""
    produtos = ler_produtos()
    print("Produtos cadastrados:", ", ".join(produtos))
    produto = pergunta("Produto: ")
    chave = next((p for p in produtos if norm(p) == norm(produto)), None)
    if not chave:
        print("Produto não está em config\\produtos.csv. Inclua uma linha lá (veja o LEIA_ME.txt).")
        return
    atributos = produtos[chave]
    pedidos = perguntar_atributos(atributos)
    fonte = pergunta(f"Fonte: 1 = API de Consultas (oficial), 2 = busca do portal (/api/search) [Enter = {FONTE_PADRAO}]: ", FONTE_PADRAO)
    uf = pergunta("UF (Enter = DF; BR = todas, demora mais): ", "DF").upper() if fonte == "1" else ""

    inicio = time.time()
    STATS.clear()
    hoje = dt.date.today()
    corte = hoje - dt.timedelta(days=365 * MESES // 12)
    palavras = [norm(w) for w in re.findall(r"\w+", chave)]
    cont = {"entrada": "nome do produto", "fonte": "API de Consultas" if fonte == "1" else "busca do portal", "uf": uf or "todas",
            "compras_vistas_na_listagem": 0, "compras_candidatas": 0, "compras_analisadas": 0, "itens_do_produto": 0,
            "itens_homologados": 0, "itens_com_preco": 0, "itens_fora_dos_12_meses": 0}
    linhas = []
    try:
        if fonte == "2":
            compras = compras_pelo_portal(chave, corte, cont)
        else:
            compras = compras_pela_consulta(palavras, uf, corte, hoje, cont)
        cont["compras_candidatas"] = len(compras)
        print(f"  {len(compras)} compras candidatas; analisando até {MAX_COMPRAS}.")
        analisar_compras(compras[:MAX_COMPRAS], palavras, atributos, pedidos, corte, cont, linhas)
    except PortalFora as e:
        print(f"\n*** PORTAL FORA OU BLOQUEADO: {e}\n*** A busca parou aqui; o que já foi lido será salvo.")
    salvar_busca(linhas, pedidos, chave, chave, cont, inicio)


def mediana_precos(linhas):
    ps = sorted(l["preco_unitario_homologado"] for l in linhas if l.get("preco_unitario_homologado"))
    return ps[len(ps) // 2] if ps else None


FATOR_MIN_CURVA, FATOR_MAX_CURVA = 0.25, 4.0  # preço aceito: de 25% a 400% da mediana da categoria


def fora_da_curva(preco, mediana):
    return bool(mediana) and preco is not None and not (mediana * FATOR_MIN_CURVA <= preco <= mediana * FATOR_MAX_CURVA)


def marcar_preco_suspeito(linhas, cont):
    """Marca (sem excluir) as linhas com preço fora da curva da categoria: observacao_preco = 'preço suspeito'.
    Regra: suspeito se preço < 0,25 x mediana ou > 4 x mediana (mediana de todas as linhas da busca)."""
    mediana = mediana_precos(linhas)
    n = 0
    for l in linhas:
        if fora_da_curva(l["preco_unitario_homologado"], mediana):
            l["observacao_preco"] = "preço suspeito"
            n += 1
    cont["precos_suspeitos_marcados"] = n
    if mediana:
        print(f"  mediana de preço da categoria: R$ {mediana:,.2f}; {n} linhas marcadas como 'preço suspeito' "
              f"(fora de {FATOR_MIN_CURVA:g}x a {FATOR_MAX_CURVA:g}x da mediana); nenhuma foi excluída.")


def _itens_da_compra(v, cache):
    chave = (v["cnpj"], v["ano"], v["seq"])
    if chave not in cache:
        base = f"{API}/orgaos/{v['cnpj']}/compras/{v['ano']}/{v['seq']}"
        todos = []
        for pg in range(1, 6):
            st, js, _ = get(f"{base}/itens", {"pagina": pg, "tamanhoPagina": 50})
            lote = js if st == 200 and isinstance(js, list) else []
            todos += lote
            if len(lote) < 50:
                break
        cache[chave] = (base, todos)
    return cache[chave]


def _sobreposicao(a, b):
    ta = {w for w in re.findall(r"[a-z0-9]{3,}", norm(a))}
    tb = {w for w in re.findall(r"[a-z0-9]{3,}", norm(b))}
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def validar_item_pncp(linha, v, palavras, mediana, cache, consultas_res):
    """No vínculo PNCP: acha o item da compra cuja descrição corresponde ao item buscado (é do produto, não é acessório),
    pega o valor homologado dele e descarta se estiver fora da curva da categoria."""
    base, itens = _itens_da_compra(v, cache)
    candidatos = [i for i in itens if eh_do_produto(i.get("descricao") or "", palavras, item=True)]
    if not candidatos:
        linha["status_item_pncp"] = "descartado: nenhum item do produto na compra do PNCP"
        return
    num = str(linha.get("numero_item") or "")
    desc = linha["descricao_item"]
    melhor = max(candidatos, key=lambda i: (_sobreposicao(desc, i.get("descricao") or "") + (0.5 if str(i.get("numeroItem")) == num else 0)))
    if _sobreposicao(desc, melhor.get("descricao") or "") < 0.1 and str(melhor.get("numeroItem")) != num:
        linha["status_item_pncp"] = "descartado: descrição do item do PNCP não corresponde"
        return
    if consultas_res[0] >= MAX_RESULTADOS:
        linha["status_item_pncp"] = "não verificado (limite de consultas de resultado)"
        return
    consultas_res[0] += 1
    st, res, _ = get(f"{base}/itens/{melhor['numeroItem']}/resultados")
    preco, _d = preco_homologado(res if st == 200 and isinstance(res, list) else [])
    descr = " ".join((melhor.get("descricao") or "").split())
    if preco is None:
        linha["status_item_pncp"] = "descartado: item do PNCP sem valor homologado"
    elif fora_da_curva(preco, mediana):
        linha["status_item_pncp"] = f"descartado: valor R$ {preco:,.2f} fora da curva da categoria"
    else:
        linha["status_item_pncp"] = "validado"
        linha["descricao_item_pncp"] = descr
        linha["valor_homologado_pncp"] = preco


def relatorio_validacao(linhas, pedidos):
    """Relatório final impresso no terminal."""
    print("\n" + "=" * 100 + "\nRELATÓRIO DE VALIDAÇÃO\n" + "=" * 100)
    nv = sum(1 for l in linhas if l.get("situacao_pncp") == "não verificado")
    sp = sum(1 for l in linhas if l.get("situacao_pncp") == "sem PNCP")
    vi = sum(1 for l in linhas if l.get("situacao_pncp") == "vinculado")
    print(f"Linhas: {len(linhas)} | não verificado: {nv} | sem PNCP: {sp} | vinculado: {vi}")
    # parcial: um exemplo de cada tipo de margem, alternando
    grupos = {"até/máximo": [], "superior/mínimo": [], "faixa/outros": []}
    for l in linhas:
        for nome in pedidos:
            s = l.get(nome, "")
            if s.startswith("parcial"):
                t = norm(s)
                g = "até/máximo" if re.search(r"\((ate|maximo|inferior|menor)", t) else "superior/mínimo" if re.search(r"\((superior|acima|mais de|maior|minimo|no minimo|a partir|pelo menos)", t) else "faixa/outros"
                grupos[g].append((l, nome, s))
    print("\n5 linhas com atributo 'parcial' (por tipo de margem):")
    escolhidas, usados = [], set()
    while len(escolhidas) < 5 and any(grupos.values()):
        for g in grupos:
            while grupos[g]:
                l, nome, s = grupos[g].pop(0)
                if (nome, s) not in usados:
                    usados.add((nome, s))
                    escolhidas.append((g, l, nome, s))
                    break
            if len(escolhidas) >= 5:
                break
    for g, l, nome, s in escolhidas:
        print(f"  linha {l['linha']} [{g}] pedido {pedidos[nome]:g} -> {nome}: {s}")
        print(f"      {l['descricao_item'][:160]}")
    if not escolhidas:
        print("  (nenhuma linha parcial encontrada)")
    print("\n5 linhas vinculadas ao PNCP com item validado:")
    ok = [l for l in linhas if l.get("status_item_pncp") == "validado"][:5]
    for l in ok:
        print(f"  ID {l['controle_pncp']} item {l['numero_item']} | valor homologado PNCP R$ {l['valor_homologado_pncp']:,.2f}")
        print(f"      descrição no PNCP: {l['descricao_item_pncp'][:200]}")
    if not ok:
        print("  (nenhuma linha validada)")
    descartes = {}
    for l in linhas:
        s = l.get("status_item_pncp", "")
        if s and s != "validado":
            descartes[s.split(" R$")[0]] = descartes.get(s.split(" R$")[0], 0) + 1
    print("\nStatus do item PNCP (não validados):", descartes or "nenhum")


def buscar_por_codigo():
    """Entrada 2: código do catálogo (item CATMAT ou PDM) na pesquisa de preço do Compras.gov.br.
    Cada registro já traz o preço unitário do resultado e a data do resultado; o idCompra é convertido
    no nº de controle do PNCP (link público e opções 3 a 5)."""
    codigo = pergunta("Código do catálogo (só números): ")
    if not codigo.isdigit():
        print("Código inválido.")
        return
    tipo = "codigoPdm" if pergunta("Esse código é de 1 = item CATMAT ou 2 = PDM (grupo de itens)? [Enter = 1]: ", "1") == "2" else "codigoItemCatalogo"
    produtos = ler_produtos()
    perfil = pergunta(f"Usar as regras de atributos de qual produto? ({', '.join(produtos)}; Enter = nenhum): ")
    chave = next((p for p in produtos if norm(p) == norm(perfil)), None)
    atributos = produtos[chave] if chave else []
    pedidos = perguntar_atributos(atributos) if atributos else {}
    uf = pergunta("UF (Enter = todas): ").upper()

    inicio = time.time()
    STATS.clear()
    hoje = dt.date.today()
    corte = hoje - dt.timedelta(days=365 * MESES // 12)
    cont = {"entrada": f"código do catálogo ({tipo}={codigo})", "fonte": "Compras.gov.br pesquisa de preço", "uf": uf or "todas",
            "registros_informados_pela_api": None, "registros_lidos": 0, "registros_com_preco": 0, "registros_fora_dos_12_meses": 0,
            "precos_suspeitos_marcados": 0, "compras_distintas": 0, "compras_ligadas_ao_pncp": 0, "compras_sem_ligacao_pncp": 0, "nome_no_catalogo": ""}
    linhas, vinculos = [], {}
    try:
        registros = []
        for pag in range(1, MAX_PAGINAS_CATALOGO + 1):
            params = {"pagina": pag, "tamanhoPagina": 100, "tipo": tipo, "codigo": codigo,
                      "dataCompraInicio": corte.isoformat(), "dataCompraFim": hoje.isoformat()}
            if uf:
                params["estado"] = uf
            st, js, _ = get(f"{COMPRAS}/modulo-pesquisa-preco/1_consultarMaterial", params)
            lote = (js or {}).get("resultado", []) if st == 200 and isinstance(js, dict) else []
            if pag == 1:
                cont["registros_informados_pela_api"] = (js or {}).get("totalRegistros") if isinstance(js, dict) else None
            print(f"  pesquisa de preço, página {pag}: HTTP {st}, {len(lote)} registros (total informado: {cont['registros_informados_pela_api']})")
            registros += lote
            if not lote or not (js or {}).get("paginasRestantes"):
                break
        cont["registros_lidos"] = len(registros)
        if registros:
            cont["nome_no_catalogo"] = registros[0].get("nomePdm", "")

        for r in registros:
            if r.get("precoUnitario") is None:
                continue
            cont["registros_com_preco"] += 1
            data_res = (r.get("dataResultado") or "")[:10]
            data_filtro, qual = (data_res, "data do resultado") if data_res else ((r.get("dataCompra") or "")[:10], "data da compra (sem data do resultado)")
            if data_filtro and data_filtro < corte.isoformat():
                cont["registros_fora_dos_12_meses"] += 1
                continue
            id_compra = str(r.get("idCompra") or "")
            desc = max([r.get("descricaoDetalhadaItem") or "", r.get("descricaoItem") or ""], key=len)
            aval, n = avaliar(desc, atributos, pedidos) if atributos else ({}, 0)
            linha = {"orgao": r.get("nomeOrgao") or r.get("nomeUasg", ""), "uf": r.get("estado", ""),
                     "data_publicacao": (r.get("dataCompra") or "")[:10], "data_resultado": data_res, "data_usada_no_filtro": qual,
                     "controle_pncp": "", "numero_item": r.get("numeroItemCompra"),
                     "descricao_item": " ".join(desc.split()), "preco_unitario_homologado": r.get("precoUnitario"),
                     "atributos_atendidos": f"{n} de {len(pedidos)}", "_n": n,
                     "link_publico": "",
                     "fonte_api_resultado": f"{COMPRAS}/modulo-pesquisa-preco/1_consultarMaterial?tipo={tipo}&codigo={codigo}",
                     "cnpj": "", "ano": "", "sequencial": "",
                     "observacao_preco": "", "situacao_pncp": "", "status_item_pncp": "", "descricao_item_pncp": "", "valor_homologado_pncp": "",
                     "codigo_catalogo": r.get("codigoItemCatalogo", ""), "marca": r.get("marca") or "", "id_compra": id_compra}
            for nome, (sit, val) in aval.items():
                linha[nome] = sit + (f" ({val})" if val else "")
            linhas.append(linha)
        marcar_preco_suspeito(linhas, cont)
        # liga ao PNCP primeiro as melhores linhas: sem "não atende" e com mais atributos atende/parcial;
        # as que passarem do limite de consultas ficam "não verificado"
        linhas.sort(key=lambda l: prioridade_ligacao(l, pedidos))
        palavras = [norm(w) for w in re.findall(r"\w+", chave)] if chave else norm(cont["nome_no_catalogo"]).split()[:1]
        mediana = mediana_precos(linhas)
        itens_pncp, consultas_res = {}, [0]
        for l in linhas:
            if l["id_compra"] not in vinculos:
                if len(vinculos) >= MAX_VINCULOS:
                    l["situacao_pncp"] = "não verificado"  # limite de consultas esgotado: não foi à API 14.133
                    continue
                vinculos[l["id_compra"]] = ligar_ao_pncp(l["id_compra"])
            v = vinculos[l["id_compra"]]
            preencher_vinculo(l, v)
            if v and v.get("cnpj"):
                l["situacao_pncp"] = "vinculado"
                validar_item_pncp(l, v, palavras, mediana, itens_pncp, consultas_res)
            else:
                l["situacao_pncp"] = "sem PNCP"  # consultou a API 14.133 e a lista veio vazia
    except PortalFora as e:
        print(f"\n*** PORTAL FORA OU BLOQUEADO: {e}\n*** A busca parou aqui; o que já foi lido será salvo.")
    cont["compras_distintas"] = len({l["id_compra"] for l in linhas})
    cont["compras_ligadas_ao_pncp"] = sum(1 for v in vinculos.values() if v and v.get("cnpj"))
    cont["compras_sem_ligacao_pncp"] = len({l["id_compra"] for l in linhas if l.get("situacao_pncp") == "sem PNCP"})
    cont["compras_nao_verificadas"] = len({l["id_compra"] for l in linhas if l.get("situacao_pncp") == "não verificado"})
    cont["linhas_nao_verificado"] = sum(1 for l in linhas if l.get("situacao_pncp") == "não verificado")
    cont["linhas_sem_pncp"] = sum(1 for l in linhas if l.get("situacao_pncp") == "sem PNCP")
    salvar_busca(linhas, pedidos, f"catalogo_{codigo}", chave or "", cont, inicio, extras=["codigo_catalogo", "marca", "id_compra", "observacao_preco", "situacao_pncp", "status_item_pncp", "descricao_item_pncp", "valor_homologado_pncp"])
    relatorio_validacao(linhas, pedidos)


def prioridade_ligacao(l, pedidos):
    """Ordem de procura no PNCP: primeiro sem 'não atende', depois mais atributos atende/parcial, mais 'atende', menor preço."""
    s = [str(l.get(k, "")) for k in pedidos]
    tem_nao = any(x.startswith("não atende") for x in s)
    bons = sum(x.startswith(("atende", "parcial")) for x in s)
    return (tem_nao, -bons, -l.get("_n", 0), l.get("preco_unitario_homologado") or 0)


def juntar_buscas(resumos):
    """Vários códigos escolhidos: junta os CSVs de cada busca num só (renumera 'linha'), soma os contadores
    e grava saida/busca_pdms_<códigos>_<data>.csv e o ultima_busca.json. Devolve o resumo junto."""
    if len(resumos) == 1:
        return resumos[0]
    todas, campos = [], []
    for r in resumos:
        with Path(r["arquivo"]).open(encoding="utf-8-sig", newline="") as fh:
            leitor = csv.DictReader(fh, delimiter=";")
            campos += [c for c in leitor.fieldnames if c not in campos]
            todas += list(leitor)
    for k, l in enumerate(todas, 1):
        l["linha"] = k
    codigos = "_".join(m.group(1) for r in resumos for m in [re.search(r"=(\d+)", r.get("entrada", ""))] if m)
    nome_arq = SAIDA / f"busca_pdms_{codigos}_{dt.date.today():%Y-%m-%d}.csv"
    with nome_arq.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(todas)
    somas = {}
    for r in resumos:  # contadores numéricos (chamadas, falhas, tempo, registros...) somados
        for k, v in r.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                somas[k] = somas.get(k, 0) + v
    junto = {**somas, "arquivo": str(nome_arq), "produto": resumos[0].get("produto", ""), "pedidos": resumos[0].get("pedidos", {}),
             "entrada": " + ".join(r.get("entrada", "") for r in resumos), "fonte": resumos[0].get("fonte", ""),
             "linhas_salvas": len(todas), "buscas_juntadas": [r["arquivo"] for r in resumos]}
    (SAIDA / "ultima_busca.json").write_text(json.dumps(junto, ensure_ascii=False, indent=1), encoding="utf-8")
    return junto


def preencher_vinculo(linha, v):
    """Copia o nº de controle do PNCP para a linha e monta o link público."""
    if v and v.get("cnpj"):
        linha.update({"controle_pncp": v["controle"], "cnpj": v["cnpj"], "ano": v["ano"], "sequencial": v["seq"],
                      "link_publico": f"https://pncp.gov.br/app/editais/{v['cnpj']}/{v['ano']}/{v['seq']}"})


def ligar_ao_pncp(id_compra):
    """idCompra do Compras.gov.br -> nº de controle, CNPJ, ano e sequencial no PNCP (mesmo caminho da rodada 3)."""
    st, js, _ = get(f"{COMPRAS}/modulo-contratacoes/1.1_consultarContratacoes_PNCP_14133_Id", {"tipo": "idCompra", "codigo": id_compra})
    res = (js or {}).get("resultado", []) if st == 200 and isinstance(js, dict) else []
    if not res:
        return None
    r = res[0]
    return {"controle": r.get("numeroControlePNCP", ""), "cnpj": r.get("orgaoEntidadeCnpj", ""),
            "ano": str(r.get("anoCompraPncp", "")), "seq": str(r.get("sequencialCompraPncp", ""))}


def salvar_busca(linhas, pedidos, nome_base, produto, cont, inicio, extras=()):
    """Salva a busca ordenada por atributos atendidos (a coluna 'linha' é o número usado nas opções 2 e 3) e o resumo."""
    linhas.sort(key=lambda l: (-l["_n"], l["preco_unitario_homologado"]))
    for k, l in enumerate(linhas, 1):
        l["linha"] = k
        del l["_n"]
    nome_arq = SAIDA / f"busca_{re.sub(r'[^a-z0-9]+', '_', norm(nome_base))}_{dt.date.today():%Y-%m-%d}.csv"
    cols = ["linha", "orgao", "uf", "data_publicacao", "data_resultado", "data_usada_no_filtro", "controle_pncp", "numero_item",
            "descricao_item", "preco_unitario_homologado", "atributos_atendidos"] + list(pedidos) + list(extras) + \
           ["link_publico", "fonte_api_resultado", "cnpj", "ano", "sequencial"]
    with nome_arq.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    resumo = {"arquivo": str(nome_arq), "produto": produto, "pedidos": pedidos, **cont, "linhas_salvas": len(linhas),
              "descricoes_com_valor": {nome: sum(1 for l in linhas if "não informado" not in l.get(nome, "")) for nome in pedidos},
              "chamadas": STATS.get("chamadas", 0), "falhas": STATS.get("falhas", 0),
              "falhas_por_tipo": {k[6:]: v for k, v in STATS.items() if k.startswith("falha:")},
              "chamadas_por_grupo": {k[6:]: v for k, v in STATS.items() if k.startswith("grupo:")},
              "falhas_por_grupo": {k[11:]: v for k, v in STATS.items() if k.startswith("falhagrupo:")},
              "tempo_s": round(time.time() - inicio)}
    (SAIDA / "ultima_busca.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nResumo:", json.dumps(resumo, ensure_ascii=False, indent=1))


def compras_pelo_portal(chave, corte, cont):
    """Fonte 2: busca do portal (/api/search, editais com o produto), só compras publicadas há até 12 meses e com resultado."""
    compras, vistas = [], set()
    for pag in range(1, MAX_PAGINAS_BUSCA + 1):
        st, js, _ = get(BUSCA, {"q": chave, "tipos_documento": "edital", "ordenacao": "-data", "pagina": pag, "tam_pagina": 100})
        itens = (js or {}).get("items", []) if st == 200 and isinstance(js, dict) else []
        print(f"  busca do portal, página {pag}: HTTP {st}, {len(itens)} editais")
        if not itens:
            break
        cont["compras_vistas_na_listagem"] += len(itens)
        for it in itens:
            data = (it.get("data_publicacao_pncp") or "")[:10]
            if (data and data < corte.isoformat()) or not it.get("tem_resultado") or it.get("cancelado"):
                continue
            k = (it.get("orgao_cnpj"), str(it.get("ano")), str(it.get("numero_sequencial")))
            if None in k or k in vistas:
                continue
            vistas.add(k)
            compras.append({"cnpj": k[0], "ano": k[1], "seq": k[2], "orgao": it.get("orgao_nome", ""), "data": data,
                            "controle": it.get("numero_controle_pncp", ""), "uf": it.get("uf", "")})
        if len(itens) < 100 or all((x.get("data_publicacao_pncp") or "9")[:10] < corte.isoformat() for x in itens):
            break  # última página, ou página inteira mais antiga que 12 meses
    return compras


def compras_pela_consulta(palavras, uf, corte, hoje, cont):
    """Fonte 1: API de Consultas (/v1/contratacoes/publicacao), mês a mês, do mais recente para trás.
    Essa API não filtra por palavra: lista as compras (pregão eletrônico e dispensa) e fica com as que citam
    o produto ou informática/TI no objeto. As que citam o produto vêm primeiro."""
    diretas, gerais, vistas = [], [], set()
    fim = hoje
    while fim > corte and len(diretas) < MAX_COMPRAS:
        ini = max(corte, fim - dt.timedelta(days=30))
        for modalidade in MODALIDADES:
            for pag in range(1, MAX_PAGINAS_CONSULTA + 1):
                params = {"dataInicial": f"{ini:%Y%m%d}", "dataFinal": f"{fim:%Y%m%d}", "codigoModalidadeContratacao": modalidade,
                          "pagina": pag, "tamanhoPagina": 50}
                if uf and uf != "BR":
                    params["uf"] = uf
                st, js, _ = get(f"{CONSULTA}/contratacoes/publicacao", params)
                dados = (js or {}).get("data", []) if st == 200 and isinstance(js, dict) else []
                cont["compras_vistas_na_listagem"] += len(dados)
                for c in dados:
                    org, uni = c.get("orgaoEntidade") or {}, c.get("unidadeOrgao") or {}
                    k = (org.get("cnpj"), str(c.get("anoCompra")), str(c.get("sequencialCompra")))
                    if None in k or k in vistas:
                        continue
                    vistas.add(k)
                    objeto = c.get("objetoCompra") or ""
                    reg = {"cnpj": k[0], "ano": k[1], "seq": k[2], "orgao": org.get("razaoSocial", ""), "uf": uni.get("ufSigla", ""),
                           "data": (c.get("dataPublicacaoPncp") or "")[:10], "controle": c.get("numeroControlePNCP", "")}
                    if eh_do_produto(objeto, palavras):
                        diretas.append(reg)
                    elif re.search(TERMOS_TI, norm(objeto)):
                        gerais.append(reg)
                if len(dados) < 50:
                    break
        print(f"  consulta {ini:%d/%m/%Y} a {fim:%d/%m/%Y} (UF {uf or 'todas'}): até agora {len(diretas)} compras citam o produto, {len(gerais)} citam informática/TI")
        fim = ini - dt.timedelta(days=1)
    return diretas + gerais


def analisar_compras(compras, palavras, atributos, pedidos, corte, cont, linhas):
    """Lê os itens de cada compra; nos itens do produto homologados, busca o resultado e marca os atributos."""
    consultas_res = 0
    for i, c in enumerate(compras, 1):
        cont["compras_analisadas"] += 1
        base = f"{API}/orgaos/{c['cnpj']}/compras/{c['ano']}/{c['seq']}"
        todos = []
        for pg in range(1, 6):
            st, js, _ = get(f"{base}/itens", {"pagina": pg, "tamanhoPagina": 50})
            lote = js if st == 200 and isinstance(js, list) else []
            todos += lote
            if len(lote) < 50:
                break
        for item in todos:
            desc = item.get("descricao", "") or ""
            if not eh_do_produto(desc, palavras, item=True):
                continue
            cont["itens_do_produto"] += 1
            # 2 = "Homologado": par código/nome visto em 205 itens reais (ver LEIA_ME); aceita o código ou o nome
            if item.get("situacaoCompraItem") != 2 and norm(item.get("situacaoCompraItemNome")) != "homologado":
                continue
            cont["itens_homologados"] += 1
            if consultas_res >= MAX_RESULTADOS:
                continue
            consultas_res += 1
            url_res = f"{base}/itens/{item['numeroItem']}/resultados"
            st, res, _ = get(url_res)
            preco, data_res = preco_homologado(res if st == 200 and isinstance(res, list) else [])
            if preco is None:
                continue
            cont["itens_com_preco"] += 1
            data_filtro, qual = (data_res, "data do resultado") if data_res else (c["data"], "data de publicação (sem data do resultado)")
            if data_filtro and data_filtro < corte.isoformat():
                cont["itens_fora_dos_12_meses"] += 1
                continue
            aval, n = avaliar(desc, atributos, pedidos)
            linha = {"orgao": c["orgao"], "uf": c["uf"], "data_publicacao": c["data"], "data_resultado": data_res,
                     "data_usada_no_filtro": qual, "controle_pncp": c["controle"],
                     "numero_item": item.get("numeroItem"), "descricao_item": " ".join(desc.split()),
                     "preco_unitario_homologado": preco, "atributos_atendidos": f"{n} de {len(pedidos)}", "_n": n,
                     "link_publico": f"https://pncp.gov.br/app/editais/{c['cnpj']}/{c['ano']}/{c['seq']}",
                     "fonte_api_resultado": url_res, "cnpj": c["cnpj"], "ano": c["ano"], "sequencial": c["seq"]}
            for nome, (sit, val) in aval.items():
                linha[nome] = sit + (f" ({val})" if val else "")
            linhas.append(linha)
        print(f"  [{i}/{len(compras)}] {c['controle']}: {len(todos)} itens lidos; {len(linhas)} linhas até agora")


ACESSORIOS = r"mochila|bolsa|maleta|capa|case|bateria|carregador|fonte|adaptador|suporte|base|cabo|memoria|teclado|mouse|pelicula|cadeado|dock|hub|locacao"


def eh_do_produto(descricao, palavras, item=False):
    """O item é do produto se a descrição tiver todas as palavras do nome (ex.: 'camera' e 'ip').
    Para item (não para o objeto da compra): o nome tem de aparecer no começo da descrição (40 caracteres)
    e a descrição não pode começar por acessório (mochila, bateria, memória...)."""
    t = norm(descricao)
    if item:
        if re.match(rf"\W*({ACESSORIOS})\b", t):
            return False
        t = t[:40]
    compacto = re.sub(r"[^a-z0-9]", "", t)  # 'no-break' vira 'nobreak'
    return all((w in compacto) if len(w) >= 4 else re.search(rf"(?<![a-z0-9]){w}(?![a-z0-9])", t) for w in palavras)


def preco_homologado(resultados):
    """(valor unitário homologado, data do resultado): resultados com situação 1 ('Informado'); no SRP, o 1º classificado."""
    validos = [r for r in resultados if r.get("situacaoCompraItemResultadoId") == 1 and r.get("valorUnitarioHomologado") is not None]
    if not validos:
        return None, ""
    validos.sort(key=lambda r: (r.get("ordemClassificacaoSrp") or 999))
    return validos[0]["valorUnitarioHomologado"], (validos[0].get("dataResultado") or "")[:10]


# ----------------------------------------------------------------- opção 2
def ultima_busca():
    arqs = sorted(SAIDA.glob("busca_*.csv"), key=lambda p: p.stat().st_mtime)
    if not arqs:
        print("Nenhuma busca salva ainda. Use a opção 1.")
        return None, []
    with arqs[-1].open(encoding="utf-8-sig", newline="") as f:
        return arqs[-1], list(csv.DictReader(f, delimiter=";"))


def opcao_2_mostrar():
    """Mostra as 20 primeiras linhas da última busca (já ordenadas por atributos atendidos)."""
    arq, linhas = ultima_busca()
    if not arq:
        return
    print(f"\n{arq.name}: {len(linhas)} linhas\n")
    print(f"{'lin':>3} {'atende':>6} {'preço':>11} {'resultado':10} {'órgão':28} descrição")
    for l in linhas[:20]:
        preco = f"{float(l['preco_unitario_homologado']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f"{l['linha']:>3} {l['atributos_atendidos']:>6} {preco:>11} {(l.get('data_resultado') or l['data_publicacao']):10} {l['orgao'][:28]:28} {l['descricao_item'][:70]}")


# ----------------------------------------------------------------- opção 3
def opcao_3_baixar():
    """Baixa os documentos da compra escolhida pelo número da linha; ZIP é extraído numa subpasta."""
    arq, linhas = ultima_busca()
    if not arq:
        return
    n = escolher_numero(f"Número da linha (1 a {len(linhas)}): ", len(linhas))
    if not n:
        return
    l = linhas[n - 1]
    if not l.get("cnpj") and l.get("id_compra"):
        try:
            v = ligar_ao_pncp(l["id_compra"])  # busca por código: compra ainda não ligada ao PNCP
        except PortalFora as e:
            print(f"*** PORTAL FORA OU BLOQUEADO: {e}")
            return
        preencher_vinculo(l, v)
    if not l.get("cnpj"):
        print("Esta compra não foi encontrada no PNCP (pode ser anterior à Lei 14.133). Sem documentos para baixar.")
        return
    destino = SAIDA / "documentos" / re.sub(r"[^0-9A-Za-z]+", "_", l["controle_pncp"] or f"{l['cnpj']}_{l['ano']}_{l['sequencial']}")
    destino.mkdir(parents=True, exist_ok=True)
    base = f"{API}/orgaos/{l['cnpj']}/compras/{l['ano']}/{l['sequencial']}"
    try:
        st, lista, _ = get(f"{base}/arquivos")
        if st != 200 or not isinstance(lista, list):
            print(f"Lista de arquivos não veio (HTTP {st}).")
            return
        (destino / "_lista_arquivos_pncp.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
        ativos = [a for a in lista if a.get("statusAtivo") is not False]
        principais = [a for a in ativos if eh_principal(a)]
        outros = len(ativos) - len(principais)
        print(f"  {len(ativos)} arquivos ativos: {len(principais)} principais (edital, TR, ETP, DFD, aviso) e {outros} outros (propostas, atas, despachos...).")
        escolhidos = principais
        if outros and pergunta(f"  Baixar também os {outros} outros? (s/N): ").lower() == "s":
            escolhidos = ativos
        for a in escolhidos:
            url = a.get("url") or f"{base}/arquivos/{a.get('sequencialDocumento')}"
            st, corpo, hd = get(url, binario=True)
            if st != 200 or not corpo:
                print(f"  {a.get('titulo')}: HTTP {st}, não baixado")
                continue
            m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', hd.get("Content-Disposition", ""))
            nome = urllib.parse.unquote_plus(m.group(1)) if m else (a.get("titulo") or "arquivo")
            nome = re.sub(r'[\\/:*?"<>|]', "_", nome)[:120]
            tipo = "pdf" if corpo[:5] == b"%PDF-" else "zip" if corpo[:2] == b"PK" else "rar" if corpo[:4] == b"Rar!" else "outro"
            alvo = destino / f"{a.get('sequencialDocumento')}_{nome}"
            if not alvo.suffix and tipo != "outro":
                alvo = alvo.with_suffix("." + tipo)
            alvo.write_bytes(corpo)
            print(f"  baixado: {alvo.name} ({tipo}, {len(corpo):,} bytes)")
            if tipo == "zip":
                extrair_zip(alvo, destino / (alvo.stem + "_extraido"))
            elif tipo == "rar":
                print("    RAR: não extraído (precisa de programa externo); abra manualmente.")
        print(f"Documentos em: {destino}")
    except PortalFora as e:
        print(f"*** PORTAL FORA OU BLOQUEADO: {e}")


TIPOS_PRINCIPAIS = ("edital", "termo de referencia", "estudo tecnico", "etp", "documento de formalizacao", "dfd", "aviso")


def eh_principal(a):
    """Documento principal da compra: pelo tipo informado no PNCP ou, em 'Outros Documentos', pelo título."""
    tipo, titulo = norm(a.get("tipoDocumentoNome")), norm(a.get("titulo"))
    if any(t in tipo for t in TIPOS_PRINCIPAIS):
        return True
    return bool(re.search(r"(?<![a-z])(edital|termo de referencia|tr|etp|estudo tecnico|especificac)", titulo)) and not re.search(r"proposta|habilitac|diligencia|recurso|despacho|suspens", titulo)


def extrair_zip(zip_path, pasta):
    """Extrai o ZIP sem deixar arquivo sair da pasta (ignora caminhos absolutos e '..'); limite de 500 MB."""
    pasta.mkdir(exist_ok=True)
    total = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            total += info.file_size
            if total > 500 * 1024 * 1024:
                print("    ZIP grande demais; extração interrompida.")
                break
            nome = info.filename.replace("\\", "/")
            alvo = (pasta / nome).resolve()
            if not str(alvo).startswith(str(pasta.resolve())):
                continue
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, alvo.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"    extraído: {alvo.relative_to(pasta)}")


# ----------------------------------------------------------------- documentos recortáveis (PDF e Word)
EXTENSOES_RECORTE = (".pdf", ".docx", ".doc")
CARACTERES_POR_BLOCO = 3000  # Word não tem páginas fixas: sem quebra de página marcada, o texto é dividido em blocos


def documentos_recortaveis():
    """PDFs e documentos Word baixados (mesma lista na opção 4 e na tela)."""
    pasta = SAIDA / "documentos"
    return sorted(x for x in pasta.rglob("*") if x.suffix.lower() in EXTENSOES_RECORTE) if pasta.exists() else []


def docx_para_paginas(caminho):
    """Texto de um .docx sem instalar nada: o .docx é um ZIP com word/document.xml.
    Páginas = quebras de página marcadas no arquivo; sem elas, blocos de ~3.000 caracteres. Devolve (páginas, aviso)."""
    import xml.etree.ElementTree as ET
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(caminho) as z:
        raiz = ET.fromstring(z.read("word/document.xml"))
    paginas, atual = [], []
    for par in raiz.iter(W + "p"):
        texto = []
        for el in par.iter():
            if el.tag == W + "t" and el.text:
                texto.append(el.text)
            elif el.tag == W + "tab":
                texto.append("\t")
            elif (el.tag == W + "br" and el.get(W + "type") == "page") or el.tag == W + "lastRenderedPageBreak":
                atual.append("".join(texto))
                texto = []
                paginas.append("\n".join(atual))
                atual = []
        atual.append("".join(texto))
    paginas.append("\n".join(atual))
    paginas = [x for x in paginas if x.strip()]
    blocos = []  # cada página longa vira blocos de ~3.000 caracteres (quebrando em fim de parágrafo)
    for pag in paginas:
        bloco = ""
        for linha in pag.split("\n"):
            if len(bloco) + len(linha) > CARACTERES_POR_BLOCO and bloco:
                blocos.append(bloco)
                bloco = ""
            bloco += linha + "\n"
        if bloco.strip():
            blocos.append(bloco)
    return blocos, (f"Word não tem páginas fixas: {len(paginas)} quebra(s) de página no arquivo; texto dividido em "
                    f"{len(blocos)} blocos de até ~{CARACTERES_POR_BLOCO} caracteres (\"PÁGINA N\" = bloco N).")


USAR_WORD_PARA_DOC = True  # autorizado pelo usuário em 28/10/2026: usar o Word instalado para converter .doc antigo


def caminho_do_word():
    """WINWORD.EXE registrado no Windows (App Paths), ou None. Só consulta; não abre nada.
    No Linux (nuvem) não há Word: devolve None e a tela só avisa."""
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe") as k:
            valor = winreg.QueryValue(k, None)
        return valor if valor and Path(valor.strip('"')).exists() else None
    except (OSError, ImportError):
        return None


def converter_doc_com_word(caminho):
    """.doc antigo -> cópia .docx ao lado do original, pelo Word (automação COM via PowerShell, sem instalar nada).
    Abre só para leitura, com macros desativadas, invisível; o original não é alterado. Devolve (caminho .docx, motivo)."""
    destino = caminho.with_name(caminho.stem + "_convertido.docx")
    if destino.exists():
        return destino, ""
    if not USAR_WORD_PARA_DOC:
        return None, "a conversão pelo Word está desligada (USAR_WORD_PARA_DOC = False)."
    if not caminho_do_word():
        return None, ("o Word não está disponível aqui (na versão on-line não há Word; no Windows, só com o Word instalado), "
                      "então o .doc não pode ser convertido automaticamente.")
    script = ("$ErrorActionPreference='Stop'; $w = New-Object -ComObject Word.Application; "
              "try { $w.Visible = $false; $w.DisplayAlerts = 0; $w.AutomationSecurity = 3; "  # 3 = macros desativadas
              "$d = $w.Documents.Open($env:DOC_ORIGEM, $false, $true, $false); "            # sem conversão, só leitura
              "$d.SaveAs2($env:DOC_DESTINO, 16); $d.Close($false) } finally { $w.Quit() }")  # 16 = .docx
    import subprocess
    env = {**os.environ, "DOC_ORIGEM": str(caminho.resolve()), "DOC_DESTINO": str(destino.resolve())}
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env,
                           capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None, "o Word não respondeu em 3 minutos."
    if r.returncode != 0 or not destino.exists():
        return None, f"o Word não conseguiu converter ({(r.stderr or r.stdout).strip()[:200]})."
    return destino, ""


def extrair_paginas(caminho):
    """(lista de textos por página, aviso) para PDF (pdfplumber) ou .docx. Para .doc antigo devolve (None, motivo)."""
    ext = caminho.suffix.lower()
    if ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(caminho) as d:
            return [(pg.extract_text() or "") for pg in d.pages], ""
    if ext == ".docx":
        return docx_para_paginas(caminho)
    if ext == ".doc":
        convertido, motivo = converter_doc_com_word(caminho)
        if not convertido:
            return None, (f"Documento .doc (formato antigo do Word): {motivo} "
                          "Abra no Word e salve como .docx ou PDF na mesma pasta, e escolha o novo arquivo.")
        paginas, aviso = docx_para_paginas(convertido)
        return paginas, f"Convertido pelo Word para {convertido.name}. {aviso}"
    return None, f"Formato {ext} não suportado para recorte."


# ----------------------------------------------------------------- opção 4
def opcao_4_recortar():
    """Recorta as páginas do item num PDF, usando o recorte_teste_ia.py (marcas '=== PÁGINA N ===')."""
    pdfs = documentos_recortaveis()  # PDF e Word
    if not pdfs:
        print("Nenhum PDF ou documento Word baixado. Use a opção 3.")
        return
    for i, p in enumerate(pdfs, 1):
        print(f"{i:>3}. {p.relative_to(SAIDA)}")
    n = escolher_numero("PDF número: ", len(pdfs))
    if not n:
        return
    pdf = pdfs[n - 1]
    produtos = ler_produtos()
    _, ult = ultima_busca()
    sugestao = json.loads((SAIDA / "ultima_busca.json").read_text(encoding="utf-8"))["arquivo"] if (SAIDA / "ultima_busca.json").exists() else ""
    padrao = next((p for p in produtos if re.sub(r"[^a-z0-9]+", "_", norm(p)) in norm(sugestao)), "")
    item = pergunta(f"Item pedido [{padrao}]: ", padrao)
    if not item:
        return
    chave = next((p for p in produtos if norm(p) == norm(item)), None)
    palavras = [item] + ([ap for a in produtos[chave] for ap in a["apelidos"]] if chave else [])
    rx = "|".join(re.escape(norm(w)) for w in palavras if len(norm(w)) >= 2)

    trabalho = SAIDA / "recortes" / re.sub(r"[^0-9A-Za-z]+", "_", pdf.stem)[:60]
    trabalho.mkdir(parents=True, exist_ok=True)
    paginas, aviso = extrair_paginas(pdf)
    if paginas is None:
        print(f"Não foi possível recortar: {aviso}")
        return
    if aviso:
        print(f"Aviso: {aviso}")
    (trabalho / "paginas.json").write_text(json.dumps(paginas, ensure_ascii=False), encoding="utf-8")
    if sum(len(p.strip()) for p in paginas) < 50 * len(paginas):
        print("Aviso: pouco texto extraído (PDF escaneado?). O recorte pode sair vazio.")

    spec = importlib.util.spec_from_file_location("recorte_teste_ia", RECORTE_PY)
    rec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rec)          # só carrega o módulo; o arquivo original não é alterado
    rec.DOCS = [("REC", "paginas.json", item, rx)]  # um documento só: o PDF escolhido
    rec.main(trabalho, trabalho)
    saida_txt = trabalho / "recorte.txt"
    (trabalho / "REC_recorte.txt").replace(saida_txt)
    print(f"Recorte salvo em: {saida_txt}")


# ----------------------------------------------------------------- opção 5
def opcao_5_texto_ia():
    """Junta INSTRUCAO_FICHA.txt + o recorte num .txt pronto para colar na IA."""
    recs = sorted((SAIDA / "recortes").glob("*/recorte.txt")) if (SAIDA / "recortes").exists() else []
    if not recs:
        print("Nenhum recorte ainda. Use a opção 4.")
        return
    for i, p in enumerate(recs, 1):
        print(f"{i:>3}. {p.parent.name}")
    n = escolher_numero("Recorte número: ", len(recs))
    if not n:
        return
    r = recs[n - 1]
    pasta = SAIDA / "para_ia"
    pasta.mkdir(exist_ok=True)
    alvo = pasta / f"{r.parent.name}_PARA_IA.txt"
    texto = INSTRUCAO.read_text(encoding="utf-8").rstrip() + "\n\n" + r.read_text(encoding="utf-8")
    alvo.write_text(texto, encoding="utf-8")
    print(f"Pronto para colar: {alvo}  ({len(texto):,} caracteres, ~{len(texto) // 4:,} tokens)")


# ----------------------------------------------------------------- opção 6
def opcao_6_ollama():
    """Por enquanto só verifica se o Ollama está instalado."""
    caminho = shutil.which("ollama")
    padrao = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    if caminho or padrao.exists():
        print(f"Ollama encontrado: {caminho or padrao}")
    else:
        print("Ollama NÃO encontrado neste computador.")
    print(f"A leitura com IA local ainda não foi implementada. Quando for, usar num_ctx >= {OLLAMA_NUM_CTX} (senão o recorte é cortado).")


# ----------------------------------------------------------------- menu
def menu():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    SAIDA.mkdir(exist_ok=True)
    opcoes = {"1": opcao_1_buscar, "2": opcao_2_mostrar, "3": opcao_3_baixar, "4": opcao_4_recortar, "5": opcao_5_texto_ia, "6": opcao_6_ollama}
    while True:
        print("\n===== Referência TIC – ferramenta de teste =====")
        print("1. Buscar compras no PNCP")
        print("2. Mostrar a tabela da última busca")
        print("3. Baixar os documentos de uma compra")
        print("4. Recortar as páginas do item num PDF")
        print("5. Gerar .txt para colar na IA")
        print("6. Ler com IA local (Ollama) – só verifica a instalação")
        print("0. Sair")
        try:
            op = input("Opção: ").strip()
        except EOFError:
            break
        if op == "0":
            break
        if op in opcoes:
            try:
                opcoes[op]()
            except EOFError:
                break
            except Exception as e:  # erro de script nunca vira conclusão sobre os dados
                print(f"ERRO DE SCRIPT na opção {op}: {type(e).__name__}: {e}")
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    menu()

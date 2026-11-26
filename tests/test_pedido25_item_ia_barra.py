"""v4h, Pedido 28 (Fase 2), SEM rede, SEM Ollama (rede e extração falsas; socket bloqueado; preparação copiada do test_tela_fase4). O '|' do item pedido vira ' / ' SÓ no texto enviado à IA (PARA_IA):
(a) item com '|' -> ' / ' só no PARA_IA; (b) item sem '|' não muda; (c) item guardado e recorte.txt em disco continuam iguais; (d) item vazio não quebra; mais a função pura.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido25_item_ia_barra.py   (na pasta do app)"""
import contextlib, datetime as dt, re, socket, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True

# O asyncio do Windows (usado pelo AppTest) abre um par de sockets em 127.0.0.1 para si mesmo (socketpair). Isso não é rede: só
# esses connects de loopback são deixados passar e CONTADOS; qualquer outro destino, e a porta 11434 (Ollama), derruba o teste.
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
# Pedido 16 (M1): este teste guarda o comportamento de 16.384. Usa uma CÓPIA TEMPORÁRIA do config com contexto_tokens=16384; o config real (hoje 32.768) não é tocado.
import atexit as _at, os as _os, re as _re, shutil as _sh
_CFG16 = DADOS / "pedido16" / f"_tmp_cfg16384_{_os.getpid()}"; _CFG16.mkdir(parents=True, exist_ok=True); _at.register(_sh.rmtree, _CFG16, ignore_errors=True)
(_CFG16 / "orcamento_tokens.csv").write_text(_re.sub(r";\d+;1500;", ";16384;1500;", f.ORCAMENTO_CSV.read_text(encoding="utf-8-sig"), count=1), encoding="utf-8-sig"); f.ORCAMENTO_CSV = _CFG16 / "orcamento_tokens.csv"

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

TMP = DADOS / "tmp_teste_pedido28"; TMP.mkdir(exist_ok=True)
RODADA = TMP / f"r{int(time.time())}"; RODADA.mkdir()
f.PASTA = RODADA                      # BASE_SAIDA do app = f.PASTA / "saida": as sessões do teste ficam na pasta de teste

# ------------------------------------------------------------------ rede falsa
HOJE = dt.date.today().isoformat()
ESTADO = {"total": 1234, "ligar": False, "falha_seq": set(), "recorte": 6000, "chamadas": [], "inesperadas": []}
REG_PNCP = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "Termo de Referência", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]

def get(url, params=None, binario=False):          # qualname 'get': o app o trata como a função original
    params = params or {}; ESTADO["chamadas"].append(url)
    if "1_consultarMaterial" in url:
        pag = params.get("pagina", 1)
        lote = [{"idCompra": f"9{(pag - 1) * 100 + i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO SIMULADO {i}", "estado": "DF",
                 "descricaoItem": "NOTEBOOK i5 16 GB RAM SSD 512 GB tela 15,6 polegadas garantia 12 meses", "numeroItemCompra": i + 1, "nomePdm": "NOTEBOOK", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(100)]
        ultima = pag * 100 >= ESTADO["total"]
        return 200, {"totalRegistros": ESTADO["total"], "resultado": lote, "paginasRestantes": 0 if ultima or pag >= 3 and ESTADO["total"] <= 300 else 1}, {}
    if "4_consultarItemMaterial" in url:
        return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        return 200, {"resultado": [REG_PNCP] if ESTADO["ligar"] else []}, {}
    if url.endswith("/arquivos"):
        return 200, LISTA, {}
    m = re.search(r"/arquivos/(\d+)$", url)
    if m:
        return (500, b"", {}) if int(m.group(1)) in ESTADO["falha_seq"] else (200, b"%PDF-1.4 conteudo simulado", {})
    ESTADO["inesperadas"].append(url); raise AssertionError(f"URL inesperada no teste: {url}")
f.get = get

def opcao_4_falsa():                               # só recorta (PDF falso não é PDF de verdade); a opção 5 é a REAL
    f.escolher_numero("posição", 99); f.pergunta("item")
    pasta = f.SAIDA / "recortes" / "TR_sim"; pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "recorte.txt").write_text(ESTADO.get("recorte_txt") or ("x" * ESTADO["recorte"]), encoding="utf-8")
    print(f"Recorte salvo em: {pasta / 'recorte.txt'}")
_opcao_4_real = f.opcao_4_recortar                 # v4h (T5): a opção 4 REAL, com a extração do PDF trocada por páginas gravadas
f.opcao_4_recortar = opcao_4_falsa

IMPRESSO_PERGUNTAR = []                            # controle: a função REALMENTE imprime a frase durante a busca
_orig_perg = f.perguntar_atributos
def perguntar_vigiado(atributos):
    r = _orig_perg(atributos); IMPRESSO_PERGUNTAR.append("Preencha os atributos" in sys.stdout.getvalue()); return r
f.perguntar_atributos = perguntar_vigiado

# ------------------------------------------------------------------ utilidades da tela
def textos(at):
    saida = []
    for lista in (at.warning, at.success, at.error, at.info, at.markdown, at.caption, at.text, at.text_area, at.subheader, at.title):
        saida += [str(e.value) for e in lista]
    return saida
def tem(at, trecho): return any(trecho in t for t in textos(at))
def onde(at, trecho): return [t for t in textos(at) if trecho in t]
def botao(at, rotulo): return next(b for b in at.button if b.label == rotulo)
def sem_excecao(at, onde_): checa(len(at.exception) == 0, f"{onde_}: sem exceção na tela" + ("" if not at.exception else f" -> {[e.value for e in at.exception]}"))

import hashlib
import servicos as sv
INSTR1 = (RAIZ / "config" / "INSTRUCAO_FICHA.txt").read_text(encoding="utf-8").rstrip()
ITEM_P = "licença VMS|software de monitoramento"
def cab(item, n=4): return f"DOCUMENTO REC | item pedido: {item} | {n} páginas no original | páginas incluídas: 1, 4, 16, 19\n"
def recorte(item, extra="=== PÁGINA 1 ===\nGOVERNO DO ESTADO\nitem x9|y9 dentro do texto do documento\n"): return cab(item) + "\n" + extra

print("=== função pura texto_ia_sem_barra_no_item ===")
t = INSTR1 + "\n\n" + recorte(ITEM_P)
n = sv.texto_ia_sem_barra_no_item(t)
checa("item pedido: licença VMS / software de monitoramento | 4 páginas" in n and ITEM_P not in n, "item com '|': vira ' / ' na 1ª linha do recorte")
_dif = [(x, y) for x, y in zip(t.split("\n"), n.split("\n")) if x != y]
checa(len(t.split("\n")) == len(n.split("\n")) and len(_dif) == 1 and _dif[0][1].replace(" / ", "|") == _dif[0][0] and n.count("x9|y9") == 1 and "x9 / y9" not in n, "só 1 linha mudou (a do item); o '|' do texto do documento ('a|b'), a instrução e o resto ficam iguais")
checa(sv.texto_ia_sem_barra_no_item(INSTR1 + "\n\n" + recorte("notebook")) == INSTR1 + "\n\n" + recorte("notebook"), "item sem '|': texto idêntico")
checa(sv.texto_ia_sem_barra_no_item("") == "" and sv.texto_ia_sem_barra_no_item(None) == "" and sv.texto_ia_sem_barra_no_item("sem cabeçalho | item pedido: a|b") == "sem cabeçalho | item pedido: a|b", "texto vazio, None ou sem o cabeçalho do recorte: não quebra e não muda")
checa(sv.texto_ia_sem_barra_no_item(recorte("")) == recorte(""), "item vazio: idêntico, sem erro")
checa(sv.texto_ia_sem_barra_no_item(recorte("a|b|c")).startswith("DOCUMENTO REC | item pedido: a / b / c | 4 páginas"), "3 termos: dois separadores trocados")
real = (DADOS / "saida" / "sessoes" / "28783508d6294ea4825afd667f6ebb2a" / "para_ia" / "6_4_TR_PARA_IA.txt")
if real.exists():
    r0 = real.read_text(encoding="utf-8"); r1 = sv.texto_ia_sem_barra_no_item(r0)
    dif = [i for i, (x, y) in enumerate(zip(r0.split("\n"), r1.split("\n"))) if x != y]
    checa(len(dif) == 1 and len(r1) == len(r0) + 2, f"PARA_IA real da sessão 28783508…: muda 1 linha (a do item), +2 caracteres ({len(r0)} -> {len(r1)})")

def buscar(at):
    botao(at, "Buscar").click().run()
    return at
print("\n=== tela: preparação (download simulado) ===")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180)
at.run(); sem_excecao(at, "abertura")
at.text_input(key="codigo_av").set_value("8435").run(); at.text_input(key="at_notebook_RAM").set_value("16")
ESTADO.update(total=300); buscar(at); sem_excecao(at, "busca")
ESTADO.update(ligar=True, falha_seq=set())
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "download simulado")
def gerar(rec_txt):
    ESTADO["recorte_txt"] = rec_txt
    botao(at, "Gerar texto para IA").click().run()
    sem_excecao(at, "gerar texto para IA")
    area = next((a.value for a in at.text_area if a.label == "Texto para colar na IA"), None)
    ok = [t for t in textos(at) if t.startswith("Pronto: `")]
    alvo = Path(re.search(r"Pronto: `(.+?)`", ok[0]).group(1)) if ok else None
    pasta = next(iter((Path(alvo).parent.parent / "recortes").glob("*/")), None) if alvo else None
    return area, alvo, (pasta / "recorte.txt") if pasta else None
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]

print("\n=== tela (a)(c): item com '|' ===")
REC_A = recorte(ITEM_P)
area, alvo, rec = gerar(REC_A)
checa(area is not None and "item pedido: licença VMS / software de monitoramento | 4 páginas" in area and ITEM_P not in area, "(a) o texto para colar na IA mostra o item com ' / '")
para = alvo.read_text(encoding="utf-8") if alvo else ""
checa(para == area and para.startswith(INSTR1 + "\n\n"), f"(a) o PARA_IA em disco é igual ao texto da tela e começa com a instrução v1 intacta ({len(para)} caracteres)")
checa("x9|y9" in para and "x9 / y9" not in para, "(a) o '|' do texto do documento não foi tocado")
rec_txt = rec.read_text(encoding="utf-8") if rec else ""
checa(rec_txt == REC_A and ITEM_P in rec_txt, "(c) recorte.txt em disco continua com o item original ('|'), idêntico ao gerado (recorte não muda)")
sha_rec = sha(rec) if rec else None
import conferir_tela as ct
import json as _json
(rec.parent / "paginas.json").write_text(_json.dumps(["x"]), encoding="utf-8")
_, item_lido, _ = ct.ler_recorte(rec.parent)
(rec.parent / "paginas.json").unlink()   # o app trata paginas.json de 1 página curta como PDF sem texto: não deixar o arquivo do teste
checa(item_lido == ITEM_P, f"(c) ler_recorte devolve o item guardado '{item_lido}' (o conferidor recebe o item original)")
checa(sha(rec) == sha_rec, "(c) recorte.txt: mesmo hash antes e depois de ler o item")

print("\n=== tela (b): item sem '|' ===")
REC_B = recorte("notebook")
area, alvo, rec = gerar(REC_B)
para = alvo.read_text(encoding="utf-8") if alvo else ""
checa(alvo is not None and area == para and para == INSTR1 + "\n\n" + (rec.read_text(encoding="utf-8") if rec else ""), "(b) PARA_IA = instrução v1 + recorte.txt, sem nenhuma troca")
checa((rec.read_text(encoding="utf-8") if rec else "") == REC_B, "(b)(c) recorte.txt igual ao gerado")

print("\n=== tela (d): item vazio ===")
REC_D = recorte("")
area, alvo, rec = gerar(REC_D)
para = alvo.read_text(encoding="utf-8") if alvo else ""
checa(alvo is not None and area == para and para == INSTR1 + "\n\n" + (rec.read_text(encoding="utf-8") if rec else ""), "(d) item vazio: sem exceção e PARA_IA sem troca")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

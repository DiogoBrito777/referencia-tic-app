"""v4h, Fase 2 – guarda de contexto no recorte, OFFLINE (socket bloqueado; os PDFs de N01 a N05 são lidos de produto_p1\\fase2\\trabalho\\documentos,
copiados para uma pasta de teste dentro da v4h; os originais não são alterados).
 U1-U4  unitários com páginas SIMULADAS (dados simulados só aqui): ordem de inclusão, para na primeira que não couber, aviso, fidelidade
 R1     N01 a N05: nº de páginas mantidas = produto_p1\\fase5\\fase1d_limite70.csv (cabem_so_texto_do_pdf)
 R2     N01 a N05: páginas mantidas = produto_p1\\fase7 (top-N pelo ranking; é o mesmo conjunto do ranking por 70% da fase 8)
 R3     N03 e N05: o texto PARA_IA gerado é IGUAL byte a byte a produto_p1\\fase8\\prompts\\N03_70_por_ranking.txt e N05_70_por_ranking.txt
 R4     a linha 'Recorte: X de Y ...' e o aviso 'Recorte reduzido' saem na opção 4; recorte_info.json e recorte_seletor_completo.txt gravados
Uso (na pasta do app): ..\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_fase2_limite_contexto.py"""
import contextlib, csv, io, json, re, shutil, socket, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
def _sem_rede(*a, **k): raise AssertionError("TENTOU ABRIR REDE")
socket.socket.connect = _sem_rede
import ferramenta as f
# Pedido 16 (M1): este teste guarda o comportamento de 16.384. Usa uma CÓPIA TEMPORÁRIA do config com contexto_tokens=16384; o config real (hoje 32.768) não é tocado.
import atexit as _at, os as _os, re as _re, shutil as _sh
_CFG16 = DADOS / "pedido16" / f"_tmp_cfg16384_{_os.getpid()}"; _CFG16.mkdir(parents=True, exist_ok=True); _at.register(_sh.rmtree, _CFG16, ignore_errors=True)
(_CFG16 / "orcamento_tokens.csv").write_text(_re.sub(r";\d+;1500;", ";16384;1500;", f.ORCAMENTO_CSV.read_text(encoding="utf-8-sig"), count=1), encoding="utf-8-sig"); f.ORCAMENTO_CSV = _CFG16 / "orcamento_tokens.csv"
import ranking_recorte as rr

SOND = DADOS; P1 = SOND / "noite_2026-11-18" / "produto_p1"
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

# ---------------- U: unitários (páginas simuladas)
print("=== U. unitários (páginas simuladas) ===")
RXI, AP = "notebook", "garantia"
pag = ["cabecalho"] + [f"texto sem nada {i}" for i in range(2, 21)]
pag[4] = "notebook notebook garantia"        # pág. 5: a=2 -> 7
pag[9] = "notebook garantia garantia"        # pág. 10: a=1 -> 5
pag[14] = "notebook"                         # pág. 15: a=1 -> 3
seq = rr.ordem_de_inclusao(pag, RXI, AP)
checa(seq[0] == 1 and seq[1:4] == [5, 10, 15], f"U1 ordem: pág. 1 primeiro, depois a pontuação decrescente (obtido {seq})")
est = lambda prompt: {"tokens_prompt": len(prompt) / 10, "limite_tokens": 100.0, "acima_do_limite": len(prompt) / 10 > 100.0}
rec_txt = "DOCUMENTO REC | item pedido: notebook | 20 páginas no original | páginas incluídas: 1, 5, 10, 15\n"
pag2 = ["a" * 300, "b", "c", "d", "e" * 300, "f", "g", "h", "i", "j" * 300, "k", "l", "m", "n", "o" * 300, "p"]
seq2 = [1, 5, 10, 15]
def fake_seq(p, rx, ap): return seq2
orig = rr.ordem_de_inclusao; rr.ordem_de_inclusao = fake_seq
try:
    info = rr.aplicar_limite(pag2, "DOCUMENTO REC | item pedido: notebook | 16 páginas no original | páginas incluídas: 1, 5, 10, 15\n", "x", "y", 4, "INSTR", est)
finally:
    rr.ordem_de_inclusao = orig
checa(info["fidelidade"] and info["mantidas"] == [1, 5] and info["fora"] == [10, 15] and info["parou_antes_da"] == 10 and info["reduzido"],
      f"U2 para na primeira página que não couber (a 10) e NÃO pega a 15 mesmo sendo menor (mantidas {info['mantidas']}, fora {info['fora']}, parou antes da {info['parou_antes_da']})")
checa("=== PÁGINA 1 ===" in info["texto"] and "=== PÁGINA 10 ===" not in info["texto"] and "páginas incluídas: 1, 5\n" in info["texto"], "U2b texto remontado só com as mantidas, em ordem numérica, cabeçalho atualizado")
checa("Recorte reduzido" in rr.aviso_do_recorte({**info, "n_relevantes": 4}) and "10, 15" in rr.aviso_do_recorte({**info, "n_relevantes": 4}), "U3 aviso 'Recorte reduzido' lista as páginas de fora")
info_ok = {"mantidas": [1, 2, 3], "n_relevantes": 3, "estimativa": 11212, "limite": 11468.8, "fracao_janela": 0.7, "fora": [], "reduzido": False, "aviso_fidelidade": ""}
checa(rr.linha_do_recorte(info_ok) == "Recorte: 3 de 3 páginas relevantes · estimativa 11.212 tokens (limite 70% = 11.468,8)" and rr.aviso_do_recorte(info_ok) == "",
      f"U3b linha sempre mostrada, sem aviso quando nada foi cortado: {rr.linha_do_recorte(info_ok)!r}")
info_inf = rr.aplicar_limite(pag2, "DOCUMENTO REC | item pedido: notebook | 16 páginas no original | páginas incluídas: 1, 2, 3\n", "zzz", "yyy", 3, "INSTR", est)
checa(info_inf["fidelidade"] is False and not info_inf["reduzido"] and "SEM o limite" in rr.aviso_do_recorte(info_inf), f"U4 se a ordem não puder ser reproduzida o recorte do seletor fica e o aviso diz isso: {rr.aviso_do_recorte(info_inf)[:90]!r}")

# ---------------- R: N01 a N05 com os PDFs (só leitura)
print("\n=== R. N01 a N05 (PDFs copiados para a pasta de teste) ===")
import time
TESTE = DADOS / "pedido8" / f"teste_limite_{int(time.time())}"   # pasta nova a cada rodada (o Drive trava arquivos e impede apagar a anterior)
f.SAIDA = TESTE / "saida"; (f.SAIDA / "documentos").mkdir(parents=True)
DOCS = sorted((P1 / "fase2" / "trabalho" / "documentos").glob("N0*.pdf"))
for p in DOCS: shutil.copy2(p, f.SAIDA / "documentos" / p.name)
def sem_rede_get(*a, **k): raise AssertionError("ferramenta.get chamada")
f.get = sem_rede_get
esperado_cont = {r["doc"]: int(r["cabem_so_texto_do_pdf"]) for r in csv.DictReader((P1 / "fase5" / "fase1d_limite70.csv").open(encoding="utf-8-sig"), delimiter=";")}
linha_topn = next(l for l in (P1 / "fase7" / "progresso.txt").read_text(encoding="utf-8").splitlines() if "top-N pelo ranking" in l)
esperado_set = {d: [int(x) for x in re.findall(r"\d+", s)] for d, s in re.findall(r"(N0\d): \[([\d, ]+)\]", linha_topn)}
print("esperado (fase5\\fase1d):", esperado_cont, "\nesperado (fase7, top-N pelo ranking):", esperado_set)
prompts = {}
for d in ("N01", "N02", "N03", "N04", "N05"):
    pdfs = f.documentos_recortaveis(); pos = [p.name for p in pdfs].index(next(p.name for p in pdfs if p.name.startswith(d))) + 1
    resp4 = [pos, "notebook"]
    f.escolher_numero = lambda msg, maximo: int(resp4.pop(0)); f.pergunta = lambda msg, padrao="": str(resp4.pop(0)) or padrao
    b4 = io.StringIO()
    with contextlib.redirect_stdout(b4): f.opcao_4_recortar()
    out4 = b4.getvalue(); pasta = next((f.SAIDA / "recortes").glob(d + "*"))
    info = json.loads((pasta / "recorte_info.json").read_text(encoding="utf-8"))
    linha = next((l for l in out4.splitlines() if l.startswith("Recorte: ")), "")
    checa(len(info["mantidas"]) == esperado_cont[d], f"R1 {d}: {len(info['mantidas'])} páginas mantidas = {esperado_cont[d]} (fase5\\fase1d_limite70.csv)")
    checa(info["mantidas"] == sorted(esperado_set[d]), f"R2 {d}: mantidas {info['mantidas']} = fase7 top-N pelo ranking {sorted(esperado_set[d])}")
    print(f"      {d}: relevantes {info['relevantes']} | fora {info['fora']} | estimativa {info['estimativa']} | {linha}")
    checa(linha.startswith(f"Recorte: {len(info['mantidas'])} de {info['n_relevantes']} páginas relevantes · estimativa ") and "(limite 70% = 11.468,8)" in linha, f"R4 {d}: linha na opção 4: {linha!r}")
    checa(("Recorte reduzido" in out4) == bool(info["fora"]) and (not info["fora"] or all(str(p) in out4.split("Recorte reduzido")[1].split("(o limite")[0] for p in info["fora"])), f"R4 {d}: aviso 'Recorte reduzido' {'com' if info['fora'] else 'sem'} as páginas de fora ({info['fora']})")
    checa(info["fidelidade"] and (pasta / "recorte_seletor_completo.txt").exists() and info["estimativa"] <= info["limite"], f"R4 {d}: fidelidade do ranking, recorte completo do seletor guardado, estimativa {info['estimativa']} <= {info['limite']}")
    recs = sorted((f.SAIDA / "recortes").glob("*/recorte.txt")); idx = [r.parent.name for r in recs].index(pasta.name) + 1
    f.escolher_numero = lambda msg, maximo: idx
    with contextlib.redirect_stdout(io.StringIO()): f.opcao_5_texto_ia()
    prompts[d] = (f.SAIDA / "para_ia" / f"{pasta.name}_PARA_IA.txt").read_text(encoding="utf-8")
for d, nome in (("N03", "N03_70_por_ranking.txt"), ("N05", "N05_70_por_ranking.txt")):
    ref = (P1 / "fase8" / "prompts" / nome).read_text(encoding="utf-8")
    checa(prompts[d] == ref, f"R3 {d}: texto PARA_IA idêntico byte a byte a fase8\\prompts\\{nome} ({len(prompts[d])} caracteres)")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)

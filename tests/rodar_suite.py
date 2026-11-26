"""Roda a suíte offline completa a partir desta pasta: cada teste num processo próprio, SEM rede (socket bloqueado; só o loopback do asyncio passa), contando OK/FALHOU por suíte.
Usa o Python com que for chamado (sys.executable). Os dados de teste ficam na pasta irmã "referencia_tic_dados_teste" (ou na indicada pela variável REFERENCIA_TIC_DADOS);
resultados e temporários dos testes vão para lá. Se algum teste gravar arquivo novo DENTRO desta pasta, o runner o MOVE (não apaga) para <dados>\\gerados_pela_suite e avisa.
Uso (na pasta do app): <python> -I -B -X utf8 tests\\rodar_suite.py [nome_da_rodada]"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
APP = Path(__file__).resolve().parent.parent
DADOS = Path(os.environ.get("REFERENCIA_TIC_DADOS") or (APP.parent / "referencia_tic_dados_teste")).resolve()
OUT = DADOS / "resultados" / (sys.argv[1] if len(sys.argv) > 1 else "suite"); OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable
BLOQUEIO = ("import socket, runpy, sys\n_o = socket.socket.connect\n"
            "def _b(self, a, *x, **k):\n    h, p = (a[0], a[1]) if isinstance(a, tuple) else (str(a), None)\n"
            "    if h in ('127.0.0.1', '::1') and p != 11434: return _o(self, a, *x, **k)\n    raise ConnectionError('BLOQUEADO pelo runner (sem rede): %r' % (a,))\n"
            "socket.socket.connect = _b\nc = sys.argv[1]\nsys.argv = [c] + sys.argv[2:]\nrunpy.run_path(c, run_name='__main__')\n")
AUTOTESTE = ("import sys; sys.path.insert(0, '.'); sys.dont_write_bytecode = True\nimport ferramenta as f\n"
             "e = f.autoteste(); print('autoteste erros:', e if e else 'nenhum'); sys.exit(1 if e else 0)\n")
(OUT / "_autoteste.py").write_text(AUTOTESTE, encoding="utf-8")
NOMES = ("rodar_casos_bateria_busca:rodar_casos test_conferir_ficha test_fase3_consertos test_id_compra_zero test_orcamento_tokens teste_word_linux test_tela_fase4 test_fase2_limite_contexto "
         "test_fase3_conferir_ficha test_pedido9_servicos test_pedido9_tela test_pedido13_tela test_pedido13b_estrutura test_pedido13c_estrutura test_pedido13d_estrutura test_pedido13e_estrutura "
         "test_pedido13e_software test_pedido13f_estrutura test_pedido13f_download test_pedido13g_estrutura test_pedido13h_estrutura test_pedido13i_estrutura test_pedido13i_painel "
         "test_pedido13i_item_pedido test_pedido13j_item_pedido test_pedido13j_tokens test_pedido13k_tela test_pedido13k_pdf_real test_pedido17_logica test_pedido17_tela "
         "test_pedido16_janela32768 test_pedido18_logica test_pedido18_tela")
SUITES = [("autoteste", str(OUT / "_autoteste.py"))]
for n in NOMES.split():
    nome, _, arq = n.partition(":"); SUITES.append((nome, str(APP / "tests" / ((arq or nome) + ".py"))))
SUITES += [(p.stem, str(p)) for p in sorted((APP / "tests").glob("test_pedido25_*.py")) + sorted((APP / "tests").glob("test_pedido33_*.py"))]
PROT = {p: p.read_bytes() for p in (DADOS / "pedido13i" / "resultado_parte_b.json", DADOS / "pedido13j" / "resultado_parte_1.json") if p.exists()}   # os testes 13i/13j regravam estes arquivos
def arquivos_do_app(): return {str(p.relative_to(APP)) for p in APP.rglob("*") if p.is_file() and ".venv" not in p.parts}
antes = arquivos_do_app()
linhas, t0 = [], time.time()
for nome, alvo in SUITES:
    if not Path(alvo).exists(): print(f"{nome}: AUSENTE (não rodou)", flush=True); linhas.append({"suite": nome, "saida": -1, "linhas_OK": 0, "linhas_FALHOU": 0, "segundos": 0, "ultima_linha": "AUSENTE", "extra": ""}); continue
    t1 = time.time()
    extra = ["pedido16"] if re.search(r"test_pedido13[b-i]_estrutura", alvo) else []
    r = subprocess.run([PY, "-I", "-B", "-X", "utf8", "-c", BLOQUEIO, alvo, *extra], cwd=APP, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=550)
    for d_ in [q for n in ("pedido13k", "pedido17", "pedido18", "pedido25") for q in (DADOS / n).glob("_tmp_*")]: shutil.rmtree(d_, ignore_errors=True)   # temporários do tipo _tmp_* (Windows só solta depois que o processo termina)
    txt = (r.stdout or "") + (r.stderr or ""); (OUT / f"{nome}.txt").write_text(txt, encoding="utf-8")
    ok, fh = len(re.findall(r"^OK\s", txt, re.M)), len(re.findall(r"^FALHOU", txt, re.M)); extra_s = ""
    if nome == "rodar_casos_bateria_busca":
        m = re.search(r"(\d+) de (\d+) passaram", txt); extra_s = f" | bateria da busca: {m.group(1)} de {m.group(2)}" if m else ""
        gerado = APP / "tests" / "resultado_casos.csv"
        if gerado.exists(): shutil.move(str(gerado), str(OUT / "resultado_casos.csv"))
    for p, b in PROT.items(): p.write_bytes(b)
    ult = next((l.strip() for l in reversed(txt.splitlines()) if l.strip() and "WARNING" not in l), "")
    linhas.append({"suite": nome, "saida": r.returncode, "linhas_OK": ok, "linhas_FALHOU": fh, "segundos": round(time.time() - t1), "ultima_linha": ult[:140], "extra": extra_s})
    print(f"{nome}: saída {r.returncode} | OK {ok} | FALHOU {fh} | {round(time.time() - t1)} s{extra_s} | {ult[:100]}", flush=True)
novos = sorted(arquivos_do_app() - antes)
movidos = []
for rel in novos:
    src = APP / rel
    if not src.exists(): continue
    topo = APP / Path(rel).parts[0]
    if not any(str(a).startswith(Path(rel).parts[0] + os.sep) for a in antes) and topo.is_dir():
        dest = DADOS / "gerados_pela_suite" / Path(rel).parts[0]
        if topo.exists(): dest.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(topo), str(dest))     # pasta nova inteira: move
        movidos.append(rel)
    elif src.exists():
        dest = DADOS / "gerados_pela_suite" / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(src), str(dest)); movidos.append(rel)
print(f"\narquivos novos gravados dentro de {APP.name}: {len(novos)} (movidos para {DADOS.name}\\gerados_pela_suite: {len(movidos)})")
for rel in novos[:30]: print("  ", rel)
tot_ok, tot_f = sum(l["linhas_OK"] for l in linhas), sum(l["linhas_FALHOU"] for l in linhas)
print(f"\nTOTAL: {len(linhas)} suítes | OK {tot_ok} | FALHOU {tot_f} | duração {round(time.time() - t0)} s")
(OUT / "resumo.json").write_text(json.dumps({"suites": linhas, "total_suites": len(linhas), "total_OK": tot_ok, "total_FALHOU": tot_f, "arquivos_novos_na_pasta_do_app": novos, "duracao_s": round(time.time() - t0)}, ensure_ascii=False, indent=1), encoding="utf-8")
sys.exit(0 if all(l["saida"] == 0 for l in linhas) else 1)

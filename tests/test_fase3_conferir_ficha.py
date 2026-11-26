"""v4h, Fase 3 – tela "Conferir ficha" (sem IA), OFFLINE: socket bloqueado (só loopback do asyncio é deixado passar e contado; porta 11434 derruba), sem Ollama.
Parte A (funções, saídas JÁ GRAVADAS em disco, só leitura): conferir_tela.conferir_resposta sobre cada saída de produto_p1\\fase1, fase2, fase4, fase6, fase7,
        fase8 e fase9; os números têm que bater com os relatórios gravados (fase5\\fase2_reavaliacao_por_execucao.csv, fase6\\fase1a_formato_por_execucao.csv e os
        resultados.json de cada fase).
Parte B (tela, streamlit.testing.v1.AppTest sobre app.py): cola a resposta, clica 'Conferir ficha' e confere números, aviso de corte, aviso literal e CSV.
Dados simulados SÓ na parte B (recorte_info.json sintético para o aviso 'Recorte reduzido').
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_fase3_conferir_ficha.py   (na pasta do app)"""
import csv, json, os, re, shutil, socket, sys, time
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
import conferir_tela as ct
import conferir_ficha_v2 as cf

SOND = DADOS; P1 = SOND / "noite_2026-11-18" / "produto_p1"
INSTR = (RAIZ / "config" / "INSTRUCAO_FICHA.txt").read_text(encoding="utf-8")
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
def lcsv(p): return list(csv.DictReader(Path(p).open(encoding="utf-8-sig"), delimiter=";"))
PAG = {d: json.loads((next((P1 / "fase2" / "trabalho" / "recortes").glob(d + "*")) / "paginas.json").read_text(encoding="utf-8")) for d in ("N01", "N02", "N03", "N04", "N05")}
def doc_de(nome):
    m = re.search(r"N0\d", nome); return m.group(0) if m else "N01"      # F2_*/A_/B_/C_ (fases 8 e 9) são todas de N01
def tela(arq, d, pec="", ctx="16384"):
    return ct.conferir_resposta(Path(arq).read_text(encoding="utf-8"), PAG[d], INSTR, "notebook", pec, ctx)

print("=== A1. fase1, fase2, fase4 (22 saídas) contra fase5\\fase2_reavaliacao_por_execucao.csv (v2) e fase6\\fase1a_formato_por_execucao.csv (formato v3) ===")
ref5 = {(r["fase"], r["execucao"]): r for r in lcsv(P1 / "fase5" / "fase2_reavaliacao_por_execucao.csv")}
ref_fmt = {(r["fase"], r["execucao"]): r["formato_ok_v3"] == "True" for r in lcsv(P1 / "fase6" / "fase1a_formato_por_execucao.csv")}
n = 0; res_fase4 = {}
for (fase, ex), r in sorted(ref5.items()):
    arq = P1 / fase / "saidas" / f"{ex}.txt"; d = doc_de(ex); t = tela(arq, d); rs = t["resumo"]; n += 1
    ok = (rs["literais"], rs["citacoes"], rs["outra_pagina"], rs["ausentes"], rs["nao_citacoes"]) == tuple(int(r[k]) for k in ("literais_v2", "citacoes_v2", "pagina_errada_v2", "em_nenhuma_v2", "nao_citacoes_v2"))
    checa(ok and t["formato_ok"] == ref_fmt[(fase, ex)],
          f"{fase} {ex}: tela = {rs['literais']}/{rs['citacoes']} literais, pág. errada {rs['outra_pagina']}, em nenhuma {rs['ausentes']}, não-cit. {rs['nao_citacoes']}, formato_ok {t['formato_ok']} | relatório = {r['literais_v2']}/{r['citacoes_v2']}, {r['pagina_errada_v2']}, {r['em_nenhuma_v2']}, {r['nao_citacoes_v2']}, formato_ok {ref_fmt[(fase, ex)]}")
    res_fase4[(fase, ex)] = t
checa(n == 22, f"A1: {n} saídas conferidas (esperado 22)")
t = res_fase4[("fase4", "N04_parte1_de_6")]
checa(t["resumo"]["literais"] == 4 and t["resumo"]["citacoes"] == 4, f"A1 pedido: N04 parte 1 da fase 4 = 4 de 4 literais (tela: {t['resumo']['literais']} de {t['resumo']['citacoes']}; a v1 dava 0 de 8 por causa das aspas)")
checa(res_fase4[("fase4", "N05_parte1_de_8")]["formato_ok"] is True, "A1 pedido: N05 parte 1 da fase 4 = formato_ok sim (v3: marca 'não' sem página vale)")

print("\n=== A2. fase6, fase7, fase8, fase9 contra o resultados.json de cada fase ===")
def lista(fase, *caminho):
    x = json.loads((P1 / fase / "resultados.json").read_text(encoding="utf-8"))
    for c in caminho: x = x[c]
    return x
CONJ = []
r6 = json.loads((P1 / "fase6" / "resultados.json").read_text(encoding="utf-8"))
CONJ += [("fase6", e) for e in r6["fase2"]] + [("fase6", v["linha"]) for v in r6["fase3"].values() if isinstance(v, dict) and "linha" in v]
CONJ += [("fase7", e) for e in lista("fase7", "execucoes")]
CONJ += [("fase8", e) for e in lista("fase8", "fase1_execucoes") + lista("fase8", "fase2_execucoes")]
CONJ += [("fase9", e) for e in lista("fase9", "medicao")]
nao_achadas = []
for fase, e in CONJ:
    ex = e["execucao"]; arq = P1 / fase / "saidas" / f"{ex}.txt"
    if not arq.exists(): nao_achadas.append((fase, ex)); continue
    ctx = int(e.get("num_ctx") or 16384); pec = e.get("prompt_eval_count"); t = tela(arq, doc_de(ex), "" if pec is None else str(pec), str(ctx)); rs = t["resumo"]
    chaves = {"literais": rs["literais"], "pagina_errada": rs["outra_pagina"], "em_nenhuma_pagina": rs["ausentes"], "nao_citacoes": rs["nao_citacoes"]}
    guardado = {k: int(e[k]) for k in chaves if e.get(k) not in (None, "", "n/d")}
    fmt = e.get("formato_ok_v3")
    ver = e.get("funcao_verificar_execucao")
    ok = all(chaves[k] == v for k, v in guardado.items()) and (fmt is None or t["formato_ok"] == (str(fmt) == "True")) and (ver is None or t["verificacao"] == ver)
    checa(ok and (bool(guardado) or fmt is not None or ver is not None), f"{fase} {ex}: tela {chaves} formato_ok {t['formato_ok']} verificação {t['verificacao']!r} | relatório {guardado or '(sem contagens gravadas nesta fase: só formato e verificação)'} formato_ok {fmt} verificação {ver!r}")
checa(not nao_achadas, f"A2: todas as saídas listadas nos resultados.json existem em disco (faltam: {nao_achadas})")
print(f"      A2: {len(CONJ) - len(nao_achadas)} saídas conferidas")
t_cut = tela(P1 / "fase2" / "saidas" / "N05.txt", "N05", "8195", "16384")
checa(t_cut["possivel_corte"] and t_cut["verificacao"] == "POSSÍVEL CORTE", f"A2: N05 da fase 2 (prompt_eval_count 8195, janela 16384) = POSSÍVEL CORTE (obtido {t_cut['verificacao']!r})")
checa(not ct.conferir_resposta("lixo", PAG["N01"], INSTR, "notebook", "x", "16384")["ficha_encontrada"] and ct.conferir_resposta("lixo", PAG["N01"], INSTR, "notebook", "x", "16384")["erro_campos"], "A2: texto sem tabela = 'ficha não encontrada'; campo opcional inválido é avisado e ignorado (não derruba)")

print("\n=== B. a tela (AppTest) ===")
TMP = DADOS / "tmp_teste_fase4"; TMP.mkdir(exist_ok=True)
RODADA = TMP / f"f3_{int(time.time())}"; RODADA.mkdir()
f.PASTA = RODADA
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
checa(len(at.exception) == 0, "a tela abre sem exceção")
sess = RODADA / "saida" / "sessoes" / at.session_state["sessao_id"]
checa(any("Ainda não há recorte" in str(c.value) for c in at.caption), "sem recorte: a seção 'Conferir ficha' avisa em vez de quebrar")
def cria_recorte(nome, d, info, mtime):
    pasta = sess / "recortes" / nome; pasta.mkdir(parents=True)
    org = next((P1 / "fase2" / "trabalho" / "recortes").glob(d + "*"))
    shutil.copy2(org / "paginas.json", pasta / "paginas.json"); shutil.copy2(org / "recorte.txt", pasta / "recorte.txt")
    if info: (pasta / "recorte_info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    os.utime(pasta / "recorte.txt", (mtime, mtime))
agora = time.time()
INFO_RED = {"relevantes": list(range(1, 17)), "n_relevantes": 16, "mantidas": list(range(1, 12)), "fora": [12, 13, 14, 15, 16], "reduzido": True, "fidelidade": True, "estimativa": 11212, "limite": 11468.8,
            "acima_do_limite": False, "parou_antes_da": 12, "aviso_fidelidade": "", "fracao_janela": 0.7}
INFO_OK = {**INFO_RED, "n_relevantes": 8, "mantidas": list(range(1, 9)), "fora": [], "reduzido": False, "parou_antes_da": None, "estimativa": 10691}
cria_recorte("A_N01", "N01", INFO_OK, agora - 400); cria_recorte("B_N03", "N03", INFO_RED, agora - 300); cria_recorte("C_N04", "N04", None, agora - 200); cria_recorte("D_N05", "N05", None, agora - 100)
at.run()
def textos(at):
    s = []
    for lista in (at.warning, at.success, at.error, at.info, at.markdown, at.caption, at.subheader):
        s += [str(e.value) for e in lista]
    return s
def tem(trecho): return any(trecho in t for t in textos(at))
checa(tem("Conferir ficha (sem IA)"), "a seção 'Conferir ficha (sem IA)' aparece")
checa(tem("Citação literal só prova que o texto existe na página, não que a ficha está certa; atributo, marca, utilidade e compatível são revisão humana."), "aviso 'citação literal só prova...' visível na tela")
sb = at.selectbox(key="ficha_recorte")
checa([o for o in sb.options][:1] == ["D_N05"] or len(sb.options) == 4, f"os 4 recortes aparecem (mais recente primeiro): {list(sb.options)}")
def escolhe(nome):
    i = [o for o in at.selectbox(key="ficha_recorte").options].index(nome); at.selectbox(key="ficha_recorte").select_index(i).run()
def cola(arq, pec="", ctx="16384"):
    at.text_area(key="ficha_resposta").set_value(Path(arq).read_text(encoding="utf-8")); at.text_input(key="ficha_pec").set_value(pec); at.text_input(key="ficha_ctx").set_value(ctx).run()
    next(b for b in at.button if b.label == "Conferir ficha").click().run()
# B1: N01 sem corte
escolhe("A_N01"); cola(P1 / "fase2" / "saidas" / "N01.txt", "8963")
checa(len(at.exception) == 0, "B1: sem exceção depois de conferir")
checa(tem("6 de 6 citações literais") and tem("formato_ok: sim") and tem("não é citação: 3"), f"B1: N01 = 6 de 6 literais, 3 não-citações, formato_ok sim ({[t for t in textos(at) if 'citações literais' in t][:1]})")
df = at.dataframe[-1].value if at.dataframe else None
checa(df is not None and len(df) == 9 and set(["campo", "valor", "pagina", "trecho", "status"]) <= set(df.columns), f"B1: tabela por campo com 9 linhas e colunas campo/valor/página/trecho/status (colunas: {None if df is None else list(df.columns)})")
checa(not any("POSSÍVEL CORTE" in str(e.value) for e in at.error), "B1: sem 'POSSÍVEL CORTE' (8963 fora de [8192, 8208])")
checa(len(at.get("download_button")) >= 1 and any("conferência (CSV)" in str(getattr(b, "proto", b)) for b in at.get("download_button")), f"B1: botão de download do CSV presente ({len(at.get('download_button'))} botões de download)")
checa(tem("Recorte: 8 de 8 páginas relevantes · estimativa 10.691 tokens (limite 70% = 11.468,8)") and not any("Recorte reduzido" in str(w.value) for w in at.warning), "B1: linha do recorte sempre mostrada e sem aviso de 'Recorte reduzido' quando nada ficou de fora")
# B2: corte
escolhe("D_N05"); cola(P1 / "fase2" / "saidas" / "N05.txt", "8195")
checa(any("POSSÍVEL CORTE: refazer com recorte menor" in str(e.value) for e in at.error), "B2: N05 com prompt_eval_count 8195 e janela 16384 mostra 'POSSÍVEL CORTE: refazer com recorte menor'")
cola(P1 / "fase2" / "saidas" / "N05.txt", "", "16384")
checa(not any("POSSÍVEL CORTE" in str(e.value) for e in at.error) and tem("Sem prompt_eval_count"), "B2: sem prompt_eval_count a tela não afirma corte e diz que não dá para verificar")
# B3: fase 4
escolhe("C_N04"); cola(P1 / "fase4" / "saidas" / "N04_parte1_de_6.txt", "9040")
checa(tem("4 de 4 citações literais"), "B3: N04 parte 1 (fase 4) na tela = 4 de 4 literais")
escolhe("D_N05"); cola(P1 / "fase4" / "saidas" / "N05_parte1_de_8.txt", "")
checa(tem("formato_ok: sim"), "B3: N05 parte 1 (fase 4) na tela = formato_ok sim")
# B4: recorte reduzido na tela
escolhe("B_N03")
checa(any("Recorte reduzido" in str(w.value) and "12, 13, 14, 15, 16" in str(w.value) for w in at.warning) and tem("Recorte: 11 de 16 páginas relevantes · estimativa 11.212 tokens (limite 70% = 11.468,8)"), "B4: recorte reduzido: linha + aviso com as páginas de fora")
# B5: texto sem ficha
at.text_area(key="ficha_resposta").set_value("isto não é uma ficha").run(); next(b for b in at.button if b.label == "Conferir ficha").click().run()
checa(any("Não achei a tabela da ficha" in str(e.value) for e in at.error) and len(at.exception) == 0, "B5: texto que não é ficha: mensagem de erro clara, sem exceção")
checa(not [h for h in LOOPBACK_INTERNO if h[1] == 11434], f"nenhuma tentativa na porta 11434 (Ollama); connects de loopback do asyncio: {len(LOOPBACK_INTERNO)}")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)

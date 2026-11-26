"""v4h, Pedido 36 (Fase 2), SEM rede (socket bloqueado; rede SIMULADA). VISUAL_NOVO True x False: a tela tem os MESMOS rótulos, avisos, valores, chaves e tabelas; só mudam o
cabeçalho (1 markdown a mais com VISUAL_NOVO) e o tipo 'primary' do botão "Procurar no catálogo". Dados simulados só aqui (regra 10).
Uso: <python> -I -B -X utf8 tests\\test_pedido36_visual.py   (na pasta do app). Cria app_visual_false.py na pasta do app durante o teste e o apaga no fim."""
import datetime as dt, hashlib, os, re, socket, sys, time, zlib
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(os.environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
_o = socket.socket.connect
def _b(self, a, *x, **k):
    h, p = (a[0], a[1]) if isinstance(a, tuple) else (str(a), None)
    if h in ("127.0.0.1", "::1") and p != 11434: return _o(self, a, *x, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
from streamlit.testing.v1 import AppTest
import ferramenta as f
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
norm = f.norm
TMP = DADOS / "pedido36" / f"_tmp_teste_visual_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat()
def get(url, params=None, binario=False):
    params = params or {}
    if "1_consultarMaterial" in url:
        lote = [{"idCompra": f"9{i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO {i}", "estado": "DF",
                 "descricaoItem": f"SOFTWARE LICENCA SIMULADA {i}", "nomePdm": "SOFTWARE", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(10)]
        return 200, {"totalRegistros": len(lote), "resultado": lote, "paginasRestantes": 0}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        d = str(params.get("codigo", ""))[-1:]
        if d not in "47": return 200, {"resultado": []}, {}
        return 200, {"resultado": [{"numeroControlePNCP": f"1111111100019{d}-1-00000{d}/2026", "orgaoEntidadeCnpj": f"1111111100019{d}", "anoCompraPncp": 2026, "sequencialCompraPncp": int(d) + 1}]}, {}
    if url.endswith("/itens"): return 200, [], {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
botao = lambda at, r: next(b for b in at.button if b.label == r)
PRIMARIOS = {"Procurar no catálogo", "Gerar texto para IA", "Conferir ficha"}
FALSO = RAIZ / "app_visual_false.py"
fonte = (RAIZ / "app.py").read_text(encoding="utf-8")
checa(fonte.count("VISUAL_NOVO = True") == 1, "app.py tem a constante 'VISUAL_NOVO = True' (1 vez)")
def snapshot(arquivo, tipo="Produto"):
    at = AppTest.from_file(str(arquivo), default_timeout=300); at.run(); assert not at.exception, [e.value for e in at.exception]
    if tipo == "Serviço": at.radio(key="tipo_busca").set_value("Serviço").run()
    foto = {"abertura": instantaneo(at)}
    if tipo == "Produto":
        at.text_input(key="termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
        at.session_state[f"tab_sug_pdm_{zlib.crc32(norm('windows 11').encode('utf-8'))}"] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
        botao(at, "Buscar").click().run(); assert not at.exception, [e.value for e in at.exception]
        foto["depois_da_busca"] = instantaneo(at)
    return at, foto
def nt(x):
    """Troca só o que depende do relógio: data e hora da busca (minuto corrente) e durações ('em 0,8 s'); o resto do texto é comparado igual."""
    x = re.sub(r"\d\d/\d\d \d\d:\d\d", "<data e hora da busca>", str(x))
    return re.sub(r"\d+(?:[.,]\d+)? ?(?:ms|s|min)\b", "<tempo>", x)
def instantaneo(at):
    md = [str(m.value) for m in at.markdown]
    return {"subheader": [s.value for s in at.subheader], "markdown": [nt(m) for m in md if "ref-cabecalho" not in m], "n_markdown": len(md), "caption": [nt(c.value) for c in at.caption],
            "info": [nt(i.value) for i in at.info], "warning": [nt(w.value) for w in at.warning], "error": [nt(e.value) for e in at.error], "success": [nt(s.value) for s in at.success],
            "button": [b.label for b in at.button], "botao_tipo": [(b.label, str(b.proto.type)) for b in at.button], "cartoes": 0, "text_input": [(t.key, t.label, t.value) for t in at.text_input], "selectbox": [(s.label, str(s.value)) for s in at.selectbox],
            "radio": [(r.label, str(r.value)) for r in at.radio], "checkbox": [(c.label, c.value) for c in at.checkbox], "expander": [e.label for e in at.expander],
            "dataframe": [hashlib.sha1(d.value.to_json().encode("utf-8")).hexdigest()[:12] for d in at.dataframe], "excecoes": len(at.exception),
            "estado": sorted(k for k in at.session_state if not str(k).startswith("$$"))}
try:
    FALSO.write_text(fonte.replace("VISUAL_NOVO = True", "VISUAL_NOVO = False"), encoding="utf-8")
    for tipo in ("Produto", "Serviço"):
        print(f"\n=== {tipo}: VISUAL_NOVO True x False ===")
        at_v, fv = snapshot(RAIZ / "app.py", tipo); at_f, ff = snapshot(FALSO, tipo)
        for momento in fv:
            a, b = fv[momento], ff[momento]; difer = [k for k in a if a[k] != b[k] and k not in ("n_markdown", "botao_tipo", "cartoes")]
            for k in difer: print("   diferença em", k, [(x[:90], y[:90]) for x, y in zip(a[k], b[k]) if x != y][:3] if isinstance(a[k], list) and a[k] and isinstance(a[k][0], str) else (len(a[k]), len(b[k])))
            checa(not difer,f"{momento}: tudo igual com True e False (rótulos, avisos, valores, tabelas, chaves); campos diferentes: {difer}")
            dt = sorted({x[0] for x, y in zip(a["botao_tipo"], b["botao_tipo"]) if x != y})
            checa(set(dt) <= PRIMARIOS and all(y[1] != "primary" for x, y in zip(a["botao_tipo"], b["botao_tipo"]) if x != y), f"{momento}: só mudam de tipo (primário) os botões principais: {dt}")
            checa(a["n_markdown"] - b["n_markdown"] == 1, f"{momento}: o único elemento de texto a mais com True é o cabeçalho (markdown True {a['n_markdown']} x False {b['n_markdown']})")
        pv = [bt.proto.type for bt in at_v.button if bt.label == ("Procurar no catálogo" if tipo == "Produto" else "Procurar no catálogo")]
        pf = [bt.proto.type for bt in at_f.button if bt.label == "Procurar no catálogo"]
        checa(pv == ["primary"] and pf != ["primary"], f"'Procurar no catálogo' é primário com True ({pv}) e não com False ({pf})")
        cab = [str(m.value) for m in at_v.markdown if "ref-cabecalho" in str(m.value)]
        checa(len(cab) == 1 and "Referência TIC" in cab[0], f"cabeçalho 'Referência TIC' aparece 1 vez com True ({len(cab)}) e 0 com False ({sum(1 for m in at_f.markdown if 'ref-cabecalho' in str(m.value))})")
finally:
    if FALSO.exists(): FALSO.unlink()
# ---- tabela_destaque (realce da linha de menor preço): extraída do app.py e testada sozinha; dados simulados SÓ aqui (regra 10)
import pandas as pd
_m = re.search(r"^def tabela_destaque\(tab\):.*?(?=^def )", fonte, re.S | re.M)
for _vn in (True, False):
    _ns = {"pd": pd, "VISUAL_NOVO": _vn}; exec(_m.group(0), _ns); td = _ns["tabela_destaque"]
    tab = pd.DataFrame({"linha": [3, 1, 2, 4], "preco_unitario_homologado": [150.0, 90.5, 90.5, None], "orgao": ["a", "b", "c", "d"]})
    r = td(tab)
    if _vn:
        marcadas = sorted({i for (i, j), v in r._compute().ctx.items() if v})
        checa(r.data.equals(tab) and list(r.data["linha"]) == [3, 1, 2, 4], "True: tabela_destaque não muda ordem nem valores (Styler sobre os mesmos dados)")
        checa(marcadas == [1, 2], f"True: só as linhas de menor preço (posições 1 e 2) têm estilo: {marcadas}")
    else:
        checa(r is tab, "False: tabela_destaque devolve a mesma tabela, sem estilo")
_ns = {"pd": pd, "VISUAL_NOVO": True}; exec(_m.group(0), _ns)
um = pd.DataFrame({"preco_unitario_homologado": [10.0, None]}); checa(_ns["tabela_destaque"](um) is um, "True: com menos de 2 preços não realça nada")
print("\nResíduo app_visual_false.py apagado:", not FALSO.exists())
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

"""v4h, Pedido 25 (Fase 3), SEM rede (socket bloqueado; rede SIMULADA). Aviso do modo rápido: depois da busca, conta entre as linhas ligadas ao PNCP os órgãos distintos, os preços
distintos e os preços suspeitos; se 2+ ligadas são do mesmo órgão ou do mesmo preço, avisa 'as ligadas podem não representar o mercado; use o modo completo'. Só contagem, sem IA.
Dados simulados só aqui (regra 10).
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido25_modo_rapido.py   (na pasta do app)"""
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
TMP = DADOS / "pedido25" / f"_tmp_teste_m_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat()
CEN = {"orgao": "mesmo", "preco": "igual", "ligar": True}
def get(url, params=None, binario=False):
    if "1_consultarMaterial" in url:
        lote = [{"idCompra": f"9{i:016d}", "precoUnitario": (0.0001 if CEN["preco"] == "igual" else 3000.0 + i), "dataResultado": HOJE, "dataCompra": HOJE,
                 "nomeOrgao": ("TRIBUNAL TESTE" if CEN["orgao"] == "mesmo" else f"ORGAO {i}"), "estado": "DF", "descricaoItem": f"SOFTWARE LICENCA SIMULADA {i}",
                 "nomePdm": "SOFTWARE", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(10)]
        return 200, {"totalRegistros": len(lote), "resultado": lote, "paginasRestantes": 0}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        if not CEN["ligar"]: return 200, {"resultado": []}, {}
        return 200, {"resultado": [{"numeroControlePNCP": "11111111000191-1-000001/2026", "orgaoEntidadeCnpj": "11111111000191", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}]}, {}
    if url.endswith("/itens"): return 200, [], {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
botao = lambda at, r: next(b for b in at.button if b.label == r)
def busca(modo="rápido", **cen):
    CEN.update({"orgao": "mesmo", "preco": "igual", "ligar": True}); CEN.update(cen)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300); at.run()
    at.text_input(key="termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
    at.session_state[f"tab_sug_pdm_{zlib.crc32(norm('windows 11').encode('utf-8'))}"] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
    if modo != "rápido": next(r for r in at.radio if r.label == "Modo").set_value(modo)   # dentro do formulário: o valor só vale junto com o clique em Buscar
    botao(at, "Buscar").click().run(); assert not at.exception, [e.value for e in at.exception]; return at
def avisos(at):
    return {"warning": [w.value for w in at.warning if str(w.value).startswith("Modo rápido:")], "caption": [c.value for c in at.caption if str(c.value).startswith("Modo rápido:")]}
def tabela(at): return next(d.value for d in at.dataframe if "descricao_item" in d.value.columns)

print("=== função pura aviso_modo_rapido ===")
L = lambda org, pr, lig=True, obs="": {"link_publico": "https://x/1" if lig else "", "orgao": org, "preco_unitario_homologado": pr, "observacao_preco": obs}
r = sv.aviso_modo_rapido([L("A", 1), L("B", 2), L("C", 3)], "rápido")
checa(r is not None and r[1] is False and "3 linha(s) ligada(s) ao PNCP, 3 órgão(s) distinto(s), 3 preço(s) distinto(s) e 0 com preço suspeito." in r[0] and "modo completo" not in r[0], f"3 ligadas, 3 órgãos, 3 preços: sem alerta ('{r[0] if r else None}')")
r = sv.aviso_modo_rapido([L("A", 1), L("a ", 2), L("A", 3)], "rápido")
checa(r[1] is True and "1 órgão(s) distinto(s)" in r[0] and "use o modo completo" in r[0], "3 ligadas do mesmo órgão (maiúsculas/espaços iguais): alerta")
r = sv.aviso_modo_rapido([L("A", 0.0001), L("B", 0.0001)], "rápido")
checa(r[1] is True and "1 preço(s) distinto(s)" in r[0], "2 ligadas com o mesmo preço: alerta")
r = sv.aviso_modo_rapido([L("A", 5)], "rápido")
checa(r is not None and r[1] is False, "1 ligada só: conta, mas não alerta (n=1 não é prova de nada)")
checa(sv.aviso_modo_rapido([L("A", 1, lig=False), L("A", 1, lig=False)], "rápido") is None, "0 ligadas (n=0): sem aviso")
checa(sv.aviso_modo_rapido([L("A", 1), L("A", 1)], "completo") is None and sv.aviso_modo_rapido([L("A", 1)], None) is None, "modo completo ou sem modo: sem aviso")
r = sv.aviso_modo_rapido([L("A", 1, obs="preço suspeito"), L("B", 2, obs="preço suspeito"), L("C", 3), L("D", 4, lig=False, obs="preço suspeito")], "rápido")
checa("3 linha(s) ligada(s)" in r[0] and "2 com preço suspeito" in r[0], "suspeitas contadas só entre as ligadas: 2 de 3 (a suspeita não ligada fica de fora)")
r = sv.aviso_modo_rapido([L("A", 1, obs="suspeito"), L("B", 2)], "rápido", "suspeito")
checa("1 com preço suspeito" in r[0], "rótulo de Serviço ('suspeito') também é contado")

print("\n=== tela (Produto, rede simulada) ===")
at = busca(orgao="mesmo", preco="igual"); av = avisos(at); t = tabela(at)
lig = int((t["abrir"].fillna("") != "").sum()) if "abrir" in t.columns else -1   # a coluna "abrir" é o link do PNCP (só nas linhas ligadas)
susp = int((t["observacao_preco"].fillna("") == "preço suspeito").sum()) if "observacao_preco" in t.columns else -1
checa(len(av["warning"]) == 1 and not av["caption"] and f"{lig} linha(s) ligada(s) ao PNCP, 1 órgão(s) distinto(s), 1 preço(s) distinto(s) e {susp} com preço suspeito." in av["warning"][0] and "use o modo completo" in av["warning"][0],
      f"rápido, mesmo órgão e mesmo preço (0,0001): alerta na tela ({lig} ligadas, {susp} suspeitas): '{av['warning'][0] if av['warning'] else None}'")
at = busca(orgao="mesmo", preco="varia"); av = avisos(at)
checa(len(av["warning"]) == 1 and "1 órgão(s) distinto(s)" in av["warning"][0] and "10 preço(s) distinto(s)" in av["warning"][0], f"rápido, mesmo órgão, preços diferentes: alerta por órgão: '{av['warning'][0][:110] if av['warning'] else None}'")
at = busca(orgao="varia", preco="igual"); av = avisos(at)
checa(len(av["warning"]) == 1 and "10 órgão(s) distinto(s)" in av["warning"][0] and "1 preço(s) distinto(s)" in av["warning"][0], f"rápido, órgãos diferentes, mesmo preço: alerta por preço: '{av['warning'][0][:110] if av['warning'] else None}'")
at = busca(orgao="varia", preco="varia"); av = avisos(at)
checa(not av["warning"] and len(av["caption"]) == 1 and "10 órgão(s) distinto(s), 10 preço(s) distinto(s)" in av["caption"][0] and "modo completo" not in av["caption"][0], f"rápido, tudo diferente: só a contagem, sem alerta: '{av['caption'][0][:120] if av['caption'] else None}'")
at = busca(modo="completo", orgao="mesmo", preco="igual"); av = avisos(at)
checa(not av["warning"] and not av["caption"], "modo completo: nenhum aviso do modo rápido")
at = busca(orgao="mesmo", preco="igual", ligar=False); av = avisos(at)
checa(not av["warning"] and not av["caption"], "rápido sem nenhuma linha ligada (n=0): nenhum aviso")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

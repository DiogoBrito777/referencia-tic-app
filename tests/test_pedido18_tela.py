"""v4h, Pedido 18 – TELA (AppTest), SEM rede (socket bloqueado; rede SIMULADA só para a busca do Produto/Serviço). Cobre: orientação de software pela contagem no CSV (xdr/edr/endpoint/365 = mensagem de serviço; windows/office =
orientação atual; Serviço sem mudança), 'Você quis dizer' só com sugestão que passa na regra (windows/office/xdr sem linha; mouze e monitor mantêm), aviso de custo do Produto com 1+ códigos (0 = nada; Serviço igual),
aviso de item único (20+ linhas do mesmo código = aviso; 2 códigos ou menos de 20 linhas = nada; Serviço sem aviso). O AppTest não mede o desenho no navegador.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido18_tela.py   (na pasta do app)"""
import csv, datetime as dt, re, socket, sys, time, zlib
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
TMP = DADOS / "pedido18" / f"_tmp_teste_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat(); CHAMADAS = []; PROD = {"n": 10, "ncod": 10}
REAIS = list(csv.DictReader((DADOS / "pedido12b" / "servicos_precos_todas.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
MODOS = {"rápido": {"MAX_PAGINAS_CATALOGO": 3, "MAX_VINCULOS": 10}, "completo": {"MAX_PAGINAS_CATALOGO": f.MAX_PAGINAS_CATALOGO, "MAX_VINCULOS": f.MAX_VINCULOS}}
def get(url, params=None, binario=False):
    params = params or {}; CHAMADAS.append((url, dict(params)))
    if "3_consultarServico" in url:
        cod = str(params.get("codigoItemCatalogo")); rs = [r for r in REAIS if r["codigo"] == cod]
        lote = [{"idCompra": f"{r['orgao_id']}{i:05d}", "numeroItemCompra": i + 1, "descricaoItem": r["descricao"], "codigoItemCatalogo": int(cod), "siglaUnidadeMedida": r["unidade"] or "UN", "quantidade": float(r["quantidade"] or 1),
                 "precoUnitario": float(r["valor"]), "nomeOrgao": f"ORGAO {r['orgao_id']}", "estado": r["uf"], "dataCompra": HOJE, "dataResultado": HOJE} for i, r in enumerate(rs)]
        return 200, {"totalRegistros": len(lote), "paginasRestantes": 0, "resultado": lote}, {}
    if "1_consultarMaterial" in url:
        lote = [{"idCompra": f"9{i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO {i}", "estado": "DF", "descricaoItem": (PROD["nome0"] if i == 0 and PROD.get("nome0") else f"SOFTWARE LICENCA SIMULADA {i}"), "numeroItemCompra": i + 1,
                 "nomePdm": "SOFTWARE", "codigoItemCatalogo": 1000 + (i % PROD["ncod"]), "marca": "X"} for i in range(PROD["n"])]
        return 200, {"totalRegistros": len(lote), "resultado": lote, "paginasRestantes": 0}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url: return 200, {"resultado": []}, {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
botao = lambda at, r: next(b for b in at.button if b.label == r)
def textos(at):
    out = [m.value for m in at.markdown] + [m.value for m in at.caption] + [m.value for m in at.info] + [m.value for m in at.warning] + [m.value for m in at.error] + [m.value for m in at.success]
    return "\n".join(str(x) for x in out)
def novo(modo):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300); at.run()
    if modo == "Serviço": at.radio(key="tipo_busca").set_value("Serviço").run()
    return at
def procura(modo, termo):
    at = novo(modo); at.text_input(key="termo" if modo == "Produto" else "serv_termo").set_value(termo).run(); botao(at, "Procurar no catálogo").click().run()
    assert not at.exception, [e.value for e in at.exception]; return at
def tem_tabela_usar(at): return any("usar" in d.value.columns for d in at.dataframe)
MSG_SERV = lambda t: sv.mensagem_software_sem_item(t, 146)

print("=== Fase 1: orientação de software em Produto (contagem no CSV de 146 itens) ===")
for t in ("xdr", "edr", "endpoint", "365"):
    at = procura("Produto", t); infos = [i.value for i in at.info]
    checa(MSG_SERV(t) in infos and not any("não é um tipo de produto" in i for i in infos) and not tem_tabela_usar(at), f"Produto '{t}': mensagem de serviço (0 de 146 itens), sem a orientação antiga e sem tabela de sugestão")
for t in ("windows", "office", "windows 11", "office 365"):
    at = procura("Produto", t); infos = [i.value for i in at.info]
    checa(any("não é um tipo de produto no catálogo oficial" in i for i in infos) and not any("Não há item de" in i for i in infos) and tem_tabela_usar(at), f"Produto '{t}': orientação atual mantida (texto antigo + tabela de sugestão)")
at = procura("Serviço", "xdr")
checa(not any("PDM Software: 0 de" in i.value for i in at.info) and not any("Não há item de" in i.value for i in at.info), "Serviço 'xdr': a mensagem nova NÃO aparece (nada muda no Serviço)")
checa(tem_tabela_usar(at) or any("Sugestão de onde procurar" in i.value for i in at.info) or any("termos_software.csv" in c.value for c in at.caption), f"Serviço 'xdr': continua com a orientação de serviço de antes ({[i.value[:50] for i in at.info]})")

print("\n=== Fase 2: 'Você quis dizer' ===")
VQD = "Você quis dizer"
for t in ("windows", "office", "xdr", "edr"):
    at = procura("Produto", t)
    checa(VQD not in textos(at) and not [b.label for b in at.button if b.key and b.key.startswith("sug_")], f"Produto '{t}': sem a linha 'Você quis dizer' e sem botão de sugestão")
at = procura("Produto", "xdr")
checa(any("Nenhum termo parecido" in w.value for w in at.warning), "Produto 'xdr': o aviso de 'nada encontrado' diz 'Nenhum termo parecido'")
at = procura("Produto", "mouze"); bsug = [b.label for b in at.button if b.key and b.key.startswith("sug_")]
checa(VQD in textos(at) and bsug == ["MOUSE COMPUTADOR"], f"Produto 'mouze': mantém 'Você quis dizer' com o botão {bsug}")
at = procura("Produto", "monitor"); bsug = [b.label for b in at.button if b.key and b.key.startswith("sug_")]
checa(VQD in textos(at) and len(bsug) == 5 and all("MONITOR" in b for b in bsug), f"Produto 'monitor': mantém as 5 sugestões {bsug}")
at = procura("Serviço", "manutenção")
checa(VQD not in textos(at), "Serviço: não tem 'Você quis dizer' (função própria de Produto; nada muda)")

print("\n=== Fase 3: aviso de custo em Produto ===")
CUSTO = "código(s) · rápido: até"
at = procura("Produto", "cadeira")
checa(not [c.value for c in at.caption if CUSTO in c.value], "Produto, 0 códigos marcados: nenhum aviso de custo")
botao(at, "Marcar todos").click().run()
cap6 = [c.value for c in at.caption if CUSTO in c.value]
checa(cap6 == [sv.aviso_custo_produto(6, MODOS)] and not [c.value for c in at.caption if "códigos × cerca de" in c.value], f"Produto, 6 códigos: '{cap6[0][:60] if cap6 else None}…' (e o aviso antigo de 'cerca de' não aparece mais)")
at = procura("Produto", "windows 11")
at.session_state[f"tab_sug_pdm_{zlib.crc32(norm('windows 11').encode('utf-8'))}"] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
cap1 = [c.value for c in at.caption if CUSTO in c.value]
checa(cap1 == [sv.aviso_custo_produto(1, MODOS)] and cap1[0].startswith("1 código(s) · rápido: até 3 páginas e 10 compras"), f"Produto, 1 código marcado: '{cap1[0][:70] if cap1 else None}…'")
at = novo("Serviço"); at.text_input(key="serv_codigo_av").set_value("27456, 27464").run()
cs = [c.value for c in at.caption]
checa(sv.estimativa_busca(2) in cs and not [c for c in cs if CUSTO in c], "Serviço, 2 códigos: aviso de antes (estimativa_busca) e NENHUM texto novo")
at = novo("Serviço"); at.text_input(key="serv_codigo_av").set_value("27456").run()
checa(not [c.value for c in at.caption if "códigos × cerca de" in c.value or CUSTO in c.value], "Serviço, 1 código: sem aviso (igual a antes)")

print("\n=== Fase 4: aviso de item único em Produto ===")
def prod_busca(n, ncod, nome0=None):
    PROD["n"], PROD["ncod"], PROD["nome0"] = n, ncod, nome0
    at = procura("Produto", "windows 11")
    at.session_state[f"tab_sug_pdm_{zlib.crc32(norm('windows 11').encode('utf-8'))}"] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
    botao(at, "Buscar").click().run(); assert not at.exception, [e.value for e in at.exception]; return at
def tab_res(at): return next(d.value for d in at.dataframe if "descricao_item" in d.value.columns)
def avisos_unico(at): return [w.value for w in at.warning if "mesmo item de catálogo" in w.value]
at = prod_busca(25, 1); n_lidas = len(tab_res(at)); au = avisos_unico(at)
checa(n_lidas == 25 and len(au) == 1 and au[0].startswith(f"As {n_lidas} linhas lidas são do mesmo item de catálogo (código 1000: SOFTWARE LICENCA SIMULADA") and "Mostrar só linhas que citam a palavra" in au[0], f"25 linhas, 1 item de catálogo: aviso -> '{au[0][:110] if au else None}…'")
checa(any(i.label == "Mostrar só linhas que citam a palavra" for i in at.text_input), "o campo 'Mostrar só linhas que citam a palavra' está na tela")
at = prod_busca(25, 2)
checa(len(tab_res(at)) == 25 and not avisos_unico(at), "25 linhas, 2 itens de catálogo: nenhum aviso")
at = prod_busca(10, 1)
checa(len(tab_res(at)) == 10 and not avisos_unico(at), "10 linhas do mesmo item (menos de 20): nenhum aviso")
at = prod_busca(20, 1)
checa(len(tab_res(at)) == 20 and len(avisos_unico(at)) == 1, "20 linhas do mesmo item (limite): aviso")
cods27499 = sum(1 for r in REAIS if r["codigo"] == "27499")
at = novo("Serviço"); at.text_input(key="serv_codigo_av").set_value("27499").run(); botao(at, "Buscar compras do serviço").click().run()
checa(not at.exception and not avisos_unico(at) and len(tab_res(at)) == cods27499, f"Serviço, 1 código com {cods27499} linhas lidas: sem aviso de item único (nada muda no Serviço)")
print("\n=== Pedido 21: nome do item no aviso (corte em palavra inteira, limite 80) ===")
def nome_na_tela(av): return av.split("(código 1000: ", 1)[1].split("). O produto de cada compra", 1)[0]
LONGO = "SOFTWARE LICENCA SISTEMA OPERACIONAL WINDOWS SERVER CLIENT SERVER SUITE PROFESSIONAL EDITION ADICIONAL COMPLETO"
at = prod_busca(25, 1, LONGO); au = avisos_unico(at)
nm = nome_na_tela(au[0]) if au else ""; base = nm[:-1]
checa(len(LONGO) > 80 and len(au) == 1 and nm.endswith("…") and len(base) <= 80 and LONGO.startswith(base) and LONGO[len(base)] == " " and not nm[:-1].endswith(" "),
      f"25 linhas, nome de {len(LONGO)} caracteres: na tela '{nm}' ({len(base)} caracteres + …), corte em palavra inteira")
checa(all(p in LONGO.split() for p in base.split()), "nenhuma palavra do nome na tela está cortada (todas as palavras são palavras inteiras do nome original)")
NOME70 = "SOFTWARE LICENCA SISTEMA OPERACIONAL WINDOWS SERVER CLIENT SERVER SUITE X"[:70].rstrip()
NOME70 = NOME70 + "Y" * (70 - len(NOME70))
at = prod_busca(25, 1, NOME70); au = avisos_unico(at); nm = nome_na_tela(au[0]) if au else ""
checa(len(NOME70) == 70 and len(au) == 1 and nm == NOME70 and "…" not in au[0], f"25 linhas, nome de {len(NOME70)} caracteres: aparece inteiro, sem '…'")
PROD["nome0"] = None
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

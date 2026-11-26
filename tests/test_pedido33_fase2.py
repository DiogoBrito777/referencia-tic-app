"""v4h, Pedido 33 (Fase 2), SEM rede (socket bloqueado; rede SIMULADA). Avisos:
(5) Etapa 3: ao LISTAR os documentos da compra, se nenhum é edital/TR/ETP/DFD/aviso, mostra o aviso 'provavelmente contratação direta' antes do botão de baixar (nada é baixado);
(6) Etapa 5: alerta novo 'Revisar · compatível' quando compatível = 'diferente' ou 'o documento não trata do item'. Os alertas de antes continuam iguais.
Dados simulados só aqui (regra 10).
Uso: <python> -I -B -X utf8 tests\\test_pedido33_fase2.py   (na pasta do app)"""
import datetime as dt, json, os, socket, sys, time, zlib
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(os.environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
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
import conferir_ficha_v2 as cf
import conferir_tela as ct
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
norm = f.norm
TMP = DADOS / "pedido33" / f"_tmp_teste_f2_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat(); CHAMADAS = []
ESTADO = {"lista": [], "status_lista": 200}
CNPJ = "11111111000191"
def get(url, params=None, binario=False):
    params = params or {}; CHAMADAS.append(url)
    if "1_consultarMaterial" in url:
        lote = [{"idCompra": f"9{i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO {i}", "estado": "DF",
                 "descricaoItem": f"SOFTWARE LICENCA SIMULADA {i}", "nomePdm": "SOFTWARE", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(10)]
        return 200, {"totalRegistros": len(lote), "resultado": lote, "paginasRestantes": 0}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        return 200, {"resultado": [{"numeroControlePNCP": f"{CNPJ}-1-000001/2026", "orgaoEntidadeCnpj": CNPJ, "anoCompraPncp": 2026, "sequencialCompraPncp": 1}]}, {}
    if url.endswith("/itens"): return 200, [], {}
    if url.endswith("/arquivos"): return ESTADO["status_lista"], (ESTADO["lista"] if ESTADO["status_lista"] == 200 else {}), {}
    if "/arquivos/" in url: return 200, b"%PDF-1.4 teste", {}
    raise AssertionError(f"URL inesperada: {url}")
f.get = get
botao = lambda at, r: next(b for b in at.button if b.label == r)
def arq(seq, titulo, tipo="", ativo=True): return {"sequencialDocumento": seq, "titulo": titulo, "tipoDocumentoNome": tipo, "statusAtivo": ativo, "url": f"https://pncp.gov.br/pncp-api/v1/orgaos/{CNPJ}/compras/2026/1/arquivos/{seq}"}
def busca():
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300); at.run()
    at.text_input(key="termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
    at.session_state[f"tab_sug_pdm_{zlib.crc32(norm('windows 11').encode('utf-8'))}"] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
    botao(at, "Buscar").click().run(); assert not at.exception, [e.value for e in at.exception]; return at
BTN_LISTAR = "Listar os TR e documentos principais desta compra (1 consulta ao PNCP, nada é baixado)"
FRASE = "provavelmente contratação direta"
def avisos_sem_tr(at): return [w.value for w in at.warning if FRASE in str(w.value)]

print("=== Item 5 (função pura) ===")
D = lambda titulo, tipo, principal=False: {"titulo": titulo, "tipo": tipo, "principal": principal, "termo_de_referencia": False}
checa(sv.aviso_sem_documento_principal([]) is None and sv.aviso_sem_documento_principal(None) is None, "lista vazia ou None: sem aviso (o PNCP não respondeu; não é conclusão)")
a1 = sv.aviso_sem_documento_principal([D("Decisão", "Decisão")])
checa(a1 is not None and a1.startswith("Esta compra não tem TR, edital, ETP, DFD nem aviso na lista do PNCP; provavelmente contratação direta."), f"só 'Decisão': aviso '{(a1 or '')[:70]}…'")
checa(sv.aviso_sem_documento_principal([D("Decisão", "Decisão"), D("Proposta", "Proposta")]) is not None, "2 arquivos, nenhum principal: aviso")
checa(sv.aviso_sem_documento_principal([D("Decisão", "Decisão"), D("TR", "Termo de Referencia", True)]) is None, "com um principal (TR): sem aviso")
checa(sv.aviso_sem_documento_principal([D("Edital", "Edital", True)]) is None, "só o edital (principal): sem aviso")

print("\n=== Item 5 (tela, Produto) ===")
ESTADO.update(lista=[arq(1, "Decisão – Ato que autoriza a Contratação Direta", "Decisão")], status_lista=200)
at = busca(); n0 = len(CHAMADAS)
checa(not avisos_sem_tr(at), "antes de clicar em 'Listar': nenhum aviso")
botao(at, BTN_LISTAR).click().run(); assert not at.exception, [e.value for e in at.exception]; nov = CHAMADAS[n0:]
av = avisos_sem_tr(at)
checa(len(av) == 1, f"compra só com 'Decisão': 1 aviso de contratação direta na tela (avisos: {len(av)})")
checa(len(nov) == 1 and nov[0].endswith("/arquivos") and not any("/arquivos/" in u for u in nov), f"o aviso sai da MESMA consulta da lista ({len(nov)} requisição) e nada foi baixado")
fonte = (RAIZ / "app.py").read_text(encoding="utf-8")
checa(fonte.index("sv.aviso_sem_documento_principal(lt[") < fonte.index('clicou_dl = st.button("Baixar documentos da linha")'), "no código, o aviso é mostrado ANTES do botão 'Baixar documentos da linha'")
ESTADO.update(lista=[arq(1, "Decisão", "Decisão"), arq(2, "Proposta da empresa", "Proposta")], status_lista=200)
at = busca(); botao(at, BTN_LISTAR).click().run()
checa(len(avisos_sem_tr(at)) == 1, "Decisão + Proposta (nenhum principal): 1 aviso")
ESTADO.update(lista=[arq(1, "Decisão", "Decisão"), arq(2, "Termo de Referência", "Termo de Referencia")], status_lista=200)
at = busca(); botao(at, BTN_LISTAR).click().run()
checa(len(avisos_sem_tr(at)) == 0, "com TR na lista: sem aviso (caso sem aviso)")
ESTADO.update(lista=[arq(1, "Edital de licitação", "Edital")], status_lista=200)
at = busca(); botao(at, BTN_LISTAR).click().run()
checa(len(avisos_sem_tr(at)) == 0, "só o edital: sem aviso")
ESTADO.update(lista=[arq(1, "Decisão", "Decisão"), arq(2, "TR antigo", "Termo de Referencia", ativo=False)], status_lista=200)
at = busca(); botao(at, BTN_LISTAR).click().run()
checa(len(avisos_sem_tr(at)) == 1, "o único TR está inativo (não conta): aviso")
ESTADO.update(lista=[], status_lista=503)
at = busca(); botao(at, BTN_LISTAR).click().run()
checa(len(avisos_sem_tr(at)) == 0 and any("O PNCP não devolveu a lista de documentos desta compra" in str(w.value) for w in at.warning), "lista que não veio (HTTP 503): só o aviso de antes, sem 'contratação direta' (falha de rede não vira conclusão)")

print("\n=== Item 6: alerta 'compatível: outro objeto' ===")
PAGS = ["Termo de Referência 2025. Garantia de 180 dias contra defeitos de fabricação. Prazo de entrega: 30 dias.", "Marca XPTO modelo Z. Tela de 15,6 polegadas. Assinado em 10/03/2025."]
CAB = "| Campo | Valor | Página | Trecho literal |\n|---|---|---|---|\n"
BASE = {"tipo de documento": ("TR", "1", "Termo de Referência"), "ano do documento": ("2025", "2", "Assinado em 10/03/2025"), "lei de base": ("não encontrado", "", ""),
        "atributo do item": ("15,6 polegadas", "2", "Tela de 15,6 polegadas"), "compatível": ("mesmo", "", ""), "garantia": ("6 (180 dias)", "1", "Garantia de 180 dias contra defeitos"),
        "prazo de entrega": ("30", "1", "Prazo de entrega: 30 dias"), "marca ou modelo": ("XPTO", "2", "Marca XPTO modelo Z"), "utilidade": ("alta", "", "serve de modelo porque traz a garantia")}
NOMES = {"tipo de documento": "tipo de documento (TR / edital)", "ano do documento": "ano do documento", "lei de base": "lei de base (14.133 / 8.666 / não encontrado)",
         "atributo do item": "atributo do item, copiado como está", "compatível": "compatível com o item pedido? (mesmo / próximo / diferente / o documento não trata do item)", "garantia": "garantia do produto (meses)",
         "prazo de entrega": "prazo de entrega (dias)", "marca ou modelo": "marca ou modelo indicado", "utilidade": "utilidade como modelo de TR"}
def ficha(**troca):
    d = {k: list(v) for k, v in BASE.items()}
    for k, v in troca.items(): d[k.replace("_", " ").replace("compativel", "compatível")] = list(v) if isinstance(v, tuple) else v
    return CAB + "\n".join(v if isinstance(v, str) else f"| {NOMES[k]} | {v[0]} | {v[1]} | {v[2]} |" for k, v in d.items()) + "\n"
COMP = "compatível: outro objeto"
def tipos(al): return sorted((a["campo"], a["alerta"]) for a in al)
for valor in ("diferente", "Diferente", "diferente (outro modelo de equipamento)", "o documento não trata do item", "O documento não trata do item", "DIFERENTE (outro objeto)", "o documento nao trata do item"):
    al = cf.alertas_revisar(ficha(compativel=(valor, "", "")))
    checa(tipos(al) == [("compatível", COMP)], f"compatível = '{valor}': 1 alerta, campo 'compatível' ({tipos(al)})")
for valor in ("mesmo", "próximo", "Próximo", "não encontrado", "", "mesmo (diferente do ano)"):
    al = cf.alertas_revisar(ficha(compativel=(valor, "", "")))
    checa(al == [], f"compatível = '{valor}': sem alerta")
al = cf.alertas_revisar(ficha(compativel=("diferente", "", "")))
checa("atributo, garantia, prazo" in al[0]["detalhe"] and ct.frase_alerta(al[0]).startswith("Revisar · compatível: o campo compatível é \"diferente\""), f"frase na tela: '{ct.frase_alerta(al[0])[:100]}…' (mesmo formato 'Revisar · campo: detalhe')")

print("\n=== os alertas de antes continuam iguais ===")
linha_ruim = "| atributo do item, copiado como está | tela | tipo de licença | 2 | Tela de 15,6 polegadas |"
CASOS = [("ficha correta", {}, "", []),
         ("lei de base: não encontrado com trecho", {"lei_de_base": ("não encontrado", "1", "Termo de Referência 2025")}, "", [("lei de base", "valor não encontrado com trecho")]),
         ("prazo: não encontrado com trecho", {"prazo_de_entrega": ("não encontrado", "1", "Prazo de entrega: 30 dias")}, "", [("prazo de entrega", "valor não encontrado com trecho")]),
         ("ano com 2 números", {"ano_do_documento": ("2025 (atualizado em 2026)", "2", "Assinado em 10/03/2025")}, "", [("ano do documento", "ano com mais de um número")]),
         ("garantia em dias", {"garantia": ("180", "1", "Garantia de 180 dias contra defeitos")}, "", [("garantia", "garantia: trecho em dias")]),
         ("garantia convertida", {"garantia": ("6 (180 dias)", "1", "Garantia de 180 dias contra defeitos")}, "", []),
         ("5 colunas", {"atributo_do_item": linha_ruim}, "", [("atributo do item", "linha com mais de 4 colunas")]),
         ("atributo igual ao item", {"atributo_do_item": ("notebook", "2", "x")}, "notebook", [("atributo do item", "atributo igual ao item pedido")])]
for rot, troca, item, esperado in CASOS:
    sem = cf.alertas_revisar(ficha(**troca), item); com = cf.alertas_revisar(ficha(compativel=("próximo", "", ""), **troca), item); comp = cf.alertas_revisar(ficha(compativel=("diferente", "", ""), **troca), item)
    checa(tipos(sem) == sorted(esperado) and tipos(com) == sorted(esperado) and tipos(comp) == sorted(esperado + [("compatível", COMP)]),
          f"{rot}: alertas de antes {len(esperado)} (iguais com compatível 'próximo'); com 'diferente' ficam esses + 1 de compatível")
res = ct.conferir_resposta(ficha(compativel=("diferente", "", "")), PAGS, "", "notebook", "", "32768")
r_antes = cf.resumo(cf.conferir(ficha(compativel=("diferente", "", "")), PAGS, "notebook", ""))
checa(res["resumo"] == r_antes and [a["alerta"] for a in res["alertas"]] == [COMP], f"conferir_resposta devolve o alerta e a contagem de citações literais não muda ({r_antes['literais']} de {r_antes['citacoes']})")
res = ct.conferir_resposta("lixo", PAGS, "", "notebook", "", "32768")
checa(res["alertas"] == [], "resposta sem ficha: alertas = []")

print("\n=== Item 6 (tela, Etapa 5) ===")
ESTADO.update(lista=[], status_lista=200)
def tela5(compat):
    at = busca()
    sess = f.PASTA / "saida" / "sessoes" / at.session_state["sessao_id"] / "recortes" / "R1"; sess.mkdir(parents=True)
    (sess / "recorte.txt").write_text("DOCUMENTO x | item pedido: windows 11 | 2 páginas no original | páginas incluídas: 1\n[pág. 1]\n" + PAGS[0] + "\n", encoding="utf-8")
    (sess / "paginas.json").write_text(json.dumps(PAGS, ensure_ascii=False), encoding="utf-8"); at.run()
    at.text_area(key="ficha_resposta").set_value(ficha(compativel=(compat, "", ""))).run(); botao(at, "Conferir ficha").click().run()
    assert not at.exception, [e.value for e in at.exception]; return at
for compat, n in (("diferente", 1), ("o documento não trata do item", 1), ("mesmo", 0), ("próximo", 0)):
    at = tela5(compat); rev = [w.value for w in at.warning if str(w.value).startswith("Revisar · compatível:")]
    checa(len(rev) == n, f"tela: compatível = '{compat}': {len(rev)} aviso(s) 'Revisar · compatível' (esperado {n}); outros 'Revisar ·': {len([w for w in at.warning if str(w.value).startswith('Revisar ·')]) - len(rev)}")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

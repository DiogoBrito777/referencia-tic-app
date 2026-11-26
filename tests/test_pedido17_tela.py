"""v4h, Pedido 17 – TELA (AppTest), SEM rede (socket bloqueado, rede SIMULADA que devolve as linhas REAIS já medidas em pedido12b\\servicos_precos_todas.csv).
Cobre: legenda do 'Item pedido' (dois modos); barra 'Concluída com falhas' (PDF sem texto); filtro por palavra na Etapa 2 (sem chamada nova à API,
resumo por código com 2+ códigos, aviso das linhas sem ligação ao PNCP, escolher linha filtrada); 'Marcar todos' (máximo 6) nas tabelas de sugestão e de códigos do catálogo, nos dois modos;
aviso 'N códigos × cerca de 12 chamadas' antes do Buscar; Produto e Serviço com os mesmos botões e textos. O AppTest não mede o desenho no navegador.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido17_tela.py   (na pasta do app)"""
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
TMP = DADOS / "pedido17" / f"_tmp_teste_{int(time.time())}"; TMP.mkdir(parents=True); f.PASTA = TMP / "sessao"; f.PASTA.mkdir()
HOJE = dt.date.today().isoformat(); CHAMADAS = []; ESTADO = {"ligar": False}
REAIS = list(csv.DictReader((DADOS / "pedido12b" / "servicos_precos_todas.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "Termo de Referencia", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]
def monta_pdf(paginas):
    """paginas: lista de None (página só com uma imagem, sem texto) ou str (texto)."""
    n = len(paginas); ids = [5 + 2 * i for i in range(n)]; corpo = {1: b"<< /Type /Catalog /Pages 2 0 R >>"}
    corpo[2] = ("<< /Type /Pages /Kids [" + " ".join(f"{i} 0 R" for i in ids) + f"] /Count {n} >>").encode()
    corpo[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    corpo[4] = b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 4 >>\nstream\n" + bytes([0, 255, 255, 0]) + b"\nendstream"
    for i, t in enumerate(paginas):
        pid, cid = ids[i], ids[i] + 1
        corpo[pid] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents {cid} 0 R /Resources << /Font << /F1 3 0 R >> /XObject << /Im0 4 0 R >> >> >>".encode()
        cont = b"q 300 0 0 300 0 0 cm /Im0 Do Q" if t is None else ("BT /F1 12 Tf 10 150 Td (" + t + ") Tj ET").encode("latin-1")
        corpo[cid] = b"<< /Length %d >>\nstream\n" % len(cont) + cont + b"\nendstream"
    out = b"%PDF-1.4\n"; offs = {}
    for k in sorted(corpo): offs[k] = len(out); out += f"{k} 0 obj\n".encode() + corpo[k] + b"\nendobj\n"
    tot = max(corpo) + 1
    out += (f"xref\n0 {tot}\n").encode() + b"0000000000 65535 f \n" + b"".join(f"{offs[k]:010d} 00000 n \n".encode() for k in range(1, tot))
    out += f"trailer\n<< /Size {tot} /Root 1 0 R >>\nstartxref\n0\n%%EOF\n".encode()    # o 0 é trocado pela posição real em monta_pdf_ok
    return out
def monta_pdf_ok(paginas):
    """Monta o PDF e corrige o startxref com a posição real da tabela xref."""
    b = monta_pdf(paginas); pos = b.rindex(b"xref\n0 "); return re.sub(rb"startxref\n\d+\n", b"startxref\n%d\n" % pos, b)
PDF_SEM_TEXTO = monta_pdf_ok([None, None, None])      # PDF só de imagem (3 páginas), igual ao do 13K
DESC_PROD = ["SOFTWARE LICENCA Windows 11 Pro", "SOFTWARE LICENCA antivirus", "Licença XDR endpoint", "SOFTWARE LICENCA Office", "LICENÇA windows 11 PRO perpétua", "SOFTWARE LICENCA SIMULADA", "SOFTWARE LICENCA SIMULADA", "SOFTWARE LICENCA SIMULADA", "SOFTWARE LICENCA SIMULADA", "SOFTWARE LICENCA SIMULADA"]
def get(url, params=None, binario=False):
    params = params or {}; CHAMADAS.append((url, dict(params)))
    if "3_consultarServico" in url:
        cod = str(params.get("codigoItemCatalogo"))
        rs = [r for r in REAIS if r["codigo"] == cod]
        lote = [{"idCompra": f"{r['orgao_id']}{i:05d}", "numeroItemCompra": i + 1, "descricaoItem": r["descricao"], "codigoItemCatalogo": int(cod), "siglaUnidadeMedida": r["unidade"] or "UN", "quantidade": float(r["quantidade"] or 1),
                 "precoUnitario": float(r["valor"]), "nomeOrgao": f"ORGAO {r['orgao_id']}", "estado": r["uf"], "dataCompra": HOJE, "dataResultado": HOJE} for i, r in enumerate(rs)]
        return 200, {"totalRegistros": len(lote), "paginasRestantes": 0, "resultado": lote}, {}
    if "1_consultarMaterial" in url:
        lote = [{"idCompra": f"9{i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO {i}", "estado": "DF", "descricaoItem": DESC_PROD[i], "numeroItemCompra": i + 1,
                 "nomePdm": "SOFTWARE", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(10)]
        return 200, {"totalRegistros": 10, "resultado": lote, "paginasRestantes": 0}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url: return 200, {"resultado": [REG] if ESTADO["ligar"] else []}, {}
    if url.endswith("/arquivos"): return 200, LISTA, {}
    if re.search(r"/arquivos/(\d+)$", url): return 200, PDF_SEM_TEXTO, {}
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
LEG = "Confira se estas palavras descrevem só o item que você quer; apague o que for de outra coisa, ou digite as opções separadas por |."
FILTRO = "Mostrar só linhas que citam a palavra"

def serv_busca(codigos="27456, 27464, 27499"):
    at = novo("Serviço"); at.text_input(key="serv_codigo_av").set_value(codigos).run()
    botao(at, "Buscar compras do serviço").click().run(); assert not at.exception, [e.value for e in at.exception]; return at
def prod_busca():
    ESTADO["ligar"] = False      # sem ligação ao PNCP na busca do produto (a ligação foi ligada de propósito no teste do serviço)
    cat =f.ler_catalogo_pdm(); pdm = next(str(r["codigoPdm"]) for r in cat if norm(r["nomePdm"]).strip() == "software" and str(r["statusPdm"]).strip().lower() == "true")
    at = novo("Produto"); at.text_input(key="termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
    at.session_state[f"tab_sug_pdm_{zlib.crc32(norm('windows 11').encode('utf-8'))}"] = {"edited_rows": {0: {"usar": True}}, "added_rows": [], "deleted_rows": []}; at.run()
    botao(at, "Buscar").click().run(); assert not at.exception, [e.value for e in at.exception]; return at
def tab_resultados(at): return next(d.value for d in at.dataframe if "descricao_item" in d.value.columns)
def tab_resumo(at): return [d.value for d in at.dataframe if "linhas que citam" in d.value.columns]

print("=== Serviço: busca de 3 códigos (rede simulada com as linhas reais do 12B) ===")
CHAMADAS.clear(); at_s = serv_busca()
n_api = len(CHAMADAS)
esperadas = sum(1 for r in REAIS if r["codigo"] in ("27456", "27464", "27499"))
tab0 = tab_resultados(at_s)
checa(len(tab0) == esperadas, f"a tabela traz as {esperadas} linhas dos 3 códigos (tabela: {len(tab0)})")
checa(any(i.label == FILTRO for i in at_s.text_input), f"campo '{FILTRO}' acima da tabela (Serviço)")
rs0 = tab_resumo(at_s)
checa(len(rs0) == 1 and list(rs0[0].columns) == ["código", "nome", "linhas lidas", "linhas que citam", "compras distintas", "órgãos distintos"] and len(rs0[0]) == 3,
      f"resumo por código com 3 códigos: colunas {list(rs0[0].columns) if rs0 else None}, {len(rs0[0]) if rs0 else 0} linhas")
checa(list(tab0["indicador_descricao"].unique()) and set(tab0["indicador_descricao"]) <= {"descrição curta", "descrição detalhada"}, f"coluna 'descrição' (indicador) na tabela: {dict(tab0['indicador_descricao'].value_counts())}")
checa(any("só conta palavras; não lê o edital" in c.value and "Regra provisória: a equipe valida" in c.value for c in at_s.caption), "a tela diz: só conta palavras; não lê o edital (regra provisória)")

print("\n=== Serviço: filtro por palavra ===")
esp_w = sv.linhas_que_citam([{"descricao_item": r["descricao"]} for r in REAIS if r["codigo"] in ("27456", "27464", "27499")], "windows 11 pro")
at_s.text_input(key="filtro_palavra").set_value("windows 11 pro").run()
tw = tab_resultados(at_s)
checa(not at_s.exception and len(tw) == len(esp_w) > 0, f"'windows 11 pro' mostra {len(tw)} linhas (esperado pela função: {len(esp_w)})")
checa(len(CHAMADAS) == n_api, f"filtrar não fez nenhuma chamada nova à API ({len(CHAMADAS)} = {n_api})")
checa(all(set(sv.palavras_de_busca("windows 11 pro")) <= set(sv.palavras_de_busca(d)) for d in tw["descricao_item"]), "toda linha mostrada cita as 3 palavras")
rs1 = tab_resumo(at_s)[0]
checa(int(rs1["linhas que citam"].sum()) == len(esp_w) and list(rs1["linhas que citam"]) == sorted(rs1["linhas que citam"], reverse=True), f"resumo por código ordenado por 'linhas que citam': {list(zip(rs1['código'], rs1['linhas que citam']))}")
nv = int(tw["compra_item"].astype(str).str.contains("não verificado").sum())
aviso_nv = [w.value for w in at_s.warning if "não têm ligação ao PNCP" in w.value]
checa((nv > 0) == bool(aviso_nv) and (not aviso_nv or ("modo completo liga mais" in aviso_nv[0] and str(nv) in aviso_nv[0])), f"aviso das linhas sem ligação ao PNCP: {nv} linhas 'não verificado' -> {'aviso: ' + aviso_nv[0][:90] if aviso_nv else 'sem aviso'}")
sel = next(s_ for s_ in at_s.selectbox if s_.label == "Linha" and s_.key != "canal_linha")
checa(len(sel.options) == len(tw), f"escolher linha: a lista da Etapa 3 só tem as {len(tw)} linhas filtradas")
at_s.text_input(key="filtro_palavra").set_value("zzzxyzqq").run()
checa(any("Nenhuma das" in w.value and "cita" in w.value for w in at_s.warning) and len(tab_resultados(at_s)) == esperadas and not at_s.exception, "palavra inexistente: aviso e a tabela volta a mostrar todas as linhas")
at_s.text_input(key="filtro_palavra").set_value("XDR").run()
checa(len(tab_resultados(at_s)) == 1 and not at_s.exception, f"'XDR' (maiúscula) nos 3 códigos: {len(tab_resultados(at_s))} linha (a do 27456)")
at_s.text_input(key="filtro_palavra").set_value("LICENCA").run()
checa(len(tab_resultados(at_s)) == len(sv.linhas_que_citam([{"descricao_item": r["descricao"]} for r in REAIS if r["codigo"] in ("27456", "27464", "27499")], "licença")), "acento e maiúscula: 'LICENCA' acha o mesmo que 'licença'")

print("\n=== Serviço: legenda e barra 'Concluída com falhas' ===")
at_s.text_input(key="filtro_palavra").set_value("").run()
ESTADO["ligar"] = True; botao(at_s, "Baixar documentos da linha").click().run()
pdf_sel = [s_ for s_ in at_s.selectbox if s_.label.startswith("Documento para recortar")]
checa(not at_s.exception and bool(pdf_sel), "documentos baixados (PDF só de lixo, sem texto) e seletor de documento na tela")
item_s = next(t for t in at_s.text_input if t.label.startswith("Item pedido"))
checa(LEG in [c.value for c in at_s.caption], "legenda fixa embaixo do campo 'Item pedido' (Serviço)")
botao(at_s, "Gerar texto para IA").click().run()
pn = at_s.session_state["painel_e3_recorte"]
checa(pn["texto"].startswith("Concluída com falhas em") and pn["barras"][0][2] == "Concluída com falhas" and "100%" not in pn["barras"][0][2], f"barra: '{pn['barras'][0][2]}' | frase: '{pn['texto'][:60]}'")
at_s2 = serv_busca("27499"); pb = at_s2.session_state["painel_e2_buscar"]
checa(all("100%" in b[2] or "Concluída" in b[2] for b in pb["barras"]) and pb["texto"].startswith("Concluída em"), f"sem falha na busca, a barra continua 'Concluída · 100%': {[b[2] for b in pb['barras']]}")

print("\n=== Produto: mesmo campo, resumo, legenda e filtro (dados simulados do material) ===")
CHAMADAS.clear(); at_p = prod_busca(); n_api_p = len(CHAMADAS)
checa(any(i.label == FILTRO for i in at_p.text_input), f"campo '{FILTRO}' também no Produto")
at_p.text_input(key="filtro_palavra").set_value("windows 11 pro").run()
tp = tab_resultados(at_p)
checa(len(tp) == 2 and len(CHAMADAS) == n_api_p and not at_p.exception, f"Produto: 'windows 11 pro' mostra {len(tp)} linhas (simuladas: 2: 'Windows 11 Pro' e 'windows 11 PRO'), sem chamada nova")
at_p.text_input(key="filtro_palavra").set_value("xdr").run()
checa(len(tab_resultados(at_p)) == 1, "Produto: 'xdr' = 1 linha")
at_p.text_input(key="filtro_palavra").set_value("zzzxyzqq").run()
checa(any("Nenhuma das" in w.value for w in at_p.warning), "Produto: palavra inexistente avisa")
at_p.text_input(key="filtro_palavra").set_value("").run()
ESTADO["ligar"] = True; botao(at_p, "Baixar documentos da linha").click().run()
item_p = [t for t in at_p.text_input if t.label.startswith("Item pedido")]
checa(bool(item_p) and LEG in [c.value for c in at_p.caption], "legenda fixa embaixo do campo 'Item pedido' (Produto) - mesma frase do Serviço")
checa(item_s.label == item_p[0].label, "o rótulo do campo 'Item pedido' é o mesmo nos dois modos")
bs, bp = sorted(b.label for b in at_s.button), sorted(b.label for b in at_p.button)
comuns = ["Baixar documentos da linha", "Gerar texto para IA", "Atualizar catálogo"]
checa(all(c in bs and c in bp for c in comuns), f"botões comuns nos dois modos: {comuns}")

print("\n=== 'Marcar todos' (máximo 6) ===")
def marcados(at): return next((t for t in textos(at).splitlines() if t.startswith("Códigos marcados:")), "")
at = novo("Serviço"); at.text_input(key="serv_termo").set_value("manutenção").run(); botao(at, "Procurar no catálogo").click().run()
n_serv = len(next(d.value for d in at.dataframe if "usar" in d.value.columns))
botao(at, "Marcar todos").click().run()
m = marcados(at)
checa(not at.exception and n_serv > 6 and len(m.split(": ")[1].split(", ")) == 6, f"Serviço, tabela do catálogo ({n_serv} linhas): 'Marcar todos' marca 6 -> '{m}'")
checa(any("marquei só as 6 primeiras" in c.value for c in at.caption), "avisa que marcou só as 6 primeiras")
checa(sv.estimativa_busca(6) in [c.value for c in at.caption], f"antes do Buscar: '{sv.estimativa_busca(6)}'")
at = novo("Produto"); at.text_input(key="termo").set_value("cadeira").run(); botao(at, "Procurar no catálogo").click().run()
n_prod = len(next(d.value for d in at.dataframe if "usar" in d.value.columns))
botao(at, "Marcar todos").click().run()
m = marcados(at)
checa(not at.exception and n_prod > 6 and len(m.split(": ")[1].split(", ")) == 6, f"Produto, tabela do catálogo ({n_prod} linhas): 'Marcar todos' marca 6 -> '{m}'")
MODOS_P18 = {"rápido": {"MAX_PAGINAS_CATALOGO": 3, "MAX_VINCULOS": 10}, "completo": {"MAX_PAGINAS_CATALOGO": f.MAX_PAGINAS_CATALOGO, "MAX_VINCULOS": f.MAX_VINCULOS}}      # Pedido 20: o Produto passou a ter o aviso de custo próprio (Pedido 18, Fase 3)
checa(any("marquei só as 6 primeiras" in c.value for c in at.caption) and sv.aviso_custo_produto(6, MODOS_P18) in [c.value for c in at.caption], "Produto: o mesmo aviso de 'Marcar todos' e o aviso de custo do Produto (aviso_custo_produto, Pedido 18) antes do Buscar")
at = novo("Serviço"); at.text_input(key="serv_termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
n_sug = len(next(d.value for d in at.dataframe if "usar" in d.value.columns)); botao(at, "Marcar todos").click().run()
checa(not at.exception and len(marcados(at).split(": ")[1].split(", ")) == min(6, n_sug), f"Serviço, tabela de sugestões ({n_sug} linhas): 'Marcar todos' marca {min(6, n_sug)}")
at = novo("Produto"); at.text_input(key="termo").set_value("windows 11").run(); botao(at, "Procurar no catálogo").click().run()
botao(at, "Marcar todos").click().run()
checa(not at.exception and len(marcados(at).split(": ")[1].split(", ")) == 1, f"Produto, tabela de sugestão (1 linha): 'Marcar todos' marca 1 -> '{marcados(at)}'")

print("\n=== aviso de custo com 2+ códigos (digitados), Serviço ===")
at = novo("Serviço"); at.text_input(key="serv_codigo_av").set_value("27456, 27464").run()
checa(sv.estimativa_busca(2) in [c.value for c in at.caption], f"2 códigos: '{sv.estimativa_busca(2)}'")
at = novo("Serviço"); at.text_input(key="serv_codigo_av").set_value("27456").run()
checa(not [c.value for c in at.caption if "códigos × cerca de" in c.value], "com 1 código o aviso não aparece")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

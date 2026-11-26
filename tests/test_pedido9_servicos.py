"""v4h, Pedido 9 – serviço (funções) e CSV com versão, OFFLINE: socket bloqueado, rede trocada por respostas SIMULADAS (dados simulados só aqui;
tudo que depende da API real fica 'NÃO TESTADO COM REDE'). Nenhum GET real: ferramenta.get é substituída e qualquer URL fora da lista simulada derruba o teste.
Cobre: catálogo local (3.108 serviços, data do download), procura por palavra, preço suspeito (marca, não apaga, sem média/mediana), canal oficial (3 campos),
busca por código de serviço com ligação ao PNCP (idCompra de 16 dígitos vira 17), lista de TR por compra e o CONTEÚDO do CSV (colunas AO FINAL).
Uso (na pasta do app): ..\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido9_servicos.py"""
import csv, io, json, socket, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
def _sem_rede(self, *a, **k): raise AssertionError("TENTOU ABRIR REDE")
socket.socket.connect = _sem_rede
import ferramenta as f
import servicos as sv

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

print("=== S1. catálogo de serviços local ===")
cat = sv.ler_catalogo()
ativos = [r for r in cat if r["statusServico"] == "True"]
checa(len(cat) == 3108, f"catálogo tem {len(cat)} serviços (esperado 3.108, o baixado em 17/11/2026; registro\\F2_estado_download.json)")
checa(sv.data_do_catalogo(cat) == max(r["baixado_em"] for r in cat if r.get("baixado_em"))[:10], f"data do download no catálogo: {sv.data_do_catalogo(cat)!r} (a mais nova da coluna baixado_em, lida do próprio arquivo: o botão Atualizar catálogo pode renová-la)")
checa(list(cat[0])[-1] == "baixado_em" and list(cat[0])[:3] == ["codigoSecao", "nomeSecao", "codigoDivisao"], "colunas originais mantidas e 'baixado_em' no fim")
a = sv.procurar("instalação elétrica", cat); codigos = [r["codigoServico"] for r in a]
checa("5606" in codigos and all(r["statusServico"] == "True" for r in a), f"'instalação elétrica' acha o código 5606 e só serviços ativos ({codigos[:5]})")
checa("5606" in [r["codigoServico"] for r in sv.procurar("instalacoes eletricas", cat)], "plural e sem acento ainda acham o 5606 ('instalacoes eletricas')")
checa(sv.procurar("zzzxxx", cat) == [] and sv.procurar("", cat) == [], "palavra inexistente ou vazia: lista vazia (sem erro)")
checa(sv.palavras_do_recorte(["INSTALACAO / MANUTENCAO ELETRICA - PREDIAL, INDUSTRIAL"]) == "instalacao|manutencao|eletrica|predial|industrial", "palavras do recorte: sem as fracas, separadas por '|'")

print("\n=== S2. preço suspeito: marca, nunca apaga, sem média/mediana ===")
def mk(precos, un="UN"): return [{"preco_unitario_homologado": p, "unidade": un, "observacao_preco": ""} for p in precos]
L = mk([100, 110, 120, 130, 125, 115, 90000, 1.0]); n_susp = sv.marcar_suspeitos(L)
checa([l["preco_unitario_homologado"] for l in L if l["observacao_preco"] == "suspeito"] == [90000, 1.0] and len(L) == 8 and n_susp == 2, f"90.000 e 1,00 marcados 'suspeito' nas duas pontas; as 8 linhas continuam ({n_susp} marcadas)")
L = mk([100, 110, 5000, 5100]); checa(sv.marcar_suspeitos(L) == 0, "dois grupos de 2 preços (100 e 5.000): ninguém é marcado (não há ponta isolada)")
L = mk([100, 110, 120]); checa(sv.marcar_suspeitos(L) == 0, "menos de 4 preços: ninguém é marcado")
L = mk([0, 100, 110, 120]); sv.marcar_suspeitos(L); checa(L[0]["observacao_preco"] == "suspeito", "preço zero é marcado")
L = mk([100, 110, 120, 130], "UN") + mk([50000, 51000, 52000, 53000], "MES"); checa(sv.marcar_suspeitos(L) == 0, "unidades diferentes não se misturam (100 'UN' x 50.000 'MES': nenhum suspeito)")
fonte = Path(RAIZ / "servicos.py").read_text(encoding="utf-8")
checa("statistics" not in fonte and "median" not in fonte.lower().replace("mediana", "") and "mean(" not in fonte, "servicos.py não importa statistics nem calcula média/mediana")

print("\n=== S3. preço do site oficial do fornecedor (digitado; nunca raspado) ===")
r0 = sv.comparar_canal_oficial(1000, "", "", ""); checa(not r0["preenchido"] and r0["rotulo"] == "" and not r0["avisos"], "sem o campo: nenhum rótulo e nenhum aviso")
r1 = sv.comparar_canal_oficial(1000, "1.250,00", "", "20/11/2026 14:30"); checa(not r1["preenchido"] and r1["rotulo"] == "" and any("link" in x for x in r1["avisos"]), f"sem link: não rotula e pede o link ({r1['avisos']})")
r2 = sv.comparar_canal_oficial(1000, "1.250,00", "https://exemplo.invalido/preco", ""); checa(not r2["preenchido"] and any("data e a hora" in x for x in r2["avisos"]), "sem data/hora: não rotula e pede")
r3 = sv.comparar_canal_oficial(1000, "1.250,00", "https://exemplo.invalido/preco", "20/11/2026 14:30")
checa(r3["preenchido"] and r3["rotulo"] == "abaixo do canal oficial" and abs(r3["diferenca"] - (-0.2)) < 1e-9 and "20/11/2026 14:30" in r3["texto"] and "https://exemplo.invalido/preco" in r3["texto"], f"pago 1.000 x oficial 1.250: 'abaixo do canal oficial' (-20%), com link e data/hora: {r3['texto']}")
r4 = sv.comparar_canal_oficial(1500, "1250.00", "http://x.y", "hoje 10h"); checa(r4["rotulo"] == "acima do canal oficial", "pago acima do oficial: 'acima do canal oficial' (o rótulo 'abaixo' só vale quando está abaixo)")
checa(sv.comparar_canal_oficial(1000, "abc", "http://x.y", "hoje")["avisos"] != [], "preço inválido: aviso, sem rótulo")

print("\n=== S4. busca por código de serviço, ligação ao PNCP e CSV (respostas SIMULADAS) ===")
TESTE = DADOS / "pedido9" / f"teste_servicos_{int(time.time())}"; (TESTE / "documentos").mkdir(parents=True)
f.SAIDA = TESTE; f.LOG = TESTE / "log_requisicoes.jsonl"
HOJE = time.strftime("%Y-%m-%d")
PRECOS = [1000.0, 1100.0, 1200.0, 1300.0, 1150.0, 1250.0, 90000.0, 1.0]
IDS = ["9251580600119202" if i < 3 else f"{92515806001192025 + i}" for i in range(8)]       # os 3 primeiros com 16 dígitos (zero à esquerda perdido)
ESTADO = {"chamadas": [], "ligar": [], "inesperadas": []}
REG = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
def get(url, params=None, binario=False):
    params = params or {}; ESTADO["chamadas"].append(url); f.contar("chamadas")
    if "3_consultarServico" in url:
        lote = [{"idCompra": IDS[i], "numeroItemCompra": i + 1, "descricaoItem": f"SERVICO SIMULADO {i}", "codigoItemCatalogo": 5606, "siglaUnidadeMedida": "UN", "nomeUnidadeMedida": "UNIDADE",
                 "quantidade": float(i + 1), "precoUnitario": PRECOS[i], "nomeOrgao": f"ORGAO SIMULADO {i}", "estado": "DF", "dataCompra": HOJE, "dataResultado": HOJE} for i in range(8)]
        return 200, {"totalRegistros": 8, "totalPaginas": 1, "paginasRestantes": 0, "resultado": lote}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        ESTADO["ligar"].append(params["codigo"])
        return 200, {"resultado": [REG] if params["codigo"].endswith(("2", "9")) else []}, {}
    if url.endswith("/arquivos"):
        return 200, [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1, "statusAtivo": True},
                     {"titulo": "TR assinado", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2, "statusAtivo": True},
                     {"titulo": "Proposta da empresa", "tipoDocumentoNome": "Proposta", "sequencialDocumento": 3, "statusAtivo": True},
                     {"titulo": "Edital antigo", "tipoDocumentoNome": "Edital", "sequencialDocumento": 4, "statusAtivo": False}], {}
    ESTADO["inesperadas"].append(url); raise AssertionError(f"URL inesperada: {url}")
f.get = get
f.MODO_ATUAL = "completo"
resumo = sv.buscar_servicos(["5606"], "")
f.MODO_ATUAL = ""
chamadas_3 = [u for u in ESTADO["chamadas"] if "3_consultarServico" in u]
checa(len(chamadas_3) == 1 and not ESTADO["inesperadas"], f"1 página de preço de serviço pedida; nenhuma URL fora da lista simulada ({len(ESTADO['chamadas'])} chamadas simuladas)")
checa(ESTADO["ligar"] and all(len(c) == 17 and c.isdigit() for c in ESTADO["ligar"]), f"ligação ao PNCP: todos os idCompra consultados têm 17 dígitos (zfill): {ESTADO['ligar'][:3]}")
checa(any(c.startswith("0") for c in ESTADO["ligar"][:3]), "os 3 idCompra de 16 dígitos ganharam zero à esquerda")
linhas = list(csv.DictReader((TESTE / Path(resumo["arquivo"]).name).open(encoding="utf-8-sig", newline=""), delimiter=";")) if Path(resumo["arquivo"]).exists() else []
cab = list(linhas[0]) if linhas else []
checa(len(linhas) == 8, f"CSV com as 8 linhas (nenhuma apagada, nem a de 90.000 nem a de 1,00): {len(linhas)}")
checa(cab[-6:] == ["versao_app", "tipo_busca", "modo", "chamadas", "falhas", "tempo_s"], f"as 6 colunas novas estão AO FINAL do CSV: {cab[-6:]}")
checa(cab[:11] == ["linha", "orgao", "uf", "data_publicacao", "data_resultado", "data_usada_no_filtro", "controle_pncp", "numero_item", "descricao_item", "preco_unitario_homologado", "atributos_atendidos"], "as colunas existentes mantêm nome e ordem")
v = linhas[0]
checa(v["versao_app"] == "v4h" and v["tipo_busca"] == "serviço" and v["modo"] == "completo", f"conteúdo: versao_app={v['versao_app']!r}, tipo_busca={v['tipo_busca']!r}, modo={v['modo']!r}")
checa(int(v["chamadas"]) == len(ESTADO["chamadas"]) and int(v["falhas"]) == 0 and v["tempo_s"].isdigit(), f"conteúdo: chamadas={v['chamadas']} (= {len(ESTADO['chamadas'])} simuladas), falhas={v['falhas']}, tempo_s={v['tempo_s']}")
checa(all(l["versao_app"] == "v4h" and l["chamadas"] == v["chamadas"] for l in linhas), "as 6 colunas têm valor em TODAS as linhas")
sus = [l for l in linhas if l["observacao_preco"] == "suspeito"]
checa(sorted(float(l["preco_unitario_homologado"]) for l in sus) == [1.0, 90000.0], f"'suspeito' marcado nas linhas de 90.000 e 1,00 e as linhas ficaram no CSV ({len(sus)} marcadas)")
checa({"unidade", "quantidade"} <= set(cab) and not any(("media" in c.lower() or "median" in c.lower() or "média" in c.lower()) for c in cab), f"colunas unidade e quantidade presentes; nenhuma coluna de média/mediana: {[c for c in cab if c in ('unidade', 'quantidade')]}")
checa(any(l["situacao_pncp"] == "vinculado" and l["link_publico"].startswith("https://pncp.gov.br/app/editais/") for l in linhas) and any(l["situacao_pncp"] == "sem PNCP" for l in linhas), "linhas 'vinculado' (com link do PNCP) e 'sem PNCP' conforme a resposta simulada")
checa(resumo.get("tipo_busca") == "serviço" and resumo.get("modo") == "completo" and resumo.get("versao_app") == "v4h", "ultima_busca.json também traz versao_app, tipo_busca e modo")
f.MODO_ATUAL = ""; sv_prod_tipo = f.TIPO_BUSCA
checa(sv_prod_tipo == "produto", "depois da busca de serviço o tipo volta a 'produto' (o caminho de produto não muda)")

print("\n=== S5. lista de TR por compra (resposta SIMULADA; NÃO TESTADO COM REDE) ===")
docs = sv.listar_documentos_compra("00000000000000", "2026", "1")
checa(len(docs) == 3 and [d["termo_de_referencia"] for d in docs] == [False, True, False] and docs[1]["principal"], f"3 documentos ativos; só o 2º é TR; o inativo some: {[(d['tipo'], d['termo_de_referencia']) for d in docs]}")
f.get = lambda *a, **k: (500, None, {}); checa(sv.listar_documentos_compra("1", "2026", "1") == [], "lista que não veio: [] (a tela explica; não afirma que não existem documentos)")

print("\n=== S6. CSV do produto (busca existente) também ganha as colunas ===")
f.TIPO_BUSCA = "produto"; f.MODO_ATUAL = "rápido"; f.STATS.clear(); f.STATS["chamadas"] = 7; f.STATS["falhas"] = 1
f.salvar_busca([{"_n": 0, "preco_unitario_homologado": 10.0, "orgao": "X"}, {"_n": 1, "preco_unitario_homologado": 5.0, "orgao": "Y"}], {}, "teste_produto", "notebook", {"entrada": "teste"}, time.time() - 12)
lp = list(csv.DictReader(next(TESTE.glob("busca_teste_produto_*.csv")).open(encoding="utf-8-sig", newline=""), delimiter=";"))
checa(list(lp[0])[-6:] == ["versao_app", "tipo_busca", "modo", "chamadas", "falhas", "tempo_s"] and lp[0]["tipo_busca"] == "produto" and lp[0]["modo"] == "rápido" and lp[0]["chamadas"] == "7" and lp[0]["falhas"] == "1" and int(lp[0]["tempo_s"]) >= 12,
      f"produto: {[ (k, lp[0][k]) for k in list(lp[0])[-6:]]}")
f.MODO_ATUAL = ""
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)

"""v4h, Pedido 13C – teste ESTRUTURAL PRODUTO x SERVIÇO (substitui o do 13B nos critérios; o 13B continua rodando). O AppTest percorre a árvore da tela e gera, para cada modo, a lista
ORDENADA de elementos da Etapa 1 (tipo, rótulo, caminho de colunas com o peso, largura pedida) em dois estados (antes e depois de procurar), incluindo a região "resultado da procura";
compara as duas listas e grava lado a lado em pedido13i\\estrutura_produto_vs_servico__<este teste>.md (pasta do pedido corrente; o argumento 1 muda a pasta; nunca grava em pasta de pedido antigo). Também confere: (1) a caixa 'Limites', o seletor e 'Nova busca' ficam na coluna central [1, 3, 1] e nenhuma
mensagem solta fica entre o cabeçalho e a Etapa 2; (2) a Etapa 2 existe com título antes e depois da busca, e as Etapas 3 e 4 têm uma linha antes da busca; (3) a mesma solução de seleção
(tabela com 'usar', sem multiselect) nos dois modos; (4) alturas das tabelas pela mesma função.
O desenho real no navegador NÃO é verificado aqui. SEM rede (socket bloqueado), rede SIMULADA, SEM Ollama.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13c_estrutura.py   (na pasta do app)"""
import difflib, re, socket, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "tests")); sys.dont_write_bytecode = True
LOOPBACK_INTERNO = []
_connect_original = socket.socket.connect
def _sem_rede(self, endereco, *a, **k):
    host, porta = (endereco[0], endereco[1]) if isinstance(endereco, tuple) else (str(endereco), None)
    if host in ("127.0.0.1", "::1") and porta != 11434:
        LOOPBACK_INTERNO.append((host, porta)); return _connect_original(self, endereco, *a, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {endereco!r}")
socket.socket.connect = _sem_rede
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from streamlit.testing.v1 import AppTest
import ferramenta as f
import servicos as sv

falhas = []
def sem_css_fora_do_visual(fonte):
    """Pedido 36: <style> e unsafe_allow_html só são aceitos dentro de aplicar_visual() e na linha do cabeçalho (ref-cabecalho); em qualquer outro lugar continuam falhando."""
    m = re.search(r"^def aplicar_visual\(\):.*?(?=^(?:def |class |if |@))", fonte, re.S | re.M)
    resto = fonte.replace(m.group(0), "") if m else fonte
    resto = "\n".join(l for l in resto.splitlines() if "ref-cabecalho" not in l)
    return m is not None and "<style" not in resto and "unsafe_allow_html" not in resto


def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

# ---- espião: largura e altura pedidas, por tipo e rótulo
LARG, ALT = {}, []
def _env(nome, orig):
    def espia(self, *a, **k):
        rot = next((x for x in a if isinstance(x, str)), "")
        LARG.setdefault((nome, rot), k.get("width"))
        if nome in ("data_editor", "dataframe"): ALT.append((nome, k.get("height")))
        return orig(self, *a, **k)
    return espia
for nome in ("text_input", "button", "radio", "selectbox", "multiselect", "checkbox", "form_submit_button", "data_editor", "dataframe"):
    setattr(DeltaGenerator, nome, _env(nome, getattr(DeltaGenerator, nome)))
def _mod(nome):
    orig = getattr(st, nome)
    def espia(*a, **k):
        rot = next((x for x in a if isinstance(x, str)), ""); LARG.setdefault((nome, rot), k.get("width"))
        if nome in ("data_editor", "dataframe"): ALT.append((nome, k.get("height")))
        return orig(*a, **k)
    setattr(st, nome, espia)
for nome in ("text_input", "button", "radio", "selectbox", "multiselect", "checkbox", "data_editor", "dataframe"): _mod(nome)

# ---- rede simulada mínima e pasta de teste
def get(url, params=None, binario=False):
    if "1_consultarMaterial" in url: return 200, {"totalRegistros": 5, "paginasRestantes": 0, "resultado": []}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": [], "totalRegistros": 0}, {}
    return 200, {"resultado": []}, {}
f.get = get
TMP = DADOS / "tmp_teste_fase4"; TMP.mkdir(exist_ok=True)
RODADA = TMP / f"p13c_{int(time.time())}"; RODADA.mkdir(); f.PASTA = RODADA

CAB = "linha;orgao;uf;data_publicacao;data_resultado;data_usada_no_filtro;controle_pncp;numero_item;descricao_item;preco_unitario_homologado;atributos_atendidos;observacao_preco;situacao_pncp;status_item_pncp;valor_estimado_pncp;link_publico;fonte_api_resultado;cnpj;ano;sequencial;id_compra;unidade;quantidade"
LIN = "1;ORGAO SIMULADO;DF;2026-11-01;2026-11-02;data do resultado;;1;ITEM SIMULADO;100.0;0 de 0;;sem PNCP;;;;;;;;123;UN;1"
def semeia(at_, tipo):
    at_.session_state["busca_atual"] = {"resumo": {"arquivo": "x.csv", "pedidos": {}}, "csv": (CAB + "\n" + LIN + "\n").encode("utf-8"), "quando": "01/01 00:00", "aceitar": False, "fim_txt": "", "log": "", "tempo": 0.0,
                                        "codigos": "0", "termo": "t", "eh_item": True, "tipo": tipo}

def rotulo_de(no):
    lab = getattr(no, "label", None)
    if isinstance(lab, str) and lab: return lab
    v = getattr(no, "value", "")
    return v if isinstance(v, str) else ""
TIPOS_TABELA = ("arrow_data_frame", "data_editor", "dataframe", "arrow_table")
from estrutura_util import etapa1_dividida, posicoes
def anda_etapa1(at):
    """Pedido 13D: A (entradas) + R (região de resultado, 'largura total') + B (entradas)."""
    d = etapa1_dividida(at, LARG)
    return d["A"] + d["R"] + d["B"], d["colunasA"]
def topo_e_resto(at):
    filhos, i_topo, iA, iB = posicoes(at)
    topo = [(cc.type, rotulo_de(cc)[:40]) for c in filhos[i_topo].children.values() for cc in c.children.values()]
    antes = [(c.type, rotulo_de(c)[:30]) for c in filhos[:iA] if c.type != "flex_container"]
    apos = []
    for c in filhos[iB + 1:]:
        if c.type == "subheader": apos.append(("subheader", rotulo_de(c)))
        elif c.type == "flex_container":
            for cc in c.children.values():
                if cc.type in ("subheader", "caption", "info"): apos.append((cc.type, rotulo_de(cc)[:70]))
    return topo, antes, apos

PAPEL = [("**Etapa 1 · Procurar no catálogo**", "painel: título"), ("Concluída em", "painel: resumo final"), ("Falhou:", "painel: resumo final"),   # Pedido 13I: painel de progresso (mesmo nos dois modos)
         ("Etapa 1 · Buscar", "título"), ("##### Procurar no catálogo", "subtítulo: procurar"), ("O que você procura?", "campo de busca"), ("Palavra do serviço", "campo de busca"),
         ("Procurar no catálogo", "BOTÃO Procurar no catálogo"), ("Catálogo oficial de materiais", "legenda do catálogo"), ("Catálogo oficial de serviços", "legenda do catálogo"),
         ("Atualizar catálogo", "BOTÃO Atualizar catálogo"), ("Testado com rede", "legenda: teste com rede"), ("Procurado:", "lista: Procurado"), ("Opção avançada", "expander: opção avançada"),
         ("Código (só números", "campo: código avançado"), ("Código do serviço", "campo: código avançado"), ("O código é", "rádio: tipo do código (só produto)"), ("##### Modo e UF", "subtítulo: modo e UF"),
         ("Regras de atributos", "ATRIBUTOS: seletor de regras (só produto)"), ("Marque um código para ver os atributos", "ATRIBUTOS: aviso (só produto)"),
         ("Modo", "rádio: Modo"), ("UF", "campo: UF"), ("Aceitar valores maiores", "ATRIBUTOS: aceitar valores maiores (só produto)"), ("Os atributos, a UF", "legenda do formulário"),
         ("O modo e a UF só valem", "legenda do formulário"), ("Buscar compras do serviço", "BOTÃO Buscar (serviço)"), ("Buscar", "BOTÃO Buscar (produto)"),
         ("Códigos marcados:", "lista: Códigos marcados"), ("Códigos marcados são", "lista: legenda dos marcados"), ("Em cinza:", "lista: legenda de desativado (só produto)"),
         ("Ver configurações (itens CATMAT)", "lista: Ver configurações (só produto)")]
def papel(el):
    r = el["rotulo"]
    if re.match(r"\d+ (serviço|código)\(s\) encontrado", r): return "lista: contagem"
    for ini, p in PAPEL:
        if r.startswith(ini): return p
    if el["tipo"] in TIPOS_TABELA: return "lista: tabela com coluna 'usar'"
    if el["tipo"] == "form": return "formulário"
    return f"{el['tipo']}: {r[:30]}"
def chave(el): return (("tabela" if el["tipo"] in TIPOS_TABELA else el["tipo"]), papel(el), el["caminho"])

def estado(modo):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
    if modo == "Serviço": at.radio(key="tipo_busca").set_value("Serviço").run()
    r = {"excecoes": [], "topo_antes": topo_e_resto(at)}
    r["antes"], r["colunas"] = anda_etapa1(at)
    if modo == "Produto": at.text_input(key="termo").set_value("notebook").run()
    else: at.text_input(key="serv_termo").set_value("instalação elétrica").run()
    r["depois"], r["colunas_depois"] = anda_etapa1(at); r["topo_depois"] = topo_e_resto(at)
    r["multiselect"] = len(at.multiselect)
    semeia(at, "serviço" if modo == "Serviço" else "produto"); at.run()
    r["topo_com_busca"] = topo_e_resto(at); r["excecoes"] = [e.value for e in at.exception]
    return r
R = {m: estado(m) for m in ("Produto", "Serviço")}
for m in R: checa(not R[m]["excecoes"], f"{m}: sem exceção ({R[m]['excecoes'][:1]})")

# ---- md lado a lado
md = ["# Etapa 1 e região 'resultado da procura': PRODUTO x SERVIÇO (estrutura, AppTest)\n", "Gerado por `tests/test_pedido13c_estrutura.py`. Cada linha: tipo · rótulo · caminho de colunas (peso) · largura pedida. Não prova o desenho no navegador.\n"]
for est, tit in (("antes", "antes de procurar"), ("depois", "depois de procurar (termo digitado + Enter)")):
    md.append(f"\n## Estado: {tit}\n"); a, b = R["Produto"][est], R["Serviço"][est]
    md.append("| # | PRODUTO | SERVIÇO |\n|---|---|---|")
    sm = difflib.SequenceMatcher(None, [chave(x) for x in a], [chave(x) for x in b], autojunk=False); n = 0
    fmt = lambda x: f"{x['tipo']} · {x['rotulo'][:46]} · {x['caminho']} · {x['largura']}"
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for k in range(max(i2 - i1, j2 - j1)):
            n += 1; xa = fmt(a[i1 + k]) if i1 + k < i2 else "—"; xb = fmt(b[j1 + k]) if j1 + k < j2 else "—"
            md.append(f"| {n}{'' if tag == 'equal' else ' ≠'} | {xa} | {xb} |")
md.append("\n## Fora da Etapa 1 (cabeçalho, topo e área de resultado)\n")
for est in ("topo_antes", "topo_com_busca"):
    md.append(f"\n### {est}\n");
    for m in R:
        topo, antes, apos = R[m][est]
        md.append(f"- **{m}** — topo (na coluna): {topo}; soltos antes da Etapa 1: {antes}; depois da Etapa 1: {apos}")

# ---- critérios
SO_PROD = {"rádio: tipo do código (só produto)", "lista: Ver configurações (só produto)", "lista: legenda de desativado (só produto)"}
def comuns(m, est):
    return [papel(x) for x in R[m][est] if x["tipo"] != "flex_container" and papel(x) not in SO_PROD and "(só produto)" not in papel(x) and not papel(x).startswith("ATRIBUTOS")
            and not (x["caminho"].startswith("largura total") and "expander" in x["caminho"])]   # Pedido 13I: o painel "Ver configurações" (só produto) fica dentro desse expander
for est in ("antes", "depois"):
    pa, pb = comuns("Produto", est), comuns("Serviço", est)
    ca = [p for p in pa if p in pb]; cb = [p for p in pb if p in pa]
    checa(ca == cb, f"[{est}] mesma ordem dos blocos em comum: {ca}")
for m in R:
    ant = R[m]["antes"]
    checa(abs(R[m]["colunas"][1][1] - 0.6) < 0.01 and abs(R[m]["colunas"][0][1] - 0.2) < 0.01 and abs(R[m]["colunas"][2][1] - 0.2) < 0.01, f"{m}: coluna central da Etapa 1 = central [1, 3, 1] ({R[m]['colunas']})")
    checa(all(x["caminho"].startswith(("col(0.60)", "largura total")) for x in ant + R[m]["depois"]), f"{m}: elementos da Etapa 1, antes e depois de procurar ({len(ant)} + {len(R[m]['depois'])}), nas colunas centrais [1, 3, 1] ou na região de resultado em largura total (Pedido 13D)")
    topo, antes, apos = R[m]["topo_antes"]
    checa([t[0] for t in topo] == ["title", "caption", "info", "radio", "button"] and topo[2][1].startswith("Limites"), f"{m}: caixa 'Limites', seletor e 'Nova busca' dentro da coluna do topo: {topo}")
    checa([t[0] for t in antes] == [], f"{m}: entre o cabeçalho e a Etapa 1 só há título e legenda (nenhuma caixa solta em largura total): {antes}")
    for est in ("topo_antes", "topo_com_busca"):
        subs = [t[1] for t in R[m][est][2] if t[0] == "subheader"]
        checa(any(s.startswith("Etapa 2 · Escolher a compra") for s in subs), f"{m} [{est}]: a Etapa 2 tem título ({[s[:44] for s in subs][:3]})")
    subs0 = [t[1] for t in R[m]["topo_antes"][2] if t[0] == "subheader"]
    checa(subs0[:3] == ["Etapa 2 · Escolher a compra", "Etapa 3 · Recorte", "Etapa 4 · IA"], f"{m}: sem busca a página mostra as Etapas 2, 3 e 4 com título antes da 5: {subs0}")
    info = [t for t in R[m]["topo_antes"][2] if t[0] == "info"]
    checa(len(info) == 1 and "Nenhuma busca nesta sessão" in info[0][1], f"{m}: caixa 'Nenhuma busca nesta sessão' dentro da Etapa 2")
    legs = [t for t in R[m]["topo_antes"][2] if t[0] == "caption" and (t[1].startswith("Depois da busca") or t[1].startswith("Depois do recorte"))]
    checa(len(legs) == 2, f"{m}: uma linha curta nas Etapas 3 e 4 sem busca: {[l[1][:40] for l in legs]}")
    checa(R[m]["multiselect"] == 0, f"{m}: nenhum multiselect (seleção só pela tabela com coluna 'usar')")
    dep = R[m]["depois"]; pos = [papel(x) for x in dep]
    checa("lista: tabela com coluna 'usar'" in pos and "lista: Códigos marcados" in pos and "lista: contagem" in pos and "lista: Procurado" in pos, f"{m}: região de resultado com Procurado, contagem, tabela 'usar' e Códigos marcados: {[p for p in pos if p.startswith('lista')]}")
    ordem_lista = [p for p in pos if p in ("lista: Procurado", "lista: contagem", "lista: tabela com coluna 'usar'", "lista: Códigos marcados", "lista: legenda dos marcados")]
    checa(ordem_lista == ["lista: Procurado", "lista: contagem", "lista: tabela com coluna 'usar'", "lista: Códigos marcados", "lista: legenda dos marcados"], f"{m}: ordem da lista Procurado < contagem < tabela < Códigos marcados < legenda: {ordem_lista}")
bot = {m: [x["rotulo"] for x in R[m]["antes"] if x["tipo"] == "button"] for m in R}
checa(bot["Produto"] == ["Procurar no catálogo", "Atualizar catálogo", "Buscar"] and bot["Serviço"] == ["Procurar no catálogo", "Atualizar catálogo", "Buscar compras do serviço"], f"botões da Etapa 1: produto {bot['Produto']} | serviço {bot['Serviço']}")
def caminho(m, rot, est="antes"): return next(x["caminho"] for x in R[m][est] if x["rotulo"].startswith(rot))
checa(caminho("Produto", "Procurar no catálogo") == caminho("Serviço", "Procurar no catálogo") and caminho("Produto", "Modo") == caminho("Serviço", "Modo") and caminho("Produto", "UF") == caminho("Serviço", "UF"), "mesmas colunas para o botão Procurar, Modo e UF nos dois modos")
tab_p = next(x for x in R["Produto"]["depois"] if x["tipo"] in TIPOS_TABELA); tab_s = next(x for x in R["Serviço"]["depois"] if x["tipo"] in TIPOS_TABELA)
checa(tab_p["caminho"] == tab_s["caminho"], f"a tabela com 'usar' fica na mesma coluna nos dois modos ({tab_p['caminho']})")
checa(tab_p["tipo"] == tab_s["tipo"], f"mesma solução de seleção (mesmo tipo de elemento: {tab_p['tipo']})")
# ---- alturas das tabelas: mesma função (altura_tabela do app.py, extraída do código-fonte porque importar o app executaria a tela)
fonte = (RAIZ / "app.py").read_text(encoding="utf-8")
ns = {}
exec(re.search(r"LIMITE_LINHAS_SEM_ROLAGEM = 40.*?\n\n\ndef altura_tabela\(.*?\n    return [^\n]+\n", fonte, re.S).group(0), ns)
at_ = ns["altura_tabela"]
checa(at_(0) == "content" and at_(15) == "content" and at_(40) == "content" and at_(41) == 600 and at_(500) == 600, f"altura_tabela: até 40 linhas 'content' (sem rolagem), acima de 40 altura fixa de 600 px: {at_(40)!r}, {at_(41)!r}")
checa(len(ALT) > 0 and all(h in ("content", 600) for _, h in ALT), f"toda tabela criada nas execuções usou a função de altura: {sorted({(n, h) for n, h in ALT}, key=str)}")
n_chamadas_tabela = len(re.findall(r"st\.(?:dataframe|data_editor)\(", fonte))
n_com_altura = len(re.findall(r"height=altura_tabela\(", fonte))
checa(n_chamadas_tabela == n_com_altura, f"no código, as {n_chamadas_tabela} chamadas de st.dataframe/st.data_editor passam height=altura_tabela(...) ({n_com_altura})")
checa(sem_css_fora_do_visual(fonte), "nenhum CSS injetado (<style> e unsafe_allow_html só dentro de aplicar_visual() e do cabeçalho do Pedido 36)")

# ---- diferenças
print("\nDiferenças (permitidas) entre os modos, estado 'depois de procurar':")
dif = [(papel(x), x["rotulo"][:50]) for x in R["Produto"]["depois"] if papel(x) not in [papel(y) for y in R["Serviço"]["depois"]]]
dif_s = [(papel(x), x["rotulo"][:50]) for x in R["Serviço"]["depois"] if papel(x) not in [papel(y) for y in R["Produto"]["depois"]]]
for d in dif: print("   só produto:", d)
for d in dif_s: print("   só serviço:", d)
md += ["\n## Diferenças entre os modos (estado depois de procurar)\n"] + [f"- só produto: {d[0]} — `{d[1]}`" for d in dif] + [f"- só serviço: {d[0]} — `{d[1]}`" for d in dif_s]
permitidas = {"rádio: tipo do código (só produto)", "lista: Ver configurações (só produto)", "lista: legenda de desativado (só produto)", "ATRIBUTOS: seletor de regras (só produto)",
              "ATRIBUTOS: aviso (só produto)", "ATRIBUTOS: aceitar valores maiores (só produto)", "legenda do formulário", "BOTÃO Buscar (produto)", "BOTÃO Buscar (serviço)",
              "legenda do catálogo", "campo de busca", "campo: código avançado",
              "empty: ", "selectbox: Código", "button: Ver configurações"}   # os 3 últimos: espaços da contagem de compras e controles de dentro de 'Ver configurações' (só produto, Item 4)
checa(all(d[0] in permitidas for d in dif + dif_s), f"as únicas diferenças são as do Item 4 e as do Pedido 13B: {sorted({d[0] for d in dif + dif_s})}")
# Pedido 13G: o .md vai SOMENTE para a pasta do pedido CORRENTE (argumento 1; padrão pedido13g), nunca para a pasta de um pedido antigo, e com o nome deste teste para não
# se misturar com o .md do teste corrente. As evidências de pedido13b a pedido13f ficam intactas.
out = DADOS / (sys.argv[1] if len(sys.argv) > 1 else "pedido13i"); out.mkdir(exist_ok=True)
(out / f"estrutura_produto_vs_servico__{Path(__file__).stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

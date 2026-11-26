"""v4h, Pedido 13D – teste ESTRUTURAL PRODUTO x SERVIÇO com a região de resultado em LARGURA TOTAL. O AppTest percorre a árvore da tela e separa a Etapa 1 em ENTRADAS (coluna A de 2/3:
título..legenda; coluna B de 2/3: opção avançada, Modo e UF, Buscar) e REGIÃO DE RESULTADO da procura (elementos no nível da página, entre A e B). Confere, nos dois modos e antes/depois de procurar:
(1) as entradas ficam nas colunas centrais [1, 3, 1] e a região de resultado fica FORA delas; (2) mesma ordem de blocos e mesma solução de seleção (tabela com 'usar'); (3) topo, Etapas 2 a 5 e alturas, como no 13C.
Grava pedido13i\\estrutura_produto_vs_servico__<este teste>.md (pasta do pedido corrente; o argumento 1 muda a pasta; nunca grava em pasta de pedido antigo). O desenho real no navegador NÃO é verificado aqui. SEM rede (socket bloqueado), rede SIMULADA, SEM Ollama.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13d_estrutura.py   (na pasta do app)"""
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
from estrutura_util import TIPOS_TABELA, etapa1_dividida, posicoes, rotulo_de

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

LARG, ALT = {}, []
def _env(nome, orig):
    def espia(self, *a, **k):
        rot = next((x for x in a if isinstance(x, str)), ""); LARG.setdefault((nome, rot), k.get("width"))
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

def get(url, params=None, binario=False):
    if "1_consultarMaterial" in url: return 200, {"totalRegistros": 5, "paginasRestantes": 0, "resultado": []}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": [], "totalRegistros": 0}, {}
    return 200, {"resultado": []}, {}
f.get = get
TMP = DADOS / "tmp_teste_fase4"; TMP.mkdir(exist_ok=True)
RODADA = TMP / f"p13d_{int(time.time())}"; RODADA.mkdir(); f.PASTA = RODADA
CAB = "linha;orgao;uf;data_publicacao;data_resultado;data_usada_no_filtro;controle_pncp;numero_item;descricao_item;preco_unitario_homologado;atributos_atendidos;observacao_preco;situacao_pncp;status_item_pncp;valor_estimado_pncp;link_publico;fonte_api_resultado;cnpj;ano;sequencial;id_compra;unidade;quantidade"
LIN = "1;ORGAO SIMULADO;DF;2026-11-01;2026-11-02;data do resultado;;1;ITEM SIMULADO;100.0;0 de 0;;sem PNCP;;;;;;;;123;UN;1"
def semeia(at_, tipo):
    at_.session_state["busca_atual"] = {"resumo": {"arquivo": "x.csv", "pedidos": {}}, "csv": (CAB + "\n" + LIN + "\n").encode("utf-8"), "quando": "01/01 00:00", "aceitar": False, "fim_txt": "", "log": "", "tempo": 0.0,
                                        "codigos": "0", "termo": "t", "eh_item": True, "tipo": tipo}

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
def tudo(d): return [dict(x, bloco="A (entradas)") for x in d["A"]] + [dict(x, bloco="R (resultado)") for x in d["R"]] + [dict(x, bloco="B (entradas)") for x in d["B"]]

def estado(modo):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
    if modo == "Serviço": at.radio(key="tipo_busca").set_value("Serviço").run()
    r = {"antes": etapa1_dividida(at, LARG), "topo_antes": topo_e_resto(at)}
    if modo == "Produto": at.text_input(key="termo").set_value("notebook").run()
    else: at.text_input(key="serv_termo").set_value("instalação elétrica").run()
    r["depois"] = etapa1_dividida(at, LARG); r["topo_depois"] = topo_e_resto(at); r["multiselect"] = len(at.multiselect)
    semeia(at, "serviço" if modo == "Serviço" else "produto"); at.run()
    r["topo_com_busca"] = topo_e_resto(at); r["excecoes"] = [e.value for e in at.exception]
    return r
R = {m: estado(m) for m in ("Produto", "Serviço")}
for m in R: checa(not R[m]["excecoes"], f"{m}: sem exceção ({R[m]['excecoes'][:1]})")

md = ["# Etapa 1: ENTRADAS (2/3) e REGIÃO DE RESULTADO (largura total): PRODUTO x SERVIÇO (estrutura, AppTest)\n",
      "Gerado por `tests/test_pedido13d_estrutura.py`. Cada linha: bloco · tipo · rótulo · caminho · largura pedida. Bloco A/B = colunas centrais [1, 3, 1]; R = região de resultado, fora das colunas (largura total). Não prova o desenho no navegador.\n"]
for est, tit in (("antes", "antes de procurar"), ("depois", "depois de procurar (termo digitado + Enter)")):
    md.append(f"\n## Estado: {tit}\n"); a, b = tudo(R["Produto"][est]), tudo(R["Serviço"][est])
    md.append("| # | PRODUTO | SERVIÇO |\n|---|---|---|")
    sm = difflib.SequenceMatcher(None, [chave(x) for x in a], [chave(x) for x in b], autojunk=False); n = 0
    fmt = lambda x: f"{x['bloco'][0]} · {x['tipo']} · {x['rotulo'][:44]} · {x['caminho']} · {x['largura']}"
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for k in range(max(i2 - i1, j2 - j1)):
            n += 1; xa = fmt(a[i1 + k]) if i1 + k < i2 else "—"; xb = fmt(b[j1 + k]) if j1 + k < j2 else "—"
            md.append(f"| {n}{'' if tag == 'equal' else ' ≠'} | {xa} | {xb} |")
md.append("\n## Fora da Etapa 1 (cabeçalho, topo e Etapas 2 a 5)\n")
for est in ("topo_antes", "topo_com_busca"):
    md.append(f"\n### {est}\n")
    for m in R:
        topo, antes, apos = R[m][est]; md.append(f"- **{m}** — topo (na coluna): {topo}; soltos antes da Etapa 1: {antes}; depois da Etapa 1: {apos}")

SO_PROD = {"rádio: tipo do código (só produto)", "lista: Ver configurações (só produto)", "lista: legenda de desativado (só produto)"}
def comuns(m, est):
    return [papel(x) for x in tudo(R[m][est]) if x["tipo"] != "flex_container" and papel(x) not in SO_PROD and "(só produto)" not in papel(x) and not papel(x).startswith("ATRIBUTOS")
            and not (x["caminho"].startswith("largura total") and "expander" in x["caminho"])]   # Pedido 13I: o painel "Ver configurações" (só produto) fica dentro desse expander
for est in ("antes", "depois"):
    pa, pb = comuns("Produto", est), comuns("Serviço", est)
    ca = [p for p in pa if p in pb]; cb = [p for p in pb if p in pa]
    checa(ca == cb, f"[{est}] mesma ordem dos blocos em comum (entradas A, resultado, entradas B): {ca}")
for m in R:
    for est in ("antes", "depois"):
        d = R[m][est]
        checa(all(abs(c[1] - w) < 0.01 for c, w in zip(d["colunasA"], (0.2, 0.6, 0.2))) and all(abs(c[1] - w) < 0.01 for c, w in zip(d["colunasB"], (0.2, 0.6, 0.2))), f"{m} [{est}]: colunas A e B = central [1, 3, 1] ({d['colunasA']} | {d['colunasB']})")
        checa(all(x["caminho"].startswith("col(0.60)") for x in d["A"] + d["B"]), f"{m} [{est}]: as ENTRADAS ({len(d['A'])} + {len(d['B'])} elementos) estão dentro das colunas centrais [1, 3, 1]")
        checa(all(x["caminho"].startswith("largura total") and "col(0.60)" not in x["caminho"] for x in d["R"]), f"{m} [{est}]: a região de resultado ({len(d['R'])} elementos) está FORA das colunas centrais [1, 3, 1], em largura total")
    antes_R, depois_R = R[m]["antes"]["R"], R[m]["depois"]["R"]
    checa(antes_R == [], f"{m}: antes de procurar não há região de resultado entre as entradas")
    pos = [papel(x) for x in depois_R]
    checa([p for p in pos if p in ("lista: Procurado", "lista: contagem", "lista: tabela com coluna 'usar'", "lista: Códigos marcados", "lista: legenda dos marcados")] ==
          ["lista: Procurado", "lista: contagem", "lista: tabela com coluna 'usar'", "lista: Códigos marcados", "lista: legenda dos marcados"], f"{m}: região de resultado na ordem Procurado < contagem < tabela 'usar' < Códigos marcados < legenda: {[p for p in pos if p.startswith('lista')]}")
    roles = [papel(x) for x in tudo(R[m]["depois"])]
    i_proc, i_res, i_av, i_modo = roles.index("BOTÃO Procurar no catálogo"), roles.index("lista: Procurado"), roles.index("expander: opção avançada"), roles.index("subtítulo: modo e UF")
    checa(i_proc < i_res < i_av < i_modo, f"{m}: ordem de leitura Procurar < resultado < opção avançada < Modo e UF")
    topo, antes, apos = R[m]["topo_antes"]
    checa([t[0] for t in topo] == ["title", "caption", "info", "radio", "button"] and topo[2][1].startswith("Limites") and [t[0] for t in antes] == [], f"{m}: Limites, seletor e Nova busca na coluna do topo; só título e legenda soltos acima: {topo}")
    subs0 = [t[1] for t in R[m]["topo_antes"][2] if t[0] == "subheader"]
    checa(subs0[:3] == ["Etapa 2 · Escolher a compra", "Etapa 3 · Recorte", "Etapa 4 · IA"], f"{m}: sem busca, a página mostra as Etapas 2, 3 e 4 com título antes da 5: {subs0}")
    checa(any(t[1].startswith("Etapa 2 · Escolher a compra") for t in R[m]["topo_com_busca"][2] if t[0] == "subheader"), f"{m}: com busca, a Etapa 2 continua com título")
    checa(R[m]["multiselect"] == 0, f"{m}: nenhum multiselect (seleção só pela tabela com 'usar')")
bot = {m: {b: [x["rotulo"] for x in R[m]["antes"][b] if x["tipo"] == "button"] for b in ("A", "B")} for m in R}
checa(bot["Produto"]["A"] == ["Procurar no catálogo", "Atualizar catálogo"] and bot["Produto"]["B"] == ["Buscar"] and bot["Serviço"]["A"] == ["Procurar no catálogo", "Atualizar catálogo"] and bot["Serviço"]["B"] == ["Buscar compras do serviço"], f"botões: {bot}")
atu = {m: [x for x in R[m]["antes"]["A"] if x["tipo"] == "button" and x["rotulo"] == "Atualizar catálogo"] for m in R}
checa(all(len(v) == 1 for v in atu.values()) and atu["Produto"][0]["caminho"] == atu["Serviço"][0]["caminho"] and atu["Produto"][0]["largura"] == atu["Serviço"][0]["largura"], f"Pedido 13F: 'Atualizar catálogo' nos dois modos, mesma coluna e mesma largura: {[(m, v[0]['caminho'], v[0]['largura']) for m, v in atu.items() if v]}")
ix = {m: [x["rotulo"] for x in R[m]["antes"]["A"]].index("Atualizar catálogo") - [x["rotulo"] for x in R[m]["antes"]["A"]].index("Procurar no catálogo") for m in R}
checa(ix["Produto"] == ix["Serviço"], f"Pedido 13F: 'Atualizar catálogo' no mesmo lugar (a mesma distância do botão Procurar) nos dois modos: {ix}")
legs = {m: next(x["rotulo"] for x in R[m]["antes"]["A"] if x["rotulo"].startswith("Catálogo oficial")) for m in R}
checa("o app não o baixa" not in legs["Serviço"] and "atualizado em" in legs["Serviço"] and "atualizado em" in legs["Produto"], f"Pedido 13F: legenda do serviço no mesmo formato da do produto (sem 'o app não o baixa'): {legs['Serviço'][:90]}")
tab_p = next(x for x in R["Produto"]["depois"]["R"] if x["tipo"] in TIPOS_TABELA); tab_s = next(x for x in R["Serviço"]["depois"]["R"] if x["tipo"] in TIPOS_TABELA)
checa(tab_p["tipo"] == tab_s["tipo"] and tab_p["caminho"] == tab_s["caminho"] == "largura total", f"mesma solução de seleção, tabela em largura total nos dois modos ({tab_p['tipo']}, {tab_p['caminho']})")
def cam(m, rot, bloco, est="antes"): return next(x["caminho"] for x in R[m][est][bloco] if x["rotulo"].startswith(rot))
checa(cam("Produto", "Procurar no catálogo", "A") == cam("Serviço", "Procurar no catálogo", "A") and cam("Produto", "Modo", "B") == cam("Serviço", "Modo", "B") and cam("Produto", "UF", "B") == cam("Serviço", "UF", "B"), "mesmas colunas para Procurar, Modo e UF nos dois modos")
fonte = (RAIZ / "app.py").read_text(encoding="utf-8"); ns = {}
exec(re.search(r"LIMITE_LINHAS_SEM_ROLAGEM = 40.*?\n\n\ndef altura_tabela\(.*?\n    return [^\n]+\n", fonte, re.S).group(0), ns)
checa(ns["altura_tabela"](40) == "content" and ns["altura_tabela"](41) == 600, "altura_tabela inalterada (até 40 linhas 'content'; acima 600 px)")
checa(len(ALT) > 0 and all(h in ("content", 600) for _, h in ALT) and len(re.findall(r"st\.(?:dataframe|data_editor)\(", fonte)) == len(re.findall(r"height=altura_tabela\(", fonte)), f"todas as tabelas usam altura_tabela: {sorted({(n, h) for n, h in ALT}, key=str)}")
checa(sem_css_fora_do_visual(fonte), "nenhum CSS injetado (<style> e unsafe_allow_html só dentro de aplicar_visual() e do cabeçalho do Pedido 36)")
print("\nDiferenças (permitidas) entre os modos, estado 'depois de procurar':")
dif = [(papel(x), x["rotulo"][:50]) for x in tudo(R["Produto"]["depois"]) if papel(x) not in [papel(y) for y in tudo(R["Serviço"]["depois"])]]
dif_s = [(papel(x), x["rotulo"][:50]) for x in tudo(R["Serviço"]["depois"]) if papel(x) not in [papel(y) for y in tudo(R["Produto"]["depois"])]]
for d in dif: print("   só produto:", d)
for d in dif_s: print("   só serviço:", d)
md += ["\n## Diferenças entre os modos (estado depois de procurar)\n"] + [f"- só produto: {d[0]} — `{d[1]}`" for d in dif] + [f"- só serviço: {d[0]} — `{d[1]}`" for d in dif_s]
permitidas = {"rádio: tipo do código (só produto)", "lista: Ver configurações (só produto)", "lista: legenda de desativado (só produto)", "ATRIBUTOS: seletor de regras (só produto)",
              "ATRIBUTOS: aviso (só produto)", "ATRIBUTOS: aceitar valores maiores (só produto)", "legenda do formulário", "BOTÃO Buscar (produto)", "BOTÃO Buscar (serviço)",
              "legenda do catálogo", "campo de busca", "campo: código avançado", "empty: ", "selectbox: Código", "button: Ver configurações"}
checa(all(d[0] in permitidas for d in dif + dif_s), f"as únicas diferenças são as permitidas (Item 4 do 13C e Pedido 13B): {sorted({d[0] for d in dif + dif_s})}")
# Pedido 13G: o .md vai SOMENTE para a pasta do pedido CORRENTE (argumento 1; padrão pedido13g), nunca para a pasta de um pedido antigo, e com o nome deste teste para não
# se misturar com o .md do teste corrente. As evidências de pedido13b a pedido13f ficam intactas.
out = DADOS / (sys.argv[1] if len(sys.argv) > 1 else "pedido13i"); out.mkdir(exist_ok=True)
(out / f"estrutura_produto_vs_servico__{Path(__file__).stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

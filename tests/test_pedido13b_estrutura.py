"""v4h, Pedido 13B – teste ESTRUTURAL da Etapa 1: PRODUTO x SERVIÇO. O AppTest percorre a árvore da tela e gera, para cada modo, a lista ORDENADA de elementos da Etapa 1
(tipo, rótulo, caminho de colunas com o peso, largura pedida ao Streamlit) em dois estados (antes e depois de procurar), compara as duas listas e grava o resultado lado a lado em
pedido13i\\estrutura_produto_vs_servico__<este teste>.md (pasta do pedido corrente; o argumento 1 muda a pasta; nunca grava em pasta de pedido antigo). Critério de aceitação (estrutural; o desenho real no navegador NÃO é verificado aqui):
  1. mesma ordem de blocos; 2. mesmos rótulos de botão (exceto o 'Buscar' final, que o pedido manda diferente por modo); 3. mesma largura de coluna;
  4. nenhum elemento da Etapa 1 fora da coluna da Etapa 1. Diferenças permitidas: só os atributos (só produto). Pedido 13F: o botão 'Atualizar catálogo' existe nos DOIS modos (não é mais diferença permitida).
SEM rede (socket bloqueado; só o loopback do asyncio), rede trocada por respostas SIMULADAS, SEM Ollama.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido13b_estrutura.py   (na pasta do app)"""
import datetime as dt, difflib, re, socket, sys, time
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

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

# ---- espião: largura pedida por rótulo
LARG = {}
def _env(nome, orig):
    def espia(self, *a, **k):
        rot = next((x for x in a if isinstance(x, str)), "")
        LARG.setdefault((nome, rot), k.get("width"))
        return orig(self, *a, **k)
    return espia
for nome in ("text_input", "button", "radio", "selectbox", "multiselect", "checkbox", "form_submit_button"):
    setattr(DeltaGenerator, nome, _env(nome, getattr(DeltaGenerator, nome)))
def _mod(nome):
    orig = getattr(st, nome)
    def espia(*a, **k):
        rot = next((x for x in a if isinstance(x, str)), ""); LARG.setdefault((nome, rot), k.get("width")); return orig(*a, **k)
    setattr(st, nome, espia)
for nome in ("text_input", "button", "radio", "selectbox", "multiselect", "checkbox"): _mod(nome)

# ---- rede simulada
HOJE = dt.date.today().isoformat()
def get(url, params=None, binario=False):
    params = params or {}
    if "1_consultarMaterial" in url: return 200, {"totalRegistros": 5, "paginasRestantes": 0, "resultado": []}, {}
    if "4_consultarItemMaterial" in url: return 200, {"resultado": [], "totalRegistros": 0}, {}
    return 200, {"resultado": []}, {}
f.get = get
TMP = DADOS / "tmp_teste_fase4"; TMP.mkdir(exist_ok=True)
RODADA = TMP / f"p13b_{int(time.time())}"; RODADA.mkdir(); f.PASTA = RODADA

# ---- percurso da árvore
def rotulo_de(no):
    lab = getattr(no, "label", None)
    if isinstance(lab, str) and lab: return lab
    v = getattr(no, "value", "")
    return v if isinstance(v, str) else ""
from estrutura_util import etapa1_dividida
def etapa1_elementos(at):
    """Pedido 13D: devolve só as ENTRADAS da Etapa 1 (colunas A e B de 2/3); a região de resultado fica em largura total, fora delas (ver test_pedido13d_estrutura.py)."""
    d = etapa1_dividida(at, LARG)
    return d["A"] + d["B"], d["colunasA"]

PAPEL = [("**Etapa 1 · Procurar no catálogo**", "painel: título"), ("Concluída em", "painel: resumo final"), ("Falhou:", "painel: resumo final"),   # Pedido 13I: painel de progresso (mesmo nos dois modos)
         ("Etapa 1 · Buscar", "título"), ("##### Procurar no catálogo", "subtítulo: procurar"), ("O que você procura?", "campo de busca"), ("Palavra do serviço", "campo de busca"),
         ("Procurar no catálogo", "BOTÃO Procurar no catálogo"), ("Catálogo oficial de materiais", "legenda do catálogo"), ("Catálogo oficial de serviços", "legenda do catálogo"),
         ("Atualizar catálogo", "BOTÃO Atualizar catálogo"), ("Testado com rede", "legenda: teste com rede"), ("Procurado:", "legenda: procurado"), ("Opção avançada", "expander: opção avançada"),
         ("Código (só números", "campo: código avançado"), ("Código do serviço", "campo: código avançado"), ("O código é", "rádio: tipo do código (só produto)"), ("##### Modo e UF", "subtítulo: modo e UF"),
         ("Regras de atributos", "ATRIBUTOS: seletor de regras (só produto)"), ("Marque 1 ou mais", "lista"), ("Marque um código para ver os atributos", "ATRIBUTOS: aviso (só produto)"),
         ("Modo", "rádio: Modo"), ("UF", "campo: UF"), ("Aceitar valores maiores", "ATRIBUTOS: aceitar valores maiores (só produto)"), ("Os atributos, a UF", "legenda do formulário"),
         ("O modo e a UF só valem", "legenda do formulário"), ("Buscar compras do serviço", "BOTÃO Buscar (serviço)"), ("Buscar", "BOTÃO Buscar (produto)"), ("Marque o(s) código(s)", "lista: marcar códigos"),
         ("Códigos marcados", "lista: marcados")]
def papel(el):
    r = el["rotulo"]
    for ini, p in PAPEL:
        if r.startswith(ini): return p
    if el["tipo"] in ("arrow_data_frame", "data_editor", "dataframe"): return "lista: tabela do que a procura achou"
    if el["tipo"] == "form": return "formulário"
    return f"{el['tipo']}: {r[:30]}"
def chave(el): return (el["tipo"] if el["tipo"] not in ("arrow_data_frame", "data_editor", "dataframe") else "tabela", papel(el), el["caminho"])

def estado(modo):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180); at.run()
    if modo == "Serviço": at.radio(key="tipo_busca").set_value("Serviço").run()
    ini, cols = etapa1_elementos(at)
    if modo == "Produto":
        at.text_input(key="termo").set_value("notebook").run()
    else:
        at.text_input(key="serv_termo").set_value("instalação elétrica").run()
    dep, cols2 = etapa1_elementos(at)
    return {"antes": ini, "depois": dep, "colunas": cols, "colunas_depois": cols2, "excecoes": [e.value for e in at.exception]}

R = {m: estado(m) for m in ("Produto", "Serviço")}
for m in R: checa(not R[m]["excecoes"], f"{m}: sem exceção ({R[m]['excecoes'][:1]})")
# ---- md lado a lado
md = ["# Etapa 1: PRODUTO x SERVIÇO (estrutura, AppTest)\n", "Gerado por `tests/test_pedido13b_estrutura.py`. Cada linha: tipo · rótulo · caminho de colunas (peso) · largura pedida ao Streamlit. Não prova o desenho no navegador.\n"]
for est in ("antes", "depois"):
    md.append(f"\n## Estado: {'antes de procurar' if est == 'antes' else 'depois de procurar (termo digitado + Enter)'}\n")
    a, b = R["Produto"][est], R["Serviço"][est]
    md.append("| # | PRODUTO | SERVIÇO |\n|---|---|---|")
    ka, kb = [chave(x) for x in a], [chave(x) for x in b]
    sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False); n = 0
    fmt = lambda x: f"{x['tipo']} · {x['rotulo'][:46]} · {x['caminho']} · {x['largura']}"
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for k in range(max(i2 - i1, j2 - j1)):
            n += 1; xa = fmt(a[i1 + k]) if i1 + k < i2 else "—"; xb = fmt(b[j1 + k]) if j1 + k < j2 else "—"
            md.append(f"| {n}{'' if tag == 'equal' else ' ≠'} | {xa} | {xb} |")
# ---- critérios
def seq_compartilhada(lst, proibidos):
    return [chave(x) for x in lst if x["tipo"] != "flex_container" and papel(x) not in proibidos and not papel(x).startswith("ATRIBUTOS") and "(só produto)" not in papel(x)]
SO_PRODUTO = {"rádio: tipo do código (só produto)"}   # Pedido 13F: o botão Atualizar catálogo saiu desta lista
for est in ("antes", "depois"):
    a = seq_compartilhada(R["Produto"][est], SO_PRODUTO); b = seq_compartilhada(R["Serviço"][est], set())
    # no serviço há legendas e botões de texto próprio; compara só a ORDEM dos papéis em comum
    pa = [x[1] for x in a]; pb = [x[1] for x in b]
    comuns = [p for p in pa if p in pb]; comuns_b = [p for p in pb if p in pa]
    checa(comuns == comuns_b, f"[{est}] mesma ordem dos blocos em comum: {comuns}")
for m in ("Produto", "Serviço"):
    lista = R[m]["antes"]
    checa(R[m]["colunas"][0][1] and abs(R[m]["colunas"][1][1] - 0.6) < 0.01 and abs(R[m]["colunas"][0][1] - 0.2) < 0.01 and abs(R[m]["colunas"][2][1] - 0.2) < 0.01, f"{m}: coluna central da Etapa 1 = central [1, 3, 1], o resto vazio ({R[m]['colunas']})")
    checa(all(x["caminho"].startswith("col(0.60)") for x in lista) and len(lista) > 0, f"{m}: todos os {len(lista)} elementos da Etapa 1 estão dentro da coluna central [1, 3, 1] (nenhum fora)")
    titulos = [x for x in lista if x["tipo"] == "subheader"]
    checa(len(titulos) == 1 and titulos[0]["rotulo"] == "Etapa 1 · Buscar", f"{m}: um título só ('Etapa 1 · Buscar'): {[t['rotulo'] for t in titulos]}")
bot = {m: [x["rotulo"] for x in R[m]["antes"] if x["tipo"] == "button"] for m in R}
checa("Procurar no catálogo" in bot["Produto"] and "Procurar no catálogo" in bot["Serviço"], f"mesmo rótulo do botão de procurar nos dois modos: {bot}")
checa(bot["Produto"].count("Procurar no catálogo") == 1 and bot["Serviço"].count("Procurar no catálogo") == 1, "um botão 'Procurar no catálogo' por modo")
checa(bot["Produto"] == ["Procurar no catálogo", "Atualizar catálogo", "Buscar"] and bot["Serviço"] == ["Procurar no catálogo", "Atualizar catálogo", "Buscar compras do serviço"], f"botões em ordem: produto {bot['Produto']} | serviço {bot['Serviço']}")
checa(all(R[m]["antes"][[x["rotulo"] for x in R[m]["antes"]].index("Procurar no catálogo")]["largura"] == "stretch" for m in R), "botão 'Procurar no catálogo' com width='stretch' (o texto não é cortado) nos dois modos")
def linha_pesos(m, rot):
    x = next(e for e in R[m]["antes"] if e["rotulo"].startswith(rot)); return x["caminho"]
checa(linha_pesos("Produto", "O que você procura?") == linha_pesos("Serviço", "Palavra do serviço"), f"campo de busca na mesma linha/colunas: {linha_pesos('Produto', 'O que você procura?')}")
checa(linha_pesos("Produto", "Procurar no catálogo") == linha_pesos("Serviço", "Procurar no catálogo"), "botão Procurar na mesma coluna nos dois modos")
checa(linha_pesos("Produto", "Modo") == linha_pesos("Serviço", "Modo") and linha_pesos("Produto", "UF") == linha_pesos("Serviço", "UF"), f"Modo e UF na mesma linha e com as mesmas colunas: {linha_pesos('Serviço', 'Modo')} | {linha_pesos('Serviço', 'UF')}")
for m in R:
    el = {x["rotulo"]: x for x in R[m]["antes"]}
    checa(el["UF"]["largura"] == 100, f"{m}: UF com rótulo curto 'UF' e width=100")
    checa(el["Modo"]["tipo"] == "radio" and el["UF"]["tipo"] == "text_input", f"{m}: Modo (rádio) e UF (campo) lado a lado")
    pos = [x["rotulo"] for x in R[m]["antes"]]
    checa(pos.index("##### Procurar no catálogo") < pos.index("Procurar no catálogo") < next(i for i, r in enumerate(pos) if r.startswith("Opção avançada")) < pos.index("##### Modo e UF") < pos.index("UF"), f"{m}: ordem título < procurar < opção avançada < Modo e UF")
leg_p = next(x for x in R["Produto"]["antes"] if x["rotulo"].startswith("Catálogo oficial de materiais")); leg_s = next(x for x in R["Serviço"]["antes"] if x["rotulo"].startswith("Catálogo oficial de serviços"))
checa(leg_p["caminho"].startswith("col(0.60)") and leg_s["caminho"].startswith("col(0.60)"), "legenda do catálogo dentro da mesma coluna nos dois modos")
atual = next(x for x in R["Produto"]["antes"] if x["rotulo"] == "Atualizar catálogo")
checa(atual["caminho"].startswith("col(0.60)") and atual["caminho"].count("col(") == 2, f"'Atualizar catálogo' DENTRO da coluna da Etapa 1, na linha da legenda ({atual['caminho']})")
atu_s = next(x for x in R["Serviço"]["antes"] if x["rotulo"] == "Atualizar catálogo")
checa(atu_s["caminho"] == atual["caminho"] and atu_s["largura"] == atual["largura"] and "o app não o baixa" not in leg_s["rotulo"], f"Pedido 13F: serviço TEM o botão, na mesma coluna ({atu_s['caminho']}) e com a mesma largura ({atu_s['largura']}); a legenda não diz que o app não baixa")
print("\nDiferenças (permitidas) entre os modos, estado 'antes de procurar':")
dif = [(papel(x), x["rotulo"][:50]) for x in R["Produto"]["antes"] if papel(x) not in [papel(y) for y in R["Serviço"]["antes"]]]
dif_s = [(papel(x), x["rotulo"][:50]) for x in R["Serviço"]["antes"] if papel(x) not in [papel(y) for y in R["Produto"]["antes"]]]
for d in dif: print("   só produto:", d)
for d in dif_s: print("   só serviço:", d)
md += ["\n## Diferenças entre os modos (estado antes de procurar)\n"] + [f"- só produto: {d[0]} — `{d[1]}`" for d in dif] + [f"- só serviço: {d[0]} — `{d[1]}`" for d in dif_s]
permitidas = {"rádio: tipo do código (só produto)", "ATRIBUTOS: seletor de regras (só produto)", "ATRIBUTOS: aviso (só produto)", "ATRIBUTOS: aceitar valores maiores (só produto)", "legenda do formulário",
              "BOTÃO Buscar (produto)", "BOTÃO Buscar (serviço)", "legenda do catálogo", "campo de busca", "campo: código avançado"}
checa(all(d[0] in permitidas or d[0].startswith("ATRIBUTOS") for d in dif + dif_s), f"as únicas diferenças são as permitidas: {sorted({d[0] for d in dif + dif_s})}")
# Pedido 13G: o .md vai SOMENTE para a pasta do pedido CORRENTE (argumento 1; padrão pedido13g), nunca para a pasta de um pedido antigo, e com o nome deste teste para não
# se misturar com o .md do teste corrente. As evidências de pedido13b a pedido13f ficam intactas.
out = DADOS / (sys.argv[1] if len(sys.argv) > 1 else "pedido13i"); out.mkdir(exist_ok=True)
(out / f"estrutura_produto_vs_servico__{Path(__file__).stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), f"nenhum connect externo nem à porta 11434 (loopback do asyncio: {len(LOOPBACK_INTERNO)})")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

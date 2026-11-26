"""Apoio dos testes estruturais (Pedidos 13B, 13C e 13D): percorre a árvore do AppTest e separa a Etapa 1 em ENTRADAS (duas colunas de 2/3: A = título..legenda; B = opção avançada..Buscar)
e REGIÃO DE RESULTADO da procura (elementos no nível da página, ENTRE A e B, em largura total). Não é um teste; só funções."""
TIPOS_TABELA = ("arrow_data_frame", "data_editor", "dataframe", "arrow_table")


def filhos_de(no):
    """Filhos de um nó, atravessando em qualquer nível os cartões do visual novo (st.container com chave 'cartao_*', Pedido 36): o conteúdo do cartão conta como filho direto do pai, igual ao app sem cartões; o cabeçalho decorativo (markdown com "ref-cabecalho") não conta como elemento."""
    for c in no.children.values():
        if c.type == "flex_container" and "-cartao_" in str(getattr(c.proto, "id", "")):
            yield from filhos_de(c)
        elif c.type == "markdown" and "ref-cabecalho" in str(c.value):
            continue   # cabeçalho decorativo "Referência TIC" (com a faixa das 5 etapas) do visual novo: não é elemento de conteúdo da página
        elif c.type in ("flex_container", "column"):
            yield _Plano(c)
        else:
            yield c


class _Plano:
    """Nó de contêiner/coluna visto SEM os cartões do visual novo: igual ao nó original, mas .children já vem achatado por filhos_de (assim os testes que andam a árvore por .children.values() não precisam saber dos cartões)."""
    def __init__(self, no):
        self._no = no

    def __getattr__(self, nome):
        return getattr(self._no, nome)

    @property
    def children(self):
        return dict(enumerate(filhos_de(self._no)))


def rotulo_de(no):
    lab = getattr(no, "label", None)
    if isinstance(lab, str) and lab:
        return lab
    v = getattr(no, "value", "")
    return v if isinstance(v, str) else ""


def _largura(LARG, c, rot):
    for n in ("text_input", "button", "radio", "selectbox", "multiselect", "checkbox", "form_submit_button"):
        if (n, rot) in LARG and c.type.startswith(n.split("_")[0]):
            return LARG[(n, rot)]
    return None


def _anda(no, caminho, out, LARG):
    for c in filhos_de(no):
        if c.type == "column":
            w = getattr(c.proto, "weight", None)
            _anda(c, caminho + [f"col({w:.2f})" if w is not None else "col"], out, LARG)
            continue
        rot = rotulo_de(c)
        lg = _largura(LARG, c, rot)
        out.append({"tipo": c.type, "rotulo": rot[:70], "caminho": " > ".join(caminho), "largura": lg if lg is not None else "herda a coluna"})
        if c.type == "expander":
            for cc in filhos_de(c):
                out.append({"tipo": cc.type, "rotulo": rotulo_de(cc)[:70], "caminho": " > ".join(caminho + ["expander"]), "largura": "herda a coluna"})
        elif getattr(c, "children", None) and c.type in ("flex_container", "form"):
            _anda(c, caminho + [c.type], out, LARG)


def posicoes(at):
    """(filhos do nível da página, índice do contêiner do topo, índice da coluna A, índice da coluna B)."""
    filhos = list(filhos_de(at.main))
    conts = [i for i, c in enumerate(filhos) if c.type == "flex_container"]
    iA = conts[1]
    iB = next(i for i in conts[2:] if any(cc.type == "expander" and rotulo_de(cc).startswith("Opção avançada") for col in filhos_de(filhos[i]) for cc in filhos_de(col)))
    return filhos, conts[0], iA, iB


def etapa1_dividida(at, LARG):
    """{'A': [...], 'R': [...], 'B': [...], 'colunasA': [(tipo, peso)], 'colunasB': [...]}; R = região de resultado (largura total)."""
    filhos, _t, iA, iB = posicoes(at)
    A, R, B = [], [], []
    _anda(list(filhos_de(filhos[iA]))[1], ["col(0.60)"], A, LARG)
    _anda(list(filhos_de(filhos[iB]))[1], ["col(0.60)"], B, LARG)
    for c in filhos[iA + 1:iB]:
        rot = rotulo_de(c)
        R.append({"tipo": c.type, "rotulo": rot[:70], "caminho": "largura total", "largura": "herda a página"})
        if c.type == "expander":
            for cc in filhos_de(c):
                R.append({"tipo": cc.type, "rotulo": rotulo_de(cc)[:70], "caminho": "largura total > expander", "largura": "herda a página"})
        elif getattr(c, "children", None) and c.type in ("flex_container", "form"):
            sub = []
            _anda(c, ["largura total", c.type], sub, LARG)
            R.extend(sub)
    cols = lambda i: [(c.type, getattr(c.proto, "weight", None)) for c in filhos_de(filhos[i])]
    return {"A": A, "R": R, "B": B, "colunasA": cols(iA), "colunasB": cols(iB)}

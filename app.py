"""Referência TIC – tela (Streamlit) por cima do ferramenta.py.

Não duplica a lógica: chama as mesmas funções do menu (buscar_por_codigo, buscar_por_nome, opcao_3_baixar,
opcao_4_recortar, opcao_5_texto_ia), respondendo às perguntas delas automaticamente com o que foi digitado na tela.
Só GET público (PNCP e Compras.gov.br), sem login e sem chave. Abra pelo ABRIR_APP.bat.
"""
import contextlib
import csv
import io
import json
import re
import sys
import threading
import time
import uuid
import zlib
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ferramenta as f  # noqa: E402



@st.cache_resource
def limites_completos():
    """Limites do ferramenta.py lidos uma vez por processo (depois, outra sessão pode estar com o módulo no modo rápido)."""
    return {k: getattr(f, k) for k in ("MAX_PAGINAS_CATALOGO", "MAX_VINCULOS", "MAX_RESULTADOS", "MAX_COMPRAS")}


# modo rápido = menos páginas e menos consultas (mais rápido, amostra menor); completo = limites do ferramenta.py
MODOS = {"rápido": {"MAX_PAGINAS_CATALOGO": 3, "MAX_VINCULOS": 10, "MAX_RESULTADOS": 10, "MAX_COMPRAS": 10},
         "completo": limites_completos()}
BASE_SAIDA = f.PASTA / "saida"  # cada sessão usa saida/sessoes/<id>
ORDEM = {"atende": 0, "a confirmar no TR": 1, "não informado": 2, "sem atributos": 2, "não atende": 3}


# ----------------------------------------------------------------- ponte com o ferramenta.py
@st.cache_resource
def trava_global():
    """O ferramenta.py é um módulo só para todas as sessões do servidor: uma operação de cada vez."""
    return threading.Lock()


def pasta_da_sessao():
    """Cada sessão grava na própria pasta (saida/sessoes/<id>): uma pessoa não vê as buscas e os documentos da outra."""
    if "sessao_id" not in st.session_state:
        st.session_state["sessao_id"] = uuid.uuid4().hex
    pasta = BASE_SAIDA / "sessoes" / st.session_state["sessao_id"]
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


@contextlib.contextmanager
def respondendo(respostas, ao_chamar=None):
    """Durante o bloco: exclusividade no ferramenta.py e pasta da sessão; as perguntas dele recebem as respostas da lista
    (em ordem; vazia = Enter), o que ele imprime fica guardado em texto e cada chamada de rede avisa o progresso."""
    trava = trava_global()
    if not trava.acquire(blocking=False):
        aviso = st.empty()
        aviso.info("Outra busca está em andamento; a sua começa em seguida.")
        trava.acquire()
        aviso.empty()
    fila = list(respostas)
    originais = (f.pergunta, f.escolher_numero, f.get, f.SAIDA, f.LOG)

    def pergunta(msg, padrao=""):
        v = str(fila.pop(0)) if fila else ""
        return v.strip() or padrao

    def escolher_numero(msg, maximo):
        v = str(fila.pop(0)) if fila else ""
        return int(v) if v.isdigit() and 1 <= int(v) <= maximo else None

    def get(url, params=None, binario=False):
        if ao_chamar:
            ao_chamar("antes", url, params or {}, None)
        resultado = originais[2](url, params, binario)
        if ao_chamar:
            ao_chamar("depois", url, params or {}, resultado)
        return resultado

    f.pergunta, f.escolher_numero, f.get = pergunta, escolher_numero, get
    f.SAIDA = pasta_da_sessao()
    f.LOG = f.SAIDA / "log_requisicoes.jsonl"
    saida = io.StringIO()
    try:
        with contextlib.redirect_stdout(saida):
            yield saida
    finally:
        f.pergunta, f.escolher_numero, f.get, f.SAIDA, f.LOG = originais
        trava.release()


@contextlib.contextmanager
def limites(modo, aceitar=False):
    """Aplica os limites do modo rápido/completo e a opção 'aceitar maiores'; devolve os originais no fim.
    Usar sempre dentro de respondendo (que garante uma operação por vez)."""
    antes = {k: getattr(f, k) for k in MODOS[modo]}
    antes_aceitar = f.ACEITAR_MAIORES
    for k, v in MODOS[modo].items():
        setattr(f, k, v)
    f.ACEITAR_MAIORES = aceitar
    try:
        yield
    finally:
        for k, v in antes.items():
            setattr(f, k, v)
        f.ACEITAR_MAIORES = antes_aceitar


def acao_atual(url, params):
    """Texto da linha 'Agora:' a partir da API chamada."""
    m = re.search(r"/orgaos/(\d+)/compras/(\d+)/(\d+)(/.*)?$", url)
    compra = f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else ""
    resto = (m.group(4) or "") if m else ""
    if "1_consultarMaterial" in url:
        return f"Compras.gov.br, pesquisa de preço: página {params.get('pagina')} do código {params.get('codigo')}"
    if "1.1_consultarContratacoes" in url:
        return f"Compras.gov.br: procurando no PNCP a compra idCompra {params.get('codigo')}"
    if "/contratacoes/publicacao" in url:
        return (f"PNCP Consultas: compras de {params.get('dataInicial')} a {params.get('dataFinal')}, "
                f"modalidade {params.get('codigoModalidadeContratacao')}, página {params.get('pagina')}")
    if "/api/search" in url:
        return f"Busca do portal PNCP: página {params.get('pagina')}"
    if re.search(r"/itens/\d+/resultados$", resto):
        return f"PNCP: resultado homologado do item {resto.split('/')[2]} da compra {compra}"
    if resto.startswith("/itens"):
        return f"PNCP: itens da compra {compra} (página {params.get('pagina', 1)})"
    if resto == "/arquivos":
        return f"PNCP: lista de arquivos da compra {compra}"
    if resto.startswith("/arquivos/"):
        return f"PNCP: baixando o arquivo {resto.split('/')[2]} da compra {compra}"
    return url


def tempo_fmt(s):
    s = max(0, int(s))
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def situacao(linha, pedidos):
    """atende / a confirmar no TR (algum 'parcial') / não informado / não atende (algum 'não atende')."""
    if not pedidos:
        return "sem atributos"
    s = [str(linha.get(k, "")) for k in pedidos]
    if any(x.startswith("não atende") for x in s):
        return "não atende"
    if any(x.startswith("parcial") for x in s):
        return "a confirmar no TR"
    if all(x.startswith("não informado") or not x for x in s):
        return "não informado"
    return "atende"


def montar_tabela(resumo, csv_bytes):
    """Tabela da busca (bytes do CSV guardados na sessão), ordenada: primeiro quem não tem 'não atende'; 'parcial' = 'a confirmar no TR'."""
    linhas = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"), newline=""), delimiter=";"))
    pedidos = list(resumo.get("pedidos") or {})
    for l in linhas:
        l["situacao"] = situacao(l, pedidos)
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    df["preco_unitario_homologado"] = pd.to_numeric(df["preco_unitario_homologado"], errors="coerce")
    df["_ordem"] = df["situacao"].map(ORDEM).fillna(2)
    df["_n"] = pd.to_numeric(df["atributos_atendidos"].str.split(" ").str[0], errors="coerce").fillna(0)
    return df.sort_values(["_ordem", "_n", "preco_unitario_homologado"], ascending=[True, False, True]).drop(columns=["_ordem", "_n"])


def contar_situacoes(df, atributos, pedidos_val, aceitar):
    """Recalcula a situação de cada linha com ou sem 'aceitar maiores', pelas mesmas descrições (sem consulta nova)."""
    cont = {"atende": 0, "a confirmar no TR": 0, "não informado": 0, "não atende": 0}
    for desc in df["descricao_item"]:
        aval = f.avaliar(str(desc), atributos, pedidos_val, aceitar_maiores=aceitar)[0]
        linha = {k: v[0] for k, v in aval.items()}
        cont[situacao(linha, list(pedidos_val))] += 1
    return cont


def arquivar_busca_atual():
    """A busca da tela vai para o histórico recolhido desta sessão."""
    atual = st.session_state.pop("busca_atual", None)
    if atual:
        st.session_state.setdefault("historico", []).append(atual)


def reabrir_busca(i):
    """Volta uma busca do histórico para a tela; a que estava na tela vai para o histórico."""
    hist = st.session_state.get("historico", [])
    if 0 <= i < len(hist):
        escolhida = hist.pop(i)
        arquivar_busca_atual()
        st.session_state["busca_atual"] = escolhida
        st.session_state.pop("docs", None)


def limpar_produto_anterior():
    """Guarda a busca atual no histórico e apaga o que é do produto anterior (códigos marcados, configuração, código escolhido).
    Não apaga 'contagens' (cache de consultas da sessão)."""
    arquivar_busca_atual()
    for k in list(st.session_state):
        if k in ("pdms", "configs", "docs", "conf_chave", "conf_valor") or k.startswith(("at_", "num_", "cfg_", "tab_pdm_", "sel_cfg_", "perfil_")):
            del st.session_state[k]
    st.session_state["codigo_av"] = ""


def nova_busca():
    """Botão 'Nova busca': guarda a busca atual no histórico e limpa a tela."""
    limpar_produto_anterior()
    st.session_state["termo"] = ""
    st.session_state["uf_busca"] = ""
    st.session_state["aceitar_busca"] = False


# ----------------------------------------------------------------- tela
st.set_page_config(page_title="Referência TIC", layout="wide")
st.title("Referência TIC – busca de compras públicas")
st.caption("Só dados públicos (PNCP e Compras.gov.br). A busca e os filtros são regras fixas, sem IA. "
           "O resultado apoia a decisão; não substitui a pesquisa de preços formal da Lei 14.133/2021.")

produtos = f.ler_produtos()
UNIDADE_TXT = {"GB": "GB", "polegadas": "polegadas", "meses": "meses", "portas": "portas", "MP": "megapixels",
               "m": "metros", "VA": "VA", "minutos": "minutos"}
SEM_REGRAS = "(sem regras de atributos)"


def usar_sugestao(nome):
    """Clique em 'Você quis dizer': troca o termo e procura de novo."""
    st.session_state["termo"] = nome
    st.session_state["procurar_agora"] = True


def usar_config(codigo_item):
    """Botão 'Usar esta configuração': preenche a opção avançada com o item CATMAT."""
    st.session_state["codigo_av"] = str(codigo_item)
    st.session_state["tipo_av"] = "Configuração específica (item CATMAT)"


def baixar_catalogo_na_tela(forcar):
    """Baixa o catálogo de PDMs mostrando o progresso (41 páginas, cerca de 3 min)."""
    barra_cat = st.progress(0.0, text="Baixando o catálogo de materiais")
    agora_cat = st.empty()

    def ao_catalogo(fase, url, params, resultado):
        if fase == "antes":
            agora_cat.markdown(f"**Agora:** Compras.gov.br, catálogo de PDMs: página {params.get('pagina')}")
        elif isinstance(resultado[1], dict):
            tot = resultado[1].get("totalPaginas") or 1
            barra_cat.progress(min(params.get("pagina", 1) / tot, 1.0), text=f"Catálogo: página {params.get('pagina')} de {tot}")

    with respondendo([], ao_catalogo):
        f.baixar_catalogo_pdm(forcar=forcar)
    agora_cat.empty()
    barra_cat.empty()


st.button("Nova busca", on_click=nova_busca, help="Limpa a tela. A busca atual fica em \"Buscas anteriores\", no fim da página.")

# ---------- 1. palavra -> códigos do catálogo (sem IA)
st.subheader("1. O que você procura?")
c1, c2 = st.columns([3, 1])
termo = c1.text_input("O que você procura? (ex.: notebook, laptop, nobreak, monitor 24)", key="termo")
c2.write("")
c2.write("")
procurar = c2.button("Procurar no catálogo") or st.session_state.pop("procurar_agora", False)
if not f.CATALOGO_PDM.exists():
    baixar_catalogo_na_tela(False)  # primeira vez
catalogo_info = f.ler_catalogo_pdm()
c5, c6 = st.columns([3, 1])
c5.caption(f"Catálogo oficial de materiais: {len(catalogo_info):,}".replace(",", ".") + " códigos, atualizado em "
           + f"{catalogo_info[0]['baixado_em'][:16].replace('T', ' ')} (config\\catalogo_pdm.csv).")
if c6.button("Atualizar catálogo", help="Baixa de novo a lista oficial de PDMs: 41 páginas, cerca de 3 minutos."):
    baixar_catalogo_na_tela(True)
    st.session_state.pop("pdms", None)
    st.rerun()

if procurar and termo.strip():
    anterior = st.session_state.get("pdms")
    if not anterior or f.norm(anterior["termo"]) != f.norm(termo):
        limpar_produto_anterior()  # termo novo: o resultado e o código do produto anterior saem sozinhos
    res_busca = f.procurar_tolerante(termo, catalogo_info, limite=15)
    cache_cont = st.session_state.setdefault("contagens", {})
    # compras e configurações: 2 chamadas por código, só os 6 primeiros códigos ativos
    a_contar = [r for r in res_busca["achados"] if r["ativo"]][:6]
    res_busca["da_sessao"] = sum(1 for r in a_contar if r["codigoPdm"] in cache_cont)
    if a_contar:
        barra_it = st.progress(0.0, text="Consultando cada código")
        agora_it = st.empty()
        for i, r in enumerate(a_contar, 1):
            cod = r["codigoPdm"]
            if cod not in cache_cont:
                agora_it.markdown(f"**Agora:** Compras.gov.br: compras e configurações do código {cod} ({r['nomePdm'][:50]})")
                with respondendo([]):
                    cache_cont[cod] = {"compras": f.contar_compras_pdm(cod), "configs": f.contar_itens_pdm(cod)}
            barra_it.progress(i / len(a_contar), text=f"Consultando códigos: {i} de {len(a_contar)}")
        barra_it.empty()
        agora_it.empty()
    st.session_state["pdms"] = {**res_busca, "termo": termo}
    st.session_state.pop("configs", None)

escolhidos = []
pd_state = st.session_state.get("pdms")
if pd_state:
    st.caption(f"Procurado: {pd_state['usada'] or pd_state['termo']}")
    if pd_state.get("corrigido_para"):
        st.info(f"Você digitou \"{pd_state['termo']}\". Mostrando resultados para \"{pd_state['corrigido_para']}\".")
    if pd_state["sugestoes"]:
        st.write("Nenhum código com esse nome exato. Você quis dizer…?")
        cols_sug = st.columns(min(len(pd_state["sugestoes"]), 5))
        for col, nome in zip(cols_sug, pd_state["sugestoes"]):
            col.button(nome[:34], key=f"sug_{nome}", on_click=usar_sugestao, args=(nome,), help=nome)
    if pd_state["achados"]:
        cont = st.session_state.get("contagens", {})
        if pd_state.get("da_sessao"):
            st.caption(f"{pd_state['da_sessao']} contagem(ns) abaixo vieram da sessão (consultadas numa busca anterior; não foram refeitas agora).")

        def cont_txt(codigo, campo):
            """Contagem como texto; só os 6 primeiros códigos ativos são consultados."""
            v = cont.get(codigo, {}).get(campo)
            return "não consultado" if v is None else f"{int(v):,}".replace(",", ".")

        tab = pd.DataFrame([{"usar": False, "código": int(r["codigoPdm"]), "nome": r["nomePdm"],
                             "compras nos últimos 12 meses": cont_txt(r["codigoPdm"], "compras"),
                             "configurações no catálogo": cont_txt(r["codigoPdm"], "configs"),
                             "situação": "ativo" if r["ativo"] else "desativado",
                             "tipo": "acessório / outra coisa?" if r["acessorio"] else "produto",
                             "classe": r["nomeClasse"]} for r in pd_state["achados"]])
        estilo = tab.style.apply(lambda l: ["color: #8a8a8a" if l["situação"] == "desativado" else "" for _ in l], axis=1)
        editado = st.data_editor(estilo, hide_index=True, width="stretch", disabled=[c for c in tab.columns if c != "usar"],
                                 column_config={"usar": st.column_config.CheckboxColumn("usar", help="Marque 1 ou mais códigos"),
                                                "compras nos últimos 12 meses": st.column_config.TextColumn(help="Registros de item comprado na pesquisa de preço do Compras.gov.br. Só os 6 primeiros códigos ativos são consultados."),
                                                "configurações no catálogo": st.column_config.TextColumn(help="Quantos itens CATMAT o código tem. Só os 6 primeiros códigos ativos são consultados.")},
                                 key=f"tab_pdm_{pd_state['termo']}")
        escolhidos = [int(c) for c in editado.loc[editado["usar"], "código"]]
        st.write(f"Códigos marcados: {', '.join(map(str, escolhidos)) or 'nenhum (marque na coluna usar)'}")
        st.caption("Códigos marcados são os tipos de produto (PDM) que o botão Buscar vai consultar, todos de uma vez numa tabela só. "
                   "Com 0 marcados (e nenhum código digitado na opção avançada), o Buscar não consulta nada e pede que você escolha um código. "
                   "\"não consultado\" na tabela: o código está desativado ou vem depois do sexto código ativo da lista; só os 6 primeiros ativos têm as contagens consultadas.")
        if any(not r["ativo"] for r in pd_state["achados"]):
            st.caption("Em cinza: código desativado no catálogo. Pode ter compras antigas, mas não é o código atual do produto.")
        marcados_inativos = [r["codigoPdm"] for r in pd_state["achados"] if not r["ativo"] and int(r["codigoPdm"]) in escolhidos]
        if marcados_inativos:
            st.warning(f"Você marcou código desativado: {', '.join(marcados_inativos)}.")

        # ---------- ver as configurações (itens CATMAT) de um código
        with st.expander("Ver configurações (itens CATMAT) de um código"):
            nomes_cod = {int(r["codigoPdm"]): r["nomePdm"] for r in pd_state["achados"]}
            cod_cfg = st.selectbox("Código", list(nomes_cod), format_func=lambda c: f"{c} – {nomes_cod[c]}")
            if st.button("Ver configurações"):
                agora_cfg = st.empty()
                agora_cfg.markdown(f"**Agora:** Compras.gov.br: configurações do código {cod_cfg}")
                with st.spinner(f"Carregando as configurações do código {cod_cfg} (Compras.gov.br)..."), respondendo([]):
                    st.session_state["configs"] = {"codigo": cod_cfg, "itens": f.itens_do_pdm(cod_cfg)}
                agora_cfg.empty()
            cfg = st.session_state.get("configs")
            if cfg and cfg["codigo"] == cod_cfg:
                perfil_cfg = f.perfil_do_pdm(cod_cfg, nomes_cod[cod_cfg], produtos)
                filtro_txt = st.text_input("Filtrar pelo texto da descrição", key=f"cfg_txt_{cod_cfg}")
                pedidos_cfg = {}
                if perfil_cfg:
                    st.write(f"Filtrar pelos atributos ({perfil_cfg}); ficam de fora os que dão \"não atende\":")
                    cols_cfg = st.columns(len(produtos[perfil_cfg]))
                    for col, a in zip(cols_cfg, produtos[perfil_cfg]):
                        v = col.text_input(f"{a['nome']} ({UNIDADE_TXT.get(a['unidade'], a['unidade'])})", key=f"cfg_{cod_cfg}_{a['nome']}")
                        try:
                            if v.strip():
                                pedidos_cfg[a["nome"]] = f.ler_valor(v)
                        except ValueError:
                            st.warning(f"{a['nome']}: valor ignorado (não é número).")
                linhas_cfg = []
                for it in cfg["itens"]:
                    if filtro_txt.strip() and f.norm(filtro_txt) not in f.norm(it["descricaoItem"]):
                        continue
                    aval = {}
                    if pedidos_cfg:
                        aval = f.avaliar(it["descricaoItem"], produtos[perfil_cfg], pedidos_cfg)[0]
                        if any(x[0].startswith("não atende") for x in aval.values()):
                            continue
                    linhas_cfg.append({"item CATMAT": it["codigoItem"], "descrição": it["descricaoItem"],
                                       "situação": "ativo" if it["ativo"] else "desativado",
                                       "avaliação": " · ".join(f"{k} {x[0]}" for k, x in aval.items())})
                st.write(f"{len(linhas_cfg)} de {len(cfg['itens'])} configurações.")
                if linhas_cfg:
                    df_cfg = pd.DataFrame(linhas_cfg)
                    # a chave inclui as linhas mostradas: o Streamlit não zera a seleção quando a lista muda (posição antiga → IndexError)
                    chave_sel = zlib.crc32("|".join(map(str, df_cfg["item CATMAT"])).encode("utf-8"))
                    sel = st.dataframe(df_cfg, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key=f"sel_cfg_{cod_cfg}_{chave_sel}")
                    linhas_sel = sel.selection.rows if sel and sel.selection else []
                    if linhas_sel:
                        cod_item = df_cfg.iloc[linhas_sel[0]]["item CATMAT"]
                        # sem rede aqui: só preenche o campo da opção avançada (abaixo), uma vez por escolha
                        if st.session_state.get("cfg_aplicada") != (cod_cfg, str(cod_item)):
                            usar_config(cod_item)
                            st.session_state["cfg_aplicada"] = (cod_cfg, str(cod_item))
                        st.write("Código da configuração escolhida (ícone à direita copia):")
                        st.code(str(cod_item), language=None)
                        st.caption("Esta configuração já foi carregada na opção avançada, logo abaixo.")
                    else:
                        st.caption("Clique na caixa à esquerda de uma linha para escolher a configuração.")
    else:
        st.warning(f"Nada encontrado no catálogo para \"{pd_state['termo']}\"."
                   + ("" if pd_state["sugestoes"] else " Nenhum termo parecido.")
                   + " Você pode incluir um sinônimo em config\\sinonimos.csv.")

with st.expander("Opção avançada: digitar o código do catálogo", expanded=bool(st.session_state.get("codigo_av"))):
    codigo = st.text_input("Código (só números; se preenchido, substitui os códigos marcados acima)", key="codigo_av")
    tipo_cod = st.radio("O código é", ["Tipo de produto (PDM) – todos os modelos", "Configuração específica (item CATMAT)"], index=0, key="tipo_av")
    conferido = None
    if codigo.strip().isdigit():
        eh_pdm = tipo_cod.startswith("Tipo de produto")
        chave_conf = (codigo.strip(), eh_pdm)
        if st.session_state.get("conf_chave") != chave_conf:
            with st.spinner(f"Conferindo o código {codigo.strip()} no catálogo (Compras.gov.br)..."), respondendo([]):
                st.session_state["conf_valor"] = f.conferir_tipo_codigo(codigo.strip(), eh_pdm, catalogo_info)
            st.session_state["conf_chave"] = chave_conf
        conferido = st.session_state["conf_valor"]
        if conferido["aviso"]:
            st.warning(conferido["aviso"])
        else:
            st.success(f"Código {codigo.strip()}: {conferido['nome']}")
    elif codigo.strip():
        st.error("O código do catálogo deve ter só números.")

# ---------- 2. regras e atributos (o perfil vem do código escolhido)
st.subheader("2. Atributos e busca")
perfil_auto = None
if conferido and conferido.get("codigo_pdm"):
    perfil_auto = f.perfil_do_pdm(conferido["codigo_pdm"], conferido["nome_pdm"], produtos)
elif escolhidos:
    r0 = next(r for r in pd_state["achados"] if int(r["codigoPdm"]) == escolhidos[0])
    perfil_auto = f.perfil_do_pdm(r0["codigoPdm"], r0["nomePdm"], produtos)
opcoes_perfil = [SEM_REGRAS, *produtos]
perfil_txt = st.selectbox("Regras de atributos (vêm do código; config\\produtos.csv)", opcoes_perfil,
                          index=opcoes_perfil.index(perfil_auto) if perfil_auto else 0, key=f"perfil_{perfil_auto}")
produto = None if perfil_txt == SEM_REGRAS else perfil_txt
if not produto:
    st.warning("Sem regras de atributos para este código: a busca traz preços e links, mas não avalia atributos."
               if (escolhidos or conferido) else "Marque um código para ver os atributos.")
atributos_tela = produtos[produto] if produto else []

# número digitado na busca ('monitor 24'): preenche o atributo ou avisa (uma vez por termo e perfil)
if pd_state and (escolhidos or conferido):
    preench, avisos_num = f.atribuir_numeros(pd_state["termo"], atributos_tela)
    chave_num = f"num_{pd_state['termo']}_{produto}"
    if not st.session_state.get(chave_num):
        for nome, valor in preench.items():
            st.session_state[f"at_{produto}_{nome}"] = valor
        st.session_state[chave_num] = True
    for nome, valor in preench.items():
        st.info(f"Da sua busca: {nome} = {valor}. Você pode mudar abaixo.")
    for av in avisos_num:
        st.warning(av)

with st.form("entrada"):
    c3, c4 = st.columns([1, 2])
    modo = c3.radio("Modo", ["rápido", "completo"], index=0, help=f"Rápido: menos páginas e consultas (amostra menor); só {MODOS['rápido']['MAX_VINCULOS']} compras são ligadas ao PNCP. Completo: liga até {MODOS['completo']['MAX_VINCULOS']}.")
    uf = c4.text_input("UF (vazio = todas)", key="uf_busca")
    valores = {}
    if atributos_tela:
        st.write("Atributos (deixe vazio o que não importa):")
        cols = st.columns(len(atributos_tela))
        for col, a in zip(cols, atributos_tela):
            un = UNIDADE_TXT.get(a["unidade"], a["unidade"])
            valores[a["nome"]] = col.text_input(f"{a['nome']} – só o número, em {un}", key=f"at_{produto}_{a['nome']}",
                                                help=f"Faixa aceita: {a['regra']} (x = valor digitado)"
                                                     + (". Aceita também 960G, 1TB, 1 T." if a["unidade"] == "GB" else ""))
    aceitar = st.checkbox("Aceitar valores maiores que o pedido (RAM, armazenamento, garantia)", key="aceitar_busca",
                          help="Sem a opção vale a faixa do produtos.csv (ex.: RAM 16 aceita de 16 a 32). Com a opção, não há teto: 64 GB também atende.")
    st.caption("Os atributos, a UF, o modo e a opção acima só valem quando você clica em Buscar.")
    buscar = st.form_submit_button("Buscar", type="primary")

area_resultado = st.empty()  # o resumo e a tabela ficam aqui: uma nova busca limpa esta área na hora

if buscar:
    with st.spinner("Passo 0: conferência offline antes de qualquer consulta..."), respondendo([]):  # trava do servidor: ACEITAR_MAIORES é do módulo, compartilhado entre sessões
        erros = f.autoteste()  # preflight offline antes de qualquer chamada de rede
    if erros:
        st.error(f"Preflight offline falhou; nenhuma chamada de rede foi feita: {erros}")
        st.stop()
    if codigo.strip():
        if not codigo.strip().isdigit():
            st.error("O código do catálogo deve ter só números.")
            st.stop()
        codigos = [(codigo.strip(), "2" if tipo_cod.startswith("Tipo de produto") else "1")]
    else:
        codigos = [(str(c), "2") for c in escolhidos]  # PDM: todos os modelos
    if not codigos:
        st.error("Escolha pelo menos 1 código: procure no passo 1 e marque \"usar\", ou digite na opção avançada.")
        st.stop()
    attrs = [valores[a["nome"]] for a in atributos_tela]
    etapas = ["1. Catálogo (Compras.gov.br)", "2. Filtros de atributos", "3. Ligação ao PNCP"]
    with area_resultado.container():
        painel = st.status("Consultando: preparando a busca", expanded=True)
        with painel:
            barras = {e: st.progress(0.0, text=f"{e}: aguardando") for e in etapas}
            agora = st.empty()
            relogio = st.empty()
    inicio = time.time()
    lim = MODOS[modo]
    resumos, logs = [], []

    def eta(ini, feito, total):
        """Tempo restante estimado pela média por chamada já feita."""
        if not ini or not feito or not total or feito >= total:
            return ""
        return f" · faltam ~{tempo_fmt((time.time() - ini) / feito * (total - feito))}"

    for n_cod, (cod, tipo) in enumerate(codigos, 1):
        prefixo = f"código {cod} ({n_cod} de {len(codigos)}) · " if len(codigos) > 1 else ""
        respostas = [cod, tipo, produto or "", *attrs, uf]
        est = {"e1_feito": 0, "e1_total": None, "e1_ini": None, "ids": set(), "lig_feito": 0, "e3_ini": None, "e3_chamadas": 0}

        def ao_chamar(fase, url, params, resultado):
            """Antes da chamada: mostra a ação em 'Agora:'. Depois: atualiza 'feito de total', % e tempo restante."""
            listagem = "1_consultarMaterial" in url
            if fase == "antes":
                agora.markdown(f"**Agora:** {prefixo}{acao_atual(url, params)}")
                painel.update(label=f"Consultando: {prefixo}{acao_atual(url, params)}"[:120])
                if listagem and est["e1_ini"] is None:
                    est["e1_ini"] = time.time()
                if not listagem and est["e3_ini"] is None:  # entrou na etapa 3: etapas 1 e 2 já terminaram
                    est["e3_ini"] = time.time()
                    barras[etapas[0]].progress(1.0, text=f"{etapas[0]}: 100% · {prefixo}{est['e1_feito']} de {est['e1_feito']} páginas")
                    barras[etapas[1]].progress(1.0, text=f"{etapas[1]}: 100% · feitos localmente, sem consulta à API (resultado no fim)")
                relogio.write(f"Tempo decorrido: {tempo_fmt(time.time() - inicio)}")
                return
            js = resultado[1]
            if listagem:
                est["e1_feito"] += 1
                if isinstance(js, dict):
                    if est["e1_total"] is None and js.get("totalRegistros") is not None:
                        est["e1_total"] = min(-(-int(js["totalRegistros"]) // 100), lim["MAX_PAGINAS_CATALOGO"]) or 1
                    est["ids"].update(str(r.get("idCompra")) for r in js.get("resultado", []) if r.get("idCompra"))
                    if not js.get("paginasRestantes"):
                        est["e1_total"] = est["e1_feito"]
                total = est["e1_total"]
                pct = min(est["e1_feito"] / total, 1.0) if total else 0.0
                barras[etapas[0]].progress(pct, text=f"{etapas[0]}: {pct:.0%} · {prefixo}{est['e1_feito']} de {total or '?'} páginas"
                                                       f"{eta(est['e1_ini'], est['e1_feito'], total)}")
            else:
                est["e3_chamadas"] += 1
                if "1.1_consultarContratacoes" in url:
                    est["lig_feito"] += 1
                total = min(len(est["ids"]), lim["MAX_VINCULOS"]) or lim["MAX_VINCULOS"]
                feito = est["lig_feito"]
                pct = min(feito / total, 1.0) if total else 0.0
                barras[etapas[2]].progress(pct, text=f"{etapas[2]}: {pct:.0%} · {prefixo}{feito} de {total} compras procuradas no PNCP · "
                                                       f"validação: {est['e3_chamadas'] - feito} chamadas{eta(est['e3_ini'], feito, total)}")
            relogio.write(f"Tempo decorrido: {tempo_fmt(time.time() - inicio)}")

        with respondendo(respostas, ao_chamar) as log, limites(modo, aceitar):
            f.buscar_por_codigo()
            resumos.append(json.loads((f.SAIDA / "ultima_busca.json").read_text(encoding="utf-8")))
        logs.append(log.getvalue())
    with respondendo([]):
        resumo_fim = f.juntar_buscas(resumos)  # vários códigos: uma tabela só
        csv_fim = Path(resumo_fim["arquivo"]).read_bytes()
    # guarda na sessão: quem busca vê só as próprias buscas; a anterior vai para o histórico recolhido
    df_fim = montar_tabela(resumo_fim, csv_fim)
    na_api = resumo_fim.get("registros_informados_pela_api")
    lidos = resumo_fim.get("registros_lidos") or 0
    parecidos = 0 if df_fim.empty else int((df_fim["situacao"] != "não atende").sum())
    fim_txt = (f"{na_api:,} na API → {lidos:,} lidos → {len(df_fim):,} no período de 12 meses → {parecidos:,} parecidos (sem 'não atende')"
               .replace(",", ".") if na_api else f"{len(df_fim)} linhas")
    painel.update(label="Consulta concluída", state="complete")
    arquivar_busca_atual()
    st.session_state["busca_atual"] = {"resumo": resumo_fim, "csv": csv_fim, "quando": time.strftime("%d/%m %H:%M"), "aceitar": aceitar,
                                       "fim_txt": fim_txt, "log": "\n".join(logs), "tempo": time.time() - inicio,
                                       "codigos": ", ".join(c for c, _ in codigos), "termo": termo,
                                       "eh_item": any(t == "1" for _, t in codigos)}
    st.session_state.pop("docs", None)
    st.rerun()

rec = st.session_state.get("busca_atual")
with area_resultado.container():
    if not rec:
        st.info("Nenhuma busca nesta sessão. Procure, marque um código, preencha os atributos e clique em Buscar.")
    else:
        resumo = rec["resumo"]
        df = montar_tabela(resumo, rec["csv"])
        pedidos_val = resumo.get("pedidos") or {}
        pedidos = list(pedidos_val)

        # ---------- resumo
        st.subheader("Resumo da busca")
        if "PORTAL FORA" in rec["log"]:
            st.warning("O portal caiu ou bloqueou durante a busca. O que já tinha sido lido foi salvo.")
        total = len(df)
        contagem = df["situacao"].value_counts() if total else pd.Series(dtype=int)
        vinc = int((df["link_publico"].fillna("") != "").sum()) if total else 0
        susp = int((df.get("observacao_preco", pd.Series(dtype=str)).fillna("") == "preço suspeito").sum()) if total else 0
        m = st.columns(6)
        m[0].metric("Total", total)
        m[1].metric("Não atende", int(contagem.get("não atende", 0)))
        m[2].metric("Parcial (a confirmar no TR)", int(contagem.get("a confirmar no TR", 0)))
        m[3].metric("Vinculados ao PNCP (linhas)", vinc)
        m[4].metric("Preço suspeito", susp)
        m[5].metric("Tempo", f"{rec['tempo']:.0f} s")
        usados = " · ".join(f"{k} {v:g}" for k, v in pedidos_val.items()) or "nenhum"
        st.caption(f"Busca de {rec['quando']} · código(s) {rec['codigos']} · atributos usados: {usados} · aceitar valores maiores: "
                   f"{'sim' if rec['aceitar'] else 'não'} · {rec['fim_txt']} · chamadas: {resumo.get('chamadas')} · falhas: {resumo.get('falhas')}")
        # efeito da opção 'aceitar valores maiores' (recalculado com as mesmas descrições, sem nova consulta)
        atrs_res = produtos.get(resumo.get("produto") or "", [])
        aplicaveis = [k for k in pedidos if f.norm(k) in f.ATRIBUTOS_ACEITA_MAIOR]
        if total and atrs_res and aplicaveis:
            sem = contar_situacoes(df, atrs_res, pedidos_val, False)
            com = contar_situacoes(df, atrs_res, pedidos_val, True)
            st.info(f"Efeito de \"aceitar valores maiores\" ({', '.join(aplicaveis)}) nestas {total} linhas: "
                    f"sem a opção, {sem['não atende']} não atendem, {sem['a confirmar no TR']} parciais e {sem['atende']} atendem; "
                    f"com a opção, {com['não atende']} não atendem, {com['a confirmar no TR']} parciais e {com['atende']} atendem.")
        with st.expander("Mensagens da busca"):
            st.text(rec["log"] or "(sem mensagens)")

        if not total and rec.get("eh_item"):
            st.info("Nenhuma compra homologada encontrada nos últimos 12 meses neste código.")

        if total:
            # ---------- tabela
            st.subheader("Resultados (primeiro quem não tem 'não atende')")
            SEM_LINK = {"sem PNCP": "sem link: compra não encontrada no PNCP",
                        "não verificado": "não verificado: limite de consultas",
                        "falhou": "falhou: sem resposta da API (não é conclusão sobre a compra)"}
            ROTULO_CURTO = {"armazenamento": "SSD"}  # o pedido de armazenamento é de SSD (ver ferramenta.avaliar_armazenamento)

            def coluna_compra_item(l):
                """'compra 144/2026 – item 42'; sem link, o motivo (texto comum, sem cor de link)."""
                if str(l.get("link_publico") or "").startswith("http"):
                    return f"compra {l.get('sequencial')}/{l.get('ano')} – item {l.get('numero_item')}"
                return SEM_LINK.get(str(l.get("situacao_pncp") or ""), "sem link: compra não encontrada no PNCP")

            def coluna_avaliacao(l):
                """Quais atributos foram avaliados e como: 'RAM parcial · SSD atende · tela parcial'."""
                partes = []
                for k in pedidos:
                    s = str(l.get(k) or "não informado")
                    sit = "não atende (só HDD)" if "só HDD" in s else s.split(" (")[0]
                    partes.append(f"{ROTULO_CURTO.get(k, k)} {sit}")
                return " · ".join(partes)

            def coluna_estimado(l):
                """Valor estimado do item no PNCP (só nas linhas ligadas ao PNCP)."""
                v = pd.to_numeric(l.get("valor_estimado_pncp"), errors="coerce")
                if pd.isna(v):
                    return "não verificado" if not str(l.get("link_publico") or "").startswith("http") else "não informado"
                return f"R$ {v:.2f}"

            def coluna_diferenca(l):
                v = pd.to_numeric(l.get("valor_estimado_pncp"), errors="coerce")
                h = l.get("preco_unitario_homologado")
                return "" if pd.isna(v) or not v or pd.isna(h) else f"{h / v - 1:+.0%}"

            df["compra_item"] = df.apply(coluna_compra_item, axis=1)
            df["avaliacao"] = df.apply(coluna_avaliacao, axis=1) if pedidos else ""
            df["estimado"] = df.apply(coluna_estimado, axis=1)
            df["dif_estimado"] = df.apply(coluna_diferenca, axis=1)
            df["abrir"] = df["link_publico"].where(df["link_publico"].fillna("").str.startswith("http"), "")
            mostrar = ["linha", "situacao", "avaliacao", "compra_item", "abrir", "estimado", "preco_unitario_homologado", "dif_estimado",
                       "observacao_preco", *pedidos, "data_resultado", "orgao", "uf", "descricao_item"]
            mostrar = [c for c in mostrar if c in df.columns]
            st.dataframe(df[mostrar], hide_index=True, width="stretch",
                         column_config={"avaliacao": st.column_config.TextColumn("avaliação", help="cada atributo pedido e o resultado"),
                                        "compra_item": st.column_config.TextColumn("compra e item no PNCP"),
                                        "abrir": st.column_config.LinkColumn("PNCP", display_text="abrir"),
                                        "estimado": st.column_config.TextColumn("preço estimado", help="Valor unitário estimado do item no PNCP (só linhas ligadas ao PNCP)."),
                                        "preco_unitario_homologado": st.column_config.NumberColumn("preço homologado", format="R$ %.2f"),
                                        "dif_estimado": st.column_config.TextColumn("homologado × estimado")})
            if (df["situacao_pncp"].fillna("") == "não verificado").any() if "situacao_pncp" in df.columns else False:
                st.caption(f"Limite de consultas: no modo rápido só {MODOS['rápido']['MAX_VINCULOS']} compras são ligadas ao PNCP; as outras ficam como "
                           f"\"não verificado\" (não quer dizer que não existam no PNCP). O modo completo liga mais: até {MODOS['completo']['MAX_VINCULOS']} compras.")
            st.download_button("Baixar CSV (ordem desta tela)", df.drop(columns=["abrir"]).to_csv(sep=";", index=False).encode("utf-8-sig"),
                               file_name=Path(resumo["arquivo"]).name.replace(".csv", "_tela.csv"), mime="text/csv")

            # ---------- linha escolhida
            st.subheader("Documentos e texto para IA")
            opcoes = df["linha"].tolist()
            escolha = st.selectbox("Linha", opcoes, format_func=lambda n: f"{n} – " + str(df.loc[df["linha"] == n, "orgao"].iloc[0])[:50]
                                   + " – " + str(df.loc[df["linha"] == n, "descricao_item"].iloc[0])[:60])
            outros = st.checkbox("Baixar também propostas, atas e despachos (podem ser dezenas de arquivos grandes)", value=False)
            if st.button("Baixar documentos da linha"):
                barra_doc = st.progress(0.0, text="Documentos: aguardando a lista de arquivos")
                agora_doc = st.empty()
                dl = {"total": None, "feito": 0, "ini": time.time()}

                def ao_baixar(fase, url, params, resultado):
                    """Mostra o arquivo atual e 'feito de total' no download (o total vem da lista de arquivos do PNCP)."""
                    if fase == "antes":
                        agora_doc.markdown(f"**Agora:** {acao_atual(url, params)}")
                        return
                    if url.endswith("/arquivos") and isinstance(resultado[1], list):
                        ativos = [a for a in resultado[1] if a.get("statusAtivo") is not False]
                        dl["total"] = len(ativos) if outros else sum(1 for a in ativos if f.eh_principal(a))  # mesma regra da opção 3
                    elif re.search(r"/arquivos/\d+$", url) or "pncp-api" in url:
                        dl["feito"] += 1
                    if dl["total"]:
                        pct = min(dl["feito"] / dl["total"], 1.0)
                        resta = f" · faltam ~{tempo_fmt((time.time() - dl['ini']) / dl['feito'] * (dl['total'] - dl['feito']))}" if 0 < dl["feito"] < dl["total"] else ""
                        barra_doc.progress(pct, text=f"Documentos: {pct:.0%} · {dl['feito']} de {dl['total']} arquivos{resta}")

                with respondendo([escolha, "s" if outros else "n"], ao_baixar) as log:
                    (f.SAIDA / "busca_tela_atual.csv").write_bytes(rec["csv"])  # a opção 3 lê a busca mais recente: a que está na tela
                    f.opcao_3_baixar()
                agora_doc.markdown("**Agora:** download concluído")
                texto = log.getvalue()
                m_dest = re.search(r"Documentos em: (.+)", texto)
                st.session_state["docs"] = {"linha": escolha, "pasta": m_dest.group(1).strip() if m_dest else "", "log": texto}

            docs = st.session_state.get("docs")
            if docs and docs["linha"] == escolha:
                if not docs["pasta"]:
                    st.warning(docs["log"].strip() or "Nada foi baixado.")
                else:
                    pasta = Path(docs["pasta"])
                    arquivos = [p for p in sorted(pasta.rglob("*")) if p.is_file() and not p.name.startswith("_lista")]
                    st.write(f"Pasta: `{pasta}`")
                    st.dataframe(pd.DataFrame([{"arquivo": str(p.relative_to(pasta)), "tamanho (KB)": round(p.stat().st_size / 1024)} for p in arquivos]),
                                 hide_index=True, width="stretch")
                    pdfs = [p for p in arquivos if p.suffix.lower() in f.EXTENSOES_RECORTE]  # PDF e Word
                    if pdfs:
                        pdf = st.selectbox("Documento para recortar: PDF ou Word (de preferência o TR)", pdfs, format_func=lambda p: p.name,
                                           index=next((i for i, p in enumerate(pdfs) if re.search(r"termo|\btr\b", f.norm(p.name))), 0))
                        if st.button("Gerar texto para IA"):
                            item = resumo.get("produto") or resumo.get("nome_no_catalogo") or produto or termo  # item pedido no recorte
                            with st.spinner("Recortando as páginas do item..."):
                                with respondendo([]):
                                    posicao = f.documentos_recortaveis().index(pdf) + 1  # mesma lista da opção 4
                                with respondendo([posicao, item]) as log4:
                                    f.opcao_4_recortar()
                                m_rec = re.search(r"Recorte salvo em: (.+)", log4.getvalue())
                                m_av = re.search(r"Aviso: ((?:Word|Convertido).+)", log4.getvalue())
                                if m_av:
                                    st.info(m_av.group(1))
                                if not m_rec:
                                    m_nao = re.search(r"Não foi possível recortar: (.+)", log4.getvalue())
                                    st.error(m_nao.group(1) if m_nao else log4.getvalue())
                                    st.stop()
                                with respondendo([]):
                                    recs = sorted((f.SAIDA / "recortes").glob("*/recorte.txt"))  # mesma lista da opção 5
                                with respondendo([recs.index(Path(m_rec.group(1).strip())) + 1]) as log5:
                                    f.opcao_5_texto_ia()
                            m_ia = re.search(r"Pronto para colar: (.+?)\s+\(", log5.getvalue())
                            if m_ia:
                                alvo = Path(m_ia.group(1))
                                texto_ia = alvo.read_text(encoding="utf-8")
                                st.success(f"Pronto: `{alvo}` (~{len(texto_ia) // 4:,} tokens). Copie e cole na IA; a resposta é rascunho para conferência humana.")
                                st.download_button("Baixar o .txt", texto_ia.encode("utf-8"), file_name=alvo.name, mime="text/plain")
                                st.text_area("Texto para colar na IA", texto_ia, height=300)
                            else:
                                st.error(log5.getvalue())
                    else:
                        st.info("Nenhum PDF ou documento Word entre os arquivos baixados.")

# ---------- buscas anteriores desta sessão (recolhidas); outras pessoas não veem
historico = st.session_state.get("historico", [])
with st.expander(f"Buscas anteriores nesta sessão ({len(historico)})"):
    if not historico:
        st.caption("Ao fazer uma nova busca, a anterior fica guardada aqui. Cada pessoa vê só as próprias buscas.")
    for i, h in enumerate(reversed(historico)):
        c_h1, c_h2, c_h3 = st.columns([4, 1, 1])
        c_h1.write(f"{h['quando']} · código(s) {h['codigos']} · {h.get('termo') or ''} · {h['fim_txt']}")
        c_h2.button("Reabrir", key=f"reabrir_{i}", on_click=reabrir_busca, args=(len(historico) - 1 - i,))
        c_h3.download_button("CSV", h["csv"], file_name=Path(h["resumo"]["arquivo"]).name, mime="text/csv", key=f"csv_hist_{i}")

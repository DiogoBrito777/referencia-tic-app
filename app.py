"""Referência TIC – tela (Streamlit) por cima do ferramenta.py.

Não duplica a lógica: chama as mesmas funções do menu (buscar_por_codigo, buscar_por_nome, opcao_3_baixar,
opcao_4_recortar, opcao_5_texto_ia), respondendo às perguntas delas automaticamente com o que foi digitado na tela.
Só GET público (PNCP e Compras.gov.br), sem login e sem chave. Para abrir: streamlit run app.py.
"""
import contextlib
import csv
import io
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ferramenta as f  # noqa: E402

# modo rápido = menos páginas e menos consultas (mais rápido, amostra menor); completo = limites do ferramenta.py
MODOS = {"rápido": {"MAX_PAGINAS_CATALOGO": 3, "MAX_VINCULOS": 10, "MAX_RESULTADOS": 10, "MAX_COMPRAS": 10},
         "completo": {"MAX_PAGINAS_CATALOGO": f.MAX_PAGINAS_CATALOGO, "MAX_VINCULOS": f.MAX_VINCULOS,
                      "MAX_RESULTADOS": f.MAX_RESULTADOS, "MAX_COMPRAS": f.MAX_COMPRAS}}
ORDEM = {"atende": 0, "a confirmar no TR": 1, "não informado": 2, "sem atributos": 2, "não atende": 3}


# ----------------------------------------------------------------- ponte com o ferramenta.py
@contextlib.contextmanager
def respondendo(respostas, ao_chamar=None):
    """Durante o bloco, as perguntas do ferramenta.py recebem as respostas da lista (em ordem; vazia = Enter),
    o que ele imprime fica guardado em texto e cada chamada de rede avisa a barra de progresso."""
    fila = list(respostas)
    originais = (f.pergunta, f.escolher_numero, f.get)

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
    saida = io.StringIO()
    try:
        with contextlib.redirect_stdout(saida):
            yield saida
    finally:
        f.pergunta, f.escolher_numero, f.get = originais


@contextlib.contextmanager
def limites(modo):
    """Aplica os limites do modo rápido/completo e devolve os originais no fim."""
    antes = {k: getattr(f, k) for k in MODOS[modo]}
    for k, v in MODOS[modo].items():
        setattr(f, k, v)
    try:
        yield
    finally:
        for k, v in antes.items():
            setattr(f, k, v)


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


def carregar_ultima():
    """Lê o resumo (ultima_busca.json) e o CSV que o ferramenta.py salvou."""
    resumo_arq = f.SAIDA / "ultima_busca.json"
    if not resumo_arq.exists():
        return None, None
    resumo = json.loads(resumo_arq.read_text(encoding="utf-8"))
    arq = f.SAIDA / Path(resumo["arquivo"]).name  # sempre nesta pasta (o resumo pode ter vindo de uma cópia)
    resumo["arquivo"] = str(arq)
    if not arq.exists():
        return resumo, None
    with arq.open(encoding="utf-8-sig", newline="") as fh:
        linhas = list(csv.DictReader(fh, delimiter=";"))
    pedidos = list(resumo.get("pedidos") or {})
    for l in linhas:
        l["situacao"] = situacao(l, pedidos)
    df = pd.DataFrame(linhas)
    if df.empty:
        return resumo, df
    df["preco_unitario_homologado"] = pd.to_numeric(df["preco_unitario_homologado"], errors="coerce")
    df["_ordem"] = df["situacao"].map(ORDEM).fillna(2)
    df["_n"] = pd.to_numeric(df["atributos_atendidos"].str.split(" ").str[0], errors="coerce").fillna(0)
    df = df.sort_values(["_ordem", "_n", "preco_unitario_homologado"], ascending=[True, False, True]).drop(columns=["_ordem", "_n"])
    return resumo, df


# ----------------------------------------------------------------- tela
st.set_page_config(page_title="Referência TIC", layout="wide")
st.title("Referência TIC – busca de compras públicas")
st.caption("Só dados públicos (PNCP e Compras.gov.br). A busca e os filtros são regras fixas, sem IA. "
           "O resultado apoia a decisão; não substitui a pesquisa de preços formal da Lei 14.133/2021.")

produtos = f.ler_produtos()
UNIDADE_TXT = {"GB": "GB", "polegadas": "polegadas", "meses": "meses", "portas": "portas", "MP": "megapixels",
               "m": "metros", "VA": "VA", "minutos": "minutos"}

# ---------- 1. palavra -> códigos do catálogo (sem IA)
st.subheader("1. O que você procura?")
c1, c2 = st.columns([3, 1])
termo = c1.text_input("O que você procura? (ex.: notebook, laptop, nobreak, monitor 24)", key="termo")
c2.write("")
c2.write("")
procurar = c2.button("Procurar no catálogo")
if procurar and termo.strip():
    if not f.CATALOGO_PDM.exists():  # primeira vez: baixa a lista oficial de PDMs (41 páginas, ~3 min)
        barra_cat = st.progress(0.0, text="Baixando o catálogo de materiais (uma vez só)")
        agora_cat = st.empty()

        def ao_catalogo(fase, url, params, resultado):
            if fase == "antes":
                agora_cat.markdown(f"**Agora:** Compras.gov.br, catálogo de PDMs: página {params.get('pagina')}")
            elif isinstance(resultado[1], dict):
                tot = resultado[1].get("totalPaginas") or 1
                barra_cat.progress(min(params.get("pagina", 1) / tot, 1.0), text=f"Catálogo: página {params.get('pagina')} de {tot}")

        with respondendo([], ao_catalogo):
            f.baixar_catalogo_pdm()
    catalogo = f.ler_catalogo_pdm()
    achados, usada, numeros = f.procurar_pdm(termo, catalogo, limite=15)
    contagem = {}
    if achados:
        barra_it = st.progress(0.0, text="Contando os itens de cada código")
        for i, r in enumerate(achados[:8], 1):  # quantos itens: 1 chamada por código (só os 8 primeiros)
            with respondendo([]):
                contagem[r["codigoPdm"]] = f.contar_itens_pdm(r["codigoPdm"])
            barra_it.progress(i / min(len(achados), 8), text=f"Contando itens: {i} de {min(len(achados), 8)} códigos")
    st.session_state["pdms"] = {"termo": termo, "achados": achados, "usada": usada, "numeros": numeros, "contagem": contagem,
                                "sugestoes": [] if achados else f.sugerir_termos(termo, catalogo),
                                "baixado_em": catalogo[0]["baixado_em"] if catalogo else ""}

escolhidos = []
pd_state = st.session_state.get("pdms")
if pd_state:
    st.caption(f"Catálogo oficial de materiais baixado em {pd_state['baixado_em'][:16].replace('T', ' ')} "
               f"(config\\catalogo_pdm.csv) · procurado: {pd_state['usada']}"
               + (f" · números {', '.join(pd_state['numeros'])} ficam para os atributos" if pd_state["numeros"] else ""))
    if pd_state["achados"]:
        tab = pd.DataFrame([{"usar": i == 0 and str(r["statusPdm"]).lower() == "true", "código": int(r["codigoPdm"]),
                             "nome": r["nomePdm"], "itens": pd_state["contagem"].get(r["codigoPdm"]),
                             "ativo": "sim" if str(r["statusPdm"]).lower() == "true" else "não", "classe": r["nomeClasse"]}
                            for i, r in enumerate(pd_state["achados"])])
        editado = st.data_editor(tab, hide_index=True, use_container_width=True, disabled=["código", "nome", "itens", "ativo", "classe"],
                                 column_config={"usar": st.column_config.CheckboxColumn("usar", help="Marque 1 ou mais códigos"),
                                                "itens": st.column_config.NumberColumn("itens no catálogo", help="só os 8 primeiros são contados")},
                                 key=f"tab_pdm_{pd_state['termo']}")
        escolhidos = [int(c) for c in editado.loc[editado["usar"], "código"]]
        st.write(f"Códigos marcados: {', '.join(map(str, escolhidos)) or 'nenhum'}")
    else:
        st.warning(f"Nada encontrado no catálogo para \"{pd_state['termo']}\"."
                   + (f" Termos parecidos: {', '.join(pd_state['sugestoes'])}." if pd_state["sugestoes"] else " Nenhum termo parecido.")
                   + " Você pode incluir um sinônimo em config\\sinonimos.csv.")

with st.expander("Opção avançada: digitar o código do catálogo"):
    codigo = st.text_input("Código (só números; se preenchido, substitui os códigos marcados acima)", "")
    tipo_cod = st.radio("O código é", ["Tipo de produto (PDM) – todos os modelos", "Configuração específica (item CATMAT)"], index=0)

# ---------- 2. regras e atributos
st.subheader("2. Atributos e busca")
alternativas = (pd_state or {}).get("usada", "")
padrao = next((i for i, p in enumerate(produtos) if f.tokens(p)[0] in alternativas.split()), 0)
produto = st.selectbox("Regras de atributos (config\\produtos.csv)", list(produtos), index=padrao)
with st.form("entrada"):
    c3, c4 = st.columns([1, 2])
    modo = c3.radio("Modo", ["rápido", "completo"], index=0, help="Rápido: menos páginas e consultas (amostra menor).")
    uf = c4.text_input("UF (vazio = todas)", "")
    st.write("Atributos (deixe vazio o que não importa):")
    cols = st.columns(max(1, len(produtos[produto])))
    valores = {}
    for col, a in zip(cols, produtos[produto]):
        un = UNIDADE_TXT.get(a["unidade"], a["unidade"])
        valores[a["nome"]] = col.text_input(f"{a['nome']} – só o número, em {un}", "", key=f"at_{produto}_{a['nome']}",
                                            help=f"Faixa aceita: {a['regra']} (x = valor digitado)"
                                                 + (". Aceita também 960G, 1TB, 1 T." if a["unidade"] == "GB" else ""))
    buscar = st.form_submit_button("Buscar", type="primary")

if buscar:
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
    attrs = [valores[a["nome"]] for a in produtos[produto]]
    etapas = ["1. Catálogo (Compras.gov.br)", "2. Filtros de atributos", "3. Ligação ao PNCP"]
    barras = {e: (st.progress(0.0, text=f"{e}: aguardando")) for e in etapas}
    agora = st.empty()
    relogio = st.empty()
    inicio = time.time()
    lim = MODOS[modo]
    por_codigo = True
    resumos, logs = [], []
    for n_cod, (cod, tipo) in enumerate(codigos, 1):
        prefixo = f"código {cod} ({n_cod} de {len(codigos)}) · " if len(codigos) > 1 else ""
        respostas = [cod, tipo, produto, *attrs, uf]
        # estado do progresso: etapa 1 (listagem), etapa 3 (PNCP); a etapa 2 é local (sem API) e mostra o resultado no fim
        est = {"e1_feito": 0, "e1_total": None, "e1_ini": None, "ids": set(),
               "lig_feito": 0, "val_feito": 0, "e3_ini": None, "e3_chamadas": 0}

        def eta(ini, feito, total):
            """Tempo restante estimado pela média por chamada já feita."""
            if not ini or not feito or not total or feito >= total:
                return ""
            return f" · faltam ~{tempo_fmt((time.time() - ini) / feito * (total - feito))}"

        def ao_chamar(fase, url, params, resultado):
            """Antes da chamada: mostra a ação em 'Agora:'. Depois: atualiza 'feito de total', % e tempo restante."""
            listagem = "1_consultarMaterial" in url or "/api/consulta" in url or "/api/search" in url
            if fase == "antes":
                agora.markdown(f"**Agora:** {prefixo}{acao_atual(url, params)}")
                if listagem and est["e1_ini"] is None:
                    est["e1_ini"] = time.time()
                if not listagem and est["e3_ini"] is None:  # entrou na etapa 3: etapas 1 e 2 já terminaram
                    est["e3_ini"] = time.time()
                    barras[etapas[0]].progress(1.0, text=f"{etapas[0]}: 100% · {est['e1_feito']} de {est['e1_feito']} chamadas")
                    barras[etapas[1]].progress(1.0, text=f"{etapas[1]}: 100% · feitos localmente, sem consulta à API (resultado abaixo no fim)")
                relogio.write(f"Tempo decorrido: {tempo_fmt(time.time() - inicio)}")
                return
            st_http, js = resultado[0], resultado[1]
            if listagem:
                est["e1_feito"] += 1
                if por_codigo and isinstance(js, dict):
                    if est["e1_total"] is None and js.get("totalRegistros") is not None:
                        est["e1_total"] = min(-(-int(js["totalRegistros"]) // 100), lim["MAX_PAGINAS_CATALOGO"]) or 1
                    est["ids"].update(str(r.get("idCompra")) for r in js.get("resultado", []) if r.get("idCompra"))
                    if not js.get("paginasRestantes"):
                        est["e1_total"] = est["e1_feito"]
                total = est["e1_total"] if por_codigo else 48  # consulta: até 12 meses x 2 modalidades x 2 páginas
                pct = min(est["e1_feito"] / total, 1.0) if total else 0.0
                txt_total = f"{est['e1_total']}" if est["e1_total"] else "?"
                if not por_codigo:
                    txt_total = "até 48"
                barras[etapas[0]].progress(pct, text=f"{etapas[0]}: {pct:.0%} · {est['e1_feito']} de {txt_total} páginas"
                                                       f"{eta(est['e1_ini'], est['e1_feito'], total)}")
            else:
                est["e3_chamadas"] += 1
                if "1.1_consultarContratacoes" in url:
                    est["lig_feito"] += 1
                elif "/itens" in url and not url.endswith("/resultados"):
                    est["val_feito"] += 1 if not por_codigo else 0
                if por_codigo:
                    total = min(len(est["ids"]), lim["MAX_VINCULOS"]) or lim["MAX_VINCULOS"]
                    feito = est["lig_feito"]
                    extra = f" · validação no PNCP: {est['e3_chamadas'] - est['lig_feito']} chamadas"
                    rotulo = f"{feito} de {total} compras procuradas no PNCP"
                else:
                    total, feito = lim["MAX_COMPRAS"], est["val_feito"]
                    extra = f" · {est['e3_chamadas']} chamadas"
                    rotulo = f"{feito} de até {total} compras lidas"
                pct = min(feito / total, 1.0) if total else 0.0
                # tempo restante: média de chamadas por compra x compras que faltam
                restante = ""
                if feito and feito < total:
                    por_compra = (time.time() - est["e3_ini"]) / feito
                    restante = f" · faltam ~{tempo_fmt(por_compra * (total - feito))}"
                barras[etapas[2]].progress(pct, text=f"{etapas[2]}: {pct:.0%} · {rotulo}{extra}{restante}")
            relogio.write(f"Tempo decorrido: {tempo_fmt(time.time() - inicio)}")

        with limites(modo), respondendo(respostas, ao_chamar) as log:
            f.buscar_por_codigo()
        resumos.append(json.loads((f.SAIDA / "ultima_busca.json").read_text(encoding="utf-8")))
        logs.append(log.getvalue())
    if len(resumos) > 1:
        f.juntar_buscas(resumos)  # vários códigos: uma tabela só
    # fim: etapa 2 mostra o resultado do filtro; todas a 100%
    res_fim, df_fim = carregar_ultima()
    r = res_fim or {}
    na_api = r.get("registros_informados_pela_api")
    lidos = r.get("registros_lidos") or r.get("compras_vistas_na_listagem") or 0
    linhas_fim = 0 if df_fim is None else len(df_fim)
    parecidos = 0 if df_fim is None or df_fim.empty else int((df_fim["situacao"] != "não atende").sum())
    inicio_txt = f"{int(na_api):,} na API → {int(lidos):,} lidos" if na_api else f"{int(lidos):,} lidos"
    barras[etapas[0]].progress(1.0, text=f"{etapas[0]}: 100% · {len(codigos)} código(s)")
    barras[etapas[1]].progress(1.0, text=f"{etapas[1]}: 100% · {inicio_txt} → {linhas_fim:,} no período de 12 meses → "
                                         f"{parecidos:,} parecidos (sem 'não atende')".replace(",", "."))
    barras[etapas[2]].progress(1.0, text=f"{etapas[2]}: 100% · {sum(x.get('chamadas', 0) for x in resumos)} chamadas no total")
    agora.markdown("**Agora:** busca concluída")
    relogio.write(f"Tempo total: {tempo_fmt(time.time() - inicio)}")
    st.session_state["log_busca"] = "\n".join(logs)
    st.session_state.pop("docs", None)

resumo, df = carregar_ultima()
if resumo is None:
    st.info("Nenhuma busca ainda. Preencha e clique em Buscar.")
    st.stop()

# ----------------------------------------------------------------- resumo
st.subheader("Resumo da última busca")
if "PORTAL FORA" in st.session_state.get("log_busca", ""):
    st.warning("O portal caiu ou bloqueou durante a busca. O que já tinha sido lido foi salvo.")
total = 0 if df is None else len(df)
contagem = df["situacao"].value_counts() if total else pd.Series(dtype=int)
vinc = int((df["link_publico"].fillna("") != "").sum()) if total else 0
susp = int((df.get("observacao_preco", pd.Series(dtype=str)).fillna("") == "preço suspeito").sum()) if total else 0
m = st.columns(6)
m[0].metric("Total", total)
m[1].metric("Não atende", int(contagem.get("não atende", 0)))
m[2].metric("Parcial (a confirmar no TR)", int(contagem.get("a confirmar no TR", 0)))
m[3].metric("Vinculados ao PNCP (linhas)", vinc)
m[4].metric("Preço suspeito", susp)
m[5].metric("Tempo (s)", resumo.get("tempo_s", "?"))
st.caption(f"Entrada: {resumo.get('entrada', '')} · fonte: {resumo.get('fonte', '')} · chamadas: {resumo.get('chamadas')} "
           f"· falhas: {resumo.get('falhas')} · salvo em: `{resumo.get('arquivo')}`")
with st.expander("Mensagens da última busca"):
    st.text(st.session_state.get("log_busca", "(a busca foi feita antes de abrir esta tela)"))
if not total:
    st.stop()

# ----------------------------------------------------------------- tabela
st.subheader("Resultados (primeiro quem não tem 'não atende')")
pedidos = list(resumo.get("pedidos") or {})
SEM_LINK = {"sem PNCP": "sem link: compra não encontrada no PNCP",
            "não verificado": "não verificado: limite de consultas"}


def coluna_pncp(l):
    """Link do PNCP; sem link, o motivo (em vez de célula vazia)."""
    if str(l.get("link_publico") or "").startswith("http"):
        return l["link_publico"]
    return SEM_LINK.get(str(l.get("situacao_pncp") or ""), "sem link: compra não encontrada no PNCP")


ROTULO_CURTO = {"armazenamento": "SSD"}  # o pedido de armazenamento é de SSD (ver ferramenta.avaliar_armazenamento)


def coluna_avaliacao(l):
    """Quais atributos foram avaliados e como: 'RAM parcial · SSD atende · tela parcial'."""
    partes = []
    for k in pedidos:
        s = str(l.get(k) or "não informado")
        sit = "não atende (só HDD)" if "só HDD" in s else s.split(" (")[0]
        partes.append(f"{ROTULO_CURTO.get(k, k)} {sit}")
    return " · ".join(partes)


df["pncp"] = df.apply(coluna_pncp, axis=1)
df["avaliacao"] = df.apply(coluna_avaliacao, axis=1) if pedidos else ""
mostrar = ["linha", "situacao", "avaliacao", *pedidos, "preco_unitario_homologado", "observacao_preco",
           "data_resultado", "orgao", "uf", "descricao_item", "pncp"]
mostrar = [c for c in mostrar if c in df.columns]
st.dataframe(df[mostrar], hide_index=True, use_container_width=True,
             column_config={"avaliacao": st.column_config.TextColumn("avaliação", help="cada atributo pedido e o resultado"),
                            "pncp": st.column_config.LinkColumn("PNCP", display_text=r"https://pncp\.gov\.br/app/editais/(.*)"),
                            "preco_unitario_homologado": st.column_config.NumberColumn("preço unitário", format="R$ %.2f")})
st.download_button("Baixar CSV (ordem desta tela)", df.to_csv(sep=";", index=False).encode("utf-8-sig"),
                   file_name=Path(resumo["arquivo"]).name.replace(".csv", "_tela.csv"), mime="text/csv")

# ----------------------------------------------------------------- linha escolhida
st.subheader("Documentos e texto para IA")
opcoes = df["linha"].tolist()
escolha = st.selectbox("Linha", opcoes, format_func=lambda n: f"{n} – " + df.loc[df["linha"] == n, "orgao"].iloc[0][:50]
                       + " – " + df.loc[df["linha"] == n, "descricao_item"].iloc[0][:60])
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
                     hide_index=True, use_container_width=True)
        pdfs = [p for p in arquivos if p.suffix.lower() in f.EXTENSOES_RECORTE]  # PDF e Word
        if pdfs:
            pdf = st.selectbox("Documento para recortar: PDF ou Word (de preferência o TR)", pdfs, format_func=lambda p: p.name,
                               index=next((i for i, p in enumerate(pdfs) if re.search(r"termo|\btr\b", f.norm(p.name))), 0))
            if st.button("Gerar texto para IA"):
                todos = f.documentos_recortaveis()  # mesma lista da opção 4
                item = resumo.get("produto") or produto  # item pedido no recorte = produto da busca
                with st.spinner("Recortando as páginas do item..."):
                    with respondendo([todos.index(pdf) + 1, item]) as log4:
                        f.opcao_4_recortar()
                    m_rec = re.search(r"Recorte salvo em: (.+)", log4.getvalue())
                    m_av = re.search(r"Aviso: ((?:Word|Convertido).+)", log4.getvalue())
                    if m_av:
                        st.info(m_av.group(1))
                    if not m_rec:
                        m_nao = re.search(r"Não foi possível recortar: (.+)", log4.getvalue())
                        st.error(m_nao.group(1) if m_nao else log4.getvalue())
                        st.stop()
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

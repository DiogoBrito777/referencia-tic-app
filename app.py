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
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ferramenta as f  # noqa: E402
import conferir_tela  # noqa: E402  (v4h: tela "Conferir ficha", funções puras)
import servicos as sv  # noqa: E402  (v4h, Pedido 9: busca de serviço)
f.INSTRUCAO = f.CONFIG / "INSTRUCAO_FICHA.txt"  # 22/11/2026: v1; com o v2 o Nemotron local não devolveu a tabela de 4 colunas em 16 de 16 execuções (v1: 7 de 7). O v2 fica em config\ para uso com o Gemini.
from conferencia import Conferencias  # noqa: E402



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


@st.cache_resource
def conferencias():
    """Conferências de código já feitas ou em andamento (sobrevivem à reexecução da tela)."""
    return Conferencias()


LIMITE_ESPERA_CONFERENCIA_S = 120
LIMITE_ESPERA_TRAVA_S = 120  # quanto uma operação espera a trava global antes de desistir com aviso


def conferir_fora_da_trava(codigo, eh_pdm):
    """Confere o código sem pegar a trava global (uma só consulta GET). Se outra sessão estiver dentro de 'respondendo'
    (que troca f.get), espera a vez com a trava, para não usar o f.get dela. Limite: sem a trava, o registro dessa consulta
    vai para o log padrão do ferramenta.py e não para o log da sessão."""
    if getattr(f.get, "__qualname__", "") == "get":
        return f.conferir_tipo_codigo(codigo, eh_pdm, catalogo_info)
    with respondendo([]):
        return f.conferir_tipo_codigo(codigo, eh_pdm, catalogo_info)


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
        aviso.info(f"Outra busca está em andamento; a sua começa em seguida (espera de até {tempo_fmt(LIMITE_ESPERA_TRAVA_S)}).")
        if not trava.acquire(timeout=LIMITE_ESPERA_TRAVA_S):
            aviso.empty()
            st.error(f"Outra busca ainda estava em andamento depois de {tempo_fmt(LIMITE_ESPERA_TRAVA_S)} e a sua não começou. "
                     "Nada foi consultado nem perdido. Tente de novo daqui a pouco.")
            st.stop()
        aviso.empty()
    originais = None  # a trava só é solta no finally, mesmo se a preparação abaixo falhar
    try:
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
        with contextlib.redirect_stdout(saida):
            yield saida
    finally:
        if originais:
            f.pergunta, f.escolher_numero, f.get, f.SAIDA, f.LOG = originais
        trava.release()


@contextlib.contextmanager
def limites(modo, aceitar=False):
    """Aplica os limites do modo rápido/completo e a opção 'aceitar maiores'; devolve os originais no fim.
    Usar sempre dentro de respondendo (que garante uma operação por vez)."""
    antes = {k: getattr(f, k) for k in MODOS[modo]}
    antes_aceitar = f.ACEITAR_MAIORES
    antes_modo = f.MODO_ATUAL
    for k, v in MODOS[modo].items():
        setattr(f, k, v)
    f.ACEITAR_MAIORES = aceitar
    f.MODO_ATUAL = modo  # v4h: vai para a coluna 'modo' do CSV
    try:
        yield
    finally:
        for k, v in antes.items():
            setattr(f, k, v)
        f.ACEITAR_MAIORES = antes_aceitar
        f.MODO_ATUAL = antes_modo


def acao_atual(url, params):
    """Texto da linha 'Agora:' a partir da API chamada."""
    m = re.search(r"/orgaos/(\d+)/compras/(\d+)/(\d+)(/.*)?$", url)
    compra = f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else ""
    resto = (m.group(4) or "") if m else ""
    if "3_consultarServico" in url:
        return f"Compras.gov.br, pesquisa de preço de serviço: página {params.get('pagina')} do código {params.get('codigoItemCatalogo')}"
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


# ----------------------------------------------------------------- PAINEL DE PROGRESSO (Pedido 13I; vale para Produto e Serviço)
# Um helper só para toda ação demorada. O painel é um st.container(border=True): NENHUM componente recolhível (nada de st.status nem st.expander), então aparece aberto,
# sem clique, e não fecha sozinho. Mostra: nome da etapa, barra(s), linha "Agora: ...", tempo decorrido e estimativa quando existir. Ao terminar FICA na tela com
# "Concluída em N s: <resumo>" ou "Falhou: <motivo>". O último estado de cada painel fica em st.session_state["painel_<chave>"] e é redesenhado a cada rerun
# (mostrar_painel) até uma nova ação da mesma etapa o substituir ou a regra de limpeza (termo novo, Nova busca, reabrir busca) apagar.
PAINEL_CHAVES = ("e1_procurar", "e1_catalogo", "e1_config", "e1_conferir", "e2_buscar", "e3_baixar", "e3_recorte", "e3_outros", "e5_conferir")


def limpar_paineis(*chaves):
    """Apaga o último estado dos painéis dados (nenhum = todos)."""
    for c in (chaves or PAINEL_CHAVES):
        st.session_state.pop(f"painel_{c}", None)


def seg_fmt(s):
    """Tempo curto para o resumo: abaixo de 10 s com 1 casa ('0,3 s'); depois como tempo_fmt."""
    return f"{s:.1f}".replace(".", ",") + " s" if s < 10 else tempo_fmt(s)


def _desenha_painel(slot, e):
    """Estado FINAL de um painel (sempre à vista): título, barras no último valor e a frase final."""
    with slot.container(border=True):
        st.markdown(f"**{e['titulo']}**")
        for _nome, pct, txt in e["barras"]:
            st.progress(pct, text=txt)
        st.markdown(e["texto"])


def mostrar_painel(chave, alvo=None):
    """Reserva o lugar do painel nesta posição da tela e desenha o último estado guardado (se valer para este alvo). Devolve o lugar (slot)."""
    slot = st.empty()
    e = st.session_state.get(f"painel_{chave}")
    if e and e.get("alvo") in (None, alvo):
        _desenha_painel(slot, e)
    return slot


class _Barra:
    def __init__(self, painel, nome):
        self.painel, self.nome = painel, nome

    def progress(self, pct, text=""):
        self.painel.barra(pct, text, self.nome)


class Painel:
    def __init__(self, chave, titulo, slot, barras=None, alvo=None):
        self.chave, self.titulo, self.slot, self.alvo = chave, titulo, slot, alvo
        self.inicio = time.time()
        self._est = ""
        self.nomes = list(barras or ["Andamento"])
        self.vals = {n: (0.0, "Aguardando" if len(self.nomes) == 1 else f"{n}: aguardando") for n in self.nomes}
        st.session_state.pop(f"painel_{chave}", None)       # a nova ação substitui o estado antigo
        with slot.container(border=True):
            st.markdown(f"**{titulo}**")
            self.els = {n: st.progress(0.0, text=self.vals[n][1]) for n in self.nomes}
            self.agora_el = st.empty()
            self.tempo_el = st.empty()
        self.barras = {n: _Barra(self, n) for n in self.nomes}

    def barra(self, pct, texto, nome=None):
        """Pedido 13K: o % vai escrito na barra, mas SÓ quando é real (n de N). pct=None = etapa única sem total conhecido: a barra fica parada e o texto diz 'em andamento'
        (o tempo decorrido sobe sozinho, ver com_relogio). Texto que já traz '%' não leva o % de novo."""
        nome = nome or self.nomes[0]
        if pct is None:
            pct, texto = 0.0, f"{texto} · em andamento"
        else:
            pct = min(max(float(pct), 0.0), 1.0)
            if "%" not in texto:
                texto = f"{texto} · {pct:.0%}"
        self.vals[nome] = (pct, texto)
        self.els[nome].progress(pct, text=texto)

    def agora(self, texto, estimativa=None):
        self.agora_el.markdown(f"**Agora:** {texto}")
        self.tempo(estimativa)

    def tempo(self, estimativa=None):
        """Estimativa None = repete a última (o relógio de 1 s não apaga o 'faltam ~...' que a etapa calculou)."""
        if estimativa is not None:
            self._est = estimativa
        self.tempo_el.write(f"Tempo decorrido: {tempo_fmt(time.time() - self.inicio)}{self._est}")

    def _fim(self, ok, texto):
        e = {"titulo": self.titulo, "ok": ok, "texto": texto, "barras": [(n, *self.vals[n]) for n in self.nomes], "alvo": self.alvo}
        st.session_state[f"painel_{self.chave}"] = e
        self.agora_el.markdown(texto)      # o painel vivo vira o final NO MESMO LUGAR (sem trocar o bloco); o redesenho completo (_desenha_painel) é só para os reruns
        self.tempo_el.empty()

    def concluir(self, resumo, verbo="Concluída"):
        com_falhas = "falhas" in verbo      # Pedido 17 (0.3): etapa que termina com falha NÃO mostra "Concluída · 100%" na barra; o rótulo diz "Concluída com falhas"
        for n in self.nomes:
            pct, txt = self.vals[n]
            if com_falhas:
                rotulo = "Concluída com falhas" if len(self.nomes) == 1 else f"{n}: concluída com falhas"
                self.vals[n] = (1.0, rotulo)
                self.els[n].progress(1.0, text=rotulo)
                continue
            self.barra(1.0, txt if pct >= 1.0 else ("Concluída" if len(self.nomes) == 1 else f"{n}: concluída"), n)
        self._fim(True, f"{verbo} em {seg_fmt(time.time() - self.inicio)}: {resumo}")

    def falhar(self, motivo):
        self._fim(False, f"Falhou: {motivo}")


def com_relogio(painel, fn):
    """Pedido 13K (C2): roda fn() numa thread e, enquanto ela trabalha, redesenha o 'Tempo decorrido' do painel a cada 1 s (antes ele só mudava quando a etapa chamava a rede).
    Devolve o que fn devolve; a exceção da thread (inclusive o st.stop() de respondendo) é repropagada aqui, na thread da tela. Não mexe no ferramenta.py: só muda QUEM chama."""
    saida = {}

    def alvo():
        try:
            saida["valor"] = fn()
        except BaseException as exc:  # noqa: BLE001  (repropagada abaixo)
            saida["erro"] = exc

    t = threading.Thread(target=alvo, daemon=True)
    add_script_run_ctx(t, get_script_run_ctx())     # a thread pode escrever nos elementos da tela desta sessão
    t.start()
    while t.is_alive():
        painel.tempo()
        t.join(1.0)
    if "erro" in saida:
        raise saida["erro"]
    return saida["valor"]


def contar_texto_dos_outros(painel, docs, cache):
    """Pedido 13K (A2): caracteres de texto de cada documento (PDF ou .docx) já baixado da compra, lidos no computador (sem rede). Devolve uma lista de dicts.
    'cache' é um dict da sessão (arquivo+tamanho+data -> avaliação): a mesma leitura não se repete. .doc antigo não é lido aqui (exigiria abrir o Word)."""
    saida = []
    painel.barra(0.0, "Documentos lidos")
    for i, p in enumerate(docs, 1):
        painel.agora(f"lendo o texto de {p.name} (no seu computador, sem rede)")
        chave = f"{p}|{p.stat().st_size}|{int(p.stat().st_mtime)}"
        if chave not in cache:
            if p.suffix.lower() == ".doc":
                cache[chave] = {"erro": ".doc antigo: não lido (abra no Word e salve como .docx ou PDF)"}
            else:
                try:
                    pags, aviso = f.extrair_paginas(p)
                    cache[chave] = sv.avaliar_texto_documento(pags) if pags is not None else {"erro": aviso}
                except Exception as exc:  # noqa: BLE001
                    cache[chave] = {"erro": f"não consegui ler ({type(exc).__name__})"}
        av = cache[chave]
        saida.append({"arquivo": p.name, **av})
        painel.barra(i / len(docs), f"Documentos lidos: {i} de {len(docs)}")
    return saida


def mostrar_sem_texto(info):
    """Pedido 13K (A2): o que aparece no lugar de 'páginas relevantes' e 'texto pronto' quando o documento escolhido não tem texto."""
    av = info["av"]
    st.error(f"{info['pdf']}: {sv.frase_sem_texto(av)} O app não faz OCR (leitura de imagem): não há texto para recortar nem para a IA.")
    outros = info.get("outros") or []
    if not outros:
        st.warning("Não há outro documento baixado desta compra. Marque \"Baixar também propostas, atas e despachos\" e baixe de novo, ou obtenha uma versão do documento com texto.")
        return
    st.write("Outros documentos já baixados desta compra, com o texto que o app consegue ler neles. Escolha em \"Documento para recortar\" um que tenha texto:")
    linhas = []
    for o in outros:
        if o.get("erro"):
            linhas.append({"documento": o["arquivo"], "páginas": "", "caracteres de texto": "", "situação": o["erro"]})
        else:
            sit = {"sem_texto": "sem texto", "parcial": f"{o['sem_texto']} de {o['paginas']} páginas sem texto", "ok": "tem texto"}[o["estado"]]
            linhas.append({"documento": o["arquivo"], "páginas": o["paginas"], "caracteres de texto": f"{o['total']:,}".replace(",", "."), "situação": sit})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch", height=altura_tabela(len(linhas)))


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
        limpar_paineis("e2_buscar", "e3_baixar", "e3_recorte", "e5_conferir")   # Pedido 13I


def limpar_produto_anterior():
    """Guarda a busca atual no histórico e apaga o que é do produto anterior (códigos marcados, configuração, código escolhido).
    Não apaga 'contagens' (cache de consultas da sessão)."""
    arquivar_busca_atual()
    limpar_paineis("e1_procurar", "e1_config", "e1_conferir", "e2_buscar", "e3_baixar", "e3_recorte", "e5_conferir")   # Pedido 13I: termo novo limpa os painéis do resultado
    for k in list(st.session_state):
        if k in ("pdms", "configs", "docs", "conf_chave", "conf_valor") or k.startswith(("at_", "num_", "cfg_", "tab_pdm_", "sel_cfg_", "perfil_")):
            del st.session_state[k]
    st.session_state["codigo_av"] = ""


def nova_busca():
    """Botão 'Nova busca': guarda a busca atual no histórico e limpa a tela."""
    limpar_produto_anterior()
    limpar_paineis()   # Pedido 13I: Nova busca limpa todos os painéis
    st.session_state["termo"] = ""
    st.session_state["uf_busca"] = ""
    st.session_state["aceitar_busca"] = False
    st.session_state.pop("serv_busca", None)   # Pedido 13: o botão também zera a procura de serviço
    st.session_state["serv_termo"] = ""
    for k in [k for k in st.session_state if str(k).startswith("tab_serv_")]:
        del st.session_state[k]
    st.session_state["serv_codigo_av"] = ""


# ----------------------------------------------------------------- serviço (v4h, Pedido 9)
@st.cache_resource
def catalogo_servicos_na_memoria(caminho, assinatura):
    """Catálogo de serviços (config\\catalogo_servicos.csv) lido uma vez por processo; a assinatura (tamanho e data do arquivo) renova se o arquivo mudar."""
    return sv.ler_catalogo(caminho)


def limpar_servico_anterior():
    """Pedido 13: ao procurar um serviço NOVO, guarda a busca atual em "Buscas anteriores" e limpa o que é do serviço anterior (documentos, canal oficial,
    lista de TR e códigos marcados). Mesma regra do produto (termo novo limpa e arquiva; o mesmo termo não limpa)."""
    arquivar_busca_atual()
    limpar_paineis("e1_procurar", "e1_conferir", "e2_buscar", "e3_baixar", "e3_recorte", "e5_conferir")   # Pedido 13I
    for k in ("docs", "canal_oficial", "lista_tr"):
        st.session_state.pop(k, None)
    for k in [k for k in st.session_state if str(k).startswith("tab_serv_")]:   # códigos marcados na tabela 'usar'
        del st.session_state[k]
    st.session_state["serv_codigo_av"] = ""   # igual ao produto (codigo_av): o código digitado também sai


def validar_codigos_servico(txt, idx):
    """Opção avançada do serviço: '5606, 22977' -> (códigos, erro, avisos). Só confere contra o catálogo local (sem rede)."""
    bruto = [x.strip() for x in re.split(r"[,;]", txt or "") if x.strip()]
    if not bruto:
        return [], "", []
    if any(not x.isdigit() for x in bruto):
        return [], "Digite só números separados por vírgula (ex.: 5606, 22977).", []
    cods = list(dict.fromkeys(bruto))
    if len(cods) > 6:
        return [], f"No máximo 6 códigos (você digitou {len(cods)}).", []
    faltam = [c for c in cods if c not in idx]
    if faltam:
        return [], f"Código(s) fora do catálogo local de serviços: {', '.join(faltam)}.", []
    avisos = [f"O código {c} está desativado no catálogo." for c in cods if str(idx[c].get("statusServico")).strip().lower() not in ("true", "1", "sim")]
    return cods, "", avisos


# ----------------------------------------------------------------- REGRA DE LARGURA DA PÁGINA (Pedido 13E; vale para Produto e Serviço)
#  (a) O CABEÇALHO (título e legenda), os controles do topo (caixa "Limites", seletor Produto/Serviço, "Nova busca") e as ENTRADAS da Etapa 1 (campo de busca, botão Procurar,
#      legenda do catálogo com Atualizar catálogo NOS DOIS modos, opção avançada, Modo e UF, botão Buscar e as mensagens do clique em Buscar) ficam na coluna CENTRAL: st.columns([1, 3, 1]),
#      com o conteúdo na do meio e o texto alinhado à esquerda dentro dela. As entradas ficam em duas colunas centrais porque a região de resultado vem entre elas
#      (ordem de leitura: Procurar > resultado > opção avançada > Modo e UF).
#  (b) TODA tabela e a região de resultado da procura (lista_resultados: "Procurado", correções, orientação, contagem, tabela com "usar", "Códigos marcados", legendas e, no produto,
#      "Ver configurações") ficam em LARGURA TOTAL, assim como as Etapas 2 a 5.
#  (c) Cada mensagem fica na largura do bloco a que pertence.
# REGRA DE ALTURA DAS TABELAS: ver altura_tabela (a mesma função serve a todas as tabelas).
LIMITE_LINHAS_SEM_ROLAGEM = 40   # até N linhas: todas aparecem, sem barra de rolagem
ALTURA_FIXA_PX = 600             # acima de N linhas: altura fixa, com rolagem


def altura_tabela(n_linhas, limite=LIMITE_LINHAS_SEM_ROLAGEM):
    """Altura de st.dataframe / st.data_editor. No Streamlit 1.66.1 height aceita "auto" (no máximo 10 linhas), "content" (altura pelo conteúdo, teto de 10.000 px),
    "stretch" (preenche o pai, não a janela) ou número de pixels. Até 'limite' linhas: "content" (todas as linhas, sem barra de rolagem). Acima: altura fixa em px, com rolagem.
    LIMITAÇÃO: o Streamlit não tem altura relativa à janela; só dá para isso com CSS injetado, o que NÃO é feito aqui. Em tela pequena, a altura fixa (acima de 40 linhas) é em px."""
    return "content" if n_linhas <= limite else ALTURA_FIXA_PX


def ler_termos_software():
    """Pedido 13E: termos de config\\termos_software.csv (coluna 'termo'; a equipe edita sem mexer no código), sem acento e sem diferenciar maiúsculas.
    Arquivo ausente ou ilegível = conjunto vazio: o app não mostra orientação e não dá erro."""
    try:
        with (f.CONFIG / "termos_software.csv").open(encoding="utf-8-sig", newline="") as fh:
            return {f.norm(l.get("termo") or "").strip() for l in csv.DictReader(fh, delimiter=";") if (l.get("termo") or "").strip()}
    except (OSError, csv.Error, UnicodeDecodeError):
        return set()


def termo_de_software(texto):
    """O termo do arquivo que aparece (como palavra inteira) no que a pessoa digitou; None se nenhum."""
    termos = ler_termos_software()
    cheio = " " + " ".join(re.findall(r"[a-z0-9]+", f.norm(texto))) + " "
    return next((t for t in sorted(termos) if f" {t} " in cheio), None)


def marcar_todos(chave_ed, n_linhas):
    """Pedido 17: botão 'Marcar todos' (máximo 6) para as tabelas com a coluna 'usar' (sugestões e códigos do catálogo), nos dois modos. O data_editor não aceita valor de fora:
    o clique troca a chave do editor (versão +1), e a tabela nasce com as 6 primeiras linhas marcadas. Devolve (versão, chave do editor). Versão 0 = chave original, sem marcar."""
    k = f"mt_{chave_ed}"
    st.button("Marcar todos", key=f"btn_{k}", help="Marca as 6 primeiras linhas da tabela (o máximo que a busca usa).",
              on_click=lambda: st.session_state.__setitem__(k, st.session_state.get(k, 0) + 1))
    ver = st.session_state.get(k, 0)
    if ver and n_linhas > 6:
        st.caption(f"Marcar todos: a tabela tem {n_linhas} linhas; marquei só as 6 primeiras (o máximo). Marque as outras uma a uma, se precisar.")
    return ver, (chave_ed if not ver else f"{chave_ed}_v{ver}")


def orientacao_software(eh_prod, termo_digitado):
    """Pedido 13E/13K: quando a procura não achou nada e o termo é de software/licença, diz onde procurar e devolve a lista das sugestões numa TABELA com a coluna 'usar'
    (igual à de resultados): marcar adiciona o código a 'Códigos marcados'. Devolve a lista dos códigos marcados (produto: int; serviço: str, no máximo 6) ou None se não
    há tabela de sugestão. Tudo do catálogo local, sem rede. Produto: o PDM 'Software' ativo (código calculado pelo catálogo, não escrito no código).
    Serviço: serviços ativos com 'licenc' ou 'software como servico' (no máximo 10). Termo sem sugestão: avisa como a equipe pode acrescentá-lo (config\\termos_software.csv)."""
    if not termo_de_software(termo_digitado):
        st.caption("Para sugerir códigos para este termo, a equipe acrescenta o termo em config\\termos_software.csv")
        return None
    chave = zlib.crc32(f.norm(termo_digitado).encode("utf-8"))
    if eh_prod:
        try:
            cat = f.ler_catalogo_pdm()
        except OSError:
            cat = []
        r_pdm = next((r for r in cat if f.norm(r["nomePdm"]).strip() == "software" and str(r["statusPdm"]).strip().lower() == "true"), None)
        pdm = str(r_pdm["codigoPdm"]) if r_pdm else None
        _dec = sv.decisao_software(termo_digitado, ler_termos_software(), sv.ler_itens_software())      # Pedido 18: a decisão sai da contagem no CSV de itens do PDM Software
        if _dec["decisao"] == "servico":
            st.info(sv.mensagem_software_sem_item(termo_digitado, _dec["total"]))
            return None
        onde = f"marque o código do PDM 'Software' ativo ({pdm}) na tabela abaixo" if pdm else "marque o código do PDM 'Software' ativo (não achei esse PDM ativo no catálogo local)"
        st.info(f"'{termo_digitado}' não é um tipo de produto no catálogo oficial (os PDMs são tipos, não marcas nem versões). "
                f"Procure 'software', {onde} e use 'Ver configurações (itens CATMAT)' com o filtro de texto '{termo_digitado}'.")
        if not r_pdm:
            return None
        chave_ed = f"tab_sug_pdm_{chave}"
        _v, chave_ed_v = marcar_todos(chave_ed, 1)
        tab = pd.DataFrame([{"usar": bool(_v), "código": int(r_pdm["codigoPdm"]), "nome": r_pdm["nomePdm"]}])
    else:
        try:
            cat = sv.ler_catalogo()
        except OSError:
            cat = []
        sug = [r for r in cat if str(r.get("statusServico", "")).strip().lower() in ("true", "1", "sim")
               and ("licenc" in f.norm(r.get("nomeServico", "")) or "software como servico" in f.norm(r.get("nomeServico", "")))][:10]
        if not sug:
            st.info("Sugestão de onde procurar: o catálogo local não tem serviço ativo com 'licenc' ou 'software como serviço'.")
            return None
        st.info("Sugestão de onde procurar. A equipe e o órgão confirmam qual código usar. Marque \"usar\" na tabela abaixo.")
        chave_ed = f"tab_sug_serv_{chave}"
        _v, chave_ed_v = marcar_todos(chave_ed, len(sug))
        tab = pd.DataFrame([{"usar": bool(_v) and i < 6, "código": int(r["codigoServico"]), "serviço": r["nomeServico"]} for i, r in enumerate(sug)])
    editado = st.data_editor(tab, hide_index=True, width="stretch", height=altura_tabela(len(tab)), disabled=[c for c in tab.columns if c != "usar"],
                             column_config={"usar": st.column_config.CheckboxColumn("usar", help="Marque o código sugerido para usá-lo na busca (sem digitar na opção avançada)")}, key=chave_ed_v)
    marcados = [int(c) for c in editado.loc[editado["usar"], "código"]]
    return marcados if eh_prod else [str(c) for c in marcados]


def lista_resultados(eh_prod, busca):
    """Região 'resultado da procura' da Etapa 1, UMA função para Produto e Serviço (Pedido 13C), na mesma ordem: 'Procurado: X'; (só produto: correção e 'Você quis dizer');
    linha da contagem; tabela com a coluna 'usar'; 'Códigos marcados: ...'; captions. Só no produto: contagem de compras, legenda de código desativado e 'Ver configurações
    (itens CATMAT)'. Devolve os códigos marcados (serviço: no máximo os 6 primeiros marcados; produto: todos, como sempre foi)."""
    escolhidos = []
    if not busca:
        return escolhidos
    termo_b = busca["termo"]
    st.caption(f"Procurado: {busca['usada'] or termo_b}" if eh_prod else f"Procurado: {termo_b}")
    if eh_prod:
        if busca.get("corrigido_para"):
            st.info(f"Você digitou \"{termo_b}\". Mostrando resultados para \"{busca['corrigido_para']}\".")
        _sug = sv.filtrar_sugestoes(termo_b, busca["sugestoes"])      # Pedido 18: só sugere o que começa com a mesma letra e difere em até 1 letra (2 se 8+ letras)
        if _sug:
            st.write("Nenhum código com esse nome exato. Você quis dizer…?")
            cols_sug = st.columns(min(len(_sug), 5))
            for col, nome in zip(cols_sug, _sug):
                col.button(nome[:34], key=f"sug_{nome}", on_click=usar_sugestao, args=(nome,), help=nome)
    achados = busca["achados"]
    if not achados:
        if eh_prod:
            st.warning(f"Nada encontrado no catálogo para \"{termo_b}\"."
                       + ("" if _sug else " Nenhum termo parecido.")
                       + " Você pode incluir um sinônimo em config\\sinonimos.csv.")
        else:
            st.warning("Nenhum serviço ativo do catálogo tem todas essas palavras. Tente menos palavras ou outra forma (ex.: \"eletrica\" em vez de \"energia\").")
        sug_marcados = orientacao_software(eh_prod, termo_b)   # Pedido 13E/13K: só quando a procura não achou nada; devolve os códigos marcados na tabela de sugestão
        if sug_marcados is None:
            return escolhidos
        escolhidos = sug_marcados[:6] if not eh_prod else sug_marcados
        st.write(f"Códigos marcados: {', '.join(map(str, escolhidos)) or 'nenhum (marque na coluna usar)'}")
        if not eh_prod and len(sug_marcados) > 6:
            st.warning(f"Você marcou {len(sug_marcados)} códigos; o limite é 6. A busca usa só os 6 primeiros marcados ({', '.join(escolhidos)}). Desmarque os que não quiser.")
        return escolhidos
    # ---- linha da contagem
    if eh_prod:
        st.caption(f"{len(achados)} código(s) encontrado(s) (no máximo 15 são mostrados).")
        cont = st.session_state.get("contagens", {})
        if busca.get("da_sessao"):
            st.caption(f"{busca['da_sessao']} contagem(ns) abaixo vieram da sessão (consultadas numa busca anterior; não foram refeitas agora).")

        def cont_txt(codigo, campo):
            """Contagem como texto; só os 6 primeiros códigos ativos são consultados."""
            v = cont.get(codigo, {}).get(campo)
            return "não consultado" if v is None else f"{int(v):,}".replace(",", ".")

        _v, chave_tab = marcar_todos(f"tab_pdm_{termo_b}", len(achados))
        tab = pd.DataFrame([{"usar": bool(_v) and i < 6, "código": int(r["codigoPdm"]), "nome": r["nomePdm"],
                             "compras nos últimos 12 meses": cont_txt(r["codigoPdm"], "compras"),
                             "configurações no catálogo": cont_txt(r["codigoPdm"], "configs"),
                             "situação": "ativo" if r["ativo"] else "desativado",
                             "tipo": "acessório / outra coisa?" if r["acessorio"] else "produto",
                             "classe": r["nomeClasse"]} for i, r in enumerate(achados)])
        estilo = tab.style.apply(lambda l: ["color: #8a8a8a" if l["situação"] == "desativado" else "" for _ in l], axis=1)
        editado = st.data_editor(estilo, hide_index=True, width="stretch", height=altura_tabela(len(tab)), disabled=[c for c in tab.columns if c != "usar"],
                                 column_config={"usar": st.column_config.CheckboxColumn("usar", help="Marque 1 ou mais códigos"),
                                                "compras nos últimos 12 meses": st.column_config.TextColumn(help="Registros de item comprado na pesquisa de preço do Compras.gov.br. Só os 6 primeiros códigos ativos são consultados."),
                                                "configurações no catálogo": st.column_config.TextColumn(help="Quantos itens CATMAT o código tem. Só os 6 primeiros códigos ativos são consultados.")},
                                 key=chave_tab)
        escolhidos = [int(c) for c in editado.loc[editado["usar"], "código"]]
    else:
        st.caption(f"{len(achados)} serviço(s) encontrado(s) (no máximo 40 são mostrados).")
        _v, chave_tab = marcar_todos(f"tab_serv_{termo_b}", len(achados))
        tab = pd.DataFrame([{"usar": bool(_v) and i < 6, "código": int(r["codigoServico"]), "serviço": r["nomeServico"], "classe": r.get("nomeClasse", ""), "grupo": r.get("nomeGrupo", "")} for i, r in enumerate(achados)])
        editado = st.data_editor(tab, hide_index=True, width="stretch", height=altura_tabela(len(tab)), disabled=[c for c in tab.columns if c != "usar"],
                                 column_config={"usar": st.column_config.CheckboxColumn("usar", help="Marque de 1 a 6 códigos")}, key=chave_tab)
        marcados = [str(int(c)) for c in editado.loc[editado["usar"], "código"]]
        escolhidos = marcados[:6]
    # ---- códigos marcados
    st.write(f"Códigos marcados: {', '.join(map(str, escolhidos)) or 'nenhum (marque na coluna usar)'}")
    if not eh_prod and len(marcados) > 6:
        st.warning(f"Você marcou {len(marcados)} códigos; o limite é 6. A busca usa só os 6 primeiros marcados ({', '.join(escolhidos)}). Desmarque os que não quiser.")
    if eh_prod and len(escolhidos) > 6:
        st.caption(f"Você marcou {len(escolhidos)} códigos: todos serão consultados; as contagens da tabela só existem para os 6 primeiros ativos.")
    # ---- captions
    if eh_prod:
        st.caption("Códigos marcados são os tipos de produto (PDM) que o botão Buscar vai consultar, todos de uma vez numa tabela só. "
                   "Com 0 marcados (e nenhum código digitado na opção avançada), o Buscar não consulta nada e pede que você escolha um código. "
                   "\"não consultado\" na tabela: o código está desativado ou vem depois do sexto código ativo da lista; só os 6 primeiros ativos têm as contagens consultadas.")
        if any(not r["ativo"] for r in achados):
            st.caption("Em cinza: código desativado no catálogo. Pode ter compras antigas, mas não é o código atual do produto.")
        marcados_inativos = [r["codigoPdm"] for r in achados if not r["ativo"] and int(r["codigoPdm"]) in escolhidos]
        if marcados_inativos:
            st.warning(f"Você marcou código desativado: {', '.join(marcados_inativos)}.")
        # ---------- ver as configurações (itens CATMAT) de um código
        with st.expander("Ver configurações (itens CATMAT) de um código"):
            nomes_cod = {int(r["codigoPdm"]): r["nomePdm"] for r in achados}
            cod_cfg = st.selectbox("Código", list(nomes_cod), format_func=lambda c: f"{c} – {nomes_cod[c]}")
            clicou_cfg = st.button("Ver configurações")
            slot_cfg = mostrar_painel("e1_config", alvo=cod_cfg)
            if clicou_cfg:
                p_cfg = Painel("e1_config", "Etapa 1 · Carregar as configurações do código", slot_cfg, alvo=cod_cfg)
                p_cfg.agora(f"Compras.gov.br: configurações do código {cod_cfg}")
                p_cfg.barra(None, f"Consultando o código {cod_cfg}")
                try:
                    with respondendo([]):
                        st.session_state["configs"] = {"codigo": cod_cfg, "itens": f.itens_do_pdm(cod_cfg)}
                except Exception as exc:  # noqa: BLE001
                    p_cfg.falhar(f"não consegui carregar as configurações do código {cod_cfg} ({type(exc).__name__}). Isso não diz nada sobre o código.")
                    raise
                p_cfg.concluir(f"{len(st.session_state['configs']['itens'])} configuração(ões) do código {cod_cfg}")
            cfg = st.session_state.get("configs")
            if cfg and cfg["codigo"] == cod_cfg:
                perfil_cfg = f.perfil_do_pdm(cod_cfg, nomes_cod[cod_cfg], produtos)
                filtro_txt = st.text_input("Filtrar pelo texto da descrição", key=f"cfg_txt_{cod_cfg}")
                pedidos_cfg = {}
                if perfil_cfg:
                    st.write(f"Filtrar pelos atributos ({perfil_cfg}); ficam de fora os que dão \"não atende\":")
                    cols_cfg = st.columns(len(produtos[perfil_cfg]), width=170 * len(produtos[perfil_cfg]))
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
                    sel = st.dataframe(df_cfg, hide_index=True, width="stretch", height=altura_tabela(len(df_cfg)), on_select="rerun", selection_mode="single-row", key=f"sel_cfg_{cod_cfg}_{chave_sel}")
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
        st.caption("Códigos marcados são os serviços que o botão Buscar compras do serviço vai consultar (até 6, todos de uma vez numa tabela só). "
                   "Com 0 marcados (e nenhum código digitado na opção avançada), a busca não consulta nada e pede que você escolha um código. A lista só mostra serviços ativos.")
    return escolhidos


def etapa1(tipo):
    """Etapa 1 (Buscar): UMA função para Produto e Serviço (Pedido 13B). Mesma coluna única (2/3 da tela, o resto vazio), mesma ordem de blocos e mesmos rótulos de botão:
    a) título; b) campo + 'Procurar no catálogo'; c) legenda do catálogo com o botão 'Atualizar catálogo' (nos DOIS modos, mesmo lugar, mesmo rótulo e largura; Pedido 13F); lista do que a procura achou;
    d) 'Opção avançada: digitar o código do catálogo'; e) 'Modo e UF' (o produto acrescenta atributos e 'aceitar valores maiores'); f) botão Buscar.
    Devolve um dict com o que a busca precisa. As tabelas de resultado (Etapas 2 a 5) ficam fora desta coluna, em largura total."""
    global catalogo_info   # conferir_fora_da_trava (função de módulo) lê o catálogo de PDMs por este nome
    eh_prod = tipo == "Produto"
    e = {"termo": "", "produto": None, "buscar": False, "escolhidos": [], "por_codigo": {}, "erro_codigo": "", "modo": "rápido", "uf": ""}
    _e1, esq, _d1 = st.columns([1, 3, 1])                  # coluna CENTRAL da Etapa 1 (regra de largura: ver o comentário acima)
    e["coluna"] = esq
    with esq, cartao("etapa1_procurar"):
        st.subheader("Etapa 1 · Buscar")
        st.markdown("##### Procurar no catálogo")
        cb1, cb2 = st.columns([2, 1], vertical_alignment="bottom")
        if eh_prod:
            termo = cb1.text_input("O que você procura? (ex.: notebook, laptop, nobreak, monitor 24)", key="termo",
                                   on_change=lambda: st.session_state.__setitem__("procurar_agora", True))     # Enter também procura
        else:
            termo = cb1.text_input("Palavra do serviço (ex.: manutenção elétrica, limpeza, vigilância)", key="serv_termo",
                                   on_change=lambda: st.session_state.__setitem__("serv_procurar_agora", True))
        procurar = cb2.button("Procurar no catálogo", width="stretch", type="primary" if VISUAL_NOVO else "secondary") or st.session_state.pop("procurar_agora" if eh_prod else "serv_procurar_agora", False)
        e["termo"] = termo
        # ---- c) legenda do catálogo + botão Atualizar catálogo: o MESMO bloco nos dois modos (Pedido 13F: nenhuma diferença de botões entre Produto e Serviço)
        if eh_prod:
            if not f.CATALOGO_PDM.exists():
                baixar_catalogo_na_tela(False)  # primeira vez
            catalogo_info = f.ler_catalogo_pdm()
            texto_cat = (f"Catálogo oficial de materiais: {len(catalogo_info):,}".replace(",", ".") + " códigos, atualizado em "
                         + f"{catalogo_info[0]['baixado_em'][:16].replace('T', ' ')} (config\\catalogo_pdm.csv).")
            ajuda_cat = "Baixa de novo a lista oficial de PDMs: 41 páginas, cerca de 3 minutos."
        else:
            caminho = sv.CATALOGO_SERVICOS
            try:
                stt = caminho.stat()
                catalogo = catalogo_servicos_na_memoria(str(caminho), (stt.st_size, int(stt.st_mtime)))
            except OSError:
                catalogo = None
            if catalogo is None:
                texto_cat = f"Catálogo oficial de serviços (CATSER): não encontrei config\\catalogo_servicos.csv."
            else:
                datas = sorted({(r.get("baixado_em") or "") for r in catalogo if r.get("baixado_em")})
                quando = datas[-1][:16].replace("T", " ") if datas else "data desconhecida"
                texto_cat = (f"Catálogo oficial de serviços (CATSER): {len(catalogo):,}".replace(",", ".") + f" serviços, atualizado em {quando} (config\\catalogo_servicos.csv).")
            ajuda_cat = "Baixa de novo a lista oficial de serviços (CATSER): 7 páginas, cerca de 30 segundos. Se o portal falhar ou a lista vier incompleta, o catálogo atual é mantido."
        cl1, cl2 = st.columns([2, 1], vertical_alignment="center")
        cl1.caption(texto_cat)
        clicou_cat = cl2.button("Atualizar catálogo", help=ajuda_cat, width="stretch")
        slot_cat = mostrar_painel("e1_catalogo")      # Pedido 13I: painel do catálogo, nos dois modos, sempre à vista
        if clicou_cat:
            if eh_prod:
                baixar_catalogo_na_tela(True, slot=slot_cat)
                st.session_state.pop("pdms", None)
                st.rerun()
            elif baixar_catalogo_na_tela(True, "Serviço", slot=slot_cat):
                st.rerun()
        if not eh_prod:
            if catalogo is None:
                st.error(f"Não achei o catálogo de serviços em {caminho}. Sem ele a busca de serviço não funciona; use 'Atualizar catálogo' para baixá-lo.")
                return e
            idx_serv = {str(r["codigoServico"]): r for r in catalogo}
        slot_proc = mostrar_painel("e1_procurar")     # Pedido 13I: painel de "Procurar no catálogo", nos dois modos
        # ---- procurar (só catálogo local no serviço; no produto, as contagens de compras)
        if eh_prod:
            if procurar and termo.strip():
                anterior = st.session_state.get("pdms")
                if not anterior or f.norm(anterior["termo"]) != f.norm(termo):
                    limpar_produto_anterior()  # termo novo: o resultado e o código do produto anterior saem sozinhos
                p_proc = Painel("e1_procurar", "Etapa 1 · Procurar no catálogo", slot_proc)
                p_proc.agora("procurando o termo na lista oficial de materiais")
                res_busca = f.procurar_tolerante(termo, catalogo_info, limite=15)
                cache_cont = st.session_state.setdefault("contagens", {})
                # compras e configurações: 2 chamadas por código, só os 6 primeiros códigos ativos
                a_contar = [r for r in res_busca["achados"] if r["ativo"]][:6]
                res_busca["da_sessao"] = sum(1 for r in a_contar if r["codigoPdm"] in cache_cont)
                def _conta_codigos():
                    p_proc.barra(0.0, "Consultando cada código")
                    for i, r in enumerate(a_contar, 1):
                        cod = r["codigoPdm"]
                        if cod not in cache_cont:
                            p_proc.agora(f"Compras.gov.br: compras e configurações do código {cod} ({r['nomePdm'][:50]})")
                            with respondendo([]):
                                cache_cont[cod] = {"compras": f.contar_compras_pdm(cod), "configs": f.contar_itens_pdm(cod)}
                        p_proc.barra(i / len(a_contar), f"Consultando códigos: {i} de {len(a_contar)}")
                        p_proc.tempo()

                try:
                    if a_contar:
                        com_relogio(p_proc, _conta_codigos)     # Pedido 13K (C2)
                except Exception as exc:  # noqa: BLE001
                    p_proc.falhar(f"a consulta de compras dos códigos parou ({type(exc).__name__}). O resultado do catálogo não foi afetado.")
                    raise
                n_ach = len(res_busca["achados"])
                p_proc.concluir(f"{n_ach} código(s) encontrado(s) no catálogo"
                                + (f"; compras e configurações consultadas para {len(a_contar)} código(s)" if a_contar else "; nenhum código ativo para consultar compras"))
                st.session_state["pdms"] = {**res_busca, "termo": termo}
                st.session_state.pop("configs", None)
            pass   # (a região de resultado do produto vem logo abaixo, FORA da coluna)
        else:
            if procurar and termo.strip():
                anterior_s = st.session_state.get("serv_busca")
                if not anterior_s or f.norm(anterior_s["termo"]) != f.norm(termo):
                    limpar_servico_anterior()  # termo novo: a busca atual vai para "Buscas anteriores" e os códigos marcados saem (mesma regra do produto)
                p_proc = Painel("e1_procurar", "Etapa 1 · Procurar no catálogo", slot_proc)
                p_proc.agora("procurando o termo na lista oficial de serviços (sem consultar o portal)")
                achados_s = sv.procurar(termo, catalogo)   # só catálogo local: sem rede e sem contagem de compras
                st.session_state["serv_busca"] = {"termo": termo, "achados": achados_s}
                p_proc.concluir(f"{len(achados_s)} serviço(s) encontrado(s) no catálogo; nenhuma consulta ao portal")
    # ---- região de resultado da procura, a mesma função nos dois modos, em LARGURA TOTAL (Pedido 13D): fora da coluna de 2/3
    if eh_prod:
        pd_state = st.session_state.get("pdms")
        escolhidos = lista_resultados(True, pd_state)
    else:
        busca_s = st.session_state.get("serv_busca")
        escolhidos = lista_resultados(False, busca_s)
    _e2, esq2, _d2 = st.columns([1, 3, 1])                 # 2ª coluna central: opção avançada, Modo e UF e o botão Buscar
    e["coluna"] = esq2                                     # as mensagens do clique em Buscar aparecem aqui, junto do botão
    with esq2, cartao("etapa1_buscar"):
        # ---- d) opção avançada: digitar o código
        if eh_prod:
            with st.expander("Opção avançada: digitar o código do catálogo", expanded=bool(st.session_state.get("codigo_av"))):
                codigo = st.text_input("Código (só números; se preenchido, substitui os códigos marcados acima)", key="codigo_av")
                tipo_cod = st.radio("O código é", ["Tipo de produto (PDM) – todos os modelos", "Configuração específica (item CATMAT)"], index=0, key="tipo_av")
                conferido = None
                if not codigo.strip().isdigit():
                    limpar_paineis("e1_conferir")          # Pedido 13I: sem código digitado, o painel da conferência some
                slot_conf = mostrar_painel("e1_conferir", alvo=codigo.strip())
                if codigo.strip().isdigit():
                    eh_pdm = tipo_cod.startswith("Tipo de produto")
                    chave_conf = (codigo.strip(), eh_pdm)
                    chave_global = (st.session_state.setdefault("sessao_id", uuid.uuid4().hex), *chave_conf)
                    if st.session_state.get("conf_chave") != chave_conf:
                        # a chave é gravada antes da chamada: uma reexecução durante a consulta espera o resultado em vez de consultar de novo
                        p_conf = Painel("e1_conferir", "Etapa 1 · Conferir o código digitado", slot_conf, alvo=codigo.strip())
                        p_conf.agora(f"conferindo o código {codigo.strip()} no catálogo (Compras.gov.br)")
                        p_conf.barra(None, f"Conferindo o código {codigo.strip()}")
                        res_conf = conferencias().obter(chave_global, lambda: conferir_fora_da_trava(codigo.strip(), eh_pdm),
                                                        LIMITE_ESPERA_CONFERENCIA_S)
                        if res_conf["estado"] == "pronto":
                            st.session_state["conf_valor"] = res_conf["valor"]
                            st.session_state["conf_chave"] = chave_conf
                            p_conf.concluir(f"código {codigo.strip()}: " + (res_conf["valor"].get("nome") or res_conf["valor"].get("aviso") or "conferido"))
                        elif res_conf["estado"] == "erro":
                            p_conf.falhar(f"não consegui conferir o código {codigo.strip()}. Isso não diz nada sobre o código.")
                            st.error(f"Não consegui conferir o código {codigo.strip()} ({res_conf['valor']}). Isso não diz nada sobre o código.")
                            st.button("Tentar conferir de novo", on_click=lambda: conferencias().esquecer(chave_global))
                        else:
                            p_conf.falhar("a conferência não terminou a tempo. Mexa em qualquer campo para tentar de novo.")
                            st.warning("A conferência do código ainda não terminou. Espere um pouco e mexa em qualquer campo para atualizar.")
                    if st.session_state.get("conf_chave") == chave_conf:
                        conferido = st.session_state["conf_valor"]
                        if conferido["aviso"]:
                            st.warning(conferido["aviso"])
                        else:
                            st.success(f"Código {codigo.strip()}: {conferido['nome']}")
                elif codigo.strip():
                    st.error("O código do catálogo deve ter só números.")
        else:
            with st.expander("Opção avançada: digitar o código do catálogo", expanded=bool(st.session_state.get("serv_codigo_av"))):
                codigo_s = st.text_input("Código do serviço (1 a 6 números separados por vírgula; se preenchido, substitui os códigos marcados acima)", key="serv_codigo_av")
                if not codigo_s.strip():
                    limpar_paineis("e1_conferir")          # Pedido 13I: sem código digitado, o painel da conferência some
                slot_conf = mostrar_painel("e1_conferir", alvo=codigo_s.strip())
                p_conf = Painel("e1_conferir", "Etapa 1 · Conferir o código digitado", slot_conf, alvo=codigo_s.strip()) if codigo_s.strip() else None
                cods_av, erro_av, avisos_av = validar_codigos_servico(codigo_s, idx_serv)
                if p_conf:
                    p_conf.agora("conferindo o(s) código(s) no catálogo local de serviços (sem consultar o portal)")
                    p_conf.concluir(f"{len(cods_av)} código(s) no catálogo local") if not erro_av else p_conf.falhar(erro_av)
                if erro_av:
                    st.error(erro_av)
                elif cods_av:
                    st.success("Código(s) no catálogo local: " + "; ".join(f"{c} – {idx_serv[c]['nomeServico']}" for c in cods_av))
                    for a_ in avisos_av:
                        st.warning(a_)
            e["erro_codigo"] = erro_av
            if codigo_s.strip() and not erro_av:
                escolhidos = cods_av
            elif codigo_s.strip() and erro_av:
                escolhidos = []
            e["por_codigo"] = {c: idx_serv[c] for c in escolhidos if c in idx_serv}
        # ---- e) Modo e UF (+ atributos no produto) e f) botão Buscar
        st.markdown("##### Modo e UF")
        if eh_prod:
            perfil_auto = None
            if conferido and conferido.get("codigo_pdm"):
                perfil_auto = f.perfil_do_pdm(conferido["codigo_pdm"], conferido["nome_pdm"], produtos)
            elif escolhidos:
                r0 = next((r for r in [*pd_state["achados"], *catalogo_info] if int(r["codigoPdm"]) == escolhidos[0]), None)   # Pedido 13K: o código pode vir da sugestão (não está nos achados)
                perfil_auto = f.perfil_do_pdm(r0["codigoPdm"], r0["nomePdm"], produtos) if r0 else None
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
        with st.form("entrada" if eh_prod else "entrada_servico"):
            c3, c4 = st.columns([2, 1])
            modo = c3.radio("Modo", ["rápido", "completo"], index=0, key=None if eh_prod else "serv_modo",
                            help=f"Rápido: menos páginas e consultas (amostra menor); só {MODOS['rápido']['MAX_VINCULOS']} compras são ligadas ao PNCP. Completo: liga até {MODOS['completo']['MAX_VINCULOS']}.")
            uf = c4.text_input("UF", key="uf_busca" if eh_prod else "serv_uf", help="Vazio = todas as UFs.", width=100)
            if eh_prod:
                valores = {}
                if atributos_tela:
                    st.write("Atributos (deixe vazio o que não importa):")
                    cols = st.columns(len(atributos_tela), width=170 * len(atributos_tela))   # Pedido 13: campos de atributo estreitos
                    for col, a in zip(cols, atributos_tela):
                        un = UNIDADE_TXT.get(a["unidade"], a["unidade"])
                        valores[a["nome"]] = col.text_input(f"{a['nome']} – só o número, em {un}", key=f"at_{produto}_{a['nome']}",
                                                            help=f"Faixa aceita: {a['regra']} (x = valor digitado)"
                                                                 + (". Aceita também 960G, 1TB, 1 T." if a["unidade"] == "GB" else ""))
                aceitar = st.checkbox("Aceitar valores maiores que o pedido (RAM, armazenamento, garantia)", key="aceitar_busca",
                                      help="Sem a opção vale a faixa do produtos.csv (ex.: RAM 16 aceita de 16 a 32). Com a opção, não há teto: 64 GB também atende.")
                st.caption("Os atributos, a UF, o modo e a opção acima só valem quando você clica em Buscar.")
                if len(escolhidos) >= 1:
                    st.caption(sv.aviso_custo_produto(len(escolhidos), MODOS))      # Pedido 18: custo da busca de Produto antes de clicar (com 1 ou mais códigos)
                buscar = st.form_submit_button("Buscar", type="primary")
            else:
                st.caption("O modo e a UF só valem quando você clica em Buscar.")
                if len(escolhidos) >= 2:
                    st.caption(sv.estimativa_busca(len(escolhidos)))      # Pedido 17: custo da busca antes de clicar
                buscar = st.form_submit_button("Buscar compras do serviço", type="primary")
    e.update(escolhidos=escolhidos, modo=modo, uf=uf, buscar=buscar)
    if eh_prod:
        e.update(produto=produto, codigo=codigo, tipo_cod=tipo_cod, conferido=conferido, atributos_tela=atributos_tela, valores=valores, aceitar=aceitar)
    return e


def buscar_servico(area, e):
    """Executa a busca de SERVIÇO (clique em 'Buscar compras do serviço'). NÃO TESTADO COM REDE de ponta a ponta: só com respostas simuladas."""
    escolhidos, por_codigo, modo_s, uf_s, termo_s = e["escolhidos"], e["por_codigo"], e["modo"], e["uf"], e["termo"]
    with e["coluna"]:   # Pedido 13C: mensagens da Etapa 1 na coluna da Etapa 1
        etapas = ["1. Pesquisa de preço do serviço (Compras.gov.br)", "2. Ligação ao PNCP"]
        pb = Painel("e2_buscar", "Etapa 2 · Buscar compras do serviço", area, barras=[PASSO0, *etapas])   # Pedido 13I: o mesmo painel do produto
        if e["erro_codigo"]:
            pb.falhar("código inválido; nenhuma consulta foi feita")
            st.error(f"A busca não foi feita: {e['erro_codigo']}")
            st.stop()
        if not escolhidos:
            pb.falhar("nenhum código escolhido; nenhuma consulta foi feita")
            st.error("A busca não foi feita: escolha pelo menos 1 código de serviço. Procure pela palavra e marque o(s) código(s) na lista, ou digite na opção avançada.")
            st.stop()
        pb.agora("Passo 0: conferência offline antes de qualquer consulta")
        pb.barra(None, PASSO0, PASSO0)
        with respondendo([]):
            erros = f.autoteste()
        if erros:
            pb.falhar("a conferência offline falhou; nenhuma consulta foi feita")
            st.error(f"Preflight offline falhou; nenhuma chamada de rede foi feita: {erros}")
            st.stop()
        pb.barra(1.0, f"{PASSO0}: concluído", PASSO0)
    barras = pb.barras
    inicio = time.time()
    est = {"pag": 0, "lig": 0, "ids": set(), "cod": None, "pag_cod": 0, "tot_cod": None, "cods_feitos": 0}

    def ao_chamar(fase, url, params, resultado):
        if fase == "antes":
            pb.agora(acao_atual(url, params))
            return
        js = resultado[1]
        if "3_consultarServico" in url:
            est["pag"] += 1
            if isinstance(js, dict):
                est["ids"].update(str(r.get("idCompra")) for r in js.get("resultado", []) if r.get("idCompra"))
            # Pedido 13K: % real = códigos concluídos + páginas do código atual (total de páginas vem da API); antes era páginas lidas / teto do modo (não era o total)
            if est["cod"] != params.get("codigoItemCatalogo"):
                est.update(cod=params.get("codigoItemCatalogo"), pag_cod=0, tot_cod=None)
            est["pag_cod"] += 1
            if isinstance(js, dict) and est["tot_cod"] is None and js.get("totalRegistros") is not None:
                est["tot_cod"] = min(-(-int(js["totalRegistros"]) // 100), MODOS[modo_s]["MAX_PAGINAS_CATALOGO"]) or 1
            acabou = not (js or {}).get("paginasRestantes") if isinstance(js, dict) else False
            acabou = acabou or est["pag_cod"] >= MODOS[modo_s]["MAX_PAGINAS_CATALOGO"]
            if acabou:
                est["cods_feitos"] += 1
            frac_atual = 0.0 if acabou else min(est["pag_cod"] / (est["tot_cod"] or est["pag_cod"] + 1), 1.0)
            n_cods = max(len(escolhidos), 1)
            barras[etapas[0]].progress(min((est["cods_feitos"] + frac_atual) / n_cods, 1.0),
                                       text=f"{etapas[0]}: {est['pag']} página(s) lida(s) · código {min(est['cods_feitos'] + (0 if acabou else 1), n_cods)} de {n_cods}")
        elif "1.1_consultarContratacoes" in url:
            est["lig"] += 1
            total = min(len(est["ids"]), MODOS[modo_s]["MAX_VINCULOS"]) or MODOS[modo_s]["MAX_VINCULOS"]
            barras[etapas[0]].progress(1.0, text=f"{etapas[0]}: concluída")
            barras[etapas[1]].progress(min(est["lig"] / total, 1.0), text=f"{etapas[1]}: {est['lig']} de {total} compras procuradas no PNCP")
        pb.tempo()

    def _busca():
        with respondendo([], ao_chamar) as log, limites(modo_s):
            return sv.buscar_servicos(escolhidos, uf_s.strip().upper()), log.getvalue()

    resumo, log_txt = com_relogio(pb, _busca)     # Pedido 13K (C2): o tempo decorrido sobe a cada 1 s enquanto a busca roda
    csv_fim = Path(resumo["arquivo"]).read_bytes()
    df_fim = montar_tabela(resumo, csv_fim)
    na_api, lidos = resumo.get("registros_informados_pela_api"), resumo.get("registros_lidos") or 0
    fim_txt = (f"{na_api:,} na API → {lidos:,} lidos → {len(df_fim):,} no período de 12 meses".replace(",", ".") if na_api else f"{len(df_fim)} linhas")
    pb.concluir(fim_txt, verbo="Concluída com falhas" if resumo.get("falhas") else "Concluída")      # Pedido 17 (0.3)
    arquivar_busca_atual()
    st.session_state.pop("canal_oficial", None)
    st.session_state.pop("lista_tr", None)
    st.session_state["busca_atual"] = {"resumo": resumo, "csv": csv_fim, "quando": time.strftime("%d/%m %H:%M"), "aceitar": False, "fim_txt": fim_txt,
                                       "log": log_txt, "tempo": time.time() - inicio, "codigos": ", ".join(escolhidos), "termo": termo_s, "eh_item": True,
                                       "tipo": "serviço", "item_recorte": sv.palavras_do_recorte([por_codigo[c]["nomeServico"] for c in escolhidos])}
    st.session_state.pop("docs", None)
    st.rerun()


# ----------------------------------------------------------------- tela
st.set_page_config(page_title="Referência TIC", layout="wide")

# ----------------------------------------------------------------- Pedido 36: visual novo, SÓ aparência
VISUAL_NOVO = True   # True liga o visual novo; False = app exatamente como antes (nenhum widget, rótulo, aviso ou chave muda de um modo para o outro)

_PILHA_CARTOES = []   # cartões abertos por cartao_ini (zerada a cada execução do script)


def cartao(nome):
    """Agrupa um bloco num cartão (st.container com borda) quando VISUAL_NOVO; com False devolve um contexto vazio. A chave só dá ao CSS um seletor estável (classe st-key-cartao_<nome>)."""
    return st.container(border=True, key=f"cartao_{nome}") if VISUAL_NOVO else contextlib.nullcontext()


def cartao_ini(nome):
    """Abre um cartão SEM reindentar o código que vem depois; cartao_fim() fecha o último aberto, no mesmo nível de indentação do mesmo bloco."""
    if VISUAL_NOVO:
        c = st.container(border=True, key=f"cartao_{nome}")
        c.__enter__()
        _PILHA_CARTOES.append(c)


def cartao_fim():
    if VISUAL_NOVO and _PILHA_CARTOES:
        _PILHA_CARTOES.pop().__exit__(None, None, None)


# CSS que serve nos DOIS temas sem calcular cor em Python: o Streamlit põe color-scheme claro/escuro no .stApp conforme o tema escolhido (Claro, Escuro ou Sistema), então
# light-dark(claro, escuro) troca sozinho na hora, sem recarregar. Os valores repetem as cores de .streamlit/config.toml; o resto usa currentColor, inherit e color-mix.
CSS_VISUAL = """
.stApp { --ref-prim: light-dark(#1E3A5F, #7FB0FF); --ref-prim-texto: light-dark(#FFFFFF, #0F1B2D); --ref-cartao: light-dark(#FFFFFF, #162A44);
         --ref-borda: light-dark(#E3E8EF, #243B58); --ref-sombra-cor: light-dark(rgba(16,24,40,.10), rgba(0,0,0,.40)); }
[data-testid="stMainBlockContainer"], [data-testid="stAppViewBlockContainer"], .stMain .block-container { max-width:1200px !important; margin-left:auto; margin-right:auto; }
.ref-cabecalho { display:flex; align-items:center; gap:.6rem; padding:.1rem 0 .7rem 0; margin-bottom:.5rem; border-bottom:1px solid var(--ref-borda);
                 font-weight:700; font-size:1.1rem; letter-spacing:.2px; color:inherit; }
.ref-cabecalho .ref-marca { width:.8rem; height:.8rem; border-radius:4px; background:var(--ref-prim); display:inline-block; }
.ref-faixa { display:flex; flex-wrap:wrap; gap:.5rem; margin:0 0 1.2rem 0; }
.ref-passo { display:inline-flex; align-items:center; gap:.45rem; padding:.3rem .8rem .3rem .35rem; border:1px solid var(--ref-borda); border-radius:999px;
             background:var(--ref-cartao); font-size:.86rem; color:inherit; }
.ref-passo b { display:inline-flex; align-items:center; justify-content:center; width:1.35rem; height:1.35rem; border-radius:50%; background:var(--ref-prim); color:var(--ref-prim-texto); font-size:.78rem; }
[class*="st-key-cartao_"] { background:var(--ref-cartao); border:1px solid var(--ref-borda) !important; border-radius:14px !important; box-shadow:0 1px 3px var(--ref-sombra-cor); padding:.9rem 1.1rem 1rem 1.1rem; margin-bottom:1.4rem; }
[class*="st-key-cartao_"] h3 { border-left:4px solid var(--ref-prim); padding-left:.7rem; font-weight:700; font-size:1.4rem; }
[data-testid="stHeading"] h1 { font-size:2rem; font-weight:700; }
/* mesma largura para tudo: o topo e a Etapa 1 ficam em colunas [1, 3, 1] (estrutura fixada por testes); só no visual novo as colunas laterais vazias somem e a central ocupa a largura toda */
[data-testid="stHorizontalBlock"]:has([class*="st-key-cartao_etapa1"]) > [data-testid="stColumn"]:not(:nth-child(2)),
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] h1) > [data-testid="stColumn"]:not(:nth-child(2)) { display:none; }
[data-testid="stHorizontalBlock"]:has([class*="st-key-cartao_etapa1"]) > [data-testid="stColumn"]:nth-child(2),
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] h1) > [data-testid="stColumn"]:nth-child(2) { flex:1 1 100% !important; width:100% !important; min-width:0; }
[data-testid="stMetric"] { background:var(--ref-cartao); border:1px solid var(--ref-borda); border-radius:14px; box-shadow:0 1px 3px var(--ref-sombra-cor); padding:.7rem .9rem; }
[data-testid="stMetricValue"] { font-weight:700; }
[data-testid="stAlert"] { border-radius:12px; border:1px solid color-mix(in srgb, currentColor 14%, transparent); }
[data-testid="stCaptionContainer"] { font-size:.82rem; opacity:.82; }
[data-testid="stDataFrame"] { border:1px solid var(--ref-borda); border-radius:12px; overflow:hidden; }
[data-testid="stTextInputRootElement"] { border:1.5px solid color-mix(in srgb, currentColor 55%, transparent) !important; min-height:2.9rem; }
[data-testid="stTextInputRootElement"]:focus-within { border-color:var(--ref-prim) !important; box-shadow:0 0 0 2px color-mix(in srgb, var(--ref-prim) 35%, transparent); }
button[data-testid^="stBaseButton-secondary"] { font-weight:500; box-shadow:none; }
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] { font-weight:600; color:var(--ref-prim-texto) !important; }
button[data-testid="stBaseButton-primary"] p, button[data-testid="stBaseButton-primaryFormSubmit"] p { color:var(--ref-prim-texto) !important; }
[data-testid="stProgress"] [role="progressbar"] > div { background-color:var(--ref-prim) !important; }
"""


HTML_CABECALHO = '<div class="ref-cabecalho"><span class="ref-marca"></span>Referência TIC</div><div class="ref-faixa"><span class="ref-passo"><b>1</b>Buscar</span><span class="ref-passo"><b>2</b>Escolher a compra</span><span class="ref-passo"><b>3</b>Recorte</span><span class="ref-passo"><b>4</b>IA</span><span class="ref-passo"><b>5</b>Conferir</span></div>'   # ref-cabecalho


def tabela_destaque(tab):
    """Só visual: com VISUAL_NOVO, realça (fundo verde translúcido, preço em negrito) a(s) linha(s) de MENOR preço homologado da própria tabela, se houver 2 ou mais preços. Não muda ordem, valores nem colunas;
    com False (ou sem 2 preços) devolve a tabela como veio."""
    if not VISUAL_NOVO or "preco_unitario_homologado" not in tab.columns:
        return tab
    p = pd.to_numeric(tab["preco_unitario_homologado"], errors="coerce")
    if int(p.notna().sum()) < 2:
        return tab
    estilos = pd.DataFrame("", index=tab.index, columns=tab.columns)
    estilos.iloc[(p == p.min()).to_numpy(), :] = "background-color: rgba(46, 160, 67, 0.22)"
    estilos.loc[:, "preco_unitario_homologado"] = estilos["preco_unitario_homologado"].where(~(p == p.min()).to_numpy(), "background-color: rgba(46, 160, 67, 0.22); font-weight: 700")
    return tab.style.apply(lambda _: estilos, axis=None)


def aplicar_visual():
    """Injeta o CSS do visual novo (st.html) e o cabeçalho com a faixa estática das 5 etapas (só visual; nenhum widget, texto, rótulo ou aviso muda)."""
    if VISUAL_NOVO:
        st.html(f"<style>{CSS_VISUAL}</style>")
        st.markdown(HTML_CABECALHO, unsafe_allow_html=True)   # ref-cabecalho


if VISUAL_NOVO:
    aplicar_visual()

produtos = f.ler_produtos()
UNIDADE_TXT = {"GB": "GB", "polegadas": "polegadas", "meses": "meses", "portas": "portas", "MP": "megapixels",
               "m": "metros", "VA": "VA", "minutos": "minutos"}
SEM_REGRAS = "(sem regras de atributos)"
PASSO0 = "Passo 0 · Conferência offline"


def usar_sugestao(nome):
    """Clique em 'Você quis dizer': troca o termo e procura de novo."""
    st.session_state["termo"] = nome
    st.session_state["procurar_agora"] = True


def usar_config(codigo_item):
    """Botão 'Usar esta configuração': preenche a opção avançada com o item CATMAT."""
    st.session_state["codigo_av"] = str(codigo_item)
    st.session_state["tipo_av"] = "Configuração específica (item CATMAT)"


def baixar_catalogo_na_tela(forcar, tipo="Produto", slot=None):
    """Baixa o catálogo mostrando o painel de progresso: PDMs (Produto, 41 páginas, cerca de 3 min) ou serviços (CATSER). Devolve True se o arquivo foi atualizado.
    No serviço, portal fora ou catálogo rejeitado na conferência = o painel mostra "Falhou: ..." e o catálogo atual é mantido (False)."""
    nome = "materiais" if tipo == "Produto" else "serviços"
    painel_cat = Painel("e1_catalogo", f"Etapa 1 · Atualizar o catálogo de {nome}", slot if slot is not None else st.empty())
    painel_cat.barra(None, f"Baixando o catálogo de {nome}")
    marca = {"ini": None}

    def ao_catalogo(fase, url, params, resultado):
        if fase == "antes":
            painel_cat.agora(f"Compras.gov.br, catálogo de {'PDMs' if tipo == 'Produto' else 'serviços'}: página {params.get('pagina')}")
            if marca["ini"] is None:
                marca["ini"] = time.time()
        elif isinstance(resultado[1], dict):
            tot = resultado[1].get("totalPaginas") or 1
            pag = params.get("pagina", 1)
            resta = f" · faltam ~{tempo_fmt((time.time() - marca['ini']) / pag * (tot - pag))}" if marca["ini"] and 0 < pag < tot else ""
            painel_cat.barra(min(pag / tot, 1.0), f"Catálogo: página {pag} de {tot}{resta}")
            painel_cat.tempo()

    def _baixa_catalogo():
        with respondendo([], ao_catalogo):
            if tipo == "Produto":
                return len(f.baixar_catalogo_pdm(forcar=forcar))
            return len(sv.baixar_catalogo_servicos(forcar=forcar))

    try:
        n_linhas = com_relogio(painel_cat, _baixa_catalogo)     # Pedido 13K (C2)
    except f.PortalFora as exc:
        painel_cat.falhar(f"não atualizei o catálogo; o atual foi mantido. {exc}")
        if tipo == "Produto":
            raise
        st.error(f"Não atualizei o catálogo de serviços: {exc}")
        return False
    painel_cat.concluir(f"catálogo de {nome} atualizado, {n_linhas:,} registros".replace(",", "."))
    return True


_te, topo, _td = st.columns([1, 3, 1])   # Pedido 13E (regra de largura): cabeçalho e controles do topo na coluna CENTRAL
with topo:
    st.title("Referência TIC – busca de compras públicas")
    st.caption("Só dados públicos (PNCP e Compras.gov.br). A busca e os filtros são regras fixas, sem IA. "
               "O resultado apoia a decisão; não substitui a pesquisa de preços formal da Lei 14.133/2021.")
    st.info("Limites: a IA apoia, quem decide é a seção; a busca não usa IA.")
    tipo_busca = st.radio("O que você vai pesquisar?", ["Produto", "Serviço"], horizontal=True, key="tipo_busca",
                          help="Produto: materiais (notebook, monitor...). Serviço: catálogo de serviços (CATSER). O restante do fluxo é o mesmo.")
    st.button("Nova busca", on_click=nova_busca, help="Limpa a tela. A busca atual fica em \"Buscas anteriores\", no fim da página.")

produto = None   # v4h: definidos aqui para o restante da tela (a busca de serviço não os preenche)
termo = ""
e1 = etapa1(tipo_busca)          # Etapa 1: UMA função para Produto e Serviço (Pedido 13B)
termo, produto = e1["termo"], e1["produto"]
area_resultado = st.empty()  # o resumo e a tabela ficam aqui: uma nova busca limpa esta área na hora
if tipo_busca == "Produto":
    codigo, tipo_cod, conferido, escolhidos, atributos_tela, valores, modo, uf, aceitar, buscar = (
        e1[k] for k in ("codigo", "tipo_cod", "conferido", "escolhidos", "atributos_tela", "valores", "modo", "uf", "aceitar", "buscar"))

    if buscar:
        etapas = ["1. Catálogo (Compras.gov.br)", "2. Filtros de atributos", "3. Ligação ao PNCP"]
        pb = Painel("e2_buscar", "Etapa 2 · Buscar compras", area_resultado, barras=[PASSO0, *etapas])   # Pedido 13I: painel único, sempre aberto (inclui o passo 0)
        with e1["coluna"]:   # Pedido 13C: mensagens da Etapa 1 na coluna da Etapa 1
            pb.agora("Passo 0: conferência offline antes de qualquer consulta")
            pb.barra(None, PASSO0, PASSO0)
            with respondendo([]):  # trava do servidor: ACEITAR_MAIORES é do módulo, compartilhado entre sessões
                erros = f.autoteste()  # preflight offline antes de qualquer chamada de rede
            if erros:
                pb.falhar("a conferência offline falhou; nenhuma consulta foi feita")
                st.error(f"Preflight offline falhou; nenhuma chamada de rede foi feita: {erros}")
                st.stop()
            pb.barra(1.0, f"{PASSO0}: concluído", PASSO0)
            if codigo.strip():
                if not codigo.strip().isdigit():
                    pb.falhar("o código do catálogo deve ter só números; nenhuma consulta foi feita")
                    st.error("O código do catálogo deve ter só números.")
                    st.stop()
                if conferido is None:
                    pb.falhar("o código ainda não foi conferido; nenhuma consulta foi feita")
                    st.error("A busca não foi feita: o código ainda não foi conferido no catálogo (veja o aviso na opção avançada). "
                             "Quando a conferência terminar, clique em Buscar de novo.")
                    st.stop()
                if conferido.get("codigo_pdm") and conferido["aviso"] and not conferido["nome"]:  # a conferência achou o código no OUTRO tipo
                    marcado_pdm = tipo_cod.startswith("Tipo de produto")
                    pb.falhar("o tipo do código (PDM ou item CATMAT) não confere com o catálogo; nenhuma consulta foi feita")
                    st.error(f"A busca não foi feita: o código {codigo.strip()} está marcado como "
                             f"{'tipo de produto (PDM)' if marcado_pdm else 'configuração específica (item CATMAT)'}, mas a conferência indica que é "
                             f"{'um item CATMAT' if marcado_pdm else 'um PDM'}. Em \"O código é\", marque "
                             f"\"{'Configuração específica (item CATMAT)' if marcado_pdm else 'Tipo de produto (PDM) – todos os modelos'}\" e clique em Buscar.")
                    st.stop()
                codigos = [(codigo.strip(), "2" if tipo_cod.startswith("Tipo de produto") else "1")]
            else:
                codigos = [(str(c), "2") for c in escolhidos]  # PDM: todos os modelos
            if not codigos:
                pb.falhar("nenhum código escolhido; nenhuma consulta foi feita")
                st.error("Escolha pelo menos 1 código: procure no passo 1 e marque \"usar\", ou digite na opção avançada.")
                st.stop()
        attrs = [valores[a["nome"]] for a in atributos_tela]
        barras = pb.barras
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
                    pb.agora(f"{prefixo}{acao_atual(url, params)}")
                    if listagem and est["e1_ini"] is None:
                        est["e1_ini"] = time.time()
                    if not listagem and est["e3_ini"] is None:  # entrou na etapa 3: etapas 1 e 2 já terminaram
                        est["e3_ini"] = time.time()
                        barras[etapas[0]].progress(1.0, text=f"{etapas[0]}: 100% · {prefixo}{est['e1_feito']} de {est['e1_feito']} páginas")
                        barras[etapas[1]].progress(1.0, text=f"{etapas[1]}: 100% · feitos localmente, sem consulta ao portal (resultado no fim)")
                    pb.tempo()
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
                pb.tempo()

            def _busca_cod():
                with respondendo(respostas, ao_chamar) as log, limites(modo, aceitar):
                    f.buscar_por_codigo()
                    resumos.append(json.loads((f.SAIDA / "ultima_busca.json").read_text(encoding="utf-8")))
                return log

            log = com_relogio(pb, _busca_cod)     # Pedido 13K (C2): o tempo decorrido sobe a cada 1 s
            logs.append(f.limpar_log_busca(log.getvalue()))  # sem o eco 'Preencha os atributos…' (Fase 3)
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
        pb.concluir(fim_txt, verbo="Concluída com falhas" if resumo_fim.get("falhas") else "Concluída")      # Pedido 17 (0.3)
        arquivar_busca_atual()
        st.session_state["busca_atual"] = {"resumo": resumo_fim, "csv": csv_fim, "quando": time.strftime("%d/%m %H:%M"), "aceitar": aceitar,
                                           "fim_txt": fim_txt, "log": "\n".join(logs), "tempo": time.time() - inicio,
                                           "codigos": ", ".join(c for c, _ in codigos), "termo": termo,
                                           "eh_item": any(t == "1" for _, t in codigos)}
        st.session_state.pop("docs", None)
        st.rerun()
else:
    if e1["buscar"]:
        buscar_servico(area_resultado, e1)

rec = st.session_state.get("busca_atual")
with area_resultado.container():
    _estado_e2 = st.session_state.get("painel_e2_buscar")
    if _estado_e2:
        _desenha_painel(st, _estado_e2)    # Pedido 13I: o painel da busca fica na tela com o estado final depois do rerun
    if not rec:
        cartao_ini("vazio_e2")
        st.subheader("Etapa 2 · Escolher a compra")   # Pedido 13C: a página não pula da Etapa 1 para a 5 sem explicação
        st.info("Nenhuma busca nesta sessão. Procure o serviço, marque o(s) código(s) e clique em Buscar compras do serviço." if tipo_busca == "Serviço"
                else "Nenhuma busca nesta sessão. Procure, marque um código, preencha os atributos e clique em Buscar.")
        cartao_fim()
        cartao_ini("vazio_e3")
        st.subheader("Etapa 3 · Recorte")
        st.caption("Depois da busca: escolha a compra, baixe o documento e gere o recorte (o texto fica dentro de 70% da janela).")
        cartao_fim()
        cartao_ini("vazio_e4")
        st.subheader("Etapa 4 · IA")
        st.caption("Depois do recorte: copie o texto para a IA e, na Etapa 5, cole a resposta para conferir.")
        cartao_fim()
    else:
        resumo = rec["resumo"]
        eh_serv = rec.get("tipo") == "serviço"
        df = montar_tabela(resumo, rec["csv"])
        pedidos_val = resumo.get("pedidos") or {}
        pedidos = list(pedidos_val)

        # ---------- resumo
        cartao_ini("etapa2_resumo")
        st.subheader("Etapa 2 · Escolher a compra: resumo da busca")
        if "PORTAL FORA" in rec["log"]:
            st.warning("O portal caiu ou bloqueou durante a busca. O que já tinha sido lido foi salvo.")
        total = len(df)
        contagem = df["situacao"].value_counts() if total else pd.Series(dtype=int)
        vinc = int((df["link_publico"].fillna("") != "").sum()) if total else 0
        susp = int((df.get("observacao_preco", pd.Series(dtype=str)).fillna("") == ("suspeito" if eh_serv else "preço suspeito")).sum()) if total else 0
        if eh_serv:
            m = st.columns(4)
            m[0].metric("Total", total)
            m[1].metric("Vinculados ao PNCP (linhas)", vinc)
            m[2].metric("Preço suspeito (marcado, não apagado)", susp)
            m[3].metric("Tempo", f"{rec['tempo']:.0f} s")
            st.caption(f"Busca de {rec['quando']} · serviço(s) código(s) {rec['codigos']} · {rec['fim_txt']} · chamadas: {resumo.get('chamadas')} · falhas: {resumo.get('falhas')} · "
                       f"modo: {resumo.get('modo', 'n/d')} · app {resumo.get('versao_app', 'n/d')}")
        else:
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
        aviso_corte = f.aviso_corte_busca(resumo)  # lidos < informados pela API (ex.: 300 no modo rápido)
        if aviso_corte:
            st.warning(aviso_corte)
        _av_rapido = sv.aviso_modo_rapido(df.to_dict("records"), resumo.get("modo"), "suspeito" if eh_serv else "preço suspeito") if total else None   # Pedido 25 (Fase 3)
        if _av_rapido:
            (st.warning if _av_rapido[1] else st.caption)(_av_rapido[0])
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

        cartao_fim()
        if total:
            # ---------- tabela
            cartao_ini("etapa2_resultados")
            st.subheader("Etapa 2 · Escolher a compra: resultados" + ("" if eh_serv else " (primeiro quem não tem 'não atende')"))
            if not eh_serv:     # Pedido 18: Produto com um único item de catálogo nas linhas lidas (nada muda no Serviço)
                _d0 = df.to_dict("records"); _n0 = {}
                for _l0 in _d0:
                    _n0.setdefault(re.sub(r"\.0$", "", str(_l0.get("codigo_catalogo") or "").strip()), str(_l0.get("descricao_item") or ""))      # Pedido 21: nome inteiro; quem corta (80, em palavra inteira) é sv.aviso_item_unico
                _aviso_unico = sv.aviso_item_unico(_d0, _n0)
                if _aviso_unico:
                    st.warning(_aviso_unico)
            # ---- Pedido 17: filtro por palavra (só no que já está na memória; nenhuma chamada à API) e resumo por código, iguais nos dois modos
            filtro_pal = st.text_input("Mostrar só linhas que citam a palavra", key="filtro_palavra",
                                       help="Procura a palavra inteira (sem diferenciar maiúscula nem acento) na descrição do item de cada linha. Várias palavras: todas na mesma linha, em qualquer ordem.")
            _dic = df.to_dict("records")
            _cit = sv.linhas_que_citam(_dic, filtro_pal)
            _ids = {id(x) for x in _cit}
            _cods = re.findall(r"\d+", rec.get("codigos") or "")
            if len(_cods) >= 2:
                try:
                    _stc2 = sv.CATALOGO_SERVICOS.stat()
                    _nm = {str(r["codigoServico"]): r["nomeServico"] for r in catalogo_servicos_na_memoria(str(sv.CATALOGO_SERVICOS), (_stc2.st_size, int(_stc2.st_mtime)))} if eh_serv else {}
                except OSError:
                    _nm = {}
                if not eh_serv:     # produto: a linha traz o item CATMAT, não o PDM; o nome mostrado é o da primeira descrição daquele item
                    for _l in _dic:
                        _nm.setdefault(re.sub(r"\.0$", "", str(_l.get("codigo_catalogo") or "").strip()), str(_l.get("descricao_item") or "")[:60])
                st.markdown("**Resumo por código**" + (f" (linhas que citam \"{filtro_pal.strip()}\")" if filtro_pal.strip() else ""))
                _res_cod = pd.DataFrame(sv.resumo_por_codigo(_dic, _cit, _nm))
                st.dataframe(_res_cod, hide_index=True, width="stretch", height=altura_tabela(len(_res_cod)))
            if filtro_pal.strip():
                if _cit:
                    df = df[[id(x) in _ids for x in _dic]]
                    st.caption(f"{len(df)} de {total} linhas citam \"{filtro_pal.strip()}\" (filtro só sobre o que já foi lido; nenhuma consulta nova).")
                    _nv = int((df["situacao_pncp"].fillna("") == "não verificado").sum()) if "situacao_pncp" in df.columns else 0
                    if _nv:
                        st.warning(f"{_nv} das {len(df)} linhas filtradas não têm ligação ao PNCP (\"não verificado: limite de consultas\"). O modo completo liga mais compras (até {MODOS['completo']['MAX_VINCULOS']}).")
                else:
                    st.warning(f"Nenhuma das {total} linhas cita \"{filtro_pal.strip()}\". Mostrando todas as linhas.")
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

            df["indicador_descricao"] = df["descricao_item"].map(sv.indicador_descricao)      # Pedido 17 (Fase 3): só conta palavras
            df["compra_item"] = df.apply(coluna_compra_item, axis=1)
            df["avaliacao"] = df.apply(coluna_avaliacao, axis=1) if pedidos else ""
            df["estimado"] = df.apply(coluna_estimado, axis=1)
            df["dif_estimado"] = df.apply(coluna_diferenca, axis=1)
            df["abrir"] = df["link_publico"].where(df["link_publico"].fillna("").str.startswith("http"), "")
            df = sv.ligadas_primeiro(df)      # Pedido 33 (1.4): linhas ligadas ao PNCP primeiro; o número da "linha" não muda
            canal = st.session_state.get("canal_oficial", {}) if eh_serv else {}
            if eh_serv:  # preço do site oficial: só o que a pessoa digitou (o app nunca acessa o site); o rótulo só aparece com os 3 campos
                for chave in ("preco", "link", "acesso"):
                    df[f"canal_oficial_{chave}"] = df["linha"].astype(str).map(lambda x, c=chave: canal.get(x, {}).get(c, ""))
                df["canal_oficial_comparacao"] = df.apply(lambda l: sv.comparar_canal_oficial(l["preco_unitario_homologado"], canal.get(str(l["linha"]), {}).get("preco"),
                                                                                              canal.get(str(l["linha"]), {}).get("link"), canal.get(str(l["linha"]), {}).get("acesso"))["rotulo"], axis=1)
                st.warning(sv.AVISO_PRECO + " Nenhuma média nem mediana é calculada; preços muito fora da faixa ficam marcados como \"suspeito\" e continuam na tabela.")
                mostrar = ["linha", "compra_item", "abrir", "unidade", "quantidade", "preco_unitario_homologado", "observacao_preco", "canal_oficial_comparacao",
                           "estimado", "dif_estimado", "data_resultado", "orgao", "uf", "indicador_descricao", "descricao_item"]
            else:
                mostrar = ["linha", "situacao", "avaliacao", "compra_item", "abrir", "estimado", "preco_unitario_homologado", "dif_estimado",
                           "observacao_preco", *pedidos, "data_resultado", "orgao", "uf", "indicador_descricao", "descricao_item"]
            mostrar = [c for c in mostrar if c in df.columns]
            st.dataframe(tabela_destaque(df[mostrar]), hide_index=True, width="stretch", height=altura_tabela(len(df)),
                         column_config={"avaliacao": st.column_config.TextColumn("avaliação", help="cada atributo pedido e o resultado"),
                                        "compra_item": st.column_config.TextColumn("compra e item no PNCP"),
                                        "abrir": st.column_config.LinkColumn("PNCP", display_text="abrir"),
                                        "estimado": st.column_config.TextColumn("preço estimado", help="Valor unitário estimado do item no PNCP (só linhas ligadas ao PNCP)."),
                                        "preco_unitario_homologado": st.column_config.NumberColumn("preço homologado", format="R$ %.2f"),
                                        "dif_estimado": st.column_config.TextColumn("homologado × estimado"),
                                        "indicador_descricao": st.column_config.TextColumn("descrição", help=f"Só conta palavras (curta: até {sv.DESCRICAO_LIMITE_PALAVRAS}); não lê o edital. Regra provisória: a equipe valida.")})
            st.caption(f"Coluna \"descrição\": só conta palavras; não lê o edital. Curta = até {sv.DESCRICAO_LIMITE_PALAVRAS} palavras; detalhada = mais que isso. Regra provisória: a equipe valida.")
            if (df["situacao_pncp"].fillna("") == "não verificado").any() if "situacao_pncp" in df.columns else False:
                st.caption(f"Limite de consultas: no modo rápido só {MODOS['rápido']['MAX_VINCULOS']} compras são ligadas ao PNCP; as outras ficam como "
                           f"\"não verificado\" (não quer dizer que não existam no PNCP). O modo completo liga mais: até {MODOS['completo']['MAX_VINCULOS']} compras.")
            if eh_serv:
                with st.expander("Preço do site oficial do fornecedor (opcional; digitado por você, o app nunca acessa o site)"):
                    st.caption("Digite o preço que você viu, o link da página e a data e a hora em que viu. A comparação só aparece quando os três estão preenchidos.")
                    lin_c = st.selectbox("Linha", df["linha"].astype(str).tolist(), key="canal_linha")
                    preco_c = st.text_input("Preço no site oficial (R$)", key="canal_preco")
                    link_c = st.text_input("Link da página do fornecedor", key="canal_link")
                    acesso_c = st.text_input("Data e hora em que você viu o preço (ex.: 20/11/2026 14:30)", key="canal_acesso")
                    if st.button("Registrar para esta linha", key="canal_registrar"):
                        pago_c = df.loc[df["linha"].astype(str) == str(lin_c), "preco_unitario_homologado"].iloc[0]
                        r_c = sv.comparar_canal_oficial(pago_c, preco_c, link_c, acesso_c)
                        if r_c["avisos"]:
                            st.warning("Não registrei: " + "; ".join(r_c["avisos"]) + ".")
                        else:
                            st.session_state.setdefault("canal_oficial", {})[str(lin_c)] = {"preco": preco_c, "link": link_c, "acesso": acesso_c}
                            st.rerun()
                    for k_c, v_c in canal.items():
                        pago_k = df.loc[df["linha"].astype(str) == k_c, "preco_unitario_homologado"]
                        if len(pago_k):
                            st.write(f"Linha {k_c}: " + (sv.comparar_canal_oficial(pago_k.iloc[0], v_c["preco"], v_c["link"], v_c["acesso"])["texto"] or "(incompleto)"))
            st.download_button("Baixar CSV (ordem desta tela)", df.drop(columns=["abrir"]).to_csv(sep=";", index=False).encode("utf-8-sig"),
                               file_name=Path(resumo["arquivo"]).name.replace(".csv", "_tela.csv"), mime="text/csv")

            # ---------- linha escolhida
            cartao_fim()
            cartao_ini("etapa3")
            st.subheader("Etapa 3 · Recorte: baixar o documento e gerar o texto para a IA")
            opcoes = df["linha"].tolist()
            escolha = st.selectbox("Linha", opcoes, format_func=lambda n: f"{n} – " + str(df.loc[df["linha"] == n, "orgao"].iloc[0])[:50]
                                   + " – " + str(df.loc[df["linha"] == n, "descricao_item"].iloc[0])[:60],
                                   index=sv.indice_primeira_ligada(df["link_publico"].tolist()))      # Pedido 33 (1.3): abre na 1ª linha ligada ao PNCP; nenhuma ligada = linha 1
            # Pedido 25 (Fase 2): o botão vale para Produto e Serviço (a lista de arquivos do PNCP é a mesma)
            lin_ok = df.loc[df["linha"] == escolha].iloc[0]
            if st.button("Listar os TR e documentos principais desta compra (1 consulta ao PNCP, nada é baixado)"):
                if not str(lin_ok.get("link_publico") or "").startswith("http"):
                    st.session_state["lista_tr"] = {"linha": escolha, "erro": "Esta linha não está ligada ao PNCP: não há compra para listar."}
                else:
                    with respondendo([]):
                        docs_c = sv.listar_documentos_compra(lin_ok["cnpj"], lin_ok["ano"], lin_ok["sequencial"])
                    st.session_state["lista_tr"] = {"linha": escolha, "docs": docs_c}
            lt = st.session_state.get("lista_tr")
            if lt and lt["linha"] == escolha:
                if lt.get("erro"):
                    st.warning(lt["erro"])
                elif not lt["docs"]:
                    st.warning("O PNCP não devolveu a lista de documentos desta compra (não quer dizer que não existam). Tente de novo mais tarde.")
                else:
                    st.dataframe(pd.DataFrame(lt["docs"]).rename(columns={"termo_de_referencia": "é TR", "principal": "principal"}), hide_index=True, width="stretch", height=altura_tabela(len(lt["docs"])))
                    _aviso_sem_tr = sv.aviso_sem_documento_principal(lt["docs"])      # Pedido 33 (5): antes do botão de baixar; nada é baixado
                    if _aviso_sem_tr:
                        st.warning(_aviso_sem_tr)
            outros = st.checkbox("Baixar também propostas, atas e despachos (podem ser dezenas de arquivos grandes)", value=False)
            clicou_dl = st.button("Baixar documentos da linha")
            slot_dl = mostrar_painel("e3_baixar", alvo=escolha)      # Pedido 13I: painel do download, sempre à vista
            if clicou_dl:
                pdl = Painel("e3_baixar", "Etapa 3 · Baixar os documentos da compra", slot_dl, alvo=escolha)
                pdl.barra(None, "Aguardando a lista de arquivos")
                dl = {"total": None, "feito": 0, "ini": time.time()}

                def ao_baixar(fase, url, params, resultado):
                    """Mostra o arquivo atual e 'feito de total' no download (o total vem da lista de arquivos do PNCP)."""
                    if fase == "antes":
                        pdl.agora(acao_atual(url, params))
                        return
                    if url.endswith("/arquivos") and isinstance(resultado[1], list):
                        ativos = [a for a in resultado[1] if a.get("statusAtivo") is not False]
                        dl["total"] = len(ativos) if outros else sum(1 for a in ativos if f.eh_principal(a))  # mesma regra da opção 3
                    elif re.search(r"/arquivos/\d+$", url) or "pncp-api" in url:
                        dl["feito"] += 1
                    if dl["total"]:
                        pct = min(dl["feito"] / dl["total"], 1.0)
                        resta = f" · faltam ~{tempo_fmt((time.time() - dl['ini']) / dl['feito'] * (dl['total'] - dl['feito']))}" if 0 < dl["feito"] < dl["total"] else ""
                        pdl.barra(pct, f"Documentos: {pct:.0%} · {dl['feito']} de {dl['total']} arquivos{resta}")
                        pdl.tempo()

                def _baixa():
                    with respondendo([escolha, "s" if outros else "n"], ao_baixar) as log:
                        (f.SAIDA / "busca_tela_atual.csv").write_bytes(rec["csv"])  # a opção 3 lê a busca mais recente: a que está na tela
                        f.opcao_3_baixar()
                    return log.getvalue()

                texto = com_relogio(pdl, _baixa)     # Pedido 13K (C2): o tempo decorrido sobe a cada 1 s, mesmo no meio de um arquivo grande
                res_dl = f.resultado_download(texto)  # "concluído" só quando o download deu certo (Fase 3)
                _m_pasta = re.search(r"Documentos em: (.+)", texto)
                msg_sp = sv.mensagem_sem_principais(texto, sv.titulos_da_lista(_m_pasta.group(1).strip()) if _m_pasta else [])   # Pedido 25: lista veio, 0 principais = regra, não falha
                falhas_dl = sv.falhas_do_download(texto)   # Pedido 28 (Fase 3): código HTTP e frase curta por arquivo que falhou; nunca o corpo da resposta nem a URL
                if msg_sp:
                    pdl.concluir(f"linha {escolha}: {msg_sp}", verbo="Concluída sem arquivos principais")
                elif res_dl["estado"] == "falhou":
                    pdl.falhar(f.texto_download(res_dl))
                else:
                    pdl.concluir(f"linha {escolha}: {f.texto_download(res_dl)}", verbo="Concluída com falhas" if res_dl["estado"] == "parcial" else "Concluída")
                m_dest = re.search(r"Documentos em: (.+)", texto)
                st.session_state["docs"] = {"linha": escolha, "pasta": m_dest.group(1).strip() if m_dest else "", "log": texto, "aviso": msg_sp or "", "falhas": falhas_dl}

            docs = st.session_state.get("docs")
            if docs and docs["linha"] == escolha:
                if docs.get("aviso"):
                    st.warning(docs["aviso"])
                for _fx in docs.get("falhas", []):
                    st.warning(f"{_fx['arquivo']}: {_fx['frase']}")
                if not docs["pasta"]:
                    st.warning(sv.sem_enderecos(docs["log"]).strip() or "Nada foi baixado.")
                else:
                    pasta = Path(docs["pasta"])
                    arquivos = [p for p in sorted(pasta.rglob("*")) if p.is_file() and not p.name.startswith("_lista")]
                    st.write(f"Pasta: `{pasta}`")
                    st.dataframe(pd.DataFrame([{"arquivo": str(p.relative_to(pasta)), "tamanho (KB)": round(p.stat().st_size / 1024)} for p in arquivos]),
                                 hide_index=True, width="stretch", height=altura_tabela(len(arquivos)))
                    pdfs = [p for p in arquivos if p.suffix.lower() in f.EXTENSOES_RECORTE]  # PDF e Word
                    if pdfs:
                        pdf = st.selectbox("Documento para recortar: PDF ou Word (de preferência o TR)", pdfs, format_func=lambda p: p.name,
                                           index=sv.indice_documento_recorte(pasta, pdfs)[0])      # Pedido 33 (1.2): TR da lista do PNCP; sem TR, 1º principal
                        # ---- Pedido 13I: "Item pedido" por item. Serviço: a descrição PRÓPRIA da linha escolhida sem as palavras do nome do serviço (itens diferentes com o mesmo código);
                        # produto: o que já era (o produto do resumo). Editável; vai para a 1ª linha do texto e para a pontuação das páginas do recorte.
                        aviso_item = ""
                        if eh_serv:
                            try:
                                _stc = sv.CATALOGO_SERVICOS.stat()
                                _nomes = {str(r["codigoServico"]): r["nomeServico"] for r in catalogo_servicos_na_memoria(str(sv.CATALOGO_SERVICOS), (_stc.st_size, int(_stc.st_mtime)))}
                            except OSError:
                                _nomes = {}
                            _lin = df.loc[df["linha"] == escolha].iloc[0]
                            _cod = re.sub(r"\.0$", "", str(_lin.get("codigo_catalogo") or "").strip())
                            _nomes_cat = [_nomes[_cod]] if _cod in _nomes else [_nomes[c] for c in re.findall(r"\d+", rec.get("codigos") or "") if c in _nomes]
                            _mesmo_cod = df.loc[df["codigo_catalogo"].astype(str).str.replace(r"\.0$", "", regex=True) == _cod, "descricao_item"] if _cod else []   # Pedido 13J: linhas do MESMO código que o app já tem
                            item_ini = sv.item_pedido_inicial(sv.separar_colagens(str(_lin.get("descricao_item") or ""), [str(x) for x in _mesmo_cod]), _nomes_cat, contexto=[str(x) for x in _mesmo_cod])   # Pedido 17 (0.4): "softwarepara" -> "software para"
                            if not item_ini:
                                item_ini = " ".join((rec.get("item_recorte") or "").split("|"))
                                aviso_item = ("Esta linha não traz descrição própria do item (ou ela só repete o nome do serviço do catálogo). "
                                              "Usei as palavras do nome do serviço, como antes. Você pode escrever o item aqui.")
                        else:
                            item_ini = rec.get("item_recorte") or resumo.get("produto") or resumo.get("nome_no_catalogo") or produto or termo   # o que já era
                        item_txt = st.text_input("Item pedido (o que a IA deve procurar no documento)", value=item_ini, key=f"item_pedido_{rec.get('quando')}_{escolha}",
                                                 help="Palavras do item, separadas por espaço: o app procura cada palavra no documento e sobe as páginas que as têm. "
                                                      "Para procurar uma frase junta, separe as opções com | (ex.: nome do item 11|outra opção).")
                        st.caption("Confira se estas palavras descrevem só o item que você quer; apague o que for de outra coisa, ou digite as opções separadas por |.")      # Pedido 17 (0.2): legenda fixa, produto e serviço
                        item = item_txt if (not eh_serv and item_txt == item_ini) else sv.item_para_recorte(item_txt, produtos.keys())
                        if aviso_item:
                            st.warning(aviso_item)
                        if item:
                            st.caption("O app procura no documento: " + "; ".join(x for x in (item.split("|") if "|" in item else [item]) if x))
                        clicou_ia = st.button("Gerar texto para IA", type="primary" if VISUAL_NOVO else "secondary")
                        slot_rec = mostrar_painel("e3_recorte", alvo=escolha)      # Pedido 13I: painel do recorte, sempre à vista
                        slot_out = mostrar_painel("e3_outros", alvo=escolha)       # Pedido 13K: painel que lê os outros documentos quando o escolhido não tem texto
                        _sem = st.session_state.get("sem_texto")
                        if _sem and _sem["alvo"] == escolha and _sem["pdf"] == pdf.name and not clicou_ia:
                            mostrar_sem_texto(_sem)       # nos reruns seguintes o aviso continua na tela
                        if clicou_ia:
                            st.session_state.pop("sem_texto", None)
                            prec = Painel("e3_recorte", "Etapa 3 · Gerar o texto para a IA", slot_rec, barras=["Recorte e texto"], alvo=escolha)
                            if not item.strip():
                                prec.falhar("o item pedido está vazio; escreva o que a IA deve procurar no documento")
                                st.error("O item pedido está vazio. Escreva o que a IA deve procurar no documento.")
                                st.stop()
                            prec.agora("recortando as páginas do item no documento escolhido")
                            prec.barra(None, "Recortando as páginas do item")
                            with respondendo([]):
                                posicao = f.documentos_recortaveis().index(pdf) + 1  # mesma lista da opção 4
                            def _recorta():
                                with respondendo([posicao, item]) as log4:
                                    f.opcao_4_recortar()
                                return log4.getvalue()

                            log4_txt = com_relogio(prec, _recorta)     # Pedido 13K (C2): a extração do PDF é uma etapa só e longa: "em andamento" + tempo decorrido subindo (sem % inventado)
                            m_rec = re.search(r"Recorte salvo em: (.+)", log4_txt)
                            m_av = re.search(r"Aviso: ((?:Word|Convertido).+)", log4_txt)
                            if m_av:
                                st.info(m_av.group(1))
                            if not m_rec:
                                m_nao = re.search(r"Não foi possível recortar: (.+)", log4_txt)
                                prec.falhar("não foi possível recortar: " + (m_nao.group(1) if m_nao else "veja a mensagem abaixo"))
                                st.error(m_nao.group(1) if m_nao else log4_txt)
                                st.stop()
                            # Pedido 13K (A1): conta os caracteres de cada página do documento escolhido ANTES de oferecer o texto; sem texto = painel "Concluída com falhas"
                            _pasta_rec = Path(m_rec.group(1).strip()).parent
                            try:
                                av_doc = sv.avaliar_texto_documento(json.loads((_pasta_rec / "paginas.json").read_text(encoding="utf-8")))
                            except (OSError, ValueError):
                                av_doc = {"paginas": 0, "sem_texto": 0, "total": 0, "estado": "não medido"}     # sem paginas.json não há o que contar: segue como antes (nunca declara 'sem texto' sem medir)
                            if av_doc["estado"] == "sem_texto":
                                prec.concluir(sv.frase_sem_texto(av_doc), verbo="Concluída com falhas")
                                p_out = Painel("e3_outros", "Etapa 3 · Ver o texto dos outros documentos da compra", slot_out, barras=["Outros documentos"], alvo=escolha)
                                _cache_chars = st.session_state.setdefault("chars_docs", {})
                                _outros_docs = [p for p in pdfs if p != pdf]
                                _lista = com_relogio(p_out, lambda: contar_texto_dos_outros(p_out, _outros_docs, _cache_chars)) if _outros_docs else []
                                p_out.concluir(f"{len(_lista)} outro(s) documento(s) lido(s)" if _lista else "não há outro documento baixado")
                                st.session_state["sem_texto"] = {"alvo": escolha, "pdf": pdf.name, "av": av_doc, "outros": _lista}
                                mostrar_sem_texto(st.session_state["sem_texto"])
                                st.stop()      # nada de "páginas relevantes", "texto pronto" nem texto para colar
                            aviso_parcial = sv.frase_paginas_sem_texto(av_doc)     # A3: só algumas páginas sem texto
                            prec.agora("montando o texto para colar na IA")
                            prec.barra(None, "Montando o texto para a IA")
                            with respondendo([]):
                                recs = sorted((f.SAIDA / "recortes").glob("*/recorte.txt"))  # mesma lista da opção 5
                            with respondendo([recs.index(Path(m_rec.group(1).strip())) + 1]) as log5:
                                f.opcao_5_texto_ia()
                            m_ia = re.search(r"Pronto para colar: (.+?)\s+\(", log5.getvalue())
                            if m_ia:
                                alvo = Path(m_ia.group(1))
                                texto_ia = alvo.read_text(encoding="utf-8")
                                _ia_barra = sv.texto_ia_sem_barra_no_item(texto_ia)   # Pedido 28: '|' do item vira ' / ' só no texto enviado à IA (recorte.txt e o item guardado não mudam)
                                if _ia_barra != texto_ia:
                                    alvo.write_text(_ia_barra, encoding="utf-8"); texto_ia = _ia_barra
                                orc_ia, aviso_tokens = f.orcamento_do_prompt(texto_ia)
                                st.session_state["recorte_atual"] = alvo.name.replace("_PARA_IA.txt", "")  # v4h: a tela "Conferir ficha" já abre neste recorte
                                info_rec = f.ranking_recorte.ler_recorte_info(Path(m_rec.group(1).strip()).parent)
                                prec.concluir((f.ranking_recorte.linha_do_recorte(info_rec) + " · " if info_rec else "") + f"texto pronto ({aviso_tokens})" + (f" · {aviso_parcial}" if aviso_parcial else ""))
                                if aviso_parcial:
                                    st.warning(f"Aviso: {aviso_parcial} A IA só lê as páginas que têm texto.")
                                if info_rec:  # v4h: guarda de contexto: a linha aparece SEMPRE; o aviso só se algo ficou de fora
                                    st.info(f.ranking_recorte.linha_do_recorte(info_rec))
                                    st.caption(f"Item pedido: {item}")
                                    aviso_rec = f.ranking_recorte.aviso_do_recorte(info_rec)
                                    if aviso_rec:
                                        st.warning(aviso_rec)
                                st.success(f"Pronto: `{alvo}` ({aviso_tokens}). Copie e cole na IA; a resposta é rascunho para conferência humana.")
                                if not orc_ia["cabe"]:
                                    st.warning(f.orcamento_tokens.aviso_nao_cabe(orc_ia))
                                st.markdown("**Etapa 4 · IA:** copie o texto abaixo e cole na IA. A resposta é rascunho; depois, na Etapa 5, cole-a para conferir.")
                                st.download_button("Baixar o .txt", texto_ia.encode("utf-8"), file_name=alvo.name, mime="text/plain")
                                st.text_area("Texto para colar na IA", texto_ia, height=150)
                            else:
                                prec.falhar("o texto para a IA não ficou pronto; veja a mensagem abaixo")
                                st.error(log5.getvalue())
                    else:
                        st.info("Nenhum PDF ou documento Word entre os arquivos baixados.")

            cartao_fim()

# ---------- v4h: Conferir ficha (sem IA): cola a resposta da IA e confere por código contra o texto do recorte
cartao_ini("etapa5")
st.subheader("Etapa 5 · Conferir ficha (sem IA)")
_saida_sessao = pasta_da_sessao()  # f.SAIDA só aponta para a pasta da sessão DENTRO de respondendo; aqui usamos a pasta da sessão diretamente
_recortes = sorted((p.parent for p in (_saida_sessao / "recortes").glob("*/recorte.txt") if (p.parent / "paginas.json").exists()),
                   key=lambda p: (p / "recorte.txt").stat().st_mtime, reverse=True) if (_saida_sessao / "recortes").exists() else []
if not _recortes:
    st.caption("Ainda não há recorte. Gere o texto para IA acima (o recorte fica guardado) e volte aqui para colar a resposta da IA.")
else:
    # Pedido 33 (1.1): com key=, o seletor guarda a escolha antiga e ignora index; por isso, quando surge ou é regravado um recorte, a escolha é refeita antes de criar o seletor
    _padrao = sv.recorte_padrao(_recortes, st.session_state.get("recorte_atual"))
    _marca = (_padrao.name, (_padrao / "recorte.txt").stat().st_mtime)
    if st.session_state.get("_ficha_recorte_marca") != _marca or st.session_state.get("ficha_recorte") not in _recortes:
        st.session_state["ficha_recorte"] = _padrao
        st.session_state["_ficha_recorte_marca"] = _marca
    pasta_rec = st.selectbox("Recorte conferido (o texto das páginas vem dele)", _recortes, format_func=lambda p: p.name, key="ficha_recorte")
    st.caption(sv.frase_recorte_conferido(_recortes, pasta_rec))
    paginas_rec, item_rec, info_rec2 = conferir_tela.ler_recorte(pasta_rec)
    if item_rec:
        st.caption(f"Item pedido: {item_rec}")    # Pedido 13I: o item do recorte conferido fica à vista
    if info_rec2:
        st.caption(f.ranking_recorte.linha_do_recorte(info_rec2))
        _aviso = f.ranking_recorte.aviso_do_recorte(info_rec2)
        if _aviso:
            st.warning(_aviso)
    resposta_ia = st.text_area("Cole aqui a resposta da IA (a tabela de 9 campos)", height=120, key="ficha_resposta")
    # Pedido 13J: texto explicativo VISÍVEL (não só no balão) e rótulos curtos, de uma linha; a janela inicial vem de config\\orcamento_tokens.csv (sem o arquivo, em branco e com aviso)
    st.caption("Tokens lidos: número que o Open WebUI/Ollama mostra depois de a IA ler o texto (prompt_eval_count). Com ele o app confere se o texto foi cortado. "
               "Janela: o tamanho de contexto em que o Ollama está rodando.")
    _cfg_tok = f.orcamento_tokens.ler_config(f.ORCAMENTO_CSV)
    ctx_ini = str(_cfg_tok["contexto_tokens"]) if _cfg_tok.get("origem") == "config" else ""
    c_a, c_b = st.columns([1, 1], width=560)   # Pedido 13B: os dois campos pequenos juntos, sem esticar a tela inteira; os dois com ajuda (mesma altura e alinhamento)
    pec_txt = c_a.text_input("Tokens lidos (opcional)", key="ficha_pec", help="Número que o Ollama devolve ao final da execução (prompt_eval_count). Serve para detectar corte do prompt.")
    ctx_txt = c_b.text_input("Janela da IA (tokens)", value=ctx_ini, key="ficha_ctx", help="Tamanho da janela de contexto (num_ctx) com que a IA rodou. O valor inicial vem de config\\orcamento_tokens.csv.")
    if not ctx_txt.strip():
        st.warning("Não achei a janela da IA em config\\orcamento_tokens.csv. Escreva a janela (tokens) no campo ao lado; sem ela o app não confere se o texto foi cortado.")
    if not pec_txt.strip():
        st.info("Sem os tokens lidos, o app não consegue conferir se o texto foi cortado. A conferência segue sem essa checagem.")
    # Pedido 13K (A4): recorte sem texto (páginas mantidas sem texto, ex.: PDF digitalizado) não é conferido: não há o que a ficha possa citar
    _paginas_mantidas = [t for i, t in enumerate(paginas_rec, 1) if i in set((info_rec2 or {}).get("mantidas") or range(1, len(paginas_rec) + 1))]
    recorte_sem_texto = sv.avaliar_texto_documento(_paginas_mantidas)["estado"] == "sem_texto"
    if recorte_sem_texto:
        st.error("Recorte sem texto: as páginas deste recorte não têm texto (PDF digitalizado, e o app não faz OCR). A ficha não pode ser conferida contra ele. "
                 "Volte à Etapa 3 e escolha um documento que tenha texto.")
    clicou_conf = st.button("Conferir ficha", type="primary" if VISUAL_NOVO else "secondary")
    slot_c5 = mostrar_painel("e5_conferir", alvo=pasta_rec.name)      # Pedido 13I: painel da conferência, sempre à vista
    if clicou_conf and recorte_sem_texto:
        p5 = Painel("e5_conferir", "Etapa 5 · Conferir a ficha", slot_c5, alvo=pasta_rec.name)
        st.session_state.pop("ficha_conferida", None)
        p5.falhar("recorte sem texto: nada foi conferido e a ficha não é tratada como conferida")
    elif clicou_conf:
        p5 = Painel("e5_conferir", "Etapa 5 · Conferir a ficha", slot_c5, alvo=pasta_rec.name)
        p5.agora("conferindo cada citação da resposta da IA com o texto do recorte")
        p5.barra(None, "Conferindo")
        st.session_state["ficha_conferida"] = {"recorte": pasta_rec.name, "res": conferir_tela.conferir_resposta(
            resposta_ia, paginas_rec, f.INSTRUCAO.read_text(encoding="utf-8"), item_rec, pec_txt if ctx_txt.strip() else "", ctx_txt)}   # sem a janela não há checagem de corte (nada de janela "inventada")
        _r5 = st.session_state["ficha_conferida"]["res"]
        if _r5["ficha_encontrada"]:
            p5.concluir(conferir_tela.frase_resumo(_r5), verbo="Conferida")
        else:
            p5.falhar(conferir_tela.frase_resumo(_r5))
    conf = st.session_state.get("ficha_conferida")
    if conf and conf["recorte"] == pasta_rec.name and not recorte_sem_texto:
        res_c = conf["res"]
        if res_c["erro_campos"]:
            st.warning(f"Campo opcional ignorado: {res_c['erro_campos']}")
        if res_c["possivel_corte"]:
            st.error("POSSÍVEL CORTE: refazer com recorte menor. Os tokens lidos estão na faixa em que o servidor da IA corta o início do prompt (onde fica a instrução).")
        elif res_c["verificacao"] == "REVISAR FORMATO":
            st.warning("REVISAR FORMATO: a ficha não tem os 9 campos ou algum campo com valor está sem página numérica.")
        elif res_c["verificacao"] == "SEM DADO":
            st.caption("Sem prompt_eval_count: não dá para verificar corte do prompt.")
        if res_c["raciocinio_descartado"]:
            st.caption("O texto antes do último <channel|> (raciocínio do modelo) foi ignorado.")
        if not res_c["ficha_encontrada"]:
            st.error(conferir_tela.frase_resumo(res_c))
        else:
            st.write(conferir_tela.frase_resumo(res_c))
            for _al in res_c.get("alertas", []):   # Pedido 25 (Fase 5): 'revisar', não 'erro'; a contagem de citações literais acima não muda
                st.warning(conferir_tela.frase_alerta(_al))
            st.dataframe(pd.DataFrame(res_c["linhas"]).rename(columns={"valor_com_suporte_no_texto": "valor com suporte no texto", "revisao_humana": "revisão humana",
                                                                      "valor_igual_ao_modelo_da_instrucao": "valor = modelo da instrução"}), hide_index=True, width="stretch", height=altura_tabela(len(res_c["linhas"])))
            st.download_button("Baixar a conferência (CSV)", res_c["csv"], file_name=f"conferencia_{conf['recorte']}.csv", mime="text/csv")
    st.caption(conferir_tela.AVISO_LITERAL)

cartao_fim()

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

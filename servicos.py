"""Serviço (v4h, Pedido 9). Catálogo de serviços CATSER local, busca de compras por código de serviço, ligação ao PNCP e lista de documentos da compra.

Toda chamada de rede passa por ferramenta.get (a mesma do produto: pausa, tentativas, log, PortalFora). Aqui não há rede própria.
NÃO TESTADO COM REDE: esta busca só foi testada com respostas simuladas (as chamadas de 17/11 em registro\\F2_servicos_2026-11-17 usaram
modulo-pesquisa-preco/3_consultarServico com tamanhoPagina=10; aqui se usa 100, como no produto, e isso ainda não foi confirmado na API).
Preço de serviço: NÃO calcula média nem mediana; unidade e quantidade são mostradas; 'suspeito' só MARCA, nunca apaga."""
import csv
import datetime as dt
import re
import time
from pathlib import Path

import ferramenta as f

CATALOGO_SERVICOS = f.CONFIG / "catalogo_servicos.csv"
CAMPOS_CATALOGO = ["codigoSecao", "nomeSecao", "codigoDivisao", "nomeDivisao", "codigoGrupo", "nomeGrupo", "codigoClasse", "nomeClasse", "codigoSubclasse",
                   "nomeSubclasse", "codigoServico", "nomeServico", "codigoCpc", "exclusivoCentralCompras", "statusServico", "dataHoraAtualizacao", "baixado_em"]
AVISO_PRECO = "Preços de serviço podem não ser comparáveis (unidade, prazo, quantidade)."
RAZAO_SUSPEITO = 10.0          # salto mínimo entre preços vizinhos (mesma unidade) para marcar 'suspeito'
PALAVRAS_FRACAS = {"de", "da", "do", "das", "dos", "e", "em", "para", "com", "por", "a", "o", "no", "na", "servico", "servicos", "tipo", "outros", "similar"}


def ler_catalogo(caminho=None):
    with Path(caminho or CATALOGO_SERVICOS).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


URL_CATALOGO_SERVICOS = f"{f.COMPRAS}/modulo-servico/6_consultarItemServico"
TAMANHO_PAGINA_CATALOGO = 500      # aceito pela API (medido em 17/11/2026, registro\F2_servicos_2026-11-17)
MINIMO_DO_ATUAL = 0.80             # arquivo novo com menos de 80% das linhas do atual é rejeitado


class CatalogoRejeitado(f.PortalFora):
    """O catálogo baixado não passou na conferência (total diferente do informado, ou muito menor que o atual). O arquivo atual NÃO foi substituído."""


def baixar_catalogo_servicos(forcar=False, destino=None, referencia=None):
    """Baixa o catálogo de serviços (modulo-servico/6_consultarItemServico, 500 por página, até totalPaginas) para config\\catalogo_servicos.csv, com a coluna baixado_em.
    Mesmo padrão de ferramenta.baixar_catalogo_pdm: usa ferramenta.get (pausa, tentativas, log), grava num arquivo temporário e só depois substitui.
    Se o arquivo já existir e forcar=False, só lê o local. Antes de substituir, copia o atual para historico\\catalogo_servicos__AAAA-MM-DD_HHMM.csv (ao lado do destino).
    ABORTA SEM SUBSTITUIR (PortalFora) se: HTTP diferente de 200 ou resposta sem 'resultado'; itens baixados diferente de totalRegistros;
    ou menos de 80% das linhas do arquivo de referência (o atual, por padrão). destino/referencia só existem para testes e para a medição com rede fora de config."""
    destino = Path(destino or CATALOGO_SERVICOS)
    referencia = Path(referencia or destino)
    if destino.exists() and not forcar:
        return ler_catalogo(destino)
    quando = f.agora()
    linhas, pagina, total_pag, total_reg = [], 1, None, None
    while total_pag is None or pagina <= total_pag:
        st, js, _ = f.get(URL_CATALOGO_SERVICOS, {"pagina": pagina, "tamanhoPagina": TAMANHO_PAGINA_CATALOGO})
        if st != 200 or not isinstance(js, dict) or "resultado" not in js or not isinstance(js["resultado"], list):
            raise f.PortalFora(f"catálogo de serviços: HTTP {st} ou resposta sem 'resultado' na página {pagina}. O catálogo atual foi mantido.")
        if total_pag is None:
            total_pag, total_reg = js.get("totalPaginas") or 1, js.get("totalRegistros")
        for r in js["resultado"]:
            l = {c: ("" if r.get(c) is None else r.get(c)) for c in CAMPOS_CATALOGO if c != "baixado_em"}
            l["baixado_em"] = quando
            linhas.append(l)
        print(f"  catálogo de serviços: página {pagina} de {total_pag} ({len(linhas)} serviços)")
        pagina += 1
    if total_reg is None or len(linhas) != total_reg:
        raise CatalogoRejeitado(f"catálogo de serviços: baixei {len(linhas)} itens, mas o portal informou totalRegistros={total_reg}. O catálogo atual foi mantido.")
    if referencia.exists():
        atuais = len(ler_catalogo(referencia))
        if atuais and len(linhas) < MINIMO_DO_ATUAL * atuais:
            raise CatalogoRejeitado(f"catálogo de serviços: baixei {len(linhas)} itens, menos de 80% dos {atuais} do catálogo atual. O catálogo atual foi mantido.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        hist = destino.parent / "historico"
        hist.mkdir(exist_ok=True)
        copia = hist / f"catalogo_servicos__{dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.csv"
        copia.write_bytes(destino.read_bytes())
    tmp = destino.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS_CATALOGO, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    tmp.replace(destino)
    return ler_catalogo(destino)


def data_do_catalogo(catalogo):
    """Data do download (coluna baixado_em, como no catalogo_pdm.csv); '' se não houver."""
    datas = sorted({(r.get("baixado_em") or "")[:10] for r in catalogo if r.get("baixado_em")})
    return datas[-1] if datas else ""


def _tokens(txt):
    return [f.singular(t) for t in re.findall(r"[a-z0-9]+", f.norm(txt)) if len(t) >= 2 or t.isdigit()]


def procurar(termo, catalogo, limite=40):
    """Palavra -> serviços do catálogo local (sem IA, sem rede). Todas as palavras do termo têm que aparecer no nome do serviço (singular/plural
    tratados). Só serviços ativos. Primeiro os que começam pela 1ª palavra, depois os de nome mais curto."""
    toks = _tokens(termo)
    if not toks:
        return []
    achados = []
    for r in catalogo:
        if str(r.get("statusServico", "")).strip().lower() not in ("true", "1", "sim"):
            continue
        nome = f.norm(r.get("nomeServico", ""))
        palavras = {f.singular(w) for w in re.findall(r"[a-z0-9]+", nome)}
        if all(t in palavras or t in nome for t in toks):
            achados.append(((not nome.startswith(toks[0])), len(nome), r))
    achados.sort(key=lambda x: (x[0], x[1], x[2].get("codigoServico", "")))
    return [r for _, _, r in achados[:limite]]


def palavras_do_recorte(nomes):
    """Palavras que o seletor de páginas procura no TR: as de 4+ letras dos nomes dos serviços escolhidos, sem as fracas, separadas por '|'
    (a opção 4 aceita 'a|b|c' como item). Vazio se não sobrar nenhuma."""
    vistas = []
    for n in nomes:
        for w in re.findall(r"[a-z0-9]+", f.norm(n)):
            if len(w) >= 4 and w not in PALAVRAS_FRACAS and w not in vistas:
                vistas.append(w)
    return "|".join(vistas[:8])


FRACAS_ITEM = PALAVRAS_FRACAS | {"ou", "ao", "aos", "as", "os", "um", "uma", "ser", "que", "mais", "sem", "pelo", "pela"}   # palavras que não identificam o item (Pedido 13I)


ITEM_MAX_PALAVRAS = 12        # Pedido 13J: tamanho máximo do texto padrão do 'Item pedido'
ITEM_FREQ_MAX = None          # Pedido 13J: palavra que aparece em tanta fração (0 a 1) das linhas do MESMO código é genérica e sai do texto padrão; None = não usa
ITEM_MIN_LINHAS_CONTEXTO = 10  # com menos linhas do mesmo código a frequência não é confiável: não filtra


def _palavras_do_texto(texto):
    return re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(texto or ""))


def frequencia_de_palavras(textos):
    """{palavra normalizada (singular) -> fração (0 a 1) dos textos em que ela aparece}. Cada texto conta uma vez por palavra."""
    n = len(textos)
    cont = {}
    for t in textos:
        for w in {f.singular(f.norm(x)) for x in _palavras_do_texto(t)}:
            cont[w] = cont.get(w, 0) + 1
    return {w: c / n for w, c in cont.items()} if n else {}


def item_pedido_inicial(descricao, nomes_catalogo, max_palavras=None, contexto=None, freq_max=None):
    """Pedido 13I/13J. Valor inicial do campo 'Item pedido' do serviço: a descrição PRÓPRIA da linha escolhida, SEM as palavras que já estão no nome do serviço do catálogo
    (nem as palavras fracas), na ordem da descrição (texto para a pessoa editar). Onde havia pontuação ou uma palavra tirada, fica uma vírgula: ela separa as ideias (e impede que
    'nome, 64' vire a frase 'nome 64' na busca). '' se não sobrar nada (o app usa então as palavras do catálogo e avisa).
    13J: 'contexto' = descrições das linhas do MESMO código que o app já tem; se há linhas suficientes (ITEM_MIN_LINHAS_CONTEXTO) e 'freq_max' está definido, também saem as palavras
    que aparecem em freq_max ou mais dessas linhas (genéricas naquele código). max_palavras e freq_max, quando não dados, vêm de ITEM_MAX_PALAVRAS e ITEM_FREQ_MAX. Sem lista de produtos."""
    max_palavras = ITEM_MAX_PALAVRAS if max_palavras is None else max_palavras
    freq_max = ITEM_FREQ_MAX if freq_max is None else freq_max
    no_nome = set()
    for n in nomes_catalogo or []:
        no_nome.update(_tokens(n))
    freq = frequencia_de_palavras(contexto) if (freq_max is not None and contexto and len(contexto) >= ITEM_MIN_LINHAS_CONTEXTO) else {}
    vistas, partes, quebra = set(), [], False       # partes: [palavra, quebra_antes]
    for m in re.finditer(r"[A-Za-zÀ-ÿ0-9]+|[^\sA-Za-zÀ-ÿ0-9]", str(descricao or "")):
        w = m.group(0)
        if not re.match(r"[A-Za-zÀ-ÿ0-9]", w):
            quebra = True
            continue
        n = f.norm(w)
        sing = f.singular(n)
        if len(n) < 2 or n in vistas or n in no_nome or sing in no_nome or n in FRACAS_ITEM or sing in FRACAS_ITEM or (freq and freq.get(sing, 0) >= freq_max):
            quebra = True
            continue
        vistas.add(n)
        partes.append([w.lower(), quebra and bool(partes)])
        quebra = False
        if len(partes) >= max_palavras:
            break
    return " ".join(w + ("," if k + 1 < len(partes) and partes[k + 1][1] else "") for k, (w, q) in enumerate(partes))


def item_para_recorte(texto, chaves=()):
    """Pedido 13I. Do texto do campo 'Item pedido' para o que o seletor de páginas recebe (ferramenta.opcao_4_recortar, que não muda):
     - com '|' = a pessoa decidiu: cada trecho entre '|' é uma opção (pode ser uma frase) e é procurada como está;
     - igual a um produto de config\\produtos.csv = como estava (o seletor usa os apelidos dele);
     - senão: viram opções 'frase1|frase2|palavra1|palavra2|...' (até 12): as palavras de 4+ letras/dígitos (sem as fracas) e, como o seletor casa pedaços de texto, as FRASES curtas
       'palavra + números/siglas curtos colados' (ex.: 'nome 11 pro', 'marca 7'), porque '11' e 'pro' sozinhos casariam com quase tudo ('projeto', 'produto'). Vírgula e ponto
       interrompem a frase. As frases vêm primeiro: o seletor confere as opções na ordem dada.
    Nunca devolve ' |' (espaço antes de '|'): o cabeçalho do recorte usa esse par para achar o fim do item."""
    t = " ".join(str(texto or "").split())
    if not t:
        return ""
    if "|" in t:
        return "|".join(x.strip() for x in t.split("|") if x.strip())
    if any(f.norm(t) == f.norm(c) for c in chaves):
        return t
    toks = re.findall(r"[a-z0-9]+|[^a-z0-9\s]", f.norm(t))
    eh_palavra = lambda x: bool(re.match(r"[a-z0-9]", x)) and x not in FRACAS_ITEM
    palavras, frases, i = [], [], 0
    while i < len(toks):
        tk = toks[i]
        if eh_palavra(tk) and len(tk) >= 4:
            if tk not in palavras:
                palavras.append(tk)
            j, curtos = i + 1, []
            while j < len(toks) and eh_palavra(toks[j]) and len(toks[j]) < 4:
                curtos.append(toks[j])
                j += 1
            if curtos and " ".join([tk, *curtos]) not in frases:
                frases.append(" ".join([tk, *curtos]))
            i = j if curtos else i + 1
        else:
            i += 1
    opcoes = (frases + palavras)[:12]
    return "|".join(opcoes) if opcoes else t


def marcar_suspeitos(linhas, razao=RAZAO_SUSPEITO):
    """Marca observacao_preco = 'suspeito' (NUNCA apaga a linha). Não calcula média nem mediana.
    Regras: (1) preço <= 0 é suspeito; (2) por unidade, com 4+ preços, ordena; em cada ponta (até 25% dos preços, no mínimo 1) procura um salto >= razao (10x)
    entre preços vizinhos e marca quem está além do salto. Preços do meio nunca são marcados. Devolve quantas linhas marcou."""
    grupos = {}
    for l in linhas:
        try:
            p = float(l.get("preco_unitario_homologado"))
        except (TypeError, ValueError):
            continue
        l.setdefault("observacao_preco", "")
        if p <= 0:
            l["observacao_preco"] = "suspeito"
            continue
        grupos.setdefault(l.get("unidade") or "(sem unidade)", []).append((p, l))
    for un, itens in grupos.items():
        n = len(itens)
        if n < 4:
            continue
        itens.sort(key=lambda x: x[0])
        lim = max(1, round(0.25 * n))                       # cada ponta só pode marcar até 25% dos preços (no mínimo 1)
        for i in range(1, lim + 1):                         # ponta de baixo: o primeiro salto >= razao dentro dos 25% de baixo marca tudo abaixo dele
            if itens[i][0] / itens[i - 1][0] >= razao:
                for _, l in itens[:i]:
                    l["observacao_preco"] = "suspeito"
                break
        for j in range(n - 1, n - lim - 1, -1):             # ponta de cima: o maior salto >= razao dentro dos 25% de cima marca tudo acima dele
            if itens[j][0] / itens[j - 1][0] >= razao:
                for _, l in itens[j:]:
                    l["observacao_preco"] = "suspeito"
                break
    return sum(1 for l in linhas if l.get("observacao_preco") == "suspeito")


def _numero_br(txt):
    """'1.234,56' ou '1234.56' ou 'R$ 90' -> float; None se vazio ou inválido."""
    t = re.sub(r"[^\d,.\-]", "", str(txt or ""))
    if not t or not re.search(r"\d", t):
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def comparar_canal_oficial(preco_pago, preco_oficial, link, acesso):
    """Campo OPCIONAL digitado pela pessoa (nunca raspado): preço no site oficial do fornecedor, com link e data/hora do acesso.
    O rótulo só aparece quando os três estão preenchidos. Devolve {'preenchido', 'rotulo', 'diferenca', 'texto', 'avisos'}."""
    out = {"preenchido": False, "rotulo": "", "diferenca": None, "texto": "", "avisos": []}
    if not str(preco_oficial or "").strip():
        return out
    oficial = _numero_br(preco_oficial)
    if oficial is None or oficial <= 0:
        out["avisos"].append("o preço do canal oficial não é um número válido")
    if not str(link or "").strip().lower().startswith(("http://", "https://")):
        out["avisos"].append("informe o link da página do fornecedor (começa com http)")
    if not str(acesso or "").strip():
        out["avisos"].append("informe a data e a hora em que você viu o preço")
    try:
        pago = float(preco_pago)
    except (TypeError, ValueError):
        pago = None
        out["avisos"].append("a linha não tem preço pago")
    if out["avisos"]:
        return out
    dif = pago / oficial - 1
    rotulo = "abaixo do canal oficial" if dif < 0 else ("acima do canal oficial" if dif > 0 else "igual ao canal oficial")
    brl = lambda v: f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")      # só os números (o link e a data não podem mudar)
    out.update(preenchido=True, rotulo=rotulo, diferenca=dif,
               texto=f"{rotulo}: pago R$ {brl(pago)} × canal oficial R$ {brl(oficial)} ({dif:+.0%}); preço visto em {str(acesso).strip()}; fonte: {str(link).strip()}")
    return out


def buscar_servicos(codigos, uf="", hoje=None):
    """Busca de compras por código de serviço (modulo-pesquisa-preco/3_consultarServico) + ligação ao PNCP (ferramenta.ligar_ao_pncp, que completa o
    idCompra com zeros até 17 dígitos). Grava o CSV com ferramenta.salvar_busca (mesmas colunas do produto + as de versão) e devolve o resumo."""
    codigos = [str(c).strip() for c in codigos if str(c).strip().isdigit()]
    antigo_tipo = f.TIPO_BUSCA
    f.TIPO_BUSCA = "serviço"
    try:
        inicio = time.time()
        f.STATS.clear()
        hoje = hoje or dt.date.today()
        corte = hoje - dt.timedelta(days=365 * f.MESES // 12)
        cont = {"entrada": f"código(s) de serviço {', '.join(codigos)}", "fonte": "Compras.gov.br pesquisa de preço de serviço (3_consultarServico)", "uf": uf or "todas",
                "registros_informados_pela_api": None, "registros_lidos": 0, "registros_com_preco": 0, "registros_fora_dos_12_meses": 0, "precos_suspeitos_marcados": 0,
                "compras_distintas": 0, "compras_ligadas_ao_pncp": 0, "compras_sem_ligacao_pncp": 0, "nome_no_catalogo": "", "tipo_busca": "serviço"}
        linhas, vinculos, falhas_compras, informados = [], {}, {}, 0
        try:
            registros = []
            for cod in codigos:
                for pag in range(1, f.MAX_PAGINAS_CATALOGO + 1):
                    params = {"pagina": pag, "tamanhoPagina": 100, "codigoItemCatalogo": cod, "dataCompraInicio": corte.isoformat(), "dataCompraFim": hoje.isoformat()}
                    if uf:
                        params["estado"] = uf
                    st, js, _ = f.get(f"{f.COMPRAS}/modulo-pesquisa-preco/3_consultarServico", params)
                    lote = (js or {}).get("resultado", []) if st == 200 and isinstance(js, dict) else []
                    if pag == 1 and isinstance(js, dict) and isinstance(js.get("totalRegistros"), int):
                        informados += js["totalRegistros"]
                    print(f"  pesquisa de preço de serviço {cod}, página {pag}: HTTP {st}, {len(lote)} registros (total informado: {(js or {}).get('totalRegistros') if isinstance(js, dict) else None})")
                    registros += lote
                    if not lote or not (js or {}).get("paginasRestantes"):
                        break
            cont["registros_informados_pela_api"] = informados if codigos else None
            cont["registros_lidos"] = len(registros)
            for r in registros:
                if r.get("precoUnitario") is None:
                    continue
                cont["registros_com_preco"] += 1
                data_res = (r.get("dataResultado") or "")[:10]
                data_filtro, qual = (data_res, "data do resultado") if data_res else ((r.get("dataCompra") or "")[:10], "data da compra (sem data do resultado)")
                if data_filtro and data_filtro < corte.isoformat():
                    cont["registros_fora_dos_12_meses"] += 1
                    continue
                desc = max([r.get("descricaoDetalhadaItem") or "", r.get("descricaoItem") or ""], key=len)
                linhas.append({"orgao": r.get("nomeOrgao") or r.get("nomeUasg", ""), "uf": r.get("estado", ""), "data_publicacao": (r.get("dataCompra") or "")[:10],
                               "data_resultado": data_res, "data_usada_no_filtro": qual, "controle_pncp": "", "numero_item": r.get("numeroItemCompra"),
                               "descricao_item": " ".join(desc.split()), "preco_unitario_homologado": r.get("precoUnitario"), "atributos_atendidos": "0 de 0", "_n": 0,
                               "link_publico": "", "fonte_api_resultado": f"{f.COMPRAS}/modulo-pesquisa-preco/3_consultarServico?codigoItemCatalogo={r.get('codigoItemCatalogo', '')}",
                               "cnpj": "", "ano": "", "sequencial": "", "observacao_preco": "", "situacao_pncp": "", "status_item_pncp": "", "descricao_item_pncp": "",
                               "valor_homologado_pncp": "", "numero_item_pncp": "", "valor_estimado_pncp": "", "codigo_catalogo": r.get("codigoItemCatalogo", ""), "marca": "",
                               "id_compra": str(r.get("idCompra") or ""), "unidade": r.get("siglaUnidadeMedida") or r.get("nomeUnidadeMedida") or "", "quantidade": r.get("quantidade", "")})
            cont["precos_suspeitos_marcados"] = marcar_suspeitos(linhas)
            linhas.sort(key=lambda l: l.get("data_resultado") or "", reverse=True)       # liga primeiro as compras mais recentes
            seguidas = 0
            for k, l in enumerate(linhas):
                if seguidas >= 3:
                    cont["ligacao_interrompida_apos_3_falhas_seguidas"] = True
                    for x in linhas[k:]:
                        if not x.get("situacao_pncp"):
                            x["situacao_pncp"] = "não processado (ligação interrompida após 3 falhas seguidas)"
                    print("\n*** 3 falhas seguidas de resposta: a ligação ao PNCP parou aqui; o que já foi lido será salvo.")
                    break
                id_c = l["id_compra"]
                if id_c in falhas_compras:
                    api, motivo = falhas_compras[id_c]
                    l["status_item_pncp"] = f"falhou: sem resposta do {api} ({motivo}); a compra já falhou nesta busca"
                    v0 = vinculos.get(id_c)          # dados da COMPRA já conhecidos antes da falha (sem chamada nova); só o status registra a falha
                    if v0 and v0.get("cnpj"):
                        f.preencher_vinculo(l, v0)
                        l["situacao_pncp"] = "vinculado"
                    else:
                        l["situacao_pncp"] = l.get("situacao_pncp") or "falhou"
                    continue
                chamadas_antes = f.STATS.get("chamadas", 0)
                try:
                    if id_c not in vinculos:
                        if len(vinculos) >= f.MAX_VINCULOS:
                            l["situacao_pncp"] = "não verificado"
                            continue
                        vinculos[id_c] = f.ligar_ao_pncp(id_c)
                    v = vinculos[id_c]
                    f.preencher_vinculo(l, v)
                    l["situacao_pncp"] = "vinculado" if v and v.get("cnpj") else "sem PNCP"
                    l["status_item_pncp"] = "serviço: item do PNCP não validado (NÃO TESTADO COM REDE)" if l["situacao_pncp"] == "vinculado" else ""
                    if f.STATS.get("chamadas", 0) > chamadas_antes:
                        seguidas = 0
                except f.PortalSemResposta as e:
                    api = "PNCP" if "://pncp.gov.br" in e.url else "Compras.gov.br"
                    falhas_compras[id_c] = (api, e.motivo or "sem resposta")
                    l["status_item_pncp"] = f"falhou: sem resposta do {api} ({e.motivo or 'sem resposta'})"
                    l["situacao_pncp"] = l.get("situacao_pncp") or "falhou"
                    seguidas += 1
                    print(f"  falhou: compra {id_c}: {api} sem resposta ({e.motivo}); seguindo ({seguidas} falha(s) seguida(s))")
        except f.PortalFora as e:
            print(f"\n*** PORTAL FORA OU BLOQUEADO: {e}\n*** A busca parou aqui; o que já foi lido será salvo.")
        cont["compras_distintas"] = len({l["id_compra"] for l in linhas})
        cont["compras_ligadas_ao_pncp"] = sum(1 for v in vinculos.values() if v and v.get("cnpj"))
        cont["compras_sem_ligacao_pncp"] = len({l["id_compra"] for l in linhas if l.get("situacao_pncp") == "sem PNCP"})
        cont["compras_nao_verificadas"] = len({l["id_compra"] for l in linhas if l.get("situacao_pncp") == "não verificado"})
        cont["linhas_nao_verificado"] = sum(1 for l in linhas if l.get("situacao_pncp") == "não verificado")
        cont["linhas_sem_pncp"] = sum(1 for l in linhas if l.get("situacao_pncp") == "sem PNCP")
        cont["itens_falhou"] = sum(1 for l in linhas if str(l.get("status_item_pncp", "")).startswith("falhou") or str(l.get("situacao_pncp", "")).startswith("falhou"))
        cont["compras_que_falharam"] = {k: f"{a}: {m}" for k, (a, m) in falhas_compras.items()}
        cont["linhas_nao_processadas"] = sum(1 for l in linhas if str(l.get("situacao_pncp", "")).startswith("não processado"))
        f.salvar_busca(linhas, {}, "servicos_" + "_".join(codigos), "", cont, inicio,
                       extras=["codigo_catalogo", "marca", "id_compra", "unidade", "quantidade", "observacao_preco", "situacao_pncp", "status_item_pncp", "descricao_item_pncp",
                               "valor_homologado_pncp", "numero_item_pncp", "valor_estimado_pncp"])
        import json
        return json.loads((f.SAIDA / "ultima_busca.json").read_text(encoding="utf-8"))
    finally:
        f.TIPO_BUSCA = antigo_tipo


def listar_documentos_compra(cnpj, ano, seq):
    """Lista (1 consulta ao PNCP, nada é baixado) os documentos ativos da compra, marcando os principais e os Termos de Referência.
    NÃO TESTADO COM REDE: testada só com resposta simulada. Devolve [] se a lista não vier."""
    st, lista, _ = f.get(f"{f.API}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos")
    if st != 200 or not isinstance(lista, list):
        return []
    out = []
    for a in lista:
        if a.get("statusAtivo") is False:
            continue
        tipo, titulo = a.get("tipoDocumentoNome") or "", a.get("titulo") or ""
        out.append({"sequencial": a.get("sequencialDocumento"), "tipo": tipo, "titulo": titulo, "principal": bool(f.eh_principal(a)),
                    "termo_de_referencia": bool(re.search(r"termo de referencia|(?<![a-z])tr(?![a-z])", f.norm(tipo + " " + titulo)))})
    return out


# ----------------------------------------------------------------- Pedido 13K: PDF sem texto (digitalizado) -- funções novas, puras, sem rede
CARACTERES_MINIMOS_PAGINA = 10   # página com menos de N caracteres (sem espaços) conta como 'sem texto'; N medido em PDFs reais (pedido13k\medicao_a1.json)


def caracteres_por_pagina(paginas):
    """Caracteres SEM espaços de cada página (a lista de textos que a extração devolveu)."""
    return [len("".join(str(p or "").split())) for p in paginas or []]


def avaliar_texto_documento(paginas):
    """{'paginas', 'sem_texto', 'total', 'estado'}: estado 'sem_texto' (total abaixo de N x páginas, incluindo 0), 'parcial' (só algumas páginas abaixo de N) ou 'ok'."""
    cs = caracteres_por_pagina(paginas)
    n, sem, total = len(cs), sum(1 for c in cs if c < CARACTERES_MINIMOS_PAGINA), sum(cs)
    estado = "sem_texto" if (n == 0 or total < CARACTERES_MINIMOS_PAGINA * n) else ("parcial" if sem else "ok")
    return {"paginas": n, "sem_texto": sem, "total": total, "estado": estado}


def frase_sem_texto(av):
    """Frase do painel quando o documento escolhido não tem texto."""
    return f"PDF sem texto: {av['sem_texto']} de {av['paginas']} páginas sem texto (provavelmente digitalizado). A IA não tem o que ler."


def frase_paginas_sem_texto(av):
    """Aviso quando só algumas páginas não têm texto (vazio se todas têm)."""
    return f"{av['sem_texto']} de {av['paginas']} páginas sem texto." if av["estado"] == "parcial" else ""


def caracteres_do_recorte(paginas, mantidas=None):
    """Caracteres (sem espaços) das páginas mantidas no recorte (numeração a partir de 1); sem 'mantidas', do documento todo."""
    cs = caracteres_por_pagina(paginas)
    return sum(c for i, c in enumerate(cs, 1) if mantidas is None or i in set(mantidas))



# ----------------------------------------------------------------- Pedido 17 (0.4): palavras coladas ("softwarepara")
def separar_colagens(texto, contexto=()):
    """Pedido 17 (0.4). Separa palavras coladas do tipo PREFIXO + palavra fraca ('softwarepara' -> 'software para'). Regra geral, sem lista de produtos e sem dicionário novo:
    o token só é separado se (a) termina numa palavra fraca do app (FRACAS_ITEM) de 3+ letras que NÃO termina em 's' (senão 'internados', 'calçados' e outros plurais seriam cortados),
    (b) o que sobra tem 5+ letras e (c) esse prefixo aparece SOZINHO, como palavra inteira, pelo menos 3 vezes nas linhas do contexto (as descrições do mesmo código que o app já tem).
    Sem contexto suficiente nada muda. Falso positivo conhecido na medição: 'sobrepor' (nos nomes de PDM)."""
    cont = {}
    for t in list(contexto or ()) + [texto]:
        for w in re.findall(r"[A-Za-zÀ-ÿ]+", str(t or "")):
            n = f.norm(w)
            cont[n] = cont.get(n, 0) + 1
    fracas = sorted((w for w in FRACAS_ITEM if len(w) >= 3 and not w.endswith("s")), key=len, reverse=True)

    def troca(m):
        w = m.group(0); n = f.norm(w)
        if n in FRACAS_ITEM or len(n) != len(w):
            return w
        for s in fracas:
            if n.endswith(s) and len(n) - len(s) >= 5 and cont.get(n[:-len(s)], 0) >= 3:
                return w[:-len(s)] + " " + w[-len(s):]
        return w
    return re.sub(r"[A-Za-zÀ-ÿ]+", troca, str(texto or ""))


# ----------------------------------------------------------------- Pedido 17: filtro por palavra nas compras, resumo por código, indicador de descrição
COLUNAS_TEXTO_COMPRA = ("descricao_item", "descricao_item_pncp")     # colunas de texto de compra que as linhas do app carregam (a API também traz objetoCompra, mas a ferramenta não a guarda)
DESCRICAO_LIMITE_PALAVRAS = 16     # Pedido 17 (Fase 3), regra PROVISÓRIA (a equipe valida): mediana das 3.693 linhas medidas no 12B = 16 palavras


def palavras_de_busca(texto):
    """Minúsculas, sem acento, separado por tudo que não for letra ou número."""
    return re.findall(r"[a-z0-9]+", f.norm(texto))


def linhas_que_citam(linhas, digitado, colunas=COLUNAS_TEXTO_COMPRA):
    """Pedido 17. Devolve as linhas (dicts) que citam o que a pessoa digitou. Regra: minúsculas, sem acento, separar por tudo que não for letra ou número; várias palavras =
    TODAS na mesma linha, em qualquer ordem; palavra INTEIRA (Windows não acha 'windowsxp'; 'xdr' não acha 'xdrive'). Procura em todas as colunas de texto não vazias.
    Nada digitado = todas as linhas. Função geral: serve para produto e serviço; sem rede."""
    ps = set(palavras_de_busca(digitado))
    if not ps:
        return list(linhas)
    saida = []
    for l in linhas:
        txt = " ".join(str(l.get(c) or "") for c in colunas if str(l.get(c) or "").strip())
        if ps <= set(palavras_de_busca(txt)):
            saida.append(l)
    return saida


def resumo_por_codigo(linhas, citam, nomes=None, coluna_codigo="codigo_catalogo"):
    """Pedido 17. Uma linha por código: código | nome | linhas lidas | linhas que citam | compras distintas | órgãos distintos (as duas últimas contam só as linhas que citam),
    ordenado por 'linhas que citam' (maior primeiro; empate: mais lidas, depois código)."""
    nomes = nomes or {}
    ids_citam = {id(l) for l in citam}
    por = {}
    for l in linhas:
        c = re.sub(r"\.0$", "", str(l.get(coluna_codigo) or "").strip())
        g = por.setdefault(c, {"lidas": 0, "citam": 0, "compras": set(), "orgaos": set()})
        g["lidas"] += 1
        if id(l) in ids_citam:
            g["citam"] += 1
            g["compras"].add(str(l.get("id_compra") or l.get("controle_pncp") or ""))
            g["orgaos"].add(str(l.get("orgao") or ""))
    res = [{"código": c, "nome": nomes.get(c, ""), "linhas lidas": g["lidas"], "linhas que citam": g["citam"], "compras distintas": len(g["compras"] - {""}), "órgãos distintos": len(g["orgaos"] - {""})}
           for c, g in por.items()]
    return sorted(res, key=lambda r: (-r["linhas que citam"], -r["linhas lidas"], r["código"]))


def indicador_descricao(texto, limite=None):
    """Pedido 17 (Fase 3). 'descrição curta' (até o limite de palavras) ou 'descrição detalhada' (acima). SÓ conta palavras; não lê o edital. Regra provisória: a equipe valida."""
    limite = DESCRICAO_LIMITE_PALAVRAS if limite is None else limite
    return "descrição curta" if len(palavras_de_busca(texto)) <= limite else "descrição detalhada"


def estimativa_busca(n_codigos, chamadas_por_codigo=12, segundos_por_codigo=39):
    """Pedido 17. Texto de aviso antes do Buscar com 2 ou mais códigos (números MEDIDOS: 12 chamadas e 39 s para 1 código no modo rápido; pausa de 3 s entre chamadas)."""
    seg = n_codigos * segundos_por_codigo
    tempo = f"{seg // 60} min {seg % 60:02d} s" if seg >= 60 else f"{seg} s"
    return (f"{n_codigos} códigos × cerca de {chamadas_por_codigo} chamadas (medido: {chamadas_por_codigo} chamadas e {segundos_por_codigo} s para 1 código no modo rápido); "
            f"pausa de 3 s entre chamadas; tempo estimado {tempo}")


# ======================= Pedido 18: produto (orientação de software, "Você quis dizer", custo, item único) =======================
ITENS_SOFTWARE_CSV = f.CONFIG / "itens_software_11248.csv"      # codigoItem;descricaoItem: os itens do PDM 'Software' (copiados do pedido11; atualizar quando o catálogo mudar)


def ler_itens_software(caminho=None):
    """Pedido 18. Itens do PDM Software (codigoItem;descricaoItem). Arquivo ausente ou ilegível = lista vazia (a orientação então não diz 'zero itens')."""
    try:
        with Path(caminho or ITENS_SOFTWARE_CSV).open(encoding="utf-8-sig", newline="") as fh:
            return [dict(l) for l in csv.DictReader(fh, delimiter=";")]
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def itens_que_citam_termo(termo, itens):
    """Pedido 18. Quantos itens citam o termo como palavra inteira (minúsculas, sem acento). 'termo' pode ter mais de uma palavra: todas no mesmo item."""
    ps = set(palavras_de_busca(termo))
    if not ps:
        return 0
    return sum(1 for i in itens if ps <= set(palavras_de_busca(i.get("descricaoItem") or "")))


def decisao_software(digitado, termos, itens):
    """Pedido 18 (Fase 1). A decisão sai da CONTAGEM no CSV, não de lista de nomes no código. 'termos' = os do config\\termos_software.csv (já sem acento).
    Devolve {"decisao": "sem_termo" | "orientacao_atual" | "servico", "termos": [os que aparecem no digitado], "contagem": {termo: n}, "total": nº de itens}.
    'orientacao_atual' = algum termo digitado tem ao menos 1 item (ou o CSV de itens não existe: não afirmo 'zero'); 'servico' = todos os termos digitados têm 0 itens."""
    cheio = " " + " ".join(palavras_de_busca(digitado)) + " "
    achados = [t for t in sorted(termos) if f" {t} " in cheio]
    if not achados:
        return {"decisao": "sem_termo", "termos": [], "contagem": {}, "total": len(itens)}
    cont = {t: itens_que_citam_termo(t, itens) for t in achados}
    if not itens or any(n > 0 for n in cont.values()):
        return {"decisao": "orientacao_atual", "termos": achados, "contagem": cont, "total": len(itens)}
    return {"decisao": "servico", "termos": achados, "contagem": cont, "total": len(itens)}


def mensagem_software_sem_item(termo_digitado, total):
    """Pedido 18 (Fase 1). Texto fixo da orientação quando o termo tem 0 itens no PDM Software."""
    return (f"Não há item de '{termo_digitado}' no catálogo de material (PDM Software: 0 de {total} itens). "
            "Compras assim costumam aparecer em SERVIÇO: mude para Serviço e procure 'licenciamento'.")


def distancia_edicao(a, b):
    """Pedido 18. Distância de edição (Levenshtein: inserir, apagar ou trocar 1 letra)."""
    if a == b:
        return 0
    ant = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(ant[j] + 1, atual[j - 1] + 1, ant[j - 1] + (ca != cb)))
        ant = atual
    return ant[-1]


def sugestao_valida(digitado, sugestao):
    """Pedido 18 (Fase 2). Só vale a sugestão se, para CADA palavra digitada (sem números), alguma palavra da sugestão tem a mesma primeira letra e distância de edição
    ≤ 1 (≤ 2 se a palavra digitada tiver 8 ou mais letras). Distância 0 (a palavra está na sugestão) vale."""
    dig = [w for w in palavras_de_busca(digitado) if not w.isdigit()]
    sug = [w for w in palavras_de_busca(sugestao) if not w.isdigit()]
    if not dig or not sug:
        return False
    for w in dig:
        lim = 2 if len(w) >= 8 else 1
        if not any(s[0] == w[0] and distancia_edicao(w, s) <= lim for s in sug):
            return False
    return True


def filtrar_sugestoes(digitado, sugestoes):
    """Pedido 18 (Fase 2). Mantém só as sugestões que passam em sugestao_valida; lista vazia = a tela não mostra a linha 'Você quis dizer…'."""
    return [s for s in sugestoes if sugestao_valida(digitado, s)]


def aviso_custo_produto(n_codigos, modos, chamadas_rapido=33, tempo_rapido="104 s", chamadas_completo=131, tempo_completo="6 min 53 s"):
    """Pedido 18 (Fase 3). Aviso antes do Buscar do Produto, com 1 ou mais códigos marcados (vazio com 0). Os limites vêm de 'modos' (os MODOS do app);
    os números 'medido em 1 código (21/11)' são do dono do projeto (33 chamadas e 104 s no rápido; 131 chamadas e 6 min 53 s no completo): nesta etapa não foram medidos de novo."""
    if n_codigos < 1:
        return ""
    r, c = modos["rápido"], modos["completo"]
    return (f"{n_codigos} código(s) · rápido: até {r['MAX_PAGINAS_CATALOGO']} páginas e {r['MAX_VINCULOS']} compras ligadas ao PNCP; "
            f"completo: até {c['MAX_PAGINAS_CATALOGO']} páginas e {c['MAX_VINCULOS']} compras. "
            f"Medido em 1 código (21/11): rápido {chamadas_rapido} chamadas e {tempo_rapido}; completo {chamadas_completo} chamadas e {tempo_completo}. "
            "Pausa de 3 s entre chamadas.")


def aviso_item_unico(linhas, nomes=None, minimo=20, coluna_codigo="codigo_catalogo", limite_nome=80):
    """Pedido 18 (Fase 4). Se há pelo menos 'minimo' linhas lidas e TODAS têm o mesmo código de catálogo, devolve o texto do aviso; senão None (2 ou mais itens: nada).
    Pedido 20 (Fase 3): o nome mostrado tem no máximo 'limite_nome' caracteres; se for maior, corta em fronteira de palavra (nunca no meio da palavra) e termina com '…'."""
    cods = [re.sub(r"\.0$", "", str(l.get(coluna_codigo) or "").strip()) for l in linhas]
    if len(cods) < minimo or len(set(cods)) != 1 or not cods[0]:
        return None
    c = cods[0]; nome = " ".join(str((nomes or {}).get(c, "")).split())
    if len(nome) > limite_nome:
        corte = nome[:limite_nome]
        if nome[limite_nome] != " " and " " in corte:     # o corte caiu no meio de uma palavra: volta ao último espaço
            corte = corte[:corte.rindex(" ")]
        nome = corte.rstrip(" ,;:/-") + "…"
    return (f"As {len(cods)} linhas lidas são do mesmo item de catálogo (código {c}{': ' + nome if nome else ''}). "
            "O produto de cada compra está no texto da descrição: use 'Mostrar só linhas que citam a palavra'.")


# ----------------------------------------------------------------- Pedido 25 (Fase 1): download sem arquivo principal -- funções puras, sem rede
def mensagem_sem_principais(log_download, titulos=None):
    """Quando a lista do PNCP veio e nenhum arquivo ativo é principal (edital, TR, ETP, DFD, aviso), o download não é falha: é regra. Lê o texto que a
    opção 3 imprimiu ('N arquivos ativos: 0 principais ... e M outros'). Devolve a frase com o motivo e os títulos, ou None nos outros casos
    (falha de rede, portal fora, lista que não veio, compra sem PNCP, ou pelo menos 1 principal). NÃO muda quais arquivos são principais (f.eh_principal)."""
    texto = log_download or ""
    m = re.search(r"(\d+) arquivos ativos: (\d+) principais", texto)
    if not m or "PORTAL FORA" in texto or "Lista de arquivos não veio" in texto or re.search(r"^\s*baixado: ", texto, re.M):
        return None
    ativos, principais = int(m.group(1)), int(m.group(2))
    if ativos < 1 or principais != 0:
        return None
    nomes = [" ".join(str(x).split()) for x in (titulos or []) if str(x).strip()]
    lista = ("; ".join(nomes[:10]) + (f"; (e mais {len(nomes) - 10})" if len(nomes) > 10 else "")) if nomes else "(títulos não disponíveis)"
    return (f"A compra tem {ativos} arquivo(s) no PNCP, mas nenhum é edital, TR, ETP, DFD ou aviso; nada foi baixado por regra. "
            f"Títulos: {lista}. Para baixar esses arquivos mesmo assim, marque \"Baixar também propostas, atas e despachos\".")


def titulos_da_lista(pasta):
    """Títulos dos arquivos ativos em <pasta>\\_lista_arquivos_pncp.json (gravado pela opção 3). [] se o arquivo não existir ou não for uma lista."""
    import json
    try:
        lista = json.loads((Path(pasta) / "_lista_arquivos_pncp.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(lista, list):
        return []
    return [str(a.get("titulo") or a.get("tipoDocumentoNome") or "(sem título)") for a in lista if isinstance(a, dict) and a.get("statusAtivo") is not False]


# ----------------------------------------------------------------- Pedido 25 (Fase 3): aviso do modo rápido -- só contagem, sem IA, sem rede
def aviso_modo_rapido(linhas, modo, rotulo_suspeito="preço suspeito"):
    """No modo rápido, conta entre as linhas LIGADAS ao PNCP (link_publico começando com http) quantos órgãos distintos há, quantas têm preço suspeito e
    quantos preços distintos. Devolve (frase, alerta) ou None (outro modo, ou nenhuma linha ligada: n=0, nada a comparar). alerta=True quando há 2+ ligadas e
    todas são do mesmo órgão ou do mesmo preço: então 'as ligadas podem não representar o mercado; use o modo completo'. Não decide nada: só conta."""
    if f.norm(str(modo or "")) != "rapido":
        return None
    lig = [l for l in (linhas or []) if str(l.get("link_publico") or "").startswith("http")]
    if not lig:
        return None
    orgaos = {" ".join(f.norm(str(l.get("orgao") or "")).split()) for l in lig} - {""}
    precos = set()
    for l in lig:
        try:
            precos.add(round(float(str(l.get("preco_unitario_homologado")).replace(",", ".")), 6))
        except (TypeError, ValueError):
            pass
    susp = sum(1 for l in lig if str(l.get("observacao_preco") or "") == rotulo_suspeito)
    n = len(lig)
    frase = (f"Modo rápido: das {n} linha(s) ligada(s) ao PNCP, {len(orgaos)} órgão(s) distinto(s), {len(precos)} preço(s) distinto(s) e {susp} com preço suspeito.")
    alerta = n >= 2 and (len(orgaos) == 1 or len(precos) == 1)
    if alerta:
        frase += " As ligadas podem não representar o mercado; use o modo completo."
    return frase, alerta


# ----------------------------------------------------------------- Pedido 28 (Fase 2): '|' do item pedido só no texto enviado à IA -- função pura, sem rede
_CABECALHO_RECORTE = re.compile(r"^(DOCUMENTO [^\n|]*\| item pedido: )(.*?)( \| \d+ páginas no original \| páginas incluídas:)", re.M)


def texto_ia_sem_barra_no_item(texto):
    """No PARA_IA, troca '|' por ' / ' SÓ dentro do item pedido da primeira linha do recorte ('DOCUMENTO … | item pedido: <item> | N páginas no original | …').
    O app usa '|' para separar termos do item; copiado pelo modelo, ele quebra a coluna da tabela da ficha. Medido em 22/11/2026 (Nemotron local, temperatura 0, n=6 por variante):
    com '|' o atributo veio com '|' dentro da célula em 6 de 6; com ' / ' em 0 de 6. Não muda o item guardado, nem recorte.txt: quem chama usa só para o texto enviado à IA.
    Sem '|' no item, ou sem essa linha, devolve o texto igual."""
    return _CABECALHO_RECORTE.sub(lambda m: m.group(1) + m.group(2).replace("|", " / ") + m.group(3), texto or "", count=1)


# ----------------------------------------------------------------- Pedido 28 (Fase 3): falhas do download com código HTTP e frase curta -- funções puras, sem rede
def frase_falha_http(codigo):
    """Frase curta em português para um código HTTP (int ou texto) devolvido pelo PNCP. Só o código entra na frase: nunca o corpo da resposta."""
    c = int(codigo)
    if c == 422:
        return "PNCP respondeu 422: erro do lado do PNCP ao carregar o arquivo; tente de novo mais tarde"
    if c == 404:
        return "PNCP respondeu 404: arquivo não encontrado no PNCP (pode ter sido removido); confira a compra no portal"
    if c == 403:
        return "PNCP respondeu 403: acesso bloqueado; o app parou e não insiste"
    if c == 429:
        return "PNCP respondeu 429: limite de requisições; espere antes de tentar de novo"
    if c >= 500:
        return f"PNCP respondeu {c}: servidor do PNCP indisponível ou com erro; tente de novo mais tarde"
    return f"PNCP respondeu {c}: o PNCP recusou o pedido deste arquivo; tente de novo mais tarde"


def frase_falha_rede(nome):
    """Frase curta para uma falha sem código HTTP (nome do erro de rede, como ReadTimeout)."""
    n = str(nome or "")
    if "timeout" in n.lower():
        return "Sem resposta do PNCP (tempo esgotado); tente de novo mais tarde"
    if "connection" in n.lower():
        return "Sem conexão com o PNCP; confira a rede e tente de novo"
    return "Falha de rede ao falar com o PNCP; tente de novo mais tarde"


def falhas_do_download(log_download):
    """Lê o que a opção 3 imprimiu e devolve [{'arquivo','codigo','frase'}], um por arquivo que falhou ('<título>: HTTP N, não baixado') mais, se o download foi interrompido,
    um item '(download interrompido)' com o código ou o nome do erro da linha '*** PORTAL FORA OU BLOQUEADO'. NUNCA copia a URL nem outro texto da linha: só o código (3 dígitos)
    ou o nome do erro. Sem falha: []."""
    texto = log_download or ""
    out = []
    for m in re.finditer(r"^[ \t]*(.+?): HTTP (\d{3}), não baixado[ \t]*$", texto, re.M):
        out.append({"arquivo": " ".join(m.group(1).split())[:80], "codigo": m.group(2), "frase": frase_falha_http(m.group(2))})
    pf = re.search(r"^\*\*\* PORTAL FORA OU BLOQUEADO: (.*)$", texto, re.M)
    if pf:
        linha = pf.group(1)
        h = re.search(r"HTTP (\d{3})", linha)
        e = re.search(r"\(([A-Za-z]*(?:Timeout|Error|Exception)[A-Za-z]*)\)", linha)
        if h:
            out.append({"arquivo": "(download interrompido)", "codigo": h.group(1), "frase": frase_falha_http(h.group(1))})
        elif e:
            out.append({"arquivo": "(download interrompido)", "codigo": e.group(1), "frase": frase_falha_rede(e.group(1))})
        else:
            out.append({"arquivo": "(download interrompido)", "codigo": "sem código", "frase": "Download interrompido: o portal não respondeu; tente de novo mais tarde"})
    return out


def resumo_falhas(falhas):
    """'HTTP 422 em 2 arquivo(s); ReadTimeout em 1' (contagem por código). '' se não há falha."""
    cont = {}
    for x in falhas or []:
        k = ("HTTP " + x["codigo"]) if x["codigo"].isdigit() else x["codigo"]
        cont[k] = cont.get(k, 0) + 1
    return "; ".join(f"{k} em {n} arquivo(s)" if k.startswith("HTTP") else f"{k} em {n}" for k, n in cont.items())


def sem_enderecos(texto):
    """Troca qualquer endereço (http/https) do texto por '(endereço omitido)': a tela não mostra URL com identificadores da compra."""
    return re.sub(r"https?://\S+", "(endereço omitido)", texto or "")


# ----------------------------------------------------------------- Pedido 33 (Fase 1): padrões da tela -- funções puras, sem rede
def ligada_ao_pncp(link):
    """Linha ligada ao PNCP = link_publico começando com http (mesma regra que a tela já usa)."""
    return str(link or "").startswith("http")


def ligadas_primeiro(df):
    """Tabela de resultados (Etapa 2): linhas ligadas ao PNCP primeiro; dentro de cada grupo a ordem é a de antes (ordenação estável).
    Devolve uma cópia: não altera o df recebido nem o CSV da busca. Sem a coluna link_publico, devolve o df como veio."""
    if "link_publico" not in df.columns:
        return df
    nao_ligada = (~df["link_publico"].map(ligada_ao_pncp)).astype(int)
    return df.assign(_nl=nao_ligada).sort_values("_nl", kind="stable").drop(columns="_nl").reset_index(drop=True)


def indice_primeira_ligada(links):
    """Posição (0, 1, ...) da primeira linha ligada ao PNCP numa lista de links; 0 se nenhuma estiver ligada (a tela abre na linha 1, como antes)."""
    return next((i for i, x in enumerate(links) if ligada_ao_pncp(x)), 0)


def _eh_tr(a):
    """Mesma regra de listar_documentos_compra para o campo 'termo_de_referencia'."""
    return bool(re.search(r"termo de referencia|(?<![a-z])tr(?![a-z])", f.norm((a.get("tipoDocumentoNome") or "") + " " + (a.get("titulo") or ""))))


def indice_documento_recorte(pasta, arquivos):
    """Posição do documento em que 'Documento para recortar' abre. 'arquivos' são os PDF/Word baixados em <pasta>, na ordem da lista da tela.
    Os arquivos baixados começam com '<sequencialDocumento>_' (os extraídos de ZIP ficam numa subpasta com esse prefixo); a ligação com a lista do PNCP
    (_lista_arquivos_pncp.json, gravada pelo download) é por esse número. Ordem: 1) arquivo marcado como TR; 2) primeiro principal (f.eh_principal);
    3) sem a lista (download antigo): nome com 'termo'/'tr', como era; 4) o primeiro. Devolve (posição, motivo)."""
    import json
    try:
        lista = json.loads((Path(pasta) / "_lista_arquivos_pncp.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        lista = None
    if isinstance(lista, list):
        ativos = [a for a in lista if isinstance(a, dict) and a.get("statusAtivo") is not False]
        grupos = (("TR", {str(a.get("sequencialDocumento")) for a in ativos if _eh_tr(a)}),
                  ("principal", {str(a.get("sequencialDocumento")) for a in ativos if f.eh_principal(a)}))
        topo = []
        for p in arquivos:
            try:
                primeiro = Path(p).relative_to(pasta).parts[0]
            except ValueError:
                primeiro = Path(p).name
            m = re.match(r"(\d+)_", primeiro)
            topo.append(m.group(1) if m else None)
        for motivo, seqs in grupos:
            for i, s in enumerate(topo):
                if s is not None and s in seqs:
                    return i, motivo
    for i, p in enumerate(arquivos):
        if re.search(r"termo|\btr\b", f.norm(Path(p).name)):
            return i, "nome"
    return 0, "primeiro"


def recorte_padrao(recortes, atual=None):
    """Recorte em que a Etapa 5 abre. 'recortes' vem do mais recente para o mais antigo. Abre no gerado por último nesta sessão (nome em 'atual', se achado na
    lista); senão no mais recente. Devolve None se não houver recorte."""
    if not recortes:
        return None
    return next((p for p in recortes if p.name == atual), recortes[0])


def frase_recorte_conferido(recortes, escolhido):
    """Uma linha dizendo qual recorte a Etapa 5 está conferindo e se é o mais recente da sessão."""
    n = len(recortes)
    base = f"Recorte conferido: {escolhido.name} ({n} recorte(s) nesta sessão)"
    if escolhido == recortes[0]:
        return base + "; é o mais recente."
    return base + f"; NÃO é o mais recente (o mais recente é {recortes[0].name})."


# ----------------------------------------------------------------- Pedido 33 (Fase 2): aviso na lista de documentos -- função pura, sem rede
def aviso_sem_documento_principal(docs):
    """'docs' = lista devolvida por listar_documentos_compra. Se a lista veio (1+ arquivo) e nenhum é edital, TR, ETP, DFD ou aviso (campo 'principal'), devolve a frase
    de aviso para mostrar ANTES do botão de baixar; senão None (lista vazia = o PNCP não respondeu: não é conclusão, a tela já tem outro aviso). Não baixa nada."""
    docs = [d for d in (docs or []) if isinstance(d, dict)]
    if not docs or any(d.get("principal") for d in docs):
        return None
    return ("Esta compra não tem TR, edital, ETP, DFD nem aviso na lista do PNCP; provavelmente contratação direta. "
            "Por regra, o download não traz nada se você não marcar \"Baixar também propostas, atas e despachos\".")

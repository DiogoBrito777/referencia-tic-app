"""Fase 4 – teste automático da TELA (streamlit.testing.v1.AppTest) sobre app.py, SEM rede, SEM navegador, SEM Ollama.
A rede é trocada por respostas falsas (ferramenta.get); socket.connect bloqueado. Dados simulados só aqui.
Cobre: (1) aviso de corte 1.234 x 300 e sem aviso com lidos = informados; (2) texto do download: concluído / PARCIAL / NÃO concluído;
(3) 'Preencha os atributos' fora de 'Mensagens da busca'; (4) linha de orçamento de tokens e aviso 'NÃO CABE' na tela do texto para IA.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_tela_fase4.py   (na pasta do app)"""
import contextlib, datetime as dt, re, socket, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True

# O asyncio do Windows (usado pelo AppTest) abre um par de sockets em 127.0.0.1 para si mesmo (socketpair). Isso não é rede: só
# esses connects de loopback são deixados passar e CONTADOS; qualquer outro destino, e a porta 11434 (Ollama), derruba o teste.
LOOPBACK_INTERNO = []
_connect_original = socket.socket.connect
def _sem_rede(self, endereco, *a, **k):
    host, porta = (endereco[0], endereco[1]) if isinstance(endereco, tuple) else (str(endereco), None)
    if host in ("127.0.0.1", "::1") and porta != 11434:
        LOOPBACK_INTERNO.append((host, porta)); return _connect_original(self, endereco, *a, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {endereco!r}")
socket.socket.connect = _sem_rede

from streamlit.testing.v1 import AppTest
import ferramenta as f
# Pedido 16 (M1): este teste guarda o comportamento de 16.384. Usa uma CÓPIA TEMPORÁRIA do config com contexto_tokens=16384; o config real (hoje 32.768) não é tocado.
import atexit as _at, os as _os, re as _re, shutil as _sh
_CFG16 = DADOS / "pedido16" / f"_tmp_cfg16384_{_os.getpid()}"; _CFG16.mkdir(parents=True, exist_ok=True); _at.register(_sh.rmtree, _CFG16, ignore_errors=True)
(_CFG16 / "orcamento_tokens.csv").write_text(_re.sub(r";\d+;1500;", ";16384;1500;", f.ORCAMENTO_CSV.read_text(encoding="utf-8-sig"), count=1), encoding="utf-8-sig"); f.ORCAMENTO_CSV = _CFG16 / "orcamento_tokens.csv"

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

TMP = DADOS / "tmp_teste_fase4"; TMP.mkdir(exist_ok=True)
RODADA = TMP / f"r{int(time.time())}"; RODADA.mkdir()
f.PASTA = RODADA                      # BASE_SAIDA do app = f.PASTA / "saida": as sessões do teste ficam na pasta de teste

# ------------------------------------------------------------------ rede falsa
HOJE = dt.date.today().isoformat()
ESTADO = {"total": 1234, "ligar": False, "falha_seq": set(), "recorte": 6000, "chamadas": [], "inesperadas": []}
REG_PNCP = {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}
LISTA = [{"titulo": "Edital", "tipoDocumentoNome": "Edital", "sequencialDocumento": 1}, {"titulo": "Termo de Referência", "tipoDocumentoNome": "Termo de Referência", "sequencialDocumento": 2}]

def get(url, params=None, binario=False):          # qualname 'get': o app o trata como a função original
    params = params or {}; ESTADO["chamadas"].append(url)
    if "1_consultarMaterial" in url:
        pag = params.get("pagina", 1)
        lote = [{"idCompra": f"9{(pag - 1) * 100 + i:016d}", "precoUnitario": 3000.0 + i, "dataResultado": HOJE, "dataCompra": HOJE, "nomeOrgao": f"ORGAO SIMULADO {i}", "estado": "DF",
                 "descricaoItem": "NOTEBOOK i5 16 GB RAM SSD 512 GB tela 15,6 polegadas garantia 12 meses", "numeroItemCompra": i + 1, "nomePdm": "NOTEBOOK", "codigoItemCatalogo": 1000 + i, "marca": "X"} for i in range(100)]
        ultima = pag * 100 >= ESTADO["total"]
        return 200, {"totalRegistros": ESTADO["total"], "resultado": lote, "paginasRestantes": 0 if ultima or pag >= 3 and ESTADO["total"] <= 300 else 1}, {}
    if "4_consultarItemMaterial" in url:
        return 200, {"resultado": []}, {}
    if "1.1_consultarContratacoes_PNCP_14133_Id" in url:
        return 200, {"resultado": [REG_PNCP] if ESTADO["ligar"] else []}, {}
    if url.endswith("/arquivos"):
        return 200, LISTA, {}
    m = re.search(r"/arquivos/(\d+)$", url)
    if m:
        return (500, b"", {}) if int(m.group(1)) in ESTADO["falha_seq"] else (200, b"%PDF-1.4 conteudo simulado", {})
    ESTADO["inesperadas"].append(url); raise AssertionError(f"URL inesperada no teste: {url}")
f.get = get

def opcao_4_falsa():                               # só recorta (PDF falso não é PDF de verdade); a opção 5 é a REAL
    f.escolher_numero("posição", 99); f.pergunta("item")
    pasta = f.SAIDA / "recortes" / "TR_sim"; pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "recorte.txt").write_text("x" * ESTADO["recorte"], encoding="utf-8")
    print(f"Recorte salvo em: {pasta / 'recorte.txt'}")
_opcao_4_real = f.opcao_4_recortar                 # v4h (T5): a opção 4 REAL, com a extração do PDF trocada por páginas gravadas
f.opcao_4_recortar = opcao_4_falsa

IMPRESSO_PERGUNTAR = []                            # controle: a função REALMENTE imprime a frase durante a busca
_orig_perg = f.perguntar_atributos
def perguntar_vigiado(atributos):
    r = _orig_perg(atributos); IMPRESSO_PERGUNTAR.append("Preencha os atributos" in sys.stdout.getvalue()); return r
f.perguntar_atributos = perguntar_vigiado

# ------------------------------------------------------------------ utilidades da tela
def textos(at):
    saida = []
    for lista in (at.warning, at.success, at.error, at.info, at.markdown, at.caption, at.text, at.text_area, at.subheader, at.title):
        saida += [str(e.value) for e in lista]
    return saida
def tem(at, trecho): return any(trecho in t for t in textos(at))
def onde(at, trecho): return [t for t in textos(at) if trecho in t]
def botao(at, rotulo): return next(b for b in at.button if b.label == rotulo)
def sem_excecao(at, onde_): checa(len(at.exception) == 0, f"{onde_}: sem exceção na tela" + ("" if not at.exception else f" -> {[e.value for e in at.exception]}"))

print("=== T0. preparação: a tela abre e o código 8435 (PDM NOTEBOOK) é conferido com resposta falsa ===")
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180)
at.run(); sem_excecao(at, "abertura")
checa(any("Referência TIC" in t.value for t in at.title), "a tela abriu (título 'Referência TIC')")
at.text_input(key="codigo_av").set_value("8435").run(); sem_excecao(at, "código digitado")
checa(tem(at, "Código 8435: NOTEBOOK"), "conferência do código com resposta falsa: " + (onde(at, "Código 8435")[:1] or ["(sem mensagem)"])[0])
checa(any(k.startswith("at_notebook_") for k in [t.key for t in at.text_input if t.key]), "atributos do perfil 'notebook' aparecem no formulário: " + str([t.key for t in at.text_input if t.key and t.key.startswith("at_")]))
at.text_input(key="at_notebook_RAM").set_value("16")

def buscar(at):
    botao(at, "Buscar").click().run()
    return at

print("\n=== T1. aviso de corte: API informa 1.234 e só 300 são lidos ===")
ESTADO.update(total=1234); ESTADO["chamadas"].clear()
buscar(at); sem_excecao(at, "busca 1.234")
n_mat = sum("1_consultarMaterial" in u for u in ESTADO["chamadas"])
checa(n_mat == 3, f"o modo rápido pediu 3 páginas da pesquisa de preço (chamadas falsas: {n_mat})")
av = onde(at, "BUSCA CORTADA")
print("  aviso na tela:", av[:1])
checa(len(av) == 1 and "1.234 registros" in av[0] and "só 300 foram lidos" in av[0] and "934 restantes" in av[0], "st.warning 'BUSCA CORTADA' com 1.234 informados, 300 lidos e 934 restantes")
checa(any("BUSCA CORTADA" in w.value for w in at.warning), "o aviso está num st.warning (visível, não só no log)")
log1 = onde(at, "pesquisa de preço, página")
checa(len(log1) >= 1, "T3-controle: o expander 'Mensagens da busca' mostra o log da busca (tem 'pesquisa de preço, página')")
checa(IMPRESSO_PERGUNTAR and IMPRESSO_PERGUNTAR[-1] is True, f"T3-controle: a função perguntar_atributos IMPRIMIU a frase durante esta busca (controle positivo: {IMPRESSO_PERGUNTAR})")
checa(not tem(at, "Preencha os atributos"), "T3: a frase 'Preencha os atributos' NÃO aparece em nenhum texto da tela (nem em 'Mensagens da busca') [busca 1.234]")

print("\n=== T1b. sem aviso quando lidos = informados (300 de 300) ===")
ESTADO.update(total=300); ESTADO["chamadas"].clear()
buscar(at); sem_excecao(at, "busca 300")
print("  chamadas falsas da 2ª busca:", sum("1_consultarMaterial" in u for u in ESTADO["chamadas"]), "| erros na tela:", [e.value[:150] for e in at.error], "| avisos:", [w.value[:100] for w in at.warning])
checa(not tem(at, "BUSCA CORTADA"), "300 informados e 300 lidos: nenhum 'BUSCA CORTADA' na tela")
checa(tem(at, "300 na API → 300 lidos") and at.session_state["busca_atual"]["resumo"]["registros_informados_pela_api"] == 300 and [h["resumo"]["registros_informados_pela_api"] for h in at.session_state["historico"]] == [1234], "a busca da tela é a NOVA (300 informados, 300 lidos); a de 1.234 foi para o histórico: " + (onde(at, "300 na API")[:1] or ["(sem resumo)"])[0][-90:])
checa(not tem(at, "Preencha os atributos") and IMPRESSO_PERGUNTAR[-1] is True, "T3: de novo, sem 'Preencha os atributos' na tela (a função imprimiu a frase na busca)")

print("\n=== T2. texto do download (linha 1; a compra só é ligada ao PNCP na hora do download) ===")
ESTADO.update(ligar=True, falha_seq=set())
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "download ok")
ok = [t for t in textos(at) if "download" in t and (t.startswith("Concluída") or t.startswith("Falhou"))]
print("  tela:", ok)
checa(any(t.startswith("Concluída em ") and t.endswith("download concluído (2 arquivo(s))") for t in ok), "2 de 2 baixados: painel 'Concluída em N s: … download concluído (2 arquivo(s))' (Pedido 13I)")

print("\n=== T4. tela do texto para IA: orçamento de tokens ===")
def gerar_texto(chars):
    ESTADO["recorte"] = chars
    botao(at, "Gerar texto para IA").click().run()
ESTADO["recorte"] = 6000
gerar_texto(6000); sem_excecao(at, "texto IA (6.000)")
suc = onde(at, "Pronto:")
print("  tela:", [s[-150:] for s in suc])
checa(len(suc) == 1 and "≈ 2.767 tokens de 16.384 (fator 2,9 car./token, config)" in suc[0], "recorte de 6.000 car.: '≈ 2.767 tokens de 16.384 (fator 2,9 car./token, config)' na mensagem de sucesso")
checa(not tem(at, "NÃO CABE"), "recorte de 6.000 car.: sem aviso 'NÃO CABE'")
gerar_texto(60000); sem_excecao(at, "texto IA (60.000)")
suc, nao = onde(at, "Pronto:"), onde(at, "NÃO CABE")
print("  tela:", [s[-150:] for s in suc], [n[:200] for n in nao])
checa(len(suc) == 1 and "≈ 21.388 tokens de 16.384 (fator 2,9 car./token, config)" in suc[0], "recorte de 60.000 car.: '≈ 21.388 tokens de 16.384 (fator 2,9 …)' na mensagem")
checa(len(nao) == 1 and "faltam ≈ 6.504" in nao[0] and any("NÃO CABE" in w.value for w in at.warning), "recorte de 60.000 car.: st.warning 'NÃO CABE' com 'faltam ≈ 6.504'")

print("\n=== T2b. download PARCIAL e NÃO concluído ===")
ESTADO["falha_seq"] = {2}
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "download parcial")
ok = [t for t in textos(at) if "download" in t and (t.startswith("Concluída") or t.startswith("Falhou"))]
print("  tela:", ok)
checa(any(t.startswith("Concluída com falhas em ") and t.endswith("download PARCIAL: 1 arquivo(s) baixado(s), 1 falhou/falharam") for t in ok) and not any("concluído (" in t for t in ok), "1 baixado e 1 falha: painel 'Concluída com falhas em N s: … download PARCIAL: 1 arquivo(s) baixado(s), 1 falhou/falharam' e NÃO diz 'concluído ('")
ESTADO["falha_seq"] = {1, 2}
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "download falho")
ok = [t for t in textos(at) if "download" in t and (t.startswith("Concluída") or t.startswith("Falhou"))]
print("  tela:", ok)
checa(any(t.startswith("Falhou: ") and t.endswith("download NÃO concluído: nenhum arquivo foi baixado") for t in ok) and not any(re.search(r"download concluído", t) for t in ok), "0 de 2 baixados: painel 'Falhou: download NÃO concluído: nenhum arquivo foi baixado'")

print("\n=== T5 (v4h). tela do texto para IA com a guarda de contexto: linha 'Recorte: X de Y ...' e aviso 'Recorte reduzido' ===")
import json as _json
_P1 = DADOS / "noite_2026-11-18" / "produto_p1"
if not _P1.exists(): _P1 = DADOS.parent / "noite_2026-11-18" / "produto_p1"
_pags = _json.loads((next((_P1 / "fase2" / "trabalho" / "recortes").glob("N03*")) / "paginas.json").read_text(encoding="utf-8"))
ESTADO.update(ligar=True, falha_seq=set())
botao(at, "Baixar documentos da linha").click().run(); sem_excecao(at, "download ok (T5)")
f.opcao_4_recortar = _opcao_4_real; f.extrair_paginas = lambda caminho: (_pags, "")      # PDF falso -> as páginas reais de N03 (só leitura)
botao(at, "Gerar texto para IA").click().run(); sem_excecao(at, "texto IA com guarda de contexto")
linha_t5 = [i.value for i in at.info if str(i.value).startswith("Recorte: ")]
print("  tela:", linha_t5, [w.value[:140] for w in at.warning if "Recorte reduzido" in w.value])
checa(len(linha_t5) == 1 and re.fullmatch(r"Recorte: \d+ de \d+ páginas relevantes · estimativa [\d.]+ tokens \(limite 70% = 11\.468,8\)", linha_t5[0]), "T5: a linha 'Recorte: X de Y páginas relevantes · estimativa Z tokens (limite 70% = 11.468,8)' aparece na tela")
_infos = list(RODADA.glob("**/recortes/*/recorte_info.json"))
_inf = _json.loads(_infos[0].read_text(encoding="utf-8")) if _infos else {}
checa(bool(_inf) and bool(linha_t5) and f"Recorte: {len(_inf['mantidas'])} de {_inf['n_relevantes']} páginas" in linha_t5[0], f"T5: a linha da tela bate com o recorte_info.json gravado (mantidas {_inf.get('mantidas')}, fora {_inf.get('fora')})")
_av = [w.value for w in at.warning if "Recorte reduzido" in w.value]
checa(bool(_inf) and ((len(_av) >= 1 and all(all(str(p) in w for p in _inf["fora"]) for w in _av)) if _inf["fora"] else not _av), f"T5: aviso 'Recorte reduzido' {'lista as páginas de fora' if _inf.get('fora') else 'ausente (nada ficou de fora)'}")
checa(len(onde(at, "Pronto:")) == 1, "T5: a mensagem 'Pronto: ...' continua aparecendo")

print("\n=== fechamento do teste ===")
print(f"connects de loopback internos do asyncio (127.0.0.1, não é rede externa): {len(LOOPBACK_INTERNO)}; destinos: {sorted(set(LOOPBACK_INTERNO))[:3]}")
checa(all(h in ("127.0.0.1", "::1") and p != 11434 for h, p in LOOPBACK_INTERNO), "nenhum connect a destino externo nem à porta 11434 (Ollama)")
checa(not ESTADO["inesperadas"],f"nenhuma URL inesperada pedida à rede falsa ({len(ESTADO['chamadas'])} chamadas falsas no total; {len(ESTADO['inesperadas'])} inesperadas)")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

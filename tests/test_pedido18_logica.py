"""v4h, Pedido 18 – LÓGICA (offline, socket bloqueado): orientação de software pela contagem no CSV dos 146 itens (Fase 1), 'Você quis dizer' com regra de letra e distância (Fase 2, tabela antes/depois
gravada em pedido18\\tabela_fase2_depois.json), aviso de custo do Produto (Fase 3) e aviso de item único (Fase 4). Não lê edital e não usa Ollama.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido18_logica.py   (na pasta do app)"""
import csv, json, socket, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
def _b(self, a, *x, **k): raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
import ferramenta as f
import servicos as sv
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
TERMOS = {f.norm(l["termo"]).strip() for l in csv.DictReader((RAIZ / "config" / "termos_software.csv").open(encoding="utf-8-sig", newline=""), delimiter=";") if (l["termo"] or "").strip()}
ITENS = sv.ler_itens_software()
MODOS = {"rápido": {"MAX_PAGINAS_CATALOGO": 3, "MAX_VINCULOS": 10}, "completo": {"MAX_PAGINAS_CATALOGO": f.MAX_PAGINAS_CATALOGO, "MAX_VINCULOS": f.MAX_VINCULOS}}

print("=== Fase 1: orientação de software pela contagem no CSV ===")
checa(len(ITENS) == 146 and list(ITENS[0].keys()) == ["codigoItem", "descricaoItem"], f"config\\itens_software_11248.csv: {len(ITENS)} itens, colunas {list(ITENS[0].keys())}")
orig = {l["codigoItem"]: " ".join(l["nome"].split()) for l in csv.DictReader((DADOS / "pedido11" / "itens_pdm_11248.csv").open(encoding="utf-8-sig", newline=""), delimiter=";")}
checa({i["codigoItem"]: " ".join(i["descricaoItem"].split()) for i in ITENS} == orig, "o CSV novo é cópia fiel (código e descrição) dos 146 itens do pedido11")
esperado = {"windows": 86, "office": 8, "xdr": 0, "edr": 0, "endpoint": 0, "365": 0}
for t, n in esperado.items():
    checa(sv.itens_que_citam_termo(t, ITENS) == n, f"itens que citam '{t}' (palavra inteira): {sv.itens_que_citam_termo(t, ITENS)} (medido em 20/11: {n})")
for dig in ("windows", "office", "windows 11 pro", "office 365", "Microsoft Office"):
    d = sv.decisao_software(dig, TERMOS, ITENS)
    checa(d["decisao"] == "orientacao_atual", f"'{dig}' -> {d['decisao']} (termos achados {d['termos']}, contagem {d['contagem']}; esperado: orientação atual)")
for dig in ("xdr", "edr", "endpoint", "365", "XDR endpoint", "EDR/XDR"):
    d = sv.decisao_software(dig, TERMOS, ITENS)
    checa(d["decisao"] == "servico" and d["total"] == 146, f"'{dig}' -> {d['decisao']} (contagem {d['contagem']}, total {d['total']}; esperado: mensagem de serviço)")
checa(sv.decisao_software("cadeira", TERMOS, ITENS)["decisao"] == "sem_termo", "'cadeira' (sem termo de software) -> sem_termo")
msg = sv.mensagem_software_sem_item("xdr", 146)
checa(msg == "Não há item de 'xdr' no catálogo de material (PDM Software: 0 de 146 itens). Compras assim costumam aparecer em SERVIÇO: mude para Serviço e procure 'licenciamento'.", f"texto da mensagem: {msg}")
# a decisão vem da contagem, não de lista fixa de nomes: o mesmo termo muda de decisão só porque o CSV muda
itens_fake = [{"codigoItem": "1", "descricaoItem": "SOFTWARE ZZZPROG VERSAO 1"}]
checa(sv.decisao_software("zzzprog", {"zzzprog"}, itens_fake)["decisao"] == "orientacao_atual" and sv.decisao_software("zzzprog", {"zzzprog"}, [{"codigoItem": "1", "descricaoItem": "SOFTWARE OUTRO"}])["decisao"] == "servico",
      "termo inventado: com 1 item que o cita = orientação atual; sem item = serviço (decisão pela contagem)")
checa(sv.decisao_software("xdr", TERMOS, [])["decisao"] == "orientacao_atual", "CSV de itens ausente/vazio: não afirma 'zero itens' (mantém a orientação atual)")
checa(sv.ler_itens_software(RAIZ / "config" / "nao_existe.csv") == [], "arquivo ausente = lista vazia, sem erro")

print("\n=== Fase 2: 'Você quis dizer' – regra de primeira letra e distância ===")
checa(sv.distancia_edicao("notbook", "notebook") == 1 and sv.distancia_edicao("lapto", "laptop") == 1 and sv.distancia_edicao("mouze", "mouse") == 1 and sv.distancia_edicao("abc", "abc") == 0 and sv.distancia_edicao("", "ab") == 2, "distância de edição: notbook/notebook 1, lapto/laptop 1, mouze/mouse 1")
checa(sv.sugestao_valida("notbook", "COMPUTADOR TIPO NOTEBOOK") and sv.sugestao_valida("lapto", "LAPTOP") and sv.sugestao_valida("mouze", "MOUSE COMPUTADOR"), "notbook, lapto, mouze: sugestão válida (mesma 1ª letra, distância 1)")
checa(not sv.sugestao_valida("xdr", "PUXADOR") and not sv.sugestao_valida("office", "FOICE") and not sv.sugestao_valida("windows", "INDOL"), "xdr/PUXADOR (outra 1ª letra), office/FOICE (outra 1ª letra), windows/INDOL (distância > 1): inválidas")
checa(not sv.sugestao_valida("mxuze", "MOUSE") and sv.sugestao_valida("computadro", "COMPUTADOR") and not sv.sugestao_valida("computxxxx", "COMPUTADOR"), "distância 2 só vale com 8+ letras (computadro vale; mxuze e computxxxx não)")
checa(sv.sugestao_valida("mouse com fio", "MOUSE COM FIO") and not sv.sugestao_valida("mouse sem fio", "MOUSE COMPUTADOR"), "várias palavras: todas as palavras digitadas precisam achar par na sugestão")
checa(sv.filtrar_sugestoes("windows", ["INDOL", "ÍNDIO"]) == [] and not sv.sugestao_valida("123", "ABC"), "sem sugestão que passe = lista vazia (a tela não mostra a linha)")
cat = f.ler_catalogo_pdm(); palavras = ["windows", "office", "xdr", "edr", "firewall", "notebook", "nobreak", "monitor", "mouze", "notbook", "lapto"]
antes = json.loads((DADOS / "pedido18" / "fase0.json").read_text(encoding="utf-8"))["antes"]
tab = {}
for p in palavras:
    r = f.procurar_tolerante(p, cat); dep = sv.filtrar_sugestoes(p, r["sugestoes"])
    tab[p] = {"antes": antes[p]["sugestoes"], "depois": dep, "corrigido_para": r["corrigido_para"], "correcao_passa_na_regra": (sv.sugestao_valida(p, r["corrigido_para"]) if r["corrigido_para"] else None)}
    checa(antes[p]["sugestoes"] == r["sugestoes"], f"'{p}': a função atual ainda devolve o mesmo que no registro da Fase 0 ({len(r['sugestoes'])} sugestões)")
(DADOS / "pedido18" / "tabela_fase2_depois.json").write_text(json.dumps(tab, ensure_ascii=False, indent=1), encoding="utf-8")
for p in ("windows", "office", "xdr", "edr"): checa(tab[p]["depois"] == [] and len(tab[p]["antes"]) > 0, f"'{p}': antes {tab[p]['antes']} -> depois {tab[p]['depois']} (sem sugestão)")
for p in ("firewall", "notebook", "nobreak"): checa(tab[p]["depois"] == [] and tab[p]["antes"] == [], f"'{p}': já não tinha sugestão (achou o nome exato) e continua sem")
checa(tab["monitor"]["depois"] == tab["monitor"]["antes"] and len(tab["monitor"]["depois"]) == 5, f"'monitor': as {len(tab['monitor']['depois'])} sugestões têm a palavra 'monitor' e continuam: {tab['monitor']['depois']}")
checa(tab["mouze"]["depois"] == ["MOUSE COMPUTADOR"] and tab["mouze"]["corrigido_para"] == "mouse" and tab["mouze"]["correcao_passa_na_regra"], f"'mouze': 'mouse' existe no catálogo -> {tab['mouze']['depois']}, corrigido para {tab['mouze']['corrigido_para']}")
checa(tab["notbook"]["corrigido_para"] == "notebook" and tab["notbook"]["correcao_passa_na_regra"] and tab["lapto"]["corrigido_para"] == "laptop" and tab["lapto"]["correcao_passa_na_regra"], "notbook -> notebook e lapto -> laptop: a correção (feita pela função de correção da digitação, que não mudou) passa na regra de letra e distância")

print("\n=== Fase 3: aviso de custo do Produto ===")
t1 = sv.aviso_custo_produto(1, MODOS); t2 = sv.aviso_custo_produto(2, MODOS)
checa(sv.aviso_custo_produto(0, MODOS) == "", "0 códigos marcados: nada")
checa(t1 == "1 código(s) · rápido: até 3 páginas e 10 compras ligadas ao PNCP; completo: até 20 páginas e 40 compras. Medido em 1 código (21/11): rápido 33 chamadas e 104 s; completo 131 chamadas e 6 min 53 s. Pausa de 3 s entre chamadas.", f"1 código: {t1}")
checa(t2.startswith("2 código(s) · rápido: até 3 páginas e 10 compras") and "até" in t2 and t2.endswith("Pausa de 3 s entre chamadas."), f"2 códigos: {t2[:70]}…")
checa("até 3 páginas e 10 compras" in t1 and "até 20 páginas e 40 compras" in t1 and t1.count("até ") == 2, "escreve 'até' antes do limite de cada modo (2 vezes: rápido e completo)")

print("\n=== Fase 4: aviso de item único ===")
mesmo = [{"codigo_catalogo": "123456", "descricao_item": f"X {i}"} for i in range(458)]
a = sv.aviso_item_unico(mesmo, {"123456": "MOUSE COMPUTADOR"})
checa(a == "As 458 linhas lidas são do mesmo item de catálogo (código 123456: MOUSE COMPUTADOR). O produto de cada compra está no texto da descrição: use 'Mostrar só linhas que citam a palavra'.", f"458 linhas do mesmo código: {a}")
checa(sv.aviso_item_unico(mesmo[:20], {"123456": "N"}) is not None and sv.aviso_item_unico(mesmo[:19], {"123456": "N"}) is None, "limite: 20 linhas = aviso; 19 = nada")
dois = [{"codigo_catalogo": "1" if i % 2 else "2"} for i in range(458)]
checa(sv.aviso_item_unico(dois) is None, "2 códigos de catálogo (458 linhas): nada")
checa(sv.aviso_item_unico([{"codigo_catalogo": "77.0"} for _ in range(25)], {"77": "ABC"}).startswith("As 25 linhas lidas são do mesmo item de catálogo (código 77: ABC)"), "código vindo como '77.0' vira 77")
checa(sv.aviso_item_unico([{"codigo_catalogo": ""} for _ in range(25)]) is None and sv.aviso_item_unico([]) is None, "sem código ou sem linhas: nada")
print("\n=== Pedido 20, Fase 3: nome cortado em fronteira de palavra (limite 80) ===")
L25 = lambda: [{"codigo_catalogo": "9"} for _ in range(25)]
def nome_do_aviso(texto): return texto.split("(código 9: ", 1)[1].split("). O produto de cada compra", 1)[0]
RESTO = ". O produto de cada compra está no texto da descrição: use 'Mostrar só linhas que citam a palavra'."
curto = "MOUSE COMPUTADOR"
a1 = sv.aviso_item_unico(L25(), {"9": curto})
checa(nome_do_aviso(a1) == curto and "…" not in a1, f"nome curto ({len(curto)} caracteres): sem corte e sem '…'")
longo = "SOFTWARE LICENCA SISTEMA OPERACIONAL WINDOWS SERVER CLIENT SERVER SUITE PROFESSIONAL EDITION ADICIONAL"
a2 = sv.aviso_item_unico(L25(), {"9": longo}); n2 = nome_do_aviso(a2); base2 = n2[:-1]
checa(len(longo) > 80 and n2.endswith("…") and len(base2) <= 80 and longo.startswith(base2) and longo[len(base2)] == " " and a2.endswith(RESTO), f"nome longo ({len(longo)} caracteres): corta em palavra inteira -> '{n2}' ({len(base2)} caracteres + …), resto do aviso igual")
exato = "X" * 39 + " " + "Y" * 40
a3 = sv.aviso_item_unico(L25(), {"9": exato})
checa(len(exato) == 80 and nome_do_aviso(a3) == exato and "…" not in a3, f"nome com exatamente o limite ({len(exato)} caracteres): sem corte e sem '…'")
um_a_mais = "X" * 39 + " " + "Y" * 41
n4 = nome_do_aviso(sv.aviso_item_unico(L25(), {"9": um_a_mais}))
checa(len(um_a_mais) == 81 and n4 == "X" * 39 + "…", f"nome com 81 caracteres (1 acima do limite, corte cairia no meio da palavra): volta ao último espaço -> '{n4}'")
n5 = nome_do_aviso(sv.aviso_item_unico(L25(), {"9": "Z" * 100}))
checa(n5 == "Z" * 80 + "…", f"palavra única de 100 caracteres (sem espaço para voltar): corta no limite de 80 e põe '…' ({len(n5)} caracteres)")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

"""v4h, Pedido 25 (Fase 5), SEM rede, SEM IA. Alertas de 'revisar' na Etapa 5 (só regras): valor 'não encontrado' com trecho; ano com mais de um número de 4 dígitos; garantia com número
e trecho em dias (sem meses); linha com mais de 4 colunas (aponta o campo). A contagem de citações literais NÃO muda. Os casos são SIMULADOS (regra 10: só dentro de testes).
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido25_alertas.py   (na pasta do app)"""
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
import conferir_ficha_v2 as cf
import conferir_tela as ct
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
PAGS = ["Termo de Referência 2025. Garantia de 180 dias contra defeitos de fabricação. Prazo de entrega: 30 dias.", "Marca XPTO modelo Z. Tela de 15,6 polegadas. Assinado em 10/03/2025."]
CAB = "| Campo | Valor | Página | Trecho literal |\n|---|---|---|---|\n"
BASE = {"tipo de documento": ("TR", "1", "Termo de Referência"), "ano do documento": ("2025", "2", "Assinado em 10/03/2025"), "lei de base": ("não encontrado", "", ""),
        "atributo do item": ("15,6 polegadas", "2", "Tela de 15,6 polegadas"), "compatível": ("mesmo", "", ""), "garantia": ("6 (180 dias)", "1", "Garantia de 180 dias contra defeitos"),
        "prazo de entrega": ("30", "1", "Prazo de entrega: 30 dias"), "marca ou modelo": ("XPTO", "2", "Marca XPTO modelo Z"), "utilidade": ("alta", "", "serve de modelo porque traz a garantia")}
NOMES = {"tipo de documento": "tipo de documento (TR / edital)", "ano do documento": "ano do documento", "lei de base": "lei de base (14.133 / 8.666 / não encontrado)",
         "atributo do item": "atributo do item, copiado como está", "compatível": "compatível com o item pedido? (mesmo / próximo)", "garantia": "garantia do produto (meses)",
         "prazo de entrega": "prazo de entrega (dias)", "marca ou modelo": "marca ou modelo indicado", "utilidade": "utilidade como modelo de TR"}
def ficha(**troca):
    d = {k: list(v) for k, v in BASE.items()}
    for k, v in troca.items(): d[k.replace("_", " ").replace("compativel", "compatível")] = list(v) if isinstance(v, tuple) else v
    linhas = []
    for k, v in d.items():
        if isinstance(v, str): linhas.append(v); continue          # linha crua (para o caso das colunas a mais)
        linhas.append(f"| {NOMES[k]} | {v[0]} | {v[1]} | {v[2]} |")
    return CAB + "\n".join(linhas) + "\n"
def alertas(texto): return cf.alertas_revisar(texto)
def tipos(al): return sorted(a["alerta"] for a in al)

print("=== caso sem alerta ===")
al = alertas(ficha())
checa(len(al) == 0, f"ficha correta: {len(al)} alertas")

print("\n=== alerta 1: valor 'não encontrado' com trecho preenchido ===")
al = alertas(ficha(lei_de_base=("não encontrado", "1", "Termo de Referência 2025")))
checa(len(al) == 1 and al[0]["campo"] == "lei de base" and al[0]["alerta"] == "valor não encontrado com trecho", f"1 caso: {len(al)} alerta(s): {tipos(al)}")
al = alertas(ficha(lei_de_base=("Não encontrado", "", "")))
checa(len(al) == 0, f"'Não encontrado' com trecho vazio: {len(al)} alertas")

print("\n=== alerta 2: ano com mais de um número de 4 dígitos ===")
al = alertas(ficha(ano_do_documento=("2025 (atualizado em 2026)", "2", "Assinado em 10/03/2025")))
checa(len(al) == 1 and al[0]["campo"] == "ano do documento" and al[0]["alerta"] == "ano com mais de um número", f"'2025 (atualizado em 2026)': {len(al)} alerta(s)")
al = alertas(ficha(ano_do_documento=("2025", "2", "Assinado em 10/03/2025")))
checa(len(al) == 0, f"um único ano: {len(al)} alertas")
al = alertas(ficha(ano_do_documento=("2025 e 2025", "2", "Assinado em 10/03/2025")))
checa(len(al) == 0, f"o mesmo ano repetido ('2025 e 2025'): {len(al)} alertas (mesmo número, nada a revisar)")

print("\n=== alerta 3: garantia com número e trecho em 'dias', sem 'meses' ===")
al = alertas(ficha(garantia=("180", "1", "Garantia de 180 dias contra defeitos")))
checa(len(al) == 1 and al[0]["campo"] == "garantia" and al[0]["alerta"] == "garantia: trecho em dias", f"'180' com trecho em dias: {len(al)} alerta(s)")
al = alertas(ficha(garantia=("180 dias", "1", "Garantia de 180 dias contra defeitos")))
checa(len(al) == 1 and al[0]["alerta"] == "garantia: trecho em dias", f"'180 dias' com trecho em dias: {len(al)} alerta(s) (o valor precisa estar em meses)")
al = alertas(ficha(garantia=("6 (180 dias)", "1", "Garantia de 180 dias contra defeitos")))
checa(len(al) == 0, f"'6 (180 dias)' com trecho em dias (formato convertido): {len(al)} alertas")
al = alertas(ficha(garantia=("6", "1", "Garantia de 6 meses (180 dias)")))
checa(len(al) == 0, f"trecho com 'meses' e 'dias': {len(al)} alertas")
al = alertas(ficha(garantia=("não encontrado", "", "")))
checa(len(al) == 0, f"garantia não encontrada (sem número): {len(al)} alertas")
al = alertas(ficha(garantia=("12", "1", "Garantia de 12 meses")))
checa(len(al) == 0, f"garantia em meses: {len(al)} alertas")

print("\n=== alerta 4: linha com mais de 4 colunas ===")
linha_ruim = "| atributo do item, copiado como está | tela | tipo de licença | 2 | Tela de 15,6 polegadas |"
al = alertas(ficha(atributo_do_item=linha_ruim))
checa(len(al) == 1 and al[0]["campo"] == "atributo do item" and al[0]["alerta"] == "linha com mais de 4 colunas" and "5 colunas" in al[0]["detalhe"], f"célula com '|' a mais (5 colunas): {len(al)} alerta(s), campo: {al[0]['campo'] if al else None}")
checa(len(alertas(ficha())) == 0, "tabela de 4 colunas: 0 alertas de colunas")

print("\n=== vários alertas juntos, na mesma ficha ===")
al = alertas(ficha(lei_de_base=("não encontrado", "1", "Termo"), ano_do_documento=("2025/2026", "2", "x"), garantia=("180", "1", "180 dias"), atributo_do_item=linha_ruim))
checa(len(al) == 4 and tipos(al) == sorted(["valor não encontrado com trecho", "ano com mais de um número", "garantia: trecho em dias", "linha com mais de 4 colunas"]), f"4 problemas, 4 alertas: {tipos(al)}")
checa(alertas("não é uma ficha") == [] and alertas("") == [] and alertas(None) == [], "texto que não é ficha: 0 alertas")

print("\n=== a contagem de citações literais não muda ===")
for rotulo, txt in (("ficha correta", ficha()), ("ficha com os 4 problemas", ficha(lei_de_base=("não encontrado", "1", "Termo"), ano_do_documento=("2025/2026", "2", "Assinado em 10/03/2025"), garantia=("180", "1", "Garantia de 180 dias contra defeitos"), atributo_do_item=linha_ruim))):
    rows = cf.conferir(txt, PAGS, "notebook", "")
    r_antes = cf.resumo(rows)
    res = ct.conferir_resposta(txt, PAGS, "", "notebook", "", "32768")
    checa(res["resumo"] == r_antes and ct.frase_resumo(res).startswith(f"{r_antes['literais']} de {r_antes['citacoes']} citações literais"), f"{rotulo}: {r_antes['literais']} de {r_antes['citacoes']} literais, igual com e sem os alertas; frase de resumo intacta")
res = ct.conferir_resposta(ficha(garantia=("180", "1", "Garantia de 180 dias contra defeitos")), PAGS, "", "notebook", "", "32768")
checa(len(res["alertas"]) == 1 and ct.frase_alerta(res["alertas"][0]).startswith("Revisar · garantia:") and "erro" not in ct.frase_alerta(res["alertas"][0]).lower(), f"conferir_resposta devolve 'alertas' (1) e a frase diz 'Revisar', não 'erro': {ct.frase_alerta(res['alertas'][0])[:90]}")
res = ct.conferir_resposta("lixo", PAGS, "", "notebook", "", "32768")
checa(res["alertas"] == [] and not res["ficha_encontrada"], "resposta sem ficha: alertas = []")

print("\n=== Pedido 27: alerta 'atributo igual ao item pedido' ===")
ITEM = "licença VMS|software de monitoramento"
AL = "atributo igual ao item pedido"
def so_item(al): return [a for a in al if a["alerta"] == AL]
al = alertas_i = cf.alertas_revisar(ficha(atributo_do_item=("notebook", "2", "Tela de 15,6 polegadas")), "notebook")
checa(len(so_item(al)) == 1 and so_item(al)[0]["campo"] == "atributo do item" and so_item(al)[0]["detalhe"] == "o atributo deve ser uma característica do item, não o próprio item pedido; confira", f"(a) item completo igual ('notebook'): {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("  NOTEBOOK ", "2", "Tela de 15,6 polegadas")), "Notebook")
checa(len(so_item(al)) == 1, f"(a2) igual sem diferenciar maiúsculas e espaços sobrando: {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("licença VMS", "2", "Tela de 15,6 polegadas")), ITEM)
checa(len(so_item(al)) == 1 and len(al) == 1, f"(b) um termo do item ('licença VMS'): {len(so_item(al))} alerta, {len(al)} no total")
al = cf.alertas_revisar(ficha(atributo_do_item=("Software de Monitoramento", "2", "x")), ITEM)
checa(len(so_item(al)) == 1, f"(b2) o outro termo (maiúsculas diferentes): {len(so_item(al))} alerta")
linha_real = "| atributo do item, copiado como está | licença VMS|software de monitoramento | 2 | trecho |"
al = cf.alertas_revisar(ficha(atributo_do_item=linha_real), ITEM)
checa(len(so_item(al)) == 1 and sorted(a["alerta"] for a in al) == sorted([AL, "linha com mais de 4 colunas"]), f"(b3) caso real: o modelo escreveu o item inteiro com '|' (a célula quebra): alertas {sorted(a['alerta'] for a in al)}")
al = cf.alertas_revisar(ficha(atributo_do_item=("Solução de sistema de vídeo segurança multiusuário e multi-site", "2", "x")), ITEM)
checa(len(so_item(al)) == 0, f"(c) atributo real ('Solução de sistema de vídeo segurança multiusuário e multi-site'): {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("não encontrado", "", "")), ITEM)
checa(len(so_item(al)) == 0, f"(d) 'não encontrado': {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("notebook", "2", "x")), "")
al2 = cf.alertas_revisar(ficha(atributo_do_item=("notebook", "2", "x")), None)
al3 = cf.alertas_revisar(ficha(atributo_do_item=("notebook", "2", "x")), "  |  ")
checa(len(so_item(al)) == len(so_item(al2)) == len(so_item(al3)) == 0, f"(e) item vazio, None ou só separadores: {len(so_item(al))}, {len(so_item(al2))}, {len(so_item(al3))} alertas e nenhum erro")
al = cf.alertas_revisar(ficha(atributo_do_item=("notebook", "2", "x")))
checa(len(so_item(al)) == 0 and len(al) == 0, f"(f) chamada antiga, sem item: {len(al)} alertas, sem erro")
checa(cf.alertas_revisar(ficha()) == [] and cf.alertas_revisar(ficha(), "notebook") == [], "(f2) ficha correta: 0 alertas com e sem item")
res = ct.conferir_resposta(ficha(atributo_do_item=("licença VMS", "2", "Tela de 15,6 polegadas")), PAGS, "", ITEM, "", "32768")
checa(len(so_item(res["alertas"])) == 1 and ct.frase_alerta(so_item(res["alertas"])[0]).startswith("Revisar · atributo do item: "), f"conferir_resposta passa o item: {ct.frase_alerta(so_item(res['alertas'])[0]) if so_item(res['alertas']) else None}")
res = ct.conferir_resposta(ficha(atributo_do_item=("licença VMS", "2", "Tela de 15,6 polegadas")), PAGS, "", "", "", "32768")
checa(len(so_item(res["alertas"])) == 0, "conferir_resposta sem item: sem o alerta novo")
r_antes = cf.resumo(cf.conferir(ficha(atributo_do_item=("licença VMS", "2", "Tela de 15,6 polegadas")), PAGS, ITEM, ""))
res = ct.conferir_resposta(ficha(atributo_do_item=("licença VMS", "2", "Tela de 15,6 polegadas")), PAGS, "", ITEM, "", "32768")
checa(res["resumo"] == r_antes, f"a contagem de citações literais não muda ({r_antes['literais']} de {r_antes['citacoes']})")

print("\n=== Pedido 28 (Fase 2b): ' / ' e '|' são o mesmo separador de termos, nos dois lados ===")
al = cf.alertas_revisar(ficha(atributo_do_item=("licença VMS / software de monitoramento", "1", "item pedido: licença VMS / software de monitoramento")), ITEM)
checa(len(so_item(al)) == 1 and so_item(al)[0]["campo"] == "atributo do item", f"(a) atributo 'licença VMS / software de monitoramento' com item 'licença VMS|software de monitoramento': {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("licença VMS / software de monitoramento", "1", "x")), "licença VMS / software de monitoramento")
checa(len(so_item(al)) == 1, f"(a2) item e atributo os dois com ' / ': {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("Licença VMS|Software de Monitoramento", "1", "x")), "licença VMS / software de monitoramento")
al = cf.alertas_revisar(ficha(atributo_do_item=("licença VMS", "1", "x")), ITEM)
checa(len(so_item(al)) == 1, f"(b) atributo 'licença VMS' (um termo): {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("software de monitoramento", "1", "x")), "licença VMS / software de monitoramento")
checa(len(so_item(al)) == 1, f"(b2) outro termo, item com ' / ': {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("Solução de sistema de vídeo segurança multiusuário e multi-site", "1", "x")), ITEM)
checa(len(so_item(al)) == 0, f"(c) atributo real ('Solução de sistema de vídeo segurança multiusuário e multi-site'): {len(so_item(al))} alerta")
al = cf.alertas_revisar(ficha(atributo_do_item=("potência em kVA/VA", "1", "x")), "potência em kVA / VA")
checa(cf._termos_sem_separador("potência em kVA/VA") == ["potencia em kva/va"] and cf._termos_sem_separador("a|b / c") == ["a", "b", "c"] and cf._termos_sem_separador("") == [] and cf._termos_sem_separador(None) == [], "(c3) separador: '|' e ' / ' separam; 'kVA/VA' não; vazio e None dão []")
al = cf.alertas_revisar(ficha(atributo_do_item=linha_real), ITEM)
checa(len(so_item(al)) == 1 and sorted(a["alerta"] for a in al) == sorted([AL, "linha com mais de 4 colunas"]), f"(d) caso antigo ('|' dentro da célula): alertas {sorted(a['alerta'] for a in al)}")
al = cf.alertas_revisar(ficha(atributo_do_item=("notebook", "2", "x")), "notebook")
checa(len(so_item(al)) == 1, "(d2) item sem separador, igual: 1 alerta (como antes)")
al = cf.alertas_revisar(ficha(atributo_do_item=("notebook", "2", "x")), "")
checa(len(so_item(al)) == 0 and len(cf.alertas_revisar(ficha())) == 0, "(d3) item vazio e chamada sem item: 0 alertas")
B = DADOS / "pedido28" / "saidas"
if (B / "B1.txt").exists():
    import conferir_tela as _ct
    _p, _, _ = _ct.ler_recorte(DADOS / "saida" / "sessoes" / "28783508d6294ea4825afd667f6ebb2a" / "recortes" / "6_4_TR") if (DADOS / "saida" / "sessoes" / "28783508d6294ea4825afd667f6ebb2a" / "recortes" / "6_4_TR").exists() else (None, None, None)
    for _n in ("B1", "B2", "B6"):
        _r = _ct.conferir_resposta((B / f"{_n}.txt").read_text(encoding="utf-8"), _p, (RAIZ / "config" / "INSTRUCAO_FICHA.txt").read_text(encoding="utf-8"), ITEM, "5281", "32768")
        _al = sorted(a["alerta"] + " (" + a["campo"] + ")" for a in _r["alertas"])
        checa(_al == sorted([AL + " (atributo do item)", "valor não encontrado com trecho (prazo de entrega)"]), f"saída real {_n}: alertas {_al}")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

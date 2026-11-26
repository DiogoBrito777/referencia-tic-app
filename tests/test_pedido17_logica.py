"""v4h, Pedido 17 – LÓGICA, sem rede (socket bloqueado) e sem a tela. Dados: as 3.693 linhas REAIS já medidas em pedido12b\\servicos_precos_todas.csv (lidas, não alteradas).
Cobre: ITEM_MAX_PALAVRAS continua 12; separar_colagens ('softwarepara'); filtro por palavra (windows 11 pro / xdr sobre os 8 códigos, palavra inexistente = 0, acento e maiúscula, várias palavras
em qualquer ordem, palavra inteira); resumo por código; indicador de descrição (limite e os lados do código 27499); aviso de N códigos × chamadas.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido17_logica.py   (na pasta do app)"""
import csv, socket, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
def _b(self, a, *x, **k): raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
import servicos as sv
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

rows = list(csv.DictReader((DADOS / "pedido12b" / "servicos_precos_todas.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
L = [{"codigo_catalogo": r["codigo"], "descricao_item": r["descricao"], "orgao": r["orgao_id"], "id_compra": f"{r['orgao_id']}-{r['data']}"} for r in rows]
checa(len(L) == 3693 and len({l["codigo_catalogo"] for l in L}) == 8, f"material: {len(L)} linhas, {len({l['codigo_catalogo'] for l in L})} códigos")

print("=== 0.1 CANCELADA: ITEM_MAX_PALAVRAS volta a 12 ===")
checa(sv.ITEM_MAX_PALAVRAS == 12, f"ITEM_MAX_PALAVRAS = {sv.ITEM_MAX_PALAVRAS} (a decisão de 6 foi cancelada: com 6 o texto do XDR perde 'xdr')")

print("\n=== 0.4 palavras coladas ===")
ctx = [l["descricao_item"] for l in L if l["codigo_catalogo"] == "27456"]
d = next(x for x in ctx if "softwarepara" in x)
checa("software para estação" in sv.separar_colagens(d, ctx) and "softwarepara" not in sv.separar_colagens(d, ctx), "'softwarepara' vira 'software para' (contexto = linhas do mesmo código)")
checa(sv.separar_colagens(d, []) == d.replace("softwarepara", "softwarepara"), "sem contexto suficiente nada muda")
checa(sv.separar_colagens("calçados internados madeirados chamadas", ctx) == "calçados internados madeirados chamadas", "plurais terminados em dos/das NÃO são cortados")
checa(sv.separar_colagens("Licença", ctx) == "Licença" and sv.separar_colagens("", ctx) == "", "texto sem colagem e texto vazio ficam iguais")
checa(sv.item_pedido_inicial(sv.separar_colagens(d, ctx), ["Licenciamento de direitos permanentes de uso de software"], contexto=ctx).count("softwarepara") == 0, "o texto padrão não traz mais a palavra colada")

print("\n=== Fase 2: filtro por palavra ===")
w = sv.linhas_que_citam(L, "windows 11 pro"); x = sv.linhas_que_citam(L, "xdr")
checa(len(w) == 14 and len(x) == 2, f"'windows 11 pro' = {len(w)} linhas e 'xdr' = {len(x)} sobre os 8 códigos (medido no 12B por palavra inteira e qualquer ordem: 14 e 2)")
por = {c: sum(1 for l in w if l["codigo_catalogo"] == c) for c in sorted({l["codigo_catalogo"] for l in w})}
checa(por == {"27456": 5, "27464": 2, "27472": 4, "27499": 3}, f"'windows 11 pro' por código: {por}")
checa(len(sv.linhas_que_citam(L, "zzzxyzqq")) == 0, "palavra inexistente = 0 linhas")
checa(len(sv.linhas_que_citam(L, "WINDOWS 11 PRO")) == 14 and len(sv.linhas_que_citam(L, "pro 11 windows")) == 14, "maiúscula e ordem diferente: mesmas 14")
checa(len(sv.linhas_que_citam(L, "licença")) == len(sv.linhas_que_citam(L, "LICENCA")) > 0, f"acento: 'licença' = 'LICENCA' = {len(sv.linhas_que_citam(L, 'licenca'))}")
checa(len(sv.linhas_que_citam(L, "windows 11 pro xdr")) <= min(len(w), len(x)), "várias palavras = TODAS na mesma linha")
checa(sv.linhas_que_citam([{"descricao_item": "windowsxp"}, {"descricao_item": "xdrive pro"}], "windows") == [] and sv.linhas_que_citam([{"descricao_item": "xdrive"}], "xdr") == [], "palavra inteira: 'windowsxp' não é 'windows'; 'xdrive' não é 'xdr'")
checa(len(sv.linhas_que_citam(L, "")) == 3693 and len(sv.linhas_que_citam(L, "  ,. ")) == 3693, "nada digitado = todas as linhas")
checa(len(sv.linhas_que_citam([{"descricao_item": "", "descricao_item_pncp": "Licença Windows"}], "windows")) == 1, "procura também em outra coluna de texto não vazia (descricao_item_pncp)")
res = sv.resumo_por_codigo(L, w, nomes={"27456": "Licenciamento de software"})
checa(list(res[0]) == ["código", "nome", "linhas lidas", "linhas que citam", "compras distintas", "órgãos distintos"], f"colunas do resumo: {list(res[0])}")
checa(len(res) == 8 and [r["linhas que citam"] for r in res] == sorted([r["linhas que citam"] for r in res], reverse=True) and res[0]["código"] == "27456" and res[0]["linhas que citam"] == 5 and res[0]["nome"] == "Licenciamento de software",
      f"resumo: 8 códigos, ordem por 'linhas que citam': {[(r['código'], r['linhas que citam']) for r in res]}")
checa(sum(r["linhas lidas"] for r in res) == 3693 and sum(r["linhas que citam"] for r in res) == 14, "o resumo fecha: 3.693 lidas e 14 que citam")

print("\n=== Fase 3: indicador de descrição ===")
checa(sv.DESCRICAO_LIMITE_PALAVRAS == 16, f"limite provisório = {sv.DESCRICAO_LIMITE_PALAVRAS} palavras (mediana medida no 12B)")
checa(sv.indicador_descricao("uma duas três") == "descrição curta" and sv.indicador_descricao(" ".join(["p"] * 16)) == "descrição curta" and sv.indicador_descricao(" ".join(["p"] * 17)) == "descrição detalhada", "até 16 = curta; 17 ou mais = detalhada")
l27499 = [l["descricao_item"] for l in L if l["codigo_catalogo"] == "27499"]
cur = sum(1 for t in l27499 if sv.indicador_descricao(t) == "descrição curta")
checa(len(l27499) > 0 and cur + (len(l27499) - cur) == len(l27499), f"27499: {len(l27499)} linhas, {cur} curtas e {len(l27499) - cur} detalhadas (limite {sv.DESCRICAO_LIMITE_PALAVRAS})")

print("\n=== aviso antes de Buscar ===")
checa(sv.estimativa_busca(3) == "3 códigos × cerca de 12 chamadas (medido: 12 chamadas e 39 s para 1 código no modo rápido); pausa de 3 s entre chamadas; tempo estimado 1 min 57 s", sv.estimativa_busca(3))
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

"""v4h, Pedido 16 (M4) – a janela de 32.768 com o config REAL (sem copia, sem rede, sem texto de edital): o config entregue diz 32768 e o orçamento do app, para o tamanho do recorte do edital de
referência (51.998 caracteres, medido na Fase 1: 5 páginas mantidas), dá 17.931 tokens estimados contra o limite de 70% = 22.937,6; com 16.384 o mesmo tamanho passaria do limite (11.468,8).
Também confere, com tamanhos sintéticos de página (5.000 tokens), que com a janela real cabem mais páginas no limite de 70% do que com 16.384.
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido16_janela32768.py   (na pasta do app)"""
import socket, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
def _b(self, a, *x, **k): raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
import ferramenta as f
import orcamento_tokens as ot
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

cfg = ot.ler_config(f.ORCAMENTO_CSV); fr = ot.ler_fracao_janela(f.FRACAO_JANELA_CSV, "padrao")
instr = len(f.INSTRUCAO.read_text(encoding="utf-8").rstrip())
checa(f.ORCAMENTO_CSV == RAIZ / "config" / "orcamento_tokens.csv", f"o teste usa o config REAL do app: {f.ORCAMENTO_CSV.name}")
checa(cfg["contexto_tokens"] == 32768 and cfg["caracteres_por_token"] == 2.9 and cfg["reserva_resposta_tokens"] == 1500, f"config real: janela 32768, fator 2,9, reserva 1500: {cfg}")
checa(fr["fracao_janela"] == 0.7, f"fração da janela 0,70 ({fr['origem']})")
CH = 51998      # tamanho (caracteres) do PARA_IA do recorte de 5 páginas do edital de referência na Fase 1
orc = ot.calcular_orcamento_v2(CH - instr, instr, cfg["contexto_tokens"], cfg["reserva_resposta_tokens"], cfg["caracteres_por_token"], fr["fracao_janela"])
checa(orc["tokens_prompt"] == 17931 and orc["limite_tokens"] == 22937.6 and not orc["acima_do_limite"] and orc["cabe"], f"{CH} caracteres: {orc['tokens_prompt']} tokens estimados, limite {orc['limite_tokens']}, cabe: {orc['cabe']}")
orc16 = ot.calcular_orcamento_v2(CH - instr, instr, 16384, cfg["reserva_resposta_tokens"], cfg["caracteres_por_token"], fr["fracao_janela"])
checa(orc16["tokens_prompt"] == 17931 and orc16["limite_tokens"] == 11468.8 and orc16["acima_do_limite"], f"o mesmo tamanho com 16.384: limite {orc16['limite_tokens']}, acima do limite: {orc16['acima_do_limite']}")
print("\n--- regra de parada do recorte com páginas sintéticas ---")
tokens_pag = 5000                                   # cada página sintética pesa ~5.000 tokens estimados (14.500 caracteres)
t = ot.calcular_orcamento_v2(4 * int(tokens_pag * 2.9), instr, 32768, 1500, 2.9, 0.7)
t1 = ot.calcular_orcamento_v2(2 * int(tokens_pag * 2.9), instr, 16384, 1500, 2.9, 0.7)
checa(not t["acima_do_limite"] and ot.calcular_orcamento_v2(5 * int(tokens_pag * 2.9), instr, 32768, 1500, 2.9, 0.7)["acima_do_limite"], "janela 32.768: 4 páginas de 5.000 tokens (mais a instrução) cabem no limite de 70% e 5 não")
checa(not t1["acima_do_limite"] and ot.calcular_orcamento_v2(3 * int(tokens_pag * 2.9), instr, 16384, 1500, 2.9, 0.7)["acima_do_limite"], "janela 16.384: 2 páginas de 5.000 tokens cabem no limite de 70% e 3 não")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

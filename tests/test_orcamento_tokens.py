"""Fase 1 – testes OFFLINE do orçamento de tokens (socket bloqueado; dados simulados só aqui).
Uso (na pasta do app): python -I -B tests\\test_orcamento_tokens.py"""
import io, re, socket, sys, contextlib
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ))

def _sem_rede(*a, **k): raise AssertionError("TENTOU ABRIR REDE")
socket.socket.connect = _sem_rede

import orcamento_tokens as ot
import ferramenta as f

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

print("=== A. função pura ===")
checa(ot.estimar_tokens(3548, 3.0) == 1183 and ot.estimar_tokens(3549, 3.0) == 1183 and ot.estimar_tokens(3550, 3.0) == 1184, "estimar_tokens arredonda PARA CIMA: 3548 e 3549 car. -> 1183; 3550 -> 1184 (fator 3,0)")
checa(ot.estimar_tokens(3000, 3.0) != ot.estimar_tokens(3000, 4.0) and ot.estimar_tokens(3000, 4.0) == 750, "o fator é parâmetro: 3000 car. = 1000 tokens a 3,0 e 750 a 4,0")
for ruim in (0, -1, None):
    try:
        ot.estimar_tokens(100, ruim); ok = False
    except ValueError:
        ok = True
    checa(ok, f"fator inválido ({ruim!r}) levanta ValueError (nada de dividir por zero em silêncio)")
o = ot.calcular_orcamento(chars_texto=6000, chars_instrucao=2022, contexto_tokens=8192, reserva_tokens=1500, car_por_token=3.0)
checa(o["tokens_instrucao"] == 674 and o["tokens_texto"] == 2000 and o["disponivel"] == 8192 - 674 - 1500 == 6018, f"disponível = contexto − instrução − reserva = 8192 − 674 − 1500 = {o['disponivel']}")
checa(o["cabe"] and o["falta"] == 0, "texto de 2000 tokens cabe em 6018 disponíveis")
limite = ot.calcular_orcamento(6018 * 3, 2022, 8192, 1500, 3.0); acima = ot.calcular_orcamento(6018 * 3 + 1, 2022, 8192, 1500, 3.0)
checa(limite["tokens_texto"] == 6018 and limite["cabe"] and not acima["cabe"] and acima["tokens_texto"] == 6019 and acima["falta"] == 1, "limite exato: 6018 tokens cabe; 6019 não cabe (falta 1)")
nao = ot.calcular_orcamento(31797, 2022, 8192, 1500, 3.0)
checa(not nao["cabe"] and nao["falta"] == 10599 - 6018, f"TR de 33.819 car. (31.797 de texto + instrução): não cabe em 8192; faltam ≈ {nao['falta']} tokens")
sem_espaco = ot.calcular_orcamento(300, 30000, 8192, 1500, 3.0)
checa(sem_espaco["disponivel"] < 0 and not sem_espaco["cabe"] and "não sobra espaço" in ot.aviso_nao_cabe(sem_espaco), f"instrução maior que a janela: disponível negativo ({sem_espaco['disponivel']}) e o aviso diz 'não sobra espaço'")
msg = ot.texto_orcamento(o, "config")
checa(msg == "≈ 2.674 tokens de 8.192 (fator 3,0 car./token, config)", f"mensagem '≈ N tokens de M' com o fator: «{msg}»")
checa(ot.aviso_nao_cabe(o) == "" and "NÃO CABE" in ot.aviso_nao_cabe(nao) and "faltam ≈ 4.581" in ot.aviso_nao_cabe(nao), "aviso só aparece quando não cabe e traz quanto falta (4.581)")
checa("fator 2,5" in ot.texto_orcamento(ot.calcular_orcamento(6000, 2022, 8192, 1500, 2.5), "config"), "o aviso mostra o fator usado também quando editado (2,5)")

print("\n=== B. config editável (config\\orcamento_tokens.csv) ===")
tmp = DADOS / "tmp_teste_fase1"; tmp.mkdir(exist_ok=True)
cfg = ot.ler_config(RAIZ / "config" / "orcamento_tokens.csv")
_lin = (RAIZ / "config" / "orcamento_tokens.csv").read_text(encoding="utf-8-sig").splitlines()[1].split(";")      # Pedido 16 (M2): o teste espera o valor LIDO do arquivo real, não um número fixo
checa(cfg == {"modelo": _lin[0], "caracteres_por_token": float(_lin[1].replace(",", ".")), "contexto_tokens": int(_lin[2]), "reserva_resposta_tokens": int(_lin[3]), "origem": "config"} and cfg["contexto_tokens"] > 0, f"config entregue: ler_config devolve o que o arquivo real diz ({_lin[1]} / {_lin[2]} / {_lin[3]}): {cfg}")
(tmp / "editado.csv").write_text("modelo;caracteres_por_token;contexto_tokens;reserva_resposta_tokens\npadrao;2,5;16384;1000\nmodelo_x;3.5;4096;500\n", encoding="utf-8-sig")
e = ot.ler_config(tmp / "editado.csv"); x = ot.ler_config(tmp / "editado.csv", "modelo_x")
checa(e["caracteres_por_token"] == 2.5 and e["contexto_tokens"] == 16384 and e["reserva_resposta_tokens"] == 1000 and x["caracteres_por_token"] == 3.5 and x["modelo"] == "modelo_x", f"config editada (vírgula e ponto decimais; linha por modelo): padrao={e['caracteres_por_token']}, modelo_x={x['caracteres_por_token']}")
for nome, texto in (("ausente.csv", None), ("vazio.csv", ""), ("lixo.csv", "modelo;caracteres_por_token;contexto_tokens;reserva_resposta_tokens\npadrao;abc;8192;1500\n"), ("zero.csv", "modelo;caracteres_por_token;contexto_tokens;reserva_resposta_tokens\npadrao;0;8192;1500\n")):
    if texto is not None: (tmp / nome).write_text(texto, encoding="utf-8")
    r = ot.ler_config(tmp / nome)
    checa(r["caracteres_por_token"] == 3.0 and r["contexto_tokens"] == 8192 and r["origem"].startswith("padrão do código"), f"config {nome}: volta ao padrão e diz de onde veio: «{r['origem']}»")
checa(ot.ler_config(tmp / "editado.csv", "nao_existe")["origem"].startswith("padrão do código (modelo 'nao_existe'"), "modelo que não está no config: padrão e aviso")

print("\n=== C. estimado × real (prompt_eval_count medido), fator do config (2,9) e, como referência, 3,0 – sem tolerância fixa ===")
MEDIDO = {"qwen3:4b-instruct": [(3548, 1220), (6745, 2199), (33819, 10388)], "nemotron (Q4_K_M)": [(3548, 1164), (6745, 2016), (33819, 9471)]}
FATOR_CFG = cfg["caracteres_por_token"]
checa(FATOR_CFG == 2.9, f"fator lido do config entregue = {FATOR_CFG}")
print(f"{'modelo':20} {'caracteres':>10} {'est.2,9':>8} {'erro 2,9':>9} {'est.3,0':>8} {'erro 3,0':>9} {'real':>7} {'car/token real':>15}  leitura (fator do config)")
for modelo, pares in MEDIDO.items():
    for chars, real in pares:
        est = ot.estimar_tokens(chars, FATOR_CFG); erro = (est - real) / real * 100
        est3 = ot.estimar_tokens(chars, 3.0); erro3 = (est3 - real) / real * 100
        leitura = "superestimou (lado seguro)" if est > real else ("subestimou (PERIGOSO)" if est < real else "igual")
        print(f"{modelo:20} {chars:>10,} {est:>8,} {erro:>+8.1f}% {est3:>8,} {erro3:>+8.1f}% {real:>7,} {chars / real:>15.2f}  {leitura}".replace(",", "."))
        checa(est > real, f"{modelo}, {chars} car.: fator {FATOR_CFG} superestima ({est} > {real}, {erro:+.1f}%)")
sub = [(m, c) for m, p in MEDIDO.items() for c, r in p if ot.estimar_tokens(c, FATOR_CFG) < r]
sub3 = [(m, c) for m, p in MEDIDO.items() for c, r in p if ot.estimar_tokens(c, 3.0) < r]
checa(not sub and len(sub3) == 1, f"RESUMO: com {FATOR_CFG}: {len(sub)} subestimativa(s) em 6; com 3,0 (referência): {len(sub3)} {sub3}")
print(f"Menor caracteres/token medido: {min(c / r for p in MEDIDO.values() for c, r in p):.2f} (qwen, texto curto). n = 6.")

print("\n=== D. opcao_5_texto_ia usa o orçamento (sem rede; SAIDA simulada em pasta de teste) ===")
saida = tmp / "saida_sim"; (saida / "recortes" / "TR_sim").mkdir(parents=True, exist_ok=True)
instr_chars = len(f.INSTRUCAO.read_text(encoding="utf-8").rstrip())
f.SAIDA = saida; f.escolher_numero = lambda msg, maximo: 1
def rodar(chars_recorte):
    (saida / "recortes" / "TR_sim" / "recorte.txt").write_text("x" * chars_recorte, encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): f.opcao_5_texto_ia()
    return buf.getvalue()
# Pedido 16 (M1): este teste guarda o comportamento de 16.384. Usa uma CÓPIA TEMPORÁRIA do config com contexto_tokens=16384; o config real (hoje 32.768) não é tocado.
import atexit as _at, os as _os, re as _re, shutil as _sh
_CFG16 = DADOS / "pedido16" / f"_tmp_cfg16384_{_os.getpid()}"; _CFG16.mkdir(parents=True, exist_ok=True); _at.register(_sh.rmtree, _CFG16, ignore_errors=True)
(_CFG16 / "orcamento_tokens.csv").write_text(_re.sub(r";\d+;1500;", ";16384;1500;", f.ORCAMENTO_CSV.read_text(encoding="utf-8-sig"), count=1), encoding="utf-8-sig"); f.ORCAMENTO_CSV = _CFG16 / "orcamento_tokens.csv"
s1 = rodar(6000)
checa("Pronto para colar:" in s1 and "≈ 2.767 tokens de 16.384 (fator 2,9 car./token, config)" in s1 and "NÃO CABE" not in s1, f"recorte pequeno: linha com '≈ N tokens de M' e fator, sem aviso: {s1.strip().splitlines()[-1][-95:]}")
checa(re.search(r"Pronto para colar: (.+?)\s+\(", s1) is not None and "~" not in s1.split("(")[-1].split(";")[0], "a linha continua no formato que o app lê (regex 'Pronto para colar: (.+?)\\s+\\(') e não tem mais '~ … tokens' do len//4")
s2 = rodar(60000)
checa("NÃO CABE" in s2 and "≈ 21.388 tokens de 16.384" in s2 and "faltam ≈ 6.504" in s2, f"recorte grande (60.000 car.): avisa que não cabe e quanto falta: {next((l for l in s2.splitlines() if 'AVISO' in l), '(sem AVISO)')[:120]}")
(tmp / "orc.csv").write_text("modelo;caracteres_por_token;contexto_tokens;reserva_resposta_tokens\npadrao;2,0;32768;1500\n", encoding="utf-8-sig"); f.ORCAMENTO_CSV = tmp / "orc.csv"
s3 = rodar(60000)
checa("fator 2,0 car./token" in s3 and "de 32.768" in s3 and "NÃO CABE" not in s3, "editando o config (2,0; janela 32.768) o fator e a janela mudam na mensagem e o mesmo texto (60.000 car.) passa a caber")

print("\n=== E. len//4 saiu do código ===")
for nome in ("ferramenta.py", "app.py"):
    t = (RAIZ / nome).read_text(encoding="utf-8")
    checa("// 4" not in t, f"{nome}: nenhum '// 4' restante")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

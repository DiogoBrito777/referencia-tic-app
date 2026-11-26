"""v4h, Pedido 25 (Fase 4), SEM rede, SEM IA. config\\INSTRUCAO_FICHA_v2.txt é um arquivo NOVO: o antigo (INSTRUCAO_FICHA.txt, hash 8dbb08b5) fica intacto e continua sendo o que ferramenta.py lê
quando o app não está em uso (testes e runners antigos). O app.py troca f.INSTRUCAO para o v2. Prova: arquivo antigo intacto; mesma tabela de 9 campos e mesmos cabeçalhos; só as regras e a
linha do atributo mudaram; as regras pedidas estão no texto; o app usa o v2 (PARA_IA e conferência); quanto o prompt cresce (caracteres e tokens pelo fator do app).
Uso: C:\\_Pro\\_MVC\\sondagem_v5\\.venv\\Scripts\\python.exe -I -B -X utf8 tests\\test_pedido25_ficha_v2.py   (na pasta do app)"""
import hashlib, math, re, socket, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(__import__("os").environ.get("REFERENCIA_TIC_DADOS") or (RAIZ.parent / "referencia_tic_dados_teste")).resolve()   # pasta dos dados de teste (cópia não pública)
sys.path.insert(0, str(RAIZ)); sys.dont_write_bytecode = True
_o = socket.socket.connect
def _b(self, a, *x, **k):
    h, p = (a[0], a[1]) if isinstance(a, tuple) else (str(a), None)
    if h in ("127.0.0.1", "::1") and p != 11434: return _o(self, a, *x, **k)
    raise AssertionError(f"TENTOU ABRIR REDE: {a!r}")
socket.socket.connect = _b
import ferramenta as f
import conferir_ficha_v2 as cf
import orcamento_tokens as ot
falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)
V1, V2 = RAIZ / "config" / "INSTRUCAO_FICHA.txt", RAIZ / "config" / "INSTRUCAO_FICHA_v2.txt"
t1, t2 = V1.read_text(encoding="utf-8"), V2.read_text(encoding="utf-8")
checa(f.INSTRUCAO == V1, f"antes de abrir o app: ferramenta.py lê o arquivo ANTIGO ({f.INSTRUCAO.name}), então testes e runners antigos não mudam")
print("\n=== arquivo antigo intacto ===")
h1 = hashlib.sha256(V1.read_bytes()).hexdigest()
checa(h1.startswith("8dbb08b5") and V1.stat().st_size == 2083, f"INSTRUCAO_FICHA.txt: hash {h1[:8]}… (esperado 8dbb08b5…), {V1.stat().st_size} bytes (esperado 2083)")

print("\n=== mesma tabela de 9 campos e mesmos cabeçalhos ===")
linhas = lambda t: [l for l in t.splitlines() if l.startswith("|")]
L1, L2 = linhas(t1), linhas(t2)
checa(len(L1) == len(L2) == 10, f"linhas de tabela: antigo {len(L1)}, v2 {len(L2)} (cabeçalho + 9 campos)")
checa(L1[0] == L2[0] == "| Campo | Valor | Página | Trecho literal |", f"cabeçalho idêntico: {L2[0]}")
checa(all(len([c for c in l.strip().strip('|').split('|')]) == 4 for l in L2), "toda linha da tabela do v2 tem exatamente 4 colunas (sem '|' dentro de célula)")
campos = lambda L: [next((k for k in cf.CAMPOS if k in cf.sem_acento(l.strip().strip("|").split("|")[0])), None) for l in L[1:]]
checa(campos(L1) == campos(L2) == cf.CAMPOS, f"os 9 campos, na mesma ordem: {campos(L2)}")
dif = [i for i, (a, b) in enumerate(zip(L1, L2)) if a != b]
checa(dif == [4], f"só 1 linha da tabela mudou: a do atributo (índice {dif})")
checa(all(l1 == l2 for l1, l2 in zip(L1[:4] + L1[5:], L2[:4] + L2[5:])), "as outras 8 linhas da tabela são idênticas ao antigo (inclui 'garantia do produto (meses)' e 'ano do documento')")
checa(t1.split("FICHA (responda só com esta tabela")[1].split("TEXTO DO DOCUMENTO:")[0].count("\n") == t2.split("FICHA (responda só com esta tabela")[1].split("TEXTO DO DOCUMENTO:")[0].count("\n"), "o bloco da ficha tem o mesmo número de linhas")
checa(t2.rstrip().endswith("TEXTO DO DOCUMENTO:") and t1.rstrip().endswith("TEXTO DO DOCUMENTO:"), "os dois terminam em 'TEXTO DO DOCUMENTO:' (o recorte entra depois)")

print("\n=== as regras pedidas estão no texto ===")
R = lambda s: s in t2
checa(R('Se o valor for "não encontrado", deixe o trecho vazio.'), "'não encontrado' vale para o valor E para o trecho (trecho vazio)")
checa(R("um único ano, com 4 dígitos") and R("Nunca escreva dois anos") and R("Não use o número do processo nem o ano de lei, decreto ou instrução normativa citada."), "ano: um único ano do documento; sem número do processo nem ano de lei")
checa(R("informe em meses") and R('anote os dias entre parênteses, por exemplo "6 (180 dias)"'), "garantia: meses; se vier em dias, converte e anota (ex.: 6 (180 dias))")
checa(R("Nunca escreva neste campo o próprio item pedido") and "serviço: tipo de licença, métrica de licenciamento, vigência, nível de serviço, requisito técnico do software" in t2, "atributo: proíbe o item pedido e dá exemplos de serviço (tipo de licença, métrica, vigência, nível de serviço, requisito técnico)")
checa(R('Não use o caractere "|" dentro de uma célula; use vírgula.'), "proíbe '|' dentro de célula (usar vírgula)")
checa(R("no Trecho, uma frase com o motivo (obrigatória)"), "utilidade: exige uma frase com o motivo")
checa("número do pregão" not in t2 and "número do pregão" in t1, "a licença de usar o 'número do pregão' como ano saiu do v2 (estava no antigo)")

print("\n=== valores da instrução (regra 5 da conferência) ===")
v1, v2 = cf.valores_da_instrucao(t1), cf.valores_da_instrucao(t2)
checa(set(v1) == set(v2), f"os mesmos campos têm valores-modelo: {sorted(v2)}")
checa(all(v1[c] == v2[c] for c in v1 if c != "atributo do item"), "valores-modelo idênticos nos outros campos")
print(f"      (atributo do item: {len(v1['atributo do item'])} valores-modelo no antigo, {len(v2['atributo do item'])} no v2)")

print("\n=== ficha montada a partir do v2 ===")
resp = "\n".join(l.replace("| | | |", "| x | 1 | y |") for l in L2[:1] + L2[1:])
fm = cf.formato(resp)
checa(fm["campos_presentes"] == 9, f"linhas_da_ficha lê 9 campos no modelo do v2 preenchido ({fm['campos_presentes']})")

print("\n=== o app usa o v1 desde o Pedido 27 (PARA_IA e conferência); o v2 fica em config\\ para o Gemini ===")
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=300); at.run()
checa(not at.exception and f.INSTRUCAO == V1, f"depois de abrir o app: f.INSTRUCAO = {f.INSTRUCAO.name} (v1; Pedido 27)")
checa(f.INSTRUCAO.read_text(encoding="utf-8") == t1, "o texto que a conferência da Etapa 5 recebe (app.py: f.INSTRUCAO.read_text) é o do v1")
TMP = DADOS / "pedido25" / f"_tmp_teste_f_{int(time.time())}"; (TMP / "recortes" / "TR_sim").mkdir(parents=True)
f.SAIDA = TMP; f.escolher_numero = lambda msg, maximo: 1
REC = "x" * 6000; (TMP / "recortes" / "TR_sim" / "recorte.txt").write_text(REC, encoding="utf-8")
f.opcao_5_texto_ia(); para = (TMP / "para_ia" / "TR_sim_PARA_IA.txt").read_text(encoding="utf-8")
checa(para == t1.rstrip() + "\n\n" + REC, f"PARA_IA = instrução v1 + recorte ({len(para)} caracteres)")
cfg = ot.ler_config(f.ORCAMENTO_CSV)
fator = cfg["caracteres_por_token"]
n1, n2 = len(t1.rstrip()), len(t2.rstrip())
tk1, tk2 = math.ceil(n1 / fator), math.ceil(n2 / fator)
orc2, _ = f.orcamento_do_prompt(para)
checa(orc2["tokens_prompt"] == math.ceil(len(para) / fator), f"orçamento do app para o PARA_IA: {orc2['tokens_prompt']} tokens (fator {fator})")
print(f"      Crescimento do prompt (só a instrução): {n1} -> {n2} caracteres (+{n2 - n1}); ≈ {tk1} -> {tk2} tokens (+{tk2 - tk1}) pelo fator {fator} car./token do app.")
checa(n2 - n1 > 0 and tk2 - tk1 > 0 and tk2 - tk1 < 400, f"crescimento medido: +{n2 - n1} caracteres, +{tk2 - tk1} tokens (menos de 400)")
print("\nRESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: {falhas}")
sys.exit(1 if falhas else 0)

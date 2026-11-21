"""Bateria da busca palavra -> código: roda sem a tela e sem rede (só o catálogo local) e gera o relatório.
Regra: PASSOU = o código esperado aparece entre os 5 primeiros E nenhum acessório vem antes dele.
"1º lugar" é informado à parte. Termo inexistente passa se não vier nenhum código.
Uso (na pasta do app): .venv\\Scripts\\python.exe -I -B tests\\rodar_casos.py"""
import csv
import datetime as dt
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PASTA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PASTA))
import ferramenta as f  # noqa: E402

TESTES = Path(__file__).resolve().parent
catalogo = f.ler_catalogo_pdm()
casos = list(csv.DictReader((TESTES / "casos_busca.csv").open(encoding="utf-8-sig"), delimiter=";"))
linhas = []
for c in casos:
    r = f.procurar_tolerante(c["termo"], catalogo, limite=15)
    codigos = [x["codigoPdm"] for x in r["achados"]]
    esperado = c["codigo_esperado"].strip()
    if esperado:
        pos = codigos.index(esperado) + 1 if esperado in codigos else 0
        antes = r["achados"][: pos - 1] if pos else []
        passou = 1 <= pos <= 5 and not any(x["acessorio"] for x in antes)
    else:
        pos = 0
        passou = not codigos
    linhas.append({"termo": c["termo"], "codigo_esperado": esperado, "nome_esperado": c["nome_esperado"], "posicao": pos or "",
                   "resultado": "PASSOU" if passou else "FALHOU", "primeiro_lugar": "sim" if pos == 1 else "não",
                   "corrigido_para": r["corrigido_para"] or "", "tres_primeiros": " | ".join(f"{x['codigoPdm']} {x['nomePdm']}" for x in r["achados"][:3]),
                   "sugestoes": " | ".join(r["sugestoes"][:3])})
    print(f"{linhas[-1]['resultado']:7} {c['termo']:12} esperado {esperado or '(nenhum)':8} posição {pos or '-':>2} "
          f"{'corrigido: ' + r['corrigido_para'] if r['corrigido_para'] else ''}")
ok = sum(l["resultado"] == "PASSOU" for l in linhas)
primeiro = sum(l["primeiro_lugar"] == "sim" for l in linhas)
saida = TESTES / "resultado_casos.csv"
with saida.open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(linhas[0]), delimiter=";")
    w.writeheader()
    w.writerows(linhas)
print(f"\n{dt.datetime.now():%d/%m/%Y %H:%M} | catálogo de {catalogo[0]['baixado_em'][:16]} | {ok} de {len(linhas)} passaram | "
      f"{primeiro} com o código esperado em 1º lugar | falharam: {[l['termo'] for l in linhas if l['resultado'] == 'FALHOU'] or 'nenhum'}")
print(f"Relatório: {saida}")
sys.exit(0 if ok == len(linhas) else 1)

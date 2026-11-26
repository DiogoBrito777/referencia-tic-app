"""Item 3.3: caso da compra 80620172000105/2026/144, itens 41 e 42 (mouse), com dados reais das APIs (GET público).
Passa os dois itens pela mesma validação da ferramenta e confere contra a pesquisa de preço do Compras.gov.br.
Uso: .venv\\Scripts\\python.exe -I -B tests\\caso_mouse.py"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ferramenta as f  # noqa: E402

v = {"cnpj": "80620172000105", "ano": "2026", "seq": "144"}
st, js, _ = f.get(f"{f.COMPRAS}/modulo-pesquisa-preco/1_consultarMaterial",
                  {"pagina": 1, "tamanhoPagina": 100, "tipo": "codigoPdm", "codigo": 5409, "idCompra": "98991305000312026"})
for r in js["resultado"]:
    linha = {"numero_item": r["numeroItemCompra"], "descricao_item": " ".join(r["descricaoItem"].split())}
    f.validar_item_pncp(linha, v, ["mouse"], mediana=None, cache={}, consultas_res=[0])
    est, hom = linha.get("valor_estimado_pncp"), r["precoUnitario"]
    print(f"item {r['numeroItemCompra']} | qtd {r['quantidade']:g} | Compras.gov.br: R$ {hom:.2f} | PNCP homologado: R$ {linha.get('valor_homologado_pncp')} | "
          f"PNCP estimado: R$ {est} | diferença do estimado: {(hom / est - 1):.0%} | item no PNCP: {linha.get('numero_item_pncp')} | status: {linha.get('status_item_pncp')}")
    print(f"   {linha['descricao_item']}")

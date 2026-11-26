"""Teste OFFLINE do zero à esquerda do idCompra (sem rede: ferramenta.get é trocada por uma função de teste; dados SIMULADOS só aqui).
Uso (na pasta do app): python -I -B tests\test_id_compra_zero.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ferramenta as f

falhas = []
def checa(cond, msg):
    print(("OK    " if cond else "FALHOU ") + msg)
    if not cond: falhas.append(msg)

# normalizar_id_compra
casos = {"8031406000272026": "08031406000272026", "2000105900372026": "02000105900372026", "3000105900072026": "03000105900072026",
         "08031406000272026": "08031406000272026", "10233306001482026": "10233306001482026", " 8031406000272026 ": "08031406000272026",
         "": "", "abc123": "abc123", "123456789012345678": "123456789012345678"}
for entrada, esperado in casos.items():
    checa(f.normalizar_id_compra(entrada) == esperado, f"normalizar_id_compra({entrada!r}) = {f.normalizar_id_compra(entrada)!r} (esperado {esperado!r})")
checa(f.normalizar_id_compra(None) == "", "normalizar_id_compra(None) = ''")
checa(f.normalizar_id_compra(8031406000272026) == "08031406000272026", "número inteiro (zero perdido na leitura) também vira 17 dígitos")

# ligar_ao_pncp: a API FALSA só conhece o id de 17 dígitos (como a real), devolvendo lista vazia para o de 16
pedidos = []
CONHECIDOS = {"08031406000272026": {"numeroControlePNCP": "00000000000000-1-000001/2026", "orgaoEntidadeCnpj": "00000000000000", "anoCompraPncp": 2026, "sequencialCompraPncp": 1}}
def get_falso(url, params=None, binario=False):
    pedidos.append((url, dict(params or {})))
    r = CONHECIDOS.get((params or {}).get("codigo"))
    return 200, {"resultado": [r] if r else []}, {}
f.get = get_falso
v16 = f.ligar_ao_pncp("8031406000272026")
checa(v16 is not None and v16["seq"] == "1" and v16["ano"] == "2026", f"id de 16 dígitos LIGA (a consulta saiu com o zero): {v16}")
checa(pedidos[0][1] == {"tipo": "idCompra", "codigo": "08031406000272026"}, f"parâmetros enviados à API: {pedidos[0][1]}")
n = len(pedidos); v17 = f.ligar_ao_pncp("08031406000272026")
checa(v17 == v16 and len(pedidos) == n + 1 and pedidos[-1][1]["codigo"] == "08031406000272026", "id que já tinha 17 dígitos segue igual (1 consulta, sem mudar)")
n = len(pedidos); vx = f.ligar_ao_pncp("10233306001482026")
checa(vx is None and pedidos[-1][1]["codigo"] == "10233306001482026" and len(pedidos) == n + 1, "id de 17 dígitos desconhecido: consulta 1 vez com o mesmo id e devolve None (não inventa vínculo)")
n = len(pedidos); vn = f.ligar_ao_pncp("16024912000942025")
checa(vn is None and pedidos[-1][1]["codigo"] == "16024912000942025", "id de 17 dígitos sem PNCP continua 'sem PNCP' (a correção não muda esse caso)")
# a v4f original (sem a correção) teria mandado o id sem zero: documenta o antes
checa("zfill" in Path(f.__file__).read_text(encoding="utf-8"), "a correção está no ferramenta.py desta cópia")
print("RESULTADO:", "TODOS PASSARAM" if not falhas else f"FALHARAM {len(falhas)}")
sys.exit(1 if falhas else 0)

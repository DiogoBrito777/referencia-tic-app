"""Recorte das páginas do item pedido em cada documento (sem IA). Uso: python3 -I recorte.py <pasta_textos> <pasta_saida>"""
import json, re, sys, unicodedata, pathlib, csv

def norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

DOCS = [
    ("D01", "web_07.json", "nobreak de 3 kVA", r"no[\s-]?break|\bups\b|\bkva\b|\d\s*va\b"),
    ("D02", "web_06.json", "nobreak de 3 kVA", r"no[\s-]?break|\bups\b|\bkva\b|\d\s*va\b"),
    ("D03", "web_17.json", "monitor de 24 polegadas", r"\bmonitor|polegada|\d\s*(\"|”|pol\b)"),
    ("D04", "web_20.json", "monitor de 24 polegadas", r"\bmonitor|polegada|\d\s*(\"|”|pol\b)"),
    ("D05", "P_08539710000104_2026_189_1.json", "monitor de 24 polegadas", r"\bmonitor|polegada|\d\s*(\"|”|pol\b)"),
    ("D06", "web_12.json", "switch de 24 portas", r"\bswitch|comutador|\bportas\b|\bpoe\b"),
    ("D07", "web_13.json", "switch de 24 portas", r"\bswitch|comutador|\bportas\b|\bpoe\b"),
    ("D08", "web_09.json", "câmera IP", r"\bcamera|bullet|\bdome\b|megapixel|\bmp\b|\bnvr\b"),
    ("D09", "web_24.json", "rádio portátil VHF", r"\bradio|transceptor|\bvhf\b|\buhf\b"),
    ("D10", "gab_SEI_161773739_PE_90007_2025_DLF_Aquisi_o.json", "equipamento de inspeção corporal (objeto principal)", r"inspecao corporal|body\s*scan|dual view|scanner|cabine|raios?[\s-]?x"),
]
APOIO = r"especifica|garantia|prazo de entrega|entregue|local de entrega|abnt|nbr|inmetro|anatel|marca|modelo"
MAX_PAG = 16

def main(src, dst):
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    resumo = []
    for cod, arq, item, rx in DOCS:
        paginas = json.load(open(src / arq, encoding="utf-8"))
        rx_item, rx_ap = re.compile(rx), re.compile(APOIO)
        pont = []
        for i, p in enumerate(paginas, 1):
            t = norm(p or "")
            a, b = len(rx_item.findall(t)), len(rx_ap.findall(t))
            pont.append((a * 3 + b if a else 0, i))
        escolhidas = {1}  # cabeçalho: órgão, número, data
        # páginas com prazo de entrega e com garantia em meses/anos (podem não citar o item)
        rx_gar = re.compile(r"garantia[^.]{0,120}?\d+\s*(\([^)]{0,30}\)\s*)?(meses|anos|mes|ano)\b")
        rx_pra = re.compile(r"prazo\s+(maximo\s+)?(de|para)\s+(a\s+)?entrega|entregues?\s+em\s+ate|prazo\s+de\s+entrega")
        for rx_c in (rx_gar, rx_pra):
            cont = sorted(((len(rx_c.findall(norm(p or ""))), i) for i, p in enumerate(paginas, 1)), reverse=True)
            for c, i in cont[:3]:
                if c > 0:
                    escolhidas.add(i)
        for s, i in sorted(pont, reverse=True):
            if s <= 0 or len(escolhidas) >= MAX_PAG:
                break
            escolhidas.add(i)
        sel = sorted(escolhidas)
        corpo = [f"DOCUMENTO {cod} | item pedido: {item} | {len(paginas)} páginas no original | páginas incluídas: {', '.join(map(str, sel))}\n"]
        for i in sel:
            corpo.append(f"\n=== PÁGINA {i} ===\n{(paginas[i-1] or '').strip()}\n")
        texto = "".join(corpo)
        (dst / f"{cod}_recorte.txt").write_text(texto, encoding="utf-8")
        total = sum(len(p or "") for p in paginas)
        resumo.append([cod, arq, item, len(paginas), len(sel), " ".join(map(str, sel)), total, len(texto), round(len(texto) / 4)])
    with open(dst / "resumo_recortes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc", "arquivo_origem", "item_pedido", "paginas_original", "paginas_recorte", "paginas_incluidas", "caracteres_original", "caracteres_recorte", "tokens_estimados_recorte"])
        w.writerows(resumo)
    for r in resumo:
        print(r[0], r[3], "->", r[4], "pág.", r[5], "| chars", r[6], "->", r[7], "| ~tokens", r[8])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

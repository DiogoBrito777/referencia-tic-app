"""[v4h: copia de produto_p1/fase6/formato_v3.py; unica mudanca = a linha do import de conferir_ficha_v2, que agora e o arquivo irmao desta pasta]
formato_v3: cópia SÓ da verificação que gerou formato_ok falso (v4g_teste\\conferir_ficha.py, função formato, linhas 82-88; a comparação de página é a linha 86).
Única mudança (decisão do grupo): no campo 'marca ou modelo', o valor 'não' é aceito sem página numérica. Nenhum outro campo muda.
Usa linhas_da_ficha e sem_acento da cópia fase5\\conferir_ficha_v2.py (que só difere da v1 por tirar o par de aspas externo do TRECHO; valor e página não mudam)."""
import re
import conferir_ficha_v2 as _v2   # v4h: a cópia irmã (na fase6 era carregada por caminho de fase5/conferir_ficha_v2.py); NADA mais mudou

def formato(texto):
    """campos_presentes, formato_ok (9 campos e todo campo com valor tem página numérica; v3: exceto 'marca ou modelo' = 'não'), ficha_sem_pagina."""
    lin = _v2.linhas_da_ficha(texto)
    com_valor = [r for r in lin if "nao encontrado" not in _v2.sem_acento(r[1])]
    com_pag = [r for r in com_valor if re.search(r"\d", r[2]) or (r[0] == "marca ou modelo" and _v2.sem_acento(r[1]) == "nao")]          # v3: única mudança
    return {"campos_presentes": len(lin), "formato_ok": len(lin) == 9 and len(com_pag) == len(com_valor),
            "ficha_sem_pagina": len(lin) == 9 and not any(re.search(r"\d", r[2]) for r in lin), "campos_com_valor": len(com_valor), "com_valor_e_pagina_numerica": len(com_pag)}

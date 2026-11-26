"""Simula Linux (os.name e winreg ausente) e chama o caminho do .doc. Sem rede, nenhum arquivo criado.
Uso: python tests/teste_word_linux.py [pasta_do_app]"""
import os
import sys
from pathlib import Path

PASTA = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent).resolve()
sys.path.insert(0, str(PASTA))
import ferramenta as f  # noqa: E402

doc = Path("pasta_que_nao_existe") / "arquivo_antigo.doc"  # objeto Path criado antes de trocar os.name
resultados = []


def tenta(nome, preparar, desfazer):
    preparar()
    try:
        r = f.extrair_paginas(doc)
        ok = r[0] is None and "Documento .doc" in r[1]
        resultados.append(ok)
        print(("OK     " if ok else "FALHOU ") + nome + f" -> {r[1][:90]}")
    except Exception as e:  # noqa: BLE001
        resultados.append(False)
        print(f"FALHOU {nome} -> EXCEÇÃO {type(e).__name__}: {e}")
    finally:
        desfazer()


nome_orig = os.name
tenta("os.name = 'posix'", lambda: setattr(os, "name", "posix"), lambda: setattr(os, "name", nome_orig))
tenta("winreg ausente (sys.modules['winreg'] = None)", lambda: sys.modules.__setitem__("winreg", None), lambda: sys.modules.pop("winreg", None))
sys.exit(0 if all(resultados) else 1)

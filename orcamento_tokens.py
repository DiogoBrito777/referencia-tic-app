"""[v2: cópia com a guarda de contexto acrescentada no fim: fracao_janela, calcular_orcamento_v2, aviso_acima_do_limite, verificar_execucao]
Orçamento de tokens do texto que vai para a IA (instrução + recorte).

Funções puras (sem rede, sem arquivo), exceto ler_config, que só lê config\\orcamento_tokens.csv.
O app NÃO sabe qual IA a pessoa vai usar: o fator caracteres por token é PARÂMETRO (por modelo) e fica em config, editável.
Padrão conservador: 3,0 caracteres por token. Superestimar é o lado seguro; subestimar faz o servidor da IA cortar o início do
prompt (onde fica a instrução) sem avisar. Por isso as contas arredondam para CIMA e o aviso diz o fator usado.
disponível para o texto = contexto - tokens da instrução - reserva para a resposta."""
import csv
import math
from pathlib import Path

FATOR_PADRAO = 3.0
CONTEXTO_PADRAO = 8192
RESERVA_PADRAO = 1500


def estimar_tokens(n_caracteres, car_por_token):
    """Tokens estimados = caracteres ÷ fator, arredondado para cima."""
    if not car_por_token or car_por_token <= 0:
        raise ValueError("o fator de caracteres por token deve ser maior que zero")
    return math.ceil(max(0, n_caracteres) / car_por_token)


def calcular_orcamento(chars_texto, chars_instrucao, contexto_tokens, reserva_tokens, car_por_token):
    """Devolve um dict com os números. cabe = tokens do texto <= disponível (igual cabe)."""
    tokens_texto = estimar_tokens(chars_texto, car_por_token)
    tokens_instrucao = estimar_tokens(chars_instrucao, car_por_token)
    disponivel = contexto_tokens - tokens_instrucao - reserva_tokens
    return {"fator": car_por_token, "contexto": contexto_tokens, "reserva": reserva_tokens, "tokens_instrucao": tokens_instrucao,
            "tokens_texto": tokens_texto, "tokens_prompt": tokens_texto + tokens_instrucao, "disponivel": disponivel,
            "cabe": tokens_texto <= disponivel, "falta": max(0, tokens_texto - disponivel)}


def _n(valor):
    return f"{valor:,}".replace(",", ".")


def _fator_txt(fator):
    return f"{fator:g}".replace(".", ",") if fator != int(fator) else f"{fator:.1f}".replace(".", ",")


def texto_orcamento(orc, origem="config"):
    """'≈ N tokens de M (fator 3,0 car./token, config)': N = instrução + texto; M = janela de contexto."""
    return f"≈ {_n(orc['tokens_prompt'])} tokens de {_n(orc['contexto'])} (fator {_fator_txt(orc['fator'])} car./token, {origem})"


def aviso_nao_cabe(orc):
    """Texto do aviso quando o recorte não cabe; vazio quando cabe."""
    if orc["cabe"]:
        return ""
    if orc["disponivel"] <= 0:
        sobra = "não sobra espaço para o texto"
    else:
        sobra = f"só há ≈ {_n(orc['disponivel'])} tokens disponíveis para o texto"
    return (f"AVISO: o texto NÃO CABE: tem ≈ {_n(orc['tokens_texto'])} tokens e {sobra} (contexto {_n(orc['contexto'])} − instrução "
            f"≈ {_n(orc['tokens_instrucao'])} − reserva da resposta {_n(orc['reserva'])}); faltam ≈ {_n(orc['falta'])}. "
            "Alguns servidores de IA cortam o prompt sem avisar. Reduza o recorte ou use uma janela maior (config\\orcamento_tokens.csv).")


def ler_config(caminho, modelo="padrao"):
    """Lê a linha do modelo em config\\orcamento_tokens.csv (colunas: modelo;caracteres_por_token;contexto_tokens;reserva_resposta_tokens).
    Qualquer problema (arquivo ausente, linha ausente, número inválido) volta ao padrão do código e diz isso em 'origem'."""
    padrao = {"modelo": modelo, "caracteres_por_token": FATOR_PADRAO, "contexto_tokens": CONTEXTO_PADRAO, "reserva_resposta_tokens": RESERVA_PADRAO}
    try:
        with Path(caminho).open(encoding="utf-8-sig", newline="") as f:
            linhas = list(csv.DictReader(f, delimiter=";"))
        alvo = next((l for l in linhas if (l.get("modelo") or "").strip().lower() == modelo.lower()), None)
        if alvo is None:
            return {**padrao, "origem": f"padrão do código (modelo '{modelo}' não está no config)"}
        fator = float(str(alvo["caracteres_por_token"]).replace(",", "."))
        contexto = int(float(str(alvo["contexto_tokens"]).replace(",", ".")))
        reserva = int(float(str(alvo["reserva_resposta_tokens"]).replace(",", ".")))
        if fator <= 0 or contexto <= 0 or reserva < 0:
            raise ValueError("valores fora do intervalo")
        return {"modelo": modelo, "caracteres_por_token": fator, "contexto_tokens": contexto, "reserva_resposta_tokens": reserva, "origem": "config"}
    except (OSError, KeyError, ValueError, TypeError) as e:
        return {**padrao, "origem": f"padrão do código (config ilegível: {type(e).__name__})"}


# ---------------------------------------------------------------- v2: guarda de contexto (acrescentado)
FRACAO_JANELA_PADRAO = 0.70


def ler_fracao_janela(caminho, modelo="padrao"):
    """Lê a fração da janela em orcamento_v2.csv (colunas: modelo;fracao_janela;observacao; aceita vírgula ou ponto). Qualquer problema volta a 0,70 e diz isso em 'origem'."""
    try:
        with Path(caminho).open(encoding="utf-8-sig", newline="") as f:
            linhas = list(csv.DictReader(f, delimiter=";"))
        alvo = next((l for l in linhas if (l.get("modelo") or "").strip().lower() == modelo.lower()), None)
        if alvo is None:
            return {"fracao_janela": FRACAO_JANELA_PADRAO, "origem": f"padrão do código (modelo '{modelo}' não está no arquivo)"}
        fracao = float(str(alvo["fracao_janela"]).replace(",", "."))
        if not 0 < fracao <= 1:
            raise ValueError("fração fora de (0, 1]")
        return {"fracao_janela": fracao, "origem": "orcamento_v2.csv"}
    except (OSError, KeyError, ValueError, TypeError) as e:
        return {"fracao_janela": FRACAO_JANELA_PADRAO, "origem": f"padrão do código (arquivo ilegível: {type(e).__name__})"}


def calcular_orcamento_v2(chars_texto, chars_instrucao, contexto_tokens, reserva_tokens, car_por_token, fracao_janela=FRACAO_JANELA_PADRAO):
    """calcular_orcamento (igual ao original) + limite = fracao_janela x janela; acima_do_limite = estimativa do PROMPT (instrução + texto) > limite. O fator não muda."""
    orc = calcular_orcamento(chars_texto, chars_instrucao, contexto_tokens, reserva_tokens, car_por_token)
    limite = fracao_janela * contexto_tokens
    orc.update({"fracao_janela": fracao_janela, "limite_tokens": limite, "acima_do_limite": orc["tokens_prompt"] > limite})
    return orc


def aviso_acima_do_limite(orc):
    """Texto do aviso quando a estimativa do prompt passa do limite (fração da janela); vazio caso contrário."""
    if not orc.get("acima_do_limite"):
        return ""
    return (f"AVISO: acima do limite: o prompt estimado em ≈ {_n(orc['tokens_prompt'])} tokens passa de {orc['fracao_janela']:.0%} da janela "
            f"({_n(round(orc['limite_tokens']))} de {_n(orc['contexto'])}; fator {_fator_txt(orc['fator'])} car./token). A estimativa pode errar para menos: reduza o recorte ou divida em partes.")


def verificar_execucao(num_ctx, prompt_eval_count, formato_ok):
    """Verificação DEPOIS da execução. 'POSSÍVEL CORTE' se prompt_eval_count estiver entre num_ctx/2 e num_ctx/2+16 (inclusive); senão 'REVISAR FORMATO' se formato_ok for falso;
    senão 'ok'. Se faltar num_ctx ou prompt_eval_count devolve 'SEM DADO' (não estima)."""
    if num_ctx is None or prompt_eval_count is None:
        return "SEM DADO"
    metade = num_ctx // 2
    if metade <= prompt_eval_count <= metade + 16:
        return "POSSÍVEL CORTE"
    if not formato_ok:
        return "REVISAR FORMATO"
    return "ok"

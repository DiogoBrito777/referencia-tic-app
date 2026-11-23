"""Conferência do código do catálogo sem repetir a chamada de rede a cada reexecução (rerun) da tela.

A chave é gravada ANTES da chamada. Uma reexecução que chegue enquanto a chamada ainda está em andamento espera
o resultado (com limite de tempo) em vez de fazer outra chamada. Sem dependência do Streamlit: o resultado fica
num dicionário comum, que sobrevive à interrupção do script da tela."""
import threading
import time


class Conferencias:
    def __init__(self, maximo=200):
        self._trava = threading.Lock()
        self._dados = {}
        self._maximo = maximo

    def obter(self, chave, executar, espera_max_s=120, sondar_s=0.2, _tentativa=1):
        """Devolve dict {estado, valor, inicio}. estado: 'pronto', 'erro' (valor = texto) ou 'pendente'
        (a espera acabou e a chamada de outra execução ainda não terminou)."""
        with self._trava:
            entrada = self._dados.get(chave)
            dono = entrada is None
            if dono:
                if len(self._dados) >= self._maximo:  # descarta as mais antigas já terminadas
                    for k in [k for k, v in self._dados.items() if v["estado"] != "pendente"][: self._maximo // 2]:
                        del self._dados[k]
                entrada = self._dados[chave] = {"estado": "pendente", "valor": None, "inicio": time.time()}
        if dono:
            terminou = False
            try:
                valor = executar()
                with self._trava:
                    entrada.update(estado="pronto", valor=valor)
                terminou = True
            except Exception as e:  # noqa: BLE001 - falha de rede vira mensagem, não derruba a tela
                with self._trava:
                    entrada.update(estado="erro", valor=f"{type(e).__name__}: {e}")
                terminou = True
            finally:
                if not terminou:  # interrompida (ex.: parada do script): quem esperava tenta uma vez de novo
                    with self._trava:
                        entrada["estado"] = "interrompida"
                        self._dados.pop(chave, None)
            return entrada
        fim = time.time() + espera_max_s
        while entrada["estado"] == "pendente" and time.time() < fim:
            time.sleep(sondar_s)
        if entrada["estado"] == "interrompida" and _tentativa < 2:
            return self.obter(chave, executar, espera_max_s, sondar_s, _tentativa + 1)
        return entrada

    def esquecer(self, chave):
        """Apaga a entrada (botão 'Tentar de novo')."""
        with self._trava:
            self._dados.pop(chave, None)

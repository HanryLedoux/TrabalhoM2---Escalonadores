"""
Simulador de CPU Round Robin com Memória Virtual (Paginação LRU)
Disciplina: Sistemas Operacionais - UNIVALI
"""

import sys
from collections import deque, OrderedDict


# ──────────────────────────────────────────────
# Estruturas de dados
# ──────────────────────────────────────────────

class Processo:
    def __init__(self, pid, chegada, paginas):
        self.pid = pid
        self.chegada = chegada
        self.paginas = paginas          # lista de páginas requisitadas (em ordem)
        self.indice_pagina = 0          # qual página está tentando acessar agora
        self.page_faults = 0
        self.tempo_inicio = None
        self.tempo_conclusao = None
        self.quantum_restante = 0

    @property
    def concluido(self):
        return self.indice_pagina >= len(self.paginas)

    def pagina_atual(self):
        if self.concluido:
            return None
        return self.paginas[self.indice_pagina]

    def __repr__(self):
        return self.pid


class GerenciadorLRU:
    """RAM com política de substituição LRU (Least Recently Used)."""

    def __init__(self, capacidade):
        self.capacidade = capacidade
        # OrderedDict: chave = página, valor = pid dono
        self._cache = OrderedDict()

    def esta_na_ram(self, pagina):
        return pagina in self._cache

    def acessar(self, pagina):
        """Registra acesso (atualiza ordem LRU). Página deve já estar na RAM."""
        self._cache.move_to_end(pagina)

    def carregar(self, pagina, pid):
        """
        Carrega a página na RAM.
        Retorna a página removida (ou None se havia espaço).
        """
        removida = None
        if pagina in self._cache:
            self._cache.move_to_end(pagina)
            return None

        if len(self._cache) >= self.capacidade:
            # Remove a página menos recentemente usada (primeiro elemento)
            pag_removida, _ = self._cache.popitem(last=False)
            removida = pag_removida

        self._cache[pagina] = pid
        return removida

    def estado(self):
        return list(self._cache.keys())


# ──────────────────────────────────────────────
# Parser do arquivo de entrada
# ──────────────────────────────────────────────

def ler_arquivo(caminho):
    """
    Formato esperado:
      Linha 1: <capacidade_ram> <quantum> <penalidade_io>
      Demais:  <chegada> <pid> <pag1,pag2,...>
    """
    with open(caminho, 'r') as f:
        linhas = [l.strip() for l in f if l.strip()]

    partes = linhas[0].split()
    capacidade_ram = int(partes[0])
    quantum = int(partes[1])
    penalidade_io = int(partes[2])

    processos = []
    for linha in linhas[1:]:
        partes = linha.split()
        chegada = int(partes[0])
        pid = partes[1]
        paginas = [int(p) for p in partes[2].split(',')]
        processos.append(Processo(pid, chegada, paginas))

    return capacidade_ram, quantum, penalidade_io, processos


# ──────────────────────────────────────────────
# Simulador principal
# ──────────────────────────────────────────────

def simular(capacidade_ram, quantum, penalidade_io, processos):
    log = []          # eventos registrados
    ram = GerenciadorLRU(capacidade_ram)

    fila_prontos = deque()   # processos prontos para CPU
    fila_bloqueados = []     # lista de (tempo_liberacao, processo)
    todos = {p.pid: p for p in processos}

    tempo = 0
    processos_restantes = list(processos)  # ainda não chegaram
    concluidos = []

    cpu_processo = None      # processo usando a CPU agora
    cpu_quantum_usado = 0    # quantos tiques usou no quantum atual

    def log_evento(msg):
        log.append(f"[Tempo {tempo:>3}] {msg}")

    def mostrar_estado(cpu, prontos, bloqueados, ram, tempo):
        """Imprime o estado completo do sistema neste tique."""
        print(f"\n{'─'*58}")
        print(f"  TIQUE {tempo}")
        print(f"{'─'*58}")

        # CPU
        if cpu:
            q_usado = cpu_quantum_usado
            barra = "█" * q_usado + "░" * (quantum - q_usado)
            print(f"  CPU      : {cpu.pid} | Quantum [{barra}] {q_usado}/{quantum}")
        else:
            print(f"  CPU      : [ OCIOSA ]")

        # Fila de Prontos
        prontos_str = " → ".join(p.pid for p in prontos) if prontos else "(vazia)"
        print(f"  Prontos  : {prontos_str}")

        # Fila de Bloqueados
        if bloqueados:
            bloq_str = "  ".join(
                f"{p.pid}(libera t={t})" for t, p in sorted(bloqueados)
            )
        else:
            bloq_str = "(vazia)"
        print(f"  Bloqueados: {bloq_str}")

        # RAM (LRU)
        estado_ram = ram.estado()
        slots = []
        for i in range(ram.capacidade):
            if i < len(estado_ram):
                slots.append(f"[pág {estado_ram[i]}]")
            else:
                slots.append("[     ]")
        ram_str = " ".join(slots)
        print(f"  RAM (LRU): {ram_str}  ← mais recente")
        print()

    print(f"\n{'═'*58}")
    print("  SIMULAÇÃO PASSO A PASSO")
    print(f"{'═'*58}")

    # ── loop principal ──
    max_iter = 10_000   # segurança contra loop infinito
    for _ in range(max_iter):
        # Mostra estado ANTES dos eventos do tique
        mostrar_estado(cpu_processo, fila_prontos, fila_bloqueados, ram, tempo)

        # 1. Chegada de novos processos
        novos = [p for p in processos_restantes if p.chegada <= tempo]
        for p in novos:
            p.tempo_inicio = tempo
            fila_prontos.append(p)
            processos_restantes.remove(p)
            log_evento(f"{p.pid} chegou e entrou na Fila de Prontos")

        # 2. Liberar processos bloqueados que cumpriram penalidade
        liberados = [(t, p) for t, p in fila_bloqueados if t <= tempo]
        for t, p in liberados:
            fila_bloqueados.remove((t, p))
            fila_prontos.append(p)
            log_evento(f"{p.pid} saiu dos Bloqueados → Fila de Prontos (tentará página {p.pagina_atual()} novamente)")

        # 3. Se CPU está livre, pega próximo da fila de prontos
        if cpu_processo is None and fila_prontos:
            cpu_processo = fila_prontos.popleft()
            cpu_quantum_usado = 0
            log_evento(f"{cpu_processo.pid} ganhou a CPU (quantum restante: {quantum})")

        # 4. Verifica se tudo terminou
        if (cpu_processo is None
                and not fila_prontos
                and not fila_bloqueados
                and not processos_restantes):
            break

        # 5. Executa 1 tique na CPU
        if cpu_processo is not None:
            p = cpu_processo
            pagina = p.pagina_atual()

            if ram.esta_na_ram(pagina):
                # ── RAM HIT ──
                ram.acessar(pagina)
                log_evento(f"{p.pid} executou página {pagina} (RAM Hit) | RAM: {ram.estado()}")
                p.indice_pagina += 1
                cpu_quantum_usado += 1

                if p.concluido:
                    p.tempo_conclusao = tempo + 1
                    concluidos.append(p)
                    log_evento(f"{p.pid} CONCLUIU todas as páginas!")
                    cpu_processo = None
                    cpu_quantum_usado = 0
                elif cpu_quantum_usado >= quantum:
                    # Preempção por quantum
                    log_evento(f"{p.pid} sofreu preempção (quantum esgotado) → volta à Fila de Prontos")
                    fila_prontos.append(p)
                    cpu_processo = None
                    cpu_quantum_usado = 0
            else:
                # ── PAGE FAULT ──
                p.page_faults += 1
                removida = ram.carregar(pagina, p.pid)
                if removida is not None:
                    log_evento(f"{p.pid} sofreu Page Fault na página {pagina} | LRU removeu página {removida} da RAM")
                else:
                    log_evento(f"{p.pid} sofreu Page Fault na página {pagina} | Página carregada na RAM (havia espaço)")

                log_evento(f"  RAM agora: {ram.estado()}")
                liberacao = tempo + penalidade_io
                fila_bloqueados.append((liberacao, p))
                cpu_processo = None
                cpu_quantum_usado = 0

        tempo += 1

    return log, concluidos, todos


# ──────────────────────────────────────────────
# Relatório final
# ──────────────────────────────────────────────

def imprimir_relatorio(log, concluidos, todos):
    print("=" * 60)
    print("          RELATÓRIO FINAL DO SIMULADOR")
    print("=" * 60)

    print("\n── Log de Execução ──")
    for linha in log:
        print(linha)

    print("\n── Resultados por Processo ──")
    print(f"{'PID':<6} {'Chegada':>8} {'Conclusão':>10} {'Retorno':>8} {'Page Faults':>12}")
    print("-" * 50)
    for p in concluidos:
        retorno = p.tempo_conclusao - p.chegada
        print(f"{p.pid:<6} {p.chegada:>8} {p.tempo_conclusao:>10} {retorno:>8} {p.page_faults:>12}")

    print("=" * 60)


# ──────────────────────────────────────────────
# Entrada
# ──────────────────────────────────────────────

if __name__ == "__main__":
    caminho = sys.argv[1] if len(sys.argv) > 1 else "arquivo_teste.txt"
    capacidade_ram, quantum, penalidade_io, processos = ler_arquivo(caminho)

    print(f"Configuração: RAM={capacidade_ram} frames | Quantum={quantum} | Penalidade I/O={penalidade_io} tiques\n")

    log, concluidos, todos = simular(capacidade_ram, quantum, penalidade_io, processos)
    imprimir_relatorio(log, concluidos, todos)
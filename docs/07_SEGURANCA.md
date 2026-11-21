# 07 – Segurança, privacidade e uso de agentes de IA

## Dados
- Só dados públicos (PNCP, Compras.gov.br). Só GET; sem login; sem contornar bloqueio.
- Documentos públicos podem conter nomes de servidores e empresas: não reproduzir dados pessoais além do necessário (LGPD).
- Nenhuma senha, token ou chave no código.

## Versão online
- Repositório público; link de uso restrito à equipe e à PMDF.
- Arquivos gerados no servidor são temporários. Pendente: cada usuário ver só as próprias buscas.

## Agentes de IA no desenvolvimento (Claude Code, Antigravity)
- Regras em AGENTS.md/prompts orientam, mas **não bloqueiam** ações.
- Bloqueio real: permissões do Claude Code (settings.json) para as ferramentas dele; no Windows nativo, comandos de terminal rodam **sem sandbox** (sandbox só em macOS/Linux/WSL2).
- Práticas adotadas: pasta de trabalho isolada por tarefa; cópia antes de editar; aprovação de comandos; relatório com provas.
- Recomendações: não aprovar tudo automaticamente; Antigravity sem administrador; manter logs.

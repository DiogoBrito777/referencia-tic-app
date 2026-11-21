# 02 – Requisitos

Status: **feito** · **parcial** · **pendente** · Atualizado em 29/10/2026 (versão v3)

## Requisitos funcionais (RF)
| Id | Requisito | Status | Observação |
|---|---|---|---|
| RF01 | Digitar a palavra do produto e ver os códigos do catálogo (PDM) correspondentes | feito (v3) | Catálogo oficial local (20.444 PDMs) + sinônimos |
| RF02 | Usuário escolhe um ou mais códigos; nenhum é marcado sozinho | parcial | Hoje o primeiro pode vir marcado |
| RF03 | Mostrar quantas compras (12 meses) cada código teve | pendente | Pedido após o caso "mouse" |
| RF04 | Abrir as configurações (itens CATMAT) de um PDM, filtrar e copiar o código | pendente | Necessidade relatada pela PMDF em 29/10 |
| RF05 | Buscar compras homologadas dos últimos 12 meses pelo código (Brasil ou UF) | feito | Compras.gov.br → PNCP |
| RF06 | Comparar atributos com faixas (RAM, armazenamento, tela, garantia) | feito | atende / parcial / não atende por atributo |
| RF07 | Distinguir SSD de HDD e classes comerciais (480/500/512 = 512) | feito (v2) | |
| RF08 | Mostrar preço homologado e link da compra no PNCP | feito | |
| RF09 | Mostrar preço estimado × homologado e nº do item | pendente | Evita confusão com a lista do PNCP |
| RF10 | Marcar preço suspeito (sem apagar a linha) | parcial | Fora de 0,25× a 4× a mediana |
| RF11 | Baixar edital/TR de uma compra (sem anexos de fornecedores) | feito | |
| RF12 | Recortar as páginas do item (PDF e Word) | feito (v3) | .doc depende de Word instalado |
| RF13 | Gerar texto para IA (instrução + recorte) | feito | |
| RF14 | Ler o TR com IA e devolver a ficha com página | pendente | Ollama local |
| RF15 | Conferir modelos do mercado pela ficha técnica do fabricante | pendente | Meta da PMDF (abordagem B) |
| RF16 | Progresso por etapa (%), linha "Agora:" e detalhes | feito (v2) | |
| RF17 | Limpar resultados ao iniciar nova busca; botão "Nova busca" | pendente | |
| RF18 | Trocar o perfil de atributos conforme o código escolhido | pendente | |
| RF19 | Botão "Atualizar catálogo" com data | pendente | |

## Requisitos não funcionais (RNF)
| Id | Requisito | Status |
|---|---|---|
| RNF01 | Só dados públicos; só GET; sem login; sem contornar bloqueio | feito |
| RNF02 | Busca e filtros determinísticos, sem IA | feito |
| RNF03 | Toda informação com fonte (link ou página) | parcial |
| RNF04 | Funcionar com IA local, sem custo por uso | pendente |
| RNF05 | Interface para leigos (pt-BR, progresso, mensagens claras) | parcial |
| RNF06 | Instalação simples (INSTALAR/ABRIR) e versão online | feito |
| RNF07 | Cada usuário vê só as próprias buscas (versão online) | pendente |
| RNF08 | Registro de cada chamada à internet (log) | feito |
| RNF09 | Nenhuma senha/chave no código | feito |

## Regras de negócio (RN)
| Id | Regra |
|---|---|
| RN01 | Só compras com item **homologado**; período de 12 meses pela data do resultado |
| RN02 | Faixas: RAM x a 2x; armazenamento x a 2x por classe; tela x±2"; garantia x−12 a x+24 (a validar com a PMDF) |
| RN03 | Faixa do catálogo que apenas cruza a faixa pedida = "parcial (a confirmar no TR)" |
| RN04 | Atributo não informado não elimina a compra |
| RN05 | O servidor confere e decide; a ferramenta não escreve o TR |

## Fora do escopo do MVP
Implantação na PMDF, manutenção após dez/2026, busca automática de fichas técnicas, compras fora do PNCP, serviços (CATSER).

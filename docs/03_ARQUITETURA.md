# 03 – Arquitetura

## Fluxo
```
Usuário digita o produto
  → [local] catálogo de PDMs + sinônimos → lista de códigos → usuário escolhe
  → [internet] Compras.gov.br (pesquisa de preço pelo código, 12 meses)
  → [local] filtros por atributo (faixas, classes, SSD × HDD)
  → [internet] PNCP: compra, item, resultado homologado, link
  → tela: resumo + tabela (avaliação, preço, link)
  → por linha: baixar edital/TR → recortar páginas do item → texto para IA
  → [pendente] IA lê o recorte e devolve a ficha com página
```

## Fontes (somente APIs oficiais)
| Fonte | Uso |
|---|---|
| dadosabertos.compras.gov.br | catálogo de materiais (PDM); pesquisa de preço por código; idCompra |
| pncp.gov.br (APIs de consulta e integração) | compras, itens, resultados (homologado), documentos, link público |

Nenhum outro site é consultado. A busca por texto do portal do PNCP foi descartada (instável).

## Papel da IA
| Etapa | IA? |
|---|---|
| Busca, filtros, preço, link | Não |
| Leitura do TR → ficha com página | Sim (pendente de integração) |
| Ficha técnica do fabricante × requisitos | Sim (pendente) |
| Rascunho da especificação do TR | Opcional (futuro) |

Modelo previsto: Ollama local (num_ctx ≥ 8192). Testes manuais anteriores usaram Claude e Gemini.

## Componentes
| Arquivo | Função |
|---|---|
| app.py | Interface Streamlit (só tela) |
| ferramenta.py | Backend: catálogo, busca, filtros, PNCP, download, recorte |
| recorte_teste_ia.py | Recorte das páginas do item com marca "=== PÁGINA N ===" |
| config/produtos.csv | Perfis de atributos e faixas por produto |
| config/sinonimos.csv | Sinônimos (ex.: laptop = notebook) |
| config/catalogo_pdm.csv | Catálogo de PDMs baixado (com data) |
| config/INSTRUCAO_FICHA.txt | Instrução da ficha para a IA |

## Execução
- Local: INSTALAR.bat → ABRIR_APP.bat (Windows, Python 3.11+).
- Online: Streamlit Community Cloud, a partir do repositório GitHub (sem conversão de .doc).

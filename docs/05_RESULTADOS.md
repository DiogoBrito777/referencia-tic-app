# 05 – Resultados

Cada número com data e origem. "A confirmar" = ainda não medido.

## Leitura de TR (manual × IA)
| Teste | Leitura manual (equipe) | IA | Data |
|---|---|---|---|
| Piloto – 5 TRs de notebook | ~50 min · 5 erros (campos divergentes) | ~2 min · 0 erros | 11/10 |
| Teste limpo – 10 TRs, 6 itens, 80 campos | 244 min · 15 erros | ~3 min · 1 erro (página fora do recorte) | 13–14/10 |

- Claude e Gemini concordaram em 40 de 40 campos (D01–D05).
- Ressalva do piloto: instrução ajustada vendo os mesmos documentos.

## Sondagem e conferência
- Busca por texto do portal: ~60% das chamadas recusadas (rodada 5).
- Regras de palavras: 17 de 22 TRs úteis reconhecidos; só 20 de 46 "requisitos" eram do produto.
- Origem dos PDFs do teste limpo: 8 de 10 de sites dos órgãos; 1 do PNCP; 1 manual (FONTES_DOS_PDFS.csv).

## Ferramenta – busca
| Medida | Resultado | Data |
|---|---|---|
| Busca pelo nome ("notebook", DF) | 4 de 11 descrições com atributos; 99 chamadas; 0 falhas; ~6,5 min | 22/10 |
| Busca pelo código (PDM 8435, Brasil) | 500 de 500 com atributos; 45 chamadas; 0 falhas; 156 s | 22/10 |
| Preço Compras.gov.br × PNCP (vinculados) | 55 de 64 iguais; 6 sem valor; 3 diferentes | verificado 26/10 |
| v2 (modo rápido) | 300 linhas; 88 não atende; 212 parciais; 17 com link; 141 s | 28/10 |
| v3 (modo rápido) | 300 linhas; 22 com link (20 sem "não atende"); 136 s | 28/10 |
| Catálogo de PDMs | 20.444 códigos; 41 chamadas; 0 falhas; 162 s | 28/10 |

## A confirmar
- Acerto da IA local (Ollama) no gabarito D01–D10.
- Tempo de conferência por um servidor da PMDF.
- Preço estimado × homologado (caso mouse: R$ 5,74 × R$ 32–45).
- Custo por documento em uso real.

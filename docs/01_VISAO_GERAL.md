# 01 – Visão geral

**Projeto:** Referência TIC – busca de compras públicas de referência para termos de referência (TR) de materiais de TI
**Contexto:** Estágio Empresarial 1 – UnDF, em parceria com o CeTI/PMDF
**Equipe:** Bruno Diogo, Pietra Cardoso, Raissa dos Santos · **Orientação:** Prof. Fernando Madeira
**Atualizado em:** 29/10/2026

## Problema (premissa a confirmar com a PMDF)
Para escrever o TR de um material de TI, o servidor pesquisa à mão, em portais diferentes, editais, especificações, códigos do catálogo e preços, e lê documentos longos. Isso leva tempo, e um dado errado do item pode ir para o edital, levando à compra de um produto que não atende.

Evidências até agora:
- Na leitura manual da equipe: 10 a 30 min por documento e erros de leitura (ver 05_RESULTADOS).
- Na reunião de 29/10, um representante da PMDF relatou ter perdido muito tempo procurando o **código do catálogo** de um produto para fazer o edital.

## Proposta
Uma ferramenta que:
1. encontra o **código do catálogo** a partir da palavra digitada;
2. busca **compras públicas parecidas** (homologadas nos últimos 12 meses), com **preço homologado** e **link oficial** no PNCP;
3. compara cada compra com os requisitos (atende / parcial / não atende);
4. baixa e recorta o TR, e uma **IA lê e devolve a ficha do item com a página** (etapa em implantação).

## Escopo
- **É:** estudo de viabilidade (MVP) com protótipo demonstrativo; mede acerto, tempo e custo.
- **Não é:** sistema para implantação; não escreve nem decide o TR; não terá manutenção depois de dez/2026.
- Só **dados públicos** (PNCP e Compras.gov.br). A busca não usa IA.

## Linha do tempo
| Data | Marco |
|---|---|
| 01/10 | Proposta apresentada à PMDF |
| 09–12/10 | 6 rodadas de sondagem das APIs e auditoria |
| 11/10 | Piloto com 5 TRs de notebook |
| 13–14/10 | Teste limpo com 10 TRs (gabarito da equipe) |
| 15/10 | Acompanhamento 1 com a PMDF; novas metas (preço homologado + link; ficha técnica do fabricante) |
| 22–28/10 | Ferramenta com menu → tela Streamlit (v1, v2, v3) → publicação online |
| 29/10 | Acompanhamento 2 com a PMDF |
| 10/12 | Relatório final (previsto) |

# 04 – Metodologia

Pesquisa aplicada, exploratória e comparativa: medir antes de construir.

## Etapas realizadas
1. **Sondagem das APIs (6 rodadas, 09–12/10):** testar fontes, campos e estabilidade; 1.852 chamadas registradas. Auditoria manual das conclusões do programa.
2. **Conferência humana das regras (Tarefas 2 e 3):** avaliar trechos que as regras marcaram como requisito e testar a busca manual no portal.
3. **Piloto (11/10):** 5 TRs de notebook; leitura manual × IA.
4. **Teste limpo (13–14/10):** 10 TRs de 6 itens; instrução e recortes feitos **antes** do gabarito.
5. **Construção incremental da ferramenta (22–28/10):** cada versão testada com o mesmo caso (PDM 8435, RAM 16, armazenamento 512, tela 15) e comparada com a anterior.
6. **Validação com a PMDF:** apresentações em 15/10 e 29/10; teste cego com servidor (previsto).

## Protocolo de medição da IA
- **Gabarito humano sem IA**, lendo o PDF inteiro.
- **IA às cegas:** cada IA recebe só o recorte e a mesma instrução, em conversa nova, sem ver o gabarito.
- **Divergência decidida pelo texto do PDF.**
- Campos objetivos: tipo, ano, lei, atributo, compatibilidade, garantia, prazo, marca. "Utilidade" fica fora.
- Contaminação: quem viu o gabarito não serve de leitor de teste.
- Resultado compara o **processo** (programa + IA × leitura manual do PDF inteiro), não a leitura isolada.

## Protocolo de verificação da ferramenta
- Toda afirmação de agente de código precisa de **prova** (número, arquivo, log): CONFERIDO × NÃO VERIFICADO.
- Versões isoladas (estável, v2, v3) para não perder o que funciona.
- Cada chamada à internet registrada em log.

## Limitações conhecidas
- Amostra pequena (15 documentos).
- Leitura manual feita pela equipe (estudantes), não por servidores.
- Recorte pode deixar página de fora; "não encontrado" deve ser conferido no PDF.
- Catálogo descreve por faixas: confirmação exata exige ler o TR.

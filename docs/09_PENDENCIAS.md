# 09 – Pendências (atualizado em 21/11/2026; as seções numeradas abaixo são de 31/10 e 01/11)

## Concluído em 21/11
- Varredura do repositório feita; histórico recriado com 1 commit limpo e publicado de novo (falta conferir outros repositórios públicos da conta); Pedido 18 (4 ajustes em Produto) e Pedidos 20 e 21 (testes, runner, nome do aviso) conferidos e testados ao vivo; app só em localhost; documentação da IA local com aviso de limites.

## Fazer agora
1. [ ] Apagar v4h\pedido14d\git_antigo e o zip de backup do repositório (têm e-mail pessoal).
2. [ ] Perguntas para a TI do órgão (não definir nós): arquitetura, rede e firewall; proxy reverso e HTTPS; contas e cadastro; Ollama como serviço; limite de chamadas ao PNCP com vários usuários; placa, VRAM e RAM; código de enquadramento de Microsoft 365 e XDR; se n=5 basta como referência.
3. [ ] Medir o estado de segurança do PC local (só leitura): quem escuta cada porta, variáveis do chat, firewall, conexões de saída, permissões de C:\_Ollama.
4. [ ] Regenerar o PDF da documentação da IA local a partir dos .md (o projeto não tem gerador) e registrar os novos hashes nos documentos internos.
5. [ ] Testar ao vivo a busca de compras do Serviço depois do Pedido 18.

## Decisões abertas
- ABRIR_V4H.bat abrir 127.0.0.1 em vez de localhost no navegador (estético).
- Causa de o código 350949 ser o único item com compras no 11248 e dos 26 valores R$0,00 no PNCP: NÃO VERIFICADA.
- Runner do Pedido 16 continua com o hash antigo de orcamento_tokens.csv (reprovaria).
- Repositório git privado para a v4h (sem texto de edital); mover as pastas pedido* para fora do código.

## Não verificado
- netstat da porta 8511; efeito real de OFFLINE_MODE; comportamento com 2 ou mais usuários.
- "Trocar WEBUI_SECRET_KEY desconecta usuários": retirado da documentação por falta de confirmação.

## Depois
- Juntar TRs de outros itens (antivírus/EDR/XDR, suíte de escritório, SaaS, banco de dados); Pedidos 14 e 15.
- Sonda J3/J4 em 22/11 (12h45 e 19h35); corrigir slides antigos para 26/11.

## 1. Dicionário e código do produto (necessidade relatada por um representante do órgão na apresentação de 29/10; validação do dicionário a confirmar)
- [x] Sinônimos e busca pelo radical (televisão → televisor; tv; nobreak) – v4 fase 1
- [ ] Equipe aprovar `config\sinonimos_SUGESTOES.csv` (coluna "aprovado"); até lá o app não usa essas sugestões
- [x] Não marcar código sozinho; ativos primeiro; desativados em cinza – v4 fase 2
- [x] Coluna "compras nos últimos 12 meses" por código; "configurações no catálogo" – v4 fase 2
- [x] Abrir configurações (itens CATMAT), filtrar e copiar o código – v4 fase 2
- [x] Perfil de atributos automático; aviso item × PDM; botão "Atualizar catálogo" – v4 fase 2
- [ ] Ampliar `config\perfis_pdm.csv` e `produtos.csv` (hoje: notebook, switch, câmera IP, nobreak, monitor)

## 2. Preço e conferência
- [x] Preço estimado × homologado + nº do item + link da compra com o item indicado – v4 fase 3
- [x] Investigar caso mouse (compra <NUMERO_COMPRA>, itens 41/42) – v4 fase 3: item 41 estimado R$ 45,17 × homologado R$ 15,73; item 42 estimado R$ 32,17 × homologado R$ 5,74; mesmos valores nas duas APIs
- [ ] Preço estimado × homologado (caso do mouse): estimado só aparece nas linhas ligadas ao PNCP: no modo rápido são poucas (limite de consultas)
- [ ] O link abre a página da compra e o texto indica o item; não foi verificado se o portal do PNCP tem endereço direto para cada item

## 3. IA
- [ ] Botão "Ler com IA" (Ollama, num_ctx ≥ 8192) com ficha e página
- [ ] Teste nos D01–D10 (local × online); híbrido script + IA

## 4. Tela e uso
- [x] Limpar resultados em nova busca; botão "Nova busca"; histórico recolhido – v4 fase 4
- [x] Cada usuário vê só as próprias buscas – v4 fase 4 (testado com duas abas no computador; falta testar na versão online)
- [ ] Levar a v4 para `referencia-tic-app` (versão online) depois da conferência da equipe: `app.py` (v4d) e `ferramenta.py` (v4e) já estão copiados na pasta local; falta o commit e conferir a versão online
- [x] Proteção de `caminho_do_word` (`os.name != "nt"` e `ImportError`) reaplicada na v4e e no `ferramenta.py` do repositório; a v4d não a tinha. Teste offline: mensagem amigável, sem exceção
- [ ] Testar o .doc antigo no Linux real (Streamlit Community Cloud): NÃO VERIFICADO
- [ ] Sessão por usuário online: testar na versão online que cada pessoa vê só as próprias buscas (só testado com duas abas no computador); apagar pastas antigas de `saida\sessoes\` (hoje ficam guardadas); uma busca espera a outra no servidor
- [x] Opção na tela "aceitar valores maiores" (RAM, disco, garantia) – v4 fase 3; a equipe decide se deve vir marcada; efeito medido em amostra de 300 de 1.448 registros (20,7%), busca interrompida aos 60 s: não atende 91 → 66, a confirmar 209 → 234
- [x] Rodada real com a v4c (modo rápido, 300 de 1.448 registros; 10 compras ligadas ao PNCP por rodada (15 e 27 linhas vinculadas)): terminou, 0 falhas, 121 s (ligada) e 112 s (desligada)
- [ ] Teste do Buscar com rede real na v4d, inclusive o modo completo (todos os 1.448 registros e mais de 10 compras ligadas ao PNCP)
- [ ] Tempo da rodada (112 a 121 s) × pausa de 3 s por chamada: a confirmar
- [ ] Causa dos 3 timeouts de 31/10 às 19:09 em .../compras/2026/10933/itens: a confirmar (a mesma URL deu 200 antes e depois)
- [x] Falha na etapa /itens do PNCP testada com falha injetada (ReadTimeout × 3): 9 de 9 – v4c
- [x] Autoteste fixa aceitar maiores = desligado (try/finally) e roda dentro da trava – v4b e v4c
- [x] Confirmar como as 300 linhas foram escolhidas: 3 primeiras páginas de 100, na ordem da API, sem parâmetro de ordenação (v4, ferramenta.py:949-961)
- [ ] Medir a duração das chamadas dentro do app (hoje só no script de teste)
- [ ] Visual pelo Figma da equipe
- [ ] Compatibilidade com o PC antigo de um membro da equipe (NumPy x86-64-v2)

## 5. Projeto
- [ ] Ficha técnica do fabricante (abordagem B)
- [ ] Teste cego com servidor do órgão
- [ ] Confirmar cronograma: 12/11 · 26/11 · 10/12
- [ ] Relatório final (ABNT / roteiro do professor)
- [ ] (superado em 21/11: histórico recriado com 1 commit limpo) Decidir nomes da equipe e do orientador no repositório público
- [ ] Link do app em README.md:5 × "uso restrito" em 07_SEGURANCA.md:9
- [ ] Atualizar 02_REQUISITOS (RF02, RF03, RF04, RF09, RF17, RF18, RF19) e 05_RESULTADOS (caso do mouse)
- [ ] Teste da tela: reproduzir o travamento na v4e (porta 8505) e repetir na v4f (8506); Buscar com rádio PDM e código de item deve avisar e não buscar. Causa do travamento NÃO confirmada.
- [ ] (superado em 21/11: histórico recriado com 1 commit limpo) Commit suspenso: main em 2bd7b01, nada commitado. Decidir: nomes em README.md e docs/01; config/sinonimos_SUGESTOES.csv (sem aprovação registrada); ABRIR_APP.bat (app.py:5 o cita; não está no repositório); link do app × "uso restrito" (07_SEGURANCA); "aceitar maiores" marcado por padrão; versão oficial. Commit só em branch nova, sem push no main.
- [ ] Limpeza: apagar o conteúdo de saida\sessoes da v4d e da v4f; mover HASHES_REFERENCIA.txt e o zip de backup de C:\_MVC para sondagem_v5ackups.
- [ ] Docs: faltam entradas da v4f e dos bugs (IndexError app.py:375, trava sem limite de espera, Buscar com tipo errado); docs/02 e 05 desatualizados.
- [ ] A confirmar: causa dos 3 timeouts do PNCP em 31/10 19:09; "1 min 58 s" da tela; tempo da rodada × pausa de 3 s; Linux real; modo completo (1.448); critério de "preço suspeito" (114 de 300 no código 14302); regra de atributos do nobreak.
- [ ] v4g (diagnóstico ainda não rodado): seleção de páginas por nome do item e sinônimos, orçamento de tokens, cabeçalho com o nome do catálogo, zip dentro de zip, aviso de mais de um item compatível, validação da ficha em código.
- [ ] Perguntar ao órgão: a IA precisa rodar local ou há alternativa aprovada? O que é "bom o suficiente" numa ficha rascunho?
- [ ] v4g, fase 0 (diagnóstico, só leitura) feita em 01/11: relatório em sondagem_v5\diagnostico_v4g\RELATORIO.md. Medições numa amostra de OUTRO edital (69 páginas); o PDF do edital 90019/2026 não está no disco, então blocos por lote/item no 90019: NÃO VERIFICADO.
- [ ] v4g, achados com número: a seleção de páginas usa regex sem limite de palavra (18 de 69 páginas da amostra acertam só no meio de outra palavra); o orçamento atual é por páginas (MAX_PAG=16 ≈ 10,3 mil tokens a 3,1 car./token) e a estimativa do código usa 4 car./token; não existe validação da ficha nem tratamento de zip dentro de zip.
- [ ] v4g, decisões pendentes: tolerância do "conferir" (0,90 vem de 4 casos); orçamento de 8.000 tokens só da entrada ou com a saída (num_ctx 8192 × 16384); OCR dentro ou fora; fornecer o PDF do 90019 e o gabarito manual; regra "item no trecho" para garantia e prazo; IA no app ou só em script.
- [ ] PNCP, fase A (01/11, só leitura; relatório em sondagem_v5\diagnostico_pncp\RELATORIO.md): 31/10 = 429 chamadas ao PNCP e 3 falhas (ReadTimeout, 19:09); 01/11 = 124 chamadas e 20 falhas (10 ReadTimeout, 7 HTTP 503, 1 HTTP 502, 2 ConnectionError), em 10:47-10:52 e 12:08-12:38. Causa NÃO confirmada (HIPÓTESE: instabilidade do PNCP); sem teste de rede.
- [ ] A busca das 12:39 rodou na porta 8504 com o app_streamlit_v4 original (sem a tolerância a falha da v4c): a ligação parou na 1ª falha e 66 de 67 linhas ficaram sem situação. Decidir qual versão ocupa a 8504.
- [ ] Registro a melhorar (proposta, não implementada): tempo de cada chamada no log, modo/limites/versão no resumo, motivo de "não verificado"/"sem PNCP"/"falhou" no CSV; mensagem "download concluído" aparece mesmo com timeout (app.py:754); sem aviso explícito quando o modo rápido corta em 300 linhas.
- [ ] Teste de rede para 03/11 (proposto, não executado; precisa de autorização e teto de chamadas): sonda de estabilidade em 3 janelas (30 chamadas no total) e busca PDM 8435 UF DF na v4f, modo rápido e completo.

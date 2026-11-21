# Referência TIC – busca de compras públicas de TIC

Projeto acadêmico (UnDF / PMDF). Busca compras públicas de TIC no **PNCP** e no **Compras.gov.br**, marca se cada item
atende aos atributos pedidos, baixa os documentos da compra e monta um texto pronto para colar numa IA.

- Só dados públicos, só leitura (GET), sem login e sem chave de API.
- A busca e os filtros são regras fixas, **sem IA**. O resultado apoia a decisão; não substitui a pesquisa de preços
  formal da Lei 14.133/2021.

## Como usar

1. **O que você procura?** Digite o produto (ex.: notebook, laptop, nobreak, monitor 24) e clique em
   "Procurar no catálogo". Marque um ou mais códigos do catálogo oficial de materiais (PDM).
2. Preencha os atributos (só o número, na unidade indicada) e clique em **Buscar**.
3. Na tabela, a coluna "avaliação" mostra cada atributo (atende / parcial / não atende / não informado).
   "Parcial" = a confirmar no Termo de Referência.
4. Escolha uma linha para baixar os documentos da compra e gerar o texto para a IA.

## Rodar no computador

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt      (Linux/Mac: .venv/bin/python)
.venv\Scripts\python -m streamlit run app.py
```

Os resultados ficam em `saida/` (criada na primeira execução; não vai para o repositório).

## Publicar na Streamlit Community Cloud

- Arquivo principal: `app.py`. Python 3.11 ou mais novo (testado no 3.14).
- Na nuvem os arquivos de `saida/` são temporários (somem quando o app reinicia). Use o botão de baixar CSV/texto.
- Arquivo `.doc` antigo do Word: na nuvem não há Word, então a tela só avisa. Arquivos `.docx` e PDF funcionam.

## Arquivos

| Arquivo | Para quê |
|---|---|
| `app.py` | tela (Streamlit) |
| `ferramenta.py` | regras da busca, filtros, downloads e recorte (também tem um menu em texto: `python ferramenta.py`) |
| `recorte_teste_ia.py` | escolhe as páginas do item no documento |
| `config/produtos.csv` | produtos, atributos e faixas aceitas (editável) |
| `config/sinonimos.csv` | sinônimos da busca no catálogo (editável) |
| `config/catalogo_pdm.csv` | catálogo oficial de PDMs de materiais (Compras.gov.br), com a data do download |
| `config/INSTRUCAO_FICHA.txt` | instrução que vai junto com o texto para a IA |

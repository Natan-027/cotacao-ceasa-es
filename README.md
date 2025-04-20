# Cotações CEASA Grande Vitória

Este repositório contém uma aplicação web simples para exibir as cotações de preços do CEASA Grande Vitória.

## Funcionalidades

- Exibição de tabela com cotações de preços atualizadas
- Download dos dados em formato PDF e CSV
- Atualização automática diária às 11h (horário do Brasil)
- Botão para atualização manual dos dados

## Tecnologias Utilizadas

- Python com Flask para o backend
- Bootstrap e DataTables para a interface
- SQLite para armazenamento de dados
- Selenium para extração de dados

## Implantação no Render.com

1. Faça fork deste repositório para sua conta GitHub
2. Acesse o [Render.com](https://render.com/) e crie uma conta (ou faça login)
3. Clique em "New" e selecione "Web Service"
4. Conecte sua conta GitHub e selecione este repositório
5. Configure as seguintes opções:
   - **Name**: ceasa-cotacoes (ou outro nome de sua preferência)
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
6. Clique em "Create Web Service"

## Desenvolvimento Local

Para executar a aplicação localmente:

1. Clone este repositório
2. Instale as dependências: `pip install -r requirements.txt`
3. Execute a aplicação: `python app.py`
4. Acesse http://localhost:5000 no seu navegador

## Estrutura do Projeto

- `app.py`: Aplicação Flask principal
- `ceasa_scraper.py`: Script para extração de dados
- `templates/`: Arquivos HTML
- `requirements.txt`: Dependências do projeto

# CEASA-ES Scraper Flask App

Este projeto contém uma aplicação Flask que realiza web scraping no site do CEASA-ES para obter as cotações de preços mais recentes.

## Funcionalidades

- Acessa o site do CEASA-ES usando Playwright para simular a interação do usuário.
- Seleciona "CEASA GRANDE VITÓRIA" e a data mais recente disponível.
- Extrai a tabela de preços da página de resultados.
- Processa os dados usando Pandas.
- Salva os dados processados em um arquivo JSON (`ceasa_data.json`).
- Gera uma página HTML (`ceasa_tabela.html`) com a tabela formatada para exibição.
- A aplicação Flask serve a página HTML na rota raiz (`/`) e os dados JSON na rota `/data.json`.
- O scraping é realizado sob demanda sempre que a rota raiz (`/`) é acessada.

## Arquivos Principais

- `app.py`: O código principal da aplicação Flask.
- `requirements.txt`: As dependências Python necessárias.
- `process_html.py`: Script auxiliar usado durante o desenvolvimento para processar HTML (a lógica principal está agora em `app.py`).
- `ceasa_data.json`: Exemplo de arquivo de dados JSON gerado.
- `ceasa_tabela.html`: Exemplo de arquivo HTML gerado.
- `post_response.html`: Exemplo do HTML bruto da página de resultados (para depuração).
- `table_debug.html`: Exemplo do HTML da tabela extraída (para depuração).

## Como Executar Localmente

1.  **Crie um ambiente virtual (recomendado):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate  # Windows
    ```
2.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Instale os navegadores Playwright (necessário apenas na primeira vez):**
    ```bash
    playwright install --with-deps chromium
    ```
4.  **Execute a aplicação Flask:**
    ```bash
    python app.py
    ```
5.  Acesse `http://127.0.0.1:8080` (ou a porta definida) no seu navegador.

## Como Implantar no Render.com

1.  **Faça o upload deste projeto para um repositório GitHub.**
2.  **Crie um novo "Web Service" no Render.com.**
3.  **Conecte seu repositório GitHub.**
4.  **Configure as definições de build e start:**
    -   **Build Command:** `pip install -r requirements.txt && playwright install --with-deps chromium`
    -   **Start Command:** `python app.py`
5.  **Certifique-se de que o Render detecta que é uma aplicação Python.**
6.  **Implante o serviço.** O Render instalará as dependências, incluindo o Playwright e o Chromium, e iniciará a aplicação Flask.

**Observação:** A primeira requisição após a implantação ou após um período de inatividade pode demorar um pouco mais, pois o serviço precisa iniciar e o processo de scraping precisa ser executado.


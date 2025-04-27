# app.py
import sys
sys.path.append("/opt/.manus/.sandbox-runtime")
from flask import Flask, send_file, render_template_string, Response
from playwright.sync_api import sync_playwright
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
import traceback
from datetime import datetime
import json
import os
import logging

# --- Configuration ---
HTML_INPUT_FILE = "post_response.html" # Temporary file for browser HTML
DATA_FILE = "ceasa_data.json"
HTML_OUTPUT_FILE = "ceasa_tabela.html"
FILTER_URL = "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php"
TARGET_MARKET_NAME = "CEASA GRANDE VITÓRIA"
TARGET_MARKET_OPTION_INDEX = 1 # Index for CEASA GRANDE VITÓRIA in the dropdown
LATEST_DATE_OPTION_INDEX = 1 # Index for the latest date in the dropdown
MARKET_SELECT_INDEX = 3 # Browser index for market dropdown
DATE_SELECT_INDEX = 4 # Browser index for date dropdown
OK_BUTTON_INDEX = 5 # Browser index for the OK button

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- Helper Functions (from process_html.py, adapted) ---
def process_html_data(html_content):
    app.logger.info("Processando dados do HTML extraído...")
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Parse the result table
        app.logger.info("Procurando tabela de dados no HTML...")
        tables = soup.find_all("table")
        app.logger.info(f"Encontradas {len(tables)} tabelas.")

        data_table = None
        # Look for the table within div#sc_grid_body or with specific content
        grid_body_div = soup.find("div", id="sc_grid_body")
        if grid_body_div:
            data_table = grid_body_div.find("table", class_="scGridTabela")
            if data_table:
                app.logger.info("Tabela encontrada via div#sc_grid_body > table.scGridTabela")
        
        if not data_table:
             # Fallback: Look for table with border=1 and specific text
            for i, table in enumerate(tables):
                if table.get("border") == "1" and "Produtos" in table.text:
                    app.logger.info(f"Tabela de dados encontrada por fallback (índice {i}).")
                    data_table = table
                    break

        if not data_table:
            app.logger.error("ERRO: Tabela de dados não encontrada no HTML.")
            return None, None

        # Use pandas to read the HTML table
        try:
            table_html = str(data_table)
            # app.logger.debug(f"Table HTML: {table_html[:500]}") # Log start of table HTML if needed
            
            # Read table, ensure correct decimal parsing
            df_list = pd.read_html(StringIO(table_html), header=0, decimal=",", thousands=".")

            if not df_list:
                app.logger.error("ERRO: pandas não conseguiu ler nenhuma tabela do HTML encontrado.")
                return None, None

            df = df_list[0]
            app.logger.info(f"Dados extraídos com sucesso. {len(df)} linhas.")
            original_cols = df.columns.tolist()
            app.logger.info(f"Colunas detectadas: {original_cols}")

            # Clean and rename columns
            df = df.dropna(how="all")
            expected_cols = ["Produtos", "Embalagem", "MIN", "M.C.", "MAX", "Situação"]
            if len(original_cols) == len(expected_cols):
                last_col_name = original_cols[-1]
                rename_map = {
                    original_cols[0]: "Produtos",
                    original_cols[1]: "Embalagem",
                    original_cols[2]: "MIN",
                    original_cols[3]: "M.C.",
                    original_cols[4]: "MAX",
                    last_col_name: "Situação"
                }
                df.rename(columns=rename_map, inplace=True)
                app.logger.info(f"Colunas renomeadas para: {df.columns.tolist()}")
            else:
                 app.logger.warning(f"Número de colunas ({len(df.columns)}) não corresponde ao esperado ({len(expected_cols)}).")

            df = df.dropna(subset=["MIN", "M.C.", "MAX"], how="all")
            app.logger.info(f"Linhas após limpeza inicial: {len(df)}")

            price_cols = ["MIN", "M.C.", "MAX"]
            for col in price_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            app.logger.info(f"Tipos de dados após conversão: \n{df.dtypes}")

            timestamp = datetime.now().isoformat()
            bulletin_date_str = "Não encontrada"
            # Extract date from page title or header (more robustly)
            title_tag = soup.find("title")
            header_td = soup.find("td", class_="scGridLabel") # Common in ScriptCase
            date_info = soup.find(lambda tag: tag.name == "td" and "Data Pesquisada:" in tag.get_text())
            
            if date_info:
                 try:
                    bulletin_date_str = date_info.get_text().split("Data Pesquisada:")[1].split("Mercado:")[0].strip()
                    app.logger.info(f"Data do boletim extraída da página: {bulletin_date_str}")
                 except Exception as e:
                    app.logger.warning(f"Não foi possível extrair data do boletim da tag TD: {e}")
            elif header_td and "Data Pesquisada:" in header_td.text:
                 try:
                    bulletin_date_str = header_td.get_text().split("Data Pesquisada:")[1].split("Mercado:")[0].strip()
                    app.logger.info(f"Data do boletim extraída da tag TD.scGridLabel: {bulletin_date_str}")
                 except Exception as e:
                    app.logger.warning(f"Não foi possível extrair data do boletim da tag TD.scGridLabel: {e}")
            elif title_tag and "Data Pesquisada:" in title_tag.text:
                 try:
                    bulletin_date_str = title_tag.get_text().split("Data Pesquisada:")[1].split("Mercado:")[0].strip()
                    app.logger.info(f"Data do boletim extraída da tag TITLE: {bulletin_date_str}")
                 except Exception as e:
                    app.logger.warning(f"Não foi possível extrair data do boletim da tag TITLE: {e}")
            else:
                app.logger.warning("Não foi possível encontrar a data do boletim na página.")

            # Store data as JSON
            data_to_store = {
                "timestamp": timestamp,
                "market": TARGET_MARKET_NAME,
                "bulletin_date": bulletin_date_str,
                "data": df.to_dict(orient="records")
            }
            try:
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data_to_store, f, ensure_ascii=False, indent=4)
                app.logger.info(f"Dados salvos em {DATA_FILE}")
            except Exception as e:
                app.logger.error(f"Erro ao salvar arquivo JSON {DATA_FILE}: {e}")
                return None, None

            # Create simple HTML table for display
            html_content_output = f"""
            <!DOCTYPE html>
            <html lang="pt-BR">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Cotação CEASA-ES ({TARGET_MARKET_NAME})</title>
                <style>
                    body {{ font-family: sans-serif; margin: 0; padding: 10px; background-color: #f8f9fa; }}
                    h2 {{ color: #343a40; text-align: center; margin-bottom: 15px; }}
                    .table-container {{ max-width: 100%; overflow-x: auto; background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    table {{ border-collapse: collapse; width: 100%; margin-top: 0; }}
                    th, td {{ border: 1px solid #dee2e6; padding: 8px 10px; text-align: left; font-size: 0.9em; }}
                    th {{ background-color: #e9ecef; color: #495057; font-weight: bold; }}
                    tr:nth-child(even) {{ background-color: #f8f9fa; }}
                    tr:hover {{ background-color: #e2e6ea; }}
                    caption {{ caption-side: bottom; padding-top: 12px; font-size: 0.85em; color: #6c757d; text-align: center; }}
                    .container {{ max-width: 1200px; margin: 10px auto; }}
                    td:nth-child(3), td:nth-child(4), td:nth-child(5) {{ text-align: right; }}
                    th:nth-child(3), th:nth-child(4), th:nth-child(5) {{ text-align: right; }}
                    a {{ color: #007bff; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>Cotação CEASA-ES - {TARGET_MARKET_NAME}</h2>
                    <div class="table-container">
                        {df.to_html(index=False, escape=False, float_format="%.2f", na_rep="", classes="dataframe")}
                    </div>
                    <caption>Dados atualizados em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")} (Data do boletim: {bulletin_date_str})<br>Fonte: <a href="{FILTER_URL}" target="_blank">CEASA-ES</a></caption>
                </div>
            </body>
            </html>
            """
            try:
                with open(HTML_OUTPUT_FILE, "w", encoding="utf-8") as f:
                    f.write(html_content_output)
                app.logger.info(f"Tabela HTML salva em {HTML_OUTPUT_FILE}")
            except Exception as e:
                app.logger.error(f"Erro ao salvar arquivo HTML {HTML_OUTPUT_FILE}: {e}")
                return None, None

            return DATA_FILE, HTML_OUTPUT_FILE

        except Exception as e:
            app.logger.error(f"Erro ao processar tabela com pandas: {e}")
            traceback.print_exc()
            return None, None

    except Exception as e:
        app.logger.error(f"Ocorreu um erro inesperado ao processar o HTML: {e}")
        traceback.print_exc()
        return None, None

# --- Scraping Function ---
def scrape_ceasa_data():
    app.logger.info("Iniciando scraping com Playwright...")
    html_content = None
    try:
        with sync_playwright() as p:
            # Launch browser - use args for Render compatibility
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            page = browser.new_page()
            app.logger.info(f"Navegando para {FILTER_URL}")
            page.goto(FILTER_URL, timeout=60000) # Increased timeout
            app.logger.info("Página carregada. Selecionando opções...")
            
            # Select Market
            page.locator(f"select").nth(MARKET_SELECT_INDEX - 1).select_option(index=TARGET_MARKET_OPTION_INDEX)
            app.logger.info(f"Mercado selecionado: {TARGET_MARKET_NAME}")
            page.wait_for_timeout(1000) # Wait for potential dynamic loading
            
            # Select Date (latest)
            page.locator(f"select").nth(DATE_SELECT_INDEX - 1).select_option(index=LATEST_DATE_OPTION_INDEX)
            app.logger.info("Data mais recente selecionada.")
            page.wait_for_timeout(500)
            
            # Click OK
            app.logger.info("Clicando no botão OK...")
            # Use a more robust selector if index fails
            ok_button_selector = f":nth-match(a:has-text(\"Ok\"), {OK_BUTTON_INDEX})"
            page.locator(ok_button_selector).click()
            
            app.logger.info("Aguardando navegação para a página de resultados...")
            page.wait_for_load_state("networkidle", timeout=60000) # Wait for network to be idle
            app.logger.info(f"Página de resultados carregada: {page.url}")
            
            # Get HTML content
            html_content = page.content()
            app.logger.info("Conteúdo HTML da página de resultados obtido.")
            
            browser.close()
            
    except Exception as e:
        app.logger.error(f"Erro durante o scraping com Playwright: {e}")
        traceback.print_exc()
        return None # Indicate failure

    return html_content

# --- Flask Routes ---
@app.route("/")
def get_data():
    app.logger.info("Recebida requisição para /")
    
    # 1. Scrape data using Playwright
    html_content = scrape_ceasa_data()
    
    if not html_content:
        # Try to return last known good data if scraping fails
        if os.path.exists(HTML_OUTPUT_FILE):
            app.logger.warning("Scraping falhou. Servindo último arquivo HTML válido.")
            try:
                return send_file(HTML_OUTPUT_FILE)
            except Exception as e:
                 app.logger.error(f"Erro ao servir arquivo HTML existente {HTML_OUTPUT_FILE}: {e}")
                 return "Erro ao obter dados do CEASA e ao servir dados antigos.", 500
        else:
            app.logger.error("Scraping falhou e não há dados antigos para servir.")
            return "Erro ao obter dados do CEASA.", 500

    # 2. Process the scraped HTML
    data_file, html_file = process_html_data(html_content)

    if not html_file:
        app.logger.error("Processamento do HTML falhou.")
        return "Erro ao processar os dados do CEASA.", 500

    # 3. Return the generated HTML file
    try:
        return send_file(html_file)
    except Exception as e:
        app.logger.error(f"Erro ao servir arquivo HTML gerado {html_file}: {e}")
        return "Erro ao servir os dados processados.", 500

@app.route("/data.json")
def get_json_data():
    app.logger.info("Recebida requisição para /data.json")
    if os.path.exists(DATA_FILE):
        try:
            return send_file(DATA_FILE, mimetype="application/json")
        except Exception as e:
            app.logger.error(f"Erro ao servir arquivo JSON {DATA_FILE}: {e}")
            return "Erro ao servir arquivo JSON.", 500
    else:
        # Optionally trigger scraping if JSON doesn't exist?
        # For now, just return error if file is missing.
        app.logger.error(f"Arquivo JSON {DATA_FILE} não encontrado.")
        return "Arquivo de dados JSON não encontrado.", 404

if __name__ == "__main__":
    # Run Flask app - listen on all interfaces for Render compatibility
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


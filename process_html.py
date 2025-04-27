#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# process_html.py
import sys
sys.path.append("/opt/.manus/.sandbox-runtime")
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO
import traceback
from datetime import datetime
import json
import os

HTML_INPUT_FILE = "post_response.html" # File containing the HTML from browser
DATA_FILE = "ceasa_data.json"
HTML_OUTPUT_FILE = "ceasa_tabela.html"
FILTER_URL = "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php"
TARGET_MARKET_NAME = "CEASA GRANDE VITÓRIA"

def process_html_data():
    print(f"Processando dados do arquivo HTML: {HTML_INPUT_FILE}")
    try:
        # 1. Read the HTML content from the file
        with open(HTML_INPUT_FILE, "r", encoding="windows-1252") as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, "html.parser")

        # 2. Parse the result table
        print("Procurando tabela de dados no HTML...")
        tables = soup.find_all("table")
        print(f"Encontradas {len(tables)} tabelas.")

        data_table = None
        for i, table in enumerate(tables):
            if table.get("border") == "1" and "Produtos" in table.text:
                print(f"Tabela de dados encontrada (índice {i}).")
                data_table = table
                break

        if not data_table:
            print("ERRO: Tabela de dados não encontrada no HTML.")
            return None, None

        # 3. Use pandas to read the HTML table
        try:
            table_html = str(data_table)
            with open("table_debug.html", "w", encoding="windows-1252") as f:
                f.write(table_html)
            print("HTML da tabela salvo em table_debug.html")
            
            # Read table, ensure correct decimal parsing
            df_list = pd.read_html(StringIO(table_html), header=0, decimal=",", thousands=".")

            if not df_list:
                print("ERRO: pandas não conseguiu ler nenhuma tabela do HTML encontrado.")
                return None, None

            df = df_list[0]
            print(f"Dados extraídos com sucesso. {len(df)} linhas.")
            # Check column name for Situação (encoding issue)
            original_cols = df.columns.tolist()
            print(f"Colunas detectadas: {original_cols}")

            # Clean and rename columns
            df = df.dropna(how="all")
            expected_cols = ["Produtos", "Embalagem", "MIN", "M.C.", "MAX", "Situação"]
            # Handle potential encoding issue in 'Situação' column name
            if len(original_cols) == len(expected_cols):
                # Find the actual name of the last column
                last_col_name = original_cols[-1]
                rename_map = {
                    original_cols[0]: "Produtos",
                    original_cols[1]: "Embalagem",
                    original_cols[2]: "MIN",
                    original_cols[3]: "M.C.",
                    original_cols[4]: "MAX",
                    last_col_name: "Situação" # Use the detected name
                }
                df.rename(columns=rename_map, inplace=True)
                print(f"Colunas renomeadas para: {df.columns.tolist()}")
            else:
                 print(f"AVISO: Número de colunas ({len(df.columns)}) não corresponde ao esperado ({len(expected_cols)}). Verifique table_debug.html.")

            # Remove potential grouping rows
            df = df.dropna(subset=["MIN", "M.C.", "MAX"], how="all")
            print(f"Linhas após limpeza inicial: {len(df)}")

            # Convert price columns to numeric (should be float now due to decimal=",")
            price_cols = ["MIN", "M.C.", "MAX"]
            for col in price_cols:
                if col in df.columns:
                    # Ensure conversion to numeric, coercing errors
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            print("Tipos de dados após conversão:")
            print(df.dtypes)

            # Add timestamp and metadata
            timestamp = datetime.now().isoformat()
            bulletin_date_str = "Não encontrada"
            date_p = soup.find(lambda tag: tag.name == "p" and "Data Pesquisada:" in tag.get_text())
            if date_p:
                try:
                    bulletin_date_str = date_p.get_text().split("Data Pesquisada:")[1].strip()
                    print(f"Data do boletim extraída da página: {bulletin_date_str}")
                except Exception as e:
                    print(f"Não foi possível extrair data do boletim da tag <p>: {e}")
            else:
                print("Não foi possível encontrar a tag <p> com a data do boletim.")

            # Store data as JSON
            data_to_store = {
                "timestamp": timestamp,
                "market": TARGET_MARKET_NAME,
                "bulletin_date": bulletin_date_str,
                "data": df.to_dict(orient="records")
            }
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data_to_store, f, ensure_ascii=False, indent=4)
            print(f"Dados salvos em {DATA_FILE}")

            # Create simple HTML table for display with correct float formatting
            html_content_output = f"""
            <html>
            <head>
                <title>Cotação CEASA-ES ({TARGET_MARKET_NAME})</title>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: sans-serif; margin: 0; padding: 20px; }}
                    h2 {{ color: #2c3e50; text-align: center; }}
                    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; color: #333; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    tr:hover {{ background-color: #f1f1f1; }}
                    caption {{ caption-side: bottom; padding-top: 10px; font-size: 0.9em; color: #555; }}
                    .container {{ max-width: 1200px; margin: 0 auto; }}
                    /* Align numeric columns to the right */
                    td:nth-child(3), td:nth-child(4), td:nth-child(5) {{ text-align: right; }}
                    th:nth-child(3), th:nth-child(4), th:nth-child(5) {{ text-align: right; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>Cotação CEASA-ES - {TARGET_MARKET_NAME}</h2>
                    {df.to_html(index=False, escape=False, float_format="%.2f", na_rep="", classes="dataframe")}
                    <caption>Dados atualizados em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")} (Data do boletim: {bulletin_date_str})<br>Fonte: <a href="{FILTER_URL}" target="_blank">CEASA-ES</a></caption>
                </div>
            </body>
            </html>
            """
            with open(HTML_OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(html_content_output)
            print(f"Tabela HTML salva em {HTML_OUTPUT_FILE}")

            return DATA_FILE, HTML_OUTPUT_FILE

        except Exception as e:
            print(f"Erro ao processar tabela com pandas: {e}")
            traceback.print_exc()
            return None, None

    except FileNotFoundError:
        print(f"ERRO: Arquivo HTML de entrada não encontrado: {HTML_INPUT_FILE}")
        return None, None
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao processar o HTML: {e}")
        traceback.print_exc()
        return None, None

if __name__ == "__main__":
    if not os.path.exists(HTML_INPUT_FILE):
        print(f"ERRO: O arquivo {HTML_INPUT_FILE} não existe. Execute a extração do HTML do navegador primeiro.")
    else:
        data_file, html_file = process_html_data()
        if data_file and html_file:
            print("\n--- Processamento do HTML concluído com sucesso ---")
            print(f"Arquivo de dados: {os.path.abspath(data_file)}")
            print(f"Arquivo HTML: {os.path.abspath(html_file)}")
        else:
            print("\n--- Processamento do HTML falhou ---")


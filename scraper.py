# scraper.py
import sys
sys.path.append("/opt/.manus/.sandbox-runtime")
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO
import traceback
from datetime import datetime
import json
import os

DATA_FILE = "ceasa_data.json"
HTML_FILE = "ceasa_tabela.html"
BASE_URL = "http://200.198.51.71/detec/"
FILTER_URL = BASE_URL + "filtro_boletim_es/filtro_boletim_es.php"
POST_URL = BASE_URL + "boletim_completo_es/boletim_completo_es.php"
TARGET_MARKET_NAME = "CEASA GRANDE VITÓRIA"
TARGET_MARKET_VALUE = "211"
# LATEST_DATE_VALUE = "20250425" # Removing date for this attempt
MARKET_PARAM_NAME = "mercado"
# DATE_PARAM_NAME = "datas"

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
    "Referer": FILTER_URL,
    "Content-Type": "application/x-www-form-urlencoded"
}

def get_latest_data():
    print(f"Iniciando busca de dados para {TARGET_MARKET_NAME} (tentando sem data específica)")
    session = requests.Session()
    session.headers.update(headers)

    try:
        # 1. GET request to get the form page and extract hidden fields and session tokens
        print(f"Fazendo requisição GET para {FILTER_URL} para obter campos ocultos e tokens de sessão...")
        response_get = session.get(FILTER_URL, timeout=30)
        response_get.raise_for_status()
        response_get.encoding = 'windows-1252'
        soup_get = BeautifulSoup(response_get.text, 'html.parser')

        # Extract hidden input fields
        hidden_inputs = {}
        for hidden_input in soup_get.find_all("input", {"type": "hidden"}):
            name = hidden_input.get("name")
            value = hidden_input.get("value", "")
            if name:
                hidden_inputs[name] = value
        
        print(f"Encontrados {len(hidden_inputs)} campos ocultos únicos.")

        # 2. Construct nmgp_parms with ONLY market parameter
        nmgp_parms_value = f"{MARKET_PARAM_NAME}?#?{TARGET_MARKET_VALUE}?@?"
        print(f"Construído nmgp_parms: {nmgp_parms_value}")

        # 3. Prepare payload with nmgp_parms and other necessary hidden fields
        payload = {
            "nmgp_parms": nmgp_parms_value,
            "script_case_init": hidden_inputs.get("script_case_init", ""),
            "script_case_session": hidden_inputs.get("script_case_session", ""),
            "csrf_token": hidden_inputs.get("csrf_token", ""),
            "nm_form_submit": hidden_inputs.get("nm_form_submit", "1"),
            "bok": hidden_inputs.get("bok", "OK"),
            "nmgp_opcao": "pesq"
        }
        
        payload = {k: v for k, v in payload.items() if v is not None}

        print(f"Fazendo requisição POST para {POST_URL} com {len(payload)} parâmetros...")
        response_post = session.post(POST_URL, data=payload, timeout=60)
        response_post.raise_for_status()
        response_post.encoding = 'windows-1252'
        soup_post = BeautifulSoup(response_post.text, 'html.parser')
        print(f"Status Code POST: {response_post.status_code}")

        with open("post_response.html", "w", encoding='windows-1252') as f:
            f.write(response_post.text)
        print("Resposta POST salva em post_response.html")

        if "Erro ao acessar o banco de dados" in response_post.text or "Incorrect syntax" in response_post.text:
            print("ERRO: Resposta POST contém mensagem de erro do banco de dados.")
            error_message = soup_post.find(class_="scErrorMessage")
            if error_message:
                print(f"Mensagem de erro: {error_message.get_text(strip=True)}")
            return None, None

        # 4. Parse the result table
        print("Procurando tabela de dados na resposta POST...")
        tables = soup_post.find_all('table')
        print(f"Encontradas {len(tables)} tabelas na página de resultados.")

        data_table = None
        for i, table in enumerate(tables):
            if 'Produto' in table.text and 'Embalagem' in table.text and 'Situação' in table.text:
                if 'AGRIAO' in table.text or 'ALFACE' in table.text:
                    print(f"Tabela de dados encontrada (índice {i}).")
                    data_table = table
                    break

        if not data_table:
            print("ERRO: Tabela de dados não encontrada na resposta POST.")
            return None, None

        # 5. Use pandas to read the HTML table
        try:
            table_html = str(data_table)
            with open("table_debug.html", "w", encoding='windows-1252') as f:
                f.write(table_html)
            print("HTML da tabela salvo em table_debug.html")
            
            df_list = pd.read_html(StringIO(table_html), header=0)

            if not df_list:
                print("ERRO: pandas não conseguiu ler nenhuma tabela do HTML encontrado.")
                return None, None

            df = df_list[0]
            print(f"Dados extraídos com sucesso. {len(df)} linhas.")
            print(f"Colunas detectadas: {df.columns.tolist()}")

            df = df.dropna(how='all')
            expected_cols = ['Produto', 'Embalagem', 'MIN', 'M.C.', 'MAX', 'Situação']
            if len(df.columns) == len(expected_cols):
                df.columns = expected_cols
                print("Colunas renomeadas para padrão esperado.")
            else:
                 header_row_index = -1
                 for idx, row in df.iterrows():
                     if 'Produto' in str(row.iloc[0]):
                         header_row_index = idx
                         break
                 if header_row_index != -1:
                     new_header = df.iloc[header_row_index]
                     df = df[header_row_index + 1:]
                     df.columns = new_header
                     print(f"Cabeçalho encontrado na linha {header_row_index} e aplicado.")
                 else:
                    print(f"AVISO: Número de colunas ({len(df.columns)}) ou cabeçalho não corresponde ao esperado. Verifique table_debug.html.")

            price_cols = ['MIN', 'M.C.', 'MAX']
            for col in price_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.', regex=False), errors='coerce')

            timestamp = datetime.now().isoformat()
            # Try to extract bulletin date from the page
            bulletin_date_str = "Não encontrada"
            date_info = soup_post.find(lambda tag: tag.name == 'td' and 'Data Pesquisada:' in tag.get_text())
            if date_info:
                try:
                    bulletin_date_str = date_info.get_text().split('Data Pesquisada:')[1].split('Mercado:')[0].strip()
                    print(f"Data do boletim extraída da página: {bulletin_date_str}")
                except Exception as e:
                    print(f"Não foi possível extrair data do boletim da página: {e}")
            else:
                print("Não foi possível encontrar a data do boletim na página.")

            data_to_store = {
                'timestamp': timestamp,
                'market': TARGET_MARKET_NAME,
                'bulletin_date': bulletin_date_str,
                'data': df.to_dict(orient='records')
            }
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_to_store, f, ensure_ascii=False, indent=4)
            print(f"Dados salvos em {DATA_FILE}")

            html_content = f"""
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
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>Cotação CEASA-ES - {TARGET_MARKET_NAME}</h2>
                    {df.to_html(index=False, escape=False, float_format='%.2f', na_rep='', classes='dataframe')}
                    <caption>Dados atualizados em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} (Data do boletim: {bulletin_date_str})<br>Fonte: <a href="{FILTER_URL}" target="_blank">CEASA-ES</a></caption>
                </div>
            </body>
            </html>
            """
            with open(HTML_FILE, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"Tabela HTML salva em {HTML_FILE}")

            return DATA_FILE, HTML_FILE

        except Exception as e:
            print(f"Erro ao processar tabela com pandas: {e}")
            traceback.print_exc()
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"Erro de requisição: {e}")
        traceback.print_exc()
        return None, None
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")
        traceback.print_exc()
        return None, None

if __name__ == "__main__":
    data_file, html_file = get_latest_data()
    if data_file and html_file:
        print("\n--- Scraping concluído com sucesso ---")
        print(f"Arquivo de dados: {os.path.abspath(data_file)}")
        print(f"Arquivo HTML: {os.path.abspath(html_file)}")
    else:
        print("\n--- Scraping falhou ---")


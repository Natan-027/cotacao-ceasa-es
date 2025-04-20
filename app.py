from flask import Flask, render_template, jsonify, send_file, request
import os
import pandas as pd
from datetime import datetime
import subprocess
import threading
import time
import json
import logging
import io
import sqlite3
from fpdf import FPDF
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Diretório onde os dados são armazenados
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_ceasa")
os.makedirs(DATA_DIR, exist_ok=True)

# Caminho para o banco de dados SQLite
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ceasa_db.sqlite")

# Função para executar a extração de dados
def executar_extracao():
    try:
        logger.info("Iniciando extração de dados...")
        resultado = extrair_dados_ceasa()
        if resultado:
            logger.info(f"Extração concluída com sucesso. {resultado['quantidade_produtos']} produtos extraídos.")
            return True
        else:
            logger.error("Falha na extração de dados.")
            return False
    except Exception as e:
        logger.error(f"Erro na extração: {str(e)}")
        return False

# Função para inicializar o banco de dados SQLite
def inicializar_banco_dados():
    """Inicializa o banco de dados SQLite se não existir."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Criar tabela de produtos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto TEXT NOT NULL,
        unidade TEXT NOT NULL,
        preco_min REAL NOT NULL,
        preco_medio REAL NOT NULL,
        preco_max REAL NOT NULL,
        data_pesquisa TEXT NOT NULL,
        mercado TEXT NOT NULL,
        data_extracao TEXT NOT NULL
    )
    ''')
    
    # Criar tabela de histórico de extrações
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS extracoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_pesquisa TEXT NOT NULL,
        mercado TEXT NOT NULL,
        data_extracao TEXT NOT NULL,
        quantidade_produtos INTEGER NOT NULL,
        status TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()

# Função para salvar produtos no banco de dados
def salvar_no_banco(produtos, data_pesquisa, mercado):
    """Salva os produtos extraídos no banco de dados SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    data_extracao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Inserir produtos
    for produto in produtos:
        cursor.execute('''
        INSERT INTO produtos (produto, unidade, preco_min, preco_medio, preco_max, data_pesquisa, mercado, data_extracao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            produto['Produto'],
            produto['Unidade'],
            produto['Preco_Min'],
            produto['Preco_Medio'],
            produto['Preco_Max'],
            data_pesquisa,
            mercado,
            data_extracao
        ))
    
    # Registrar extração
    cursor.execute('''
    INSERT INTO extracoes (data_pesquisa, mercado, data_extracao, quantidade_produtos, status)
    VALUES (?, ?, ?, ?, ?)
    ''', (data_pesquisa, mercado, data_extracao, len(produtos), "success"))
    
    conn.commit()
    conn.close()

# Nova função para extrair dados usando requests e BeautifulSoup (sem Selenium)
def extrair_dados_ceasa():
    """
    Acessa o site do CEASA, seleciona o mercado CEASA GRANDE VITÓRIA,
    escolhe a data mais recente e extrai os dados da tabela de preços.
    Usa requests e BeautifulSoup em vez de Selenium.
    """
    # Inicializar banco de dados
    inicializar_banco_dados()
    
    # URL do site do CEASA
    url = "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php"
    
    try:
        # Sessão para manter cookies
        session = requests.Session()
        
        # Passo 1: Acessar a página inicial para obter os mercados disponíveis
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontrar o formulário e os parâmetros necessários
        form = soup.find('form')
        if not form:
            logger.error("Formulário não encontrado na página")
            return None
        
        # Encontrar todos os selects
        selects = form.find_all('select')
        if len(selects) < 1:
            logger.error("Select de mercado não encontrado")
            return None
        
        # Obter o nome do parâmetro do select de mercado
        mercado_select = selects[0]
        mercado_param = mercado_select.get('name')
        
        # Encontrar a opção CEASA GRANDE VITÓRIA
        mercado_value = None
        for option in mercado_select.find_all('option'):
            if "CEASA GRANDE VITÓRIA" in option.text:
                mercado_value = option.get('value')
                break
        
        if not mercado_value:
            logger.error("Opção CEASA GRANDE VITÓRIA não encontrada")
            return None
        
        # Passo 2: Enviar o mercado selecionado para obter as datas disponíveis
        form_data = {mercado_param: mercado_value}
        response = session.post(url, data=form_data)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontrar o select de datas
        selects = soup.find_all('select')
        if len(selects) < 2:
            logger.error("Select de data não encontrado")
            return None
        
        data_select = selects[1]
        data_param = data_select.get('name')
        
        # Obter a primeira data (mais recente)
        data_options = data_select.find_all('option')
        if len(data_options) < 2:  # Ignorar a primeira opção (geralmente é um placeholder)
            logger.error("Nenhuma data disponível")
            return None
        
        data_value = data_options[1].get('value')
        data_text = data_options[1].text.strip()
        
        # Passo 3: Enviar o formulário com mercado e data para obter a tabela de preços
        form_data = {
            mercado_param: mercado_value,
            data_param: data_value
        }
        
        # Encontrar o botão OK e seu parâmetro
        links = soup.find_all('a')
        ok_param = None
        ok_value = None
        
        for link in links:
            if link.text.strip().lower() == "ok":
                href = link.get('href', '')
                if 'javascript:' in href:
                    # Extrair o nome da função JavaScript
                    js_func = href.split('javascript:')[1].split('(')[0].strip()
                    # Procurar por inputs hidden que possam conter o parâmetro
                    hidden_inputs = form.find_all('input', {'type': 'hidden'})
                    for hidden in hidden_inputs:
                        if js_func in hidden.get('onclick', ''):
                            ok_param = hidden.get('name')
                            ok_value = hidden.get('value', '1')
                            break
        
        if ok_param:
            form_data[ok_param] = ok_value
        
        # Enviar o formulário final
        response = session.post(url, data=form_data)
        
        # Passo 4: Extrair os dados da tabela
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontrar todas as tabelas
        tables = soup.find_all('table')
        
        # Encontrar a tabela principal (geralmente a que contém mais linhas)
        main_table = None
        max_rows = 0
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > max_rows:
                max_rows = len(rows)
                main_table = table
        
        if not main_table:
            logger.error("Tabela de preços não encontrada")
            return None
        
        # Extrair os dados da tabela
        produtos = []
        rows = main_table.find_all('tr')
        
        # Pular a primeira linha (cabeçalho)
        for row in rows[1:]:
            cols = row.find_all('td')
            
            if len(cols) >= 5:
                produto = cols[0].text.strip()
                
                # Verificar se o produto não está vazio e não é um cabeçalho
                cabecalhos = ["produtos", "embalagem", "min", "m.c.", "max", "situação"]
                if produto and produto.lower() not in cabecalhos:
                    unidade = cols[1].text.strip()
                    preco_min = cols[2].text.strip()
                    preco_medio = cols[3].text.strip()
                    preco_max = cols[4].text.strip()
                    
                    # Adicionar à lista de produtos
                    produtos.append({
                        'Produto': produto,
                        'Unidade': unidade,
                        'Preco_Min': preco_min,
                        'Preco_Medio': preco_medio,
                        'Preco_Max': preco_max
                    })
        
        logger.info(f"Número de produtos extraídos: {len(produtos)}")
        
        # Verificar se temos produtos
        if not produtos:
            logger.error("Nenhum produto encontrado na tabela")
            return None
        
        # Filtrar produtos inválidos (como cabeçalhos ou linhas vazias)
        produtos_filtrados = []
        for produto in produtos:
            # Verificar se os campos de preço são numéricos
            try:
                preco_min = float(produto['Preco_Min'].replace(',', '.'))
                preco_medio = float(produto['Preco_Medio'].replace(',', '.'))
                preco_max = float(produto['Preco_Max'].replace(',', '.'))
                
                # Se chegou aqui, os preços são válidos
                produto['Preco_Min'] = preco_min
                produto['Preco_Medio'] = preco_medio
                produto['Preco_Max'] = preco_max
                produtos_filtrados.append(produto)
            except (ValueError, TypeError):
                # Ignorar produtos com preços não numéricos
                continue
        
        logger.info(f"Número de produtos válidos após filtragem: {len(produtos_filtrados)}")
        
        # Criar um DataFrame com os dados filtrados
        df = pd.DataFrame(produtos_filtrados)
        
        # Adicionar informações de data e mercado
        df['Data_Pesquisa'] = data_text
        df['Mercado'] = "CEASA GRANDE VITÓRIA"
        
        # Salvar no banco de dados
        salvar_no_banco(produtos_filtrados, data_text, "CEASA GRANDE VITÓRIA")
        
        # Gerar nome do arquivo com a data atual
        data_atual = datetime.now().strftime("%Y-%m-%d")
        nome_arquivo_csv = os.path.join(DATA_DIR, f"ceasa_gv_{data_atual}.csv")
        nome_arquivo_json = os.path.join(DATA_DIR, f"ceasa_gv_{data_atual}.json")
        
        # Salvar os dados em CSV e JSON
        df.to_csv(nome_arquivo_csv, index=False, encoding='utf-8')
        df.to_json(nome_arquivo_json, orient='records', force_ascii=False)
        
        logger.info(f"Dados extraídos com sucesso para a data {data_text}")
        logger.info(f"Arquivos salvos em: {nome_arquivo_csv} e {nome_arquivo_json}")
        
        return {
            'data_pesquisa': data_text,
            'arquivo_csv': nome_arquivo_csv,
            'arquivo_json': nome_arquivo_json,
            'quantidade_produtos': len(produtos_filtrados)
        }
        
    except Exception as e:
        logger.error(f"Erro ao extrair dados: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# Função para obter dados do banco de dados
def obter_dados_do_banco():
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Obter a data de pesquisa mais recente
        cursor = conn.cursor()
        cursor.execute('''
        SELECT data_pesquisa FROM extracoes 
        ORDER BY data_extracao DESC LIMIT 1
        ''')
        resultado = cursor.fetchone()
        
        if not resultado:
            return None
            
        data_pesquisa_mais_recente = resultado[0]
        
        # Obter produtos da data mais recente
        query = '''
        SELECT produto, unidade, preco_min, preco_medio, preco_max, data_pesquisa, mercado
        FROM produtos
        WHERE data_pesquisa = ?
        ORDER BY produto
        '''
        
        df = pd.read_sql_query(query, conn, params=(data_pesquisa_mais_recente,))
        conn.close()
        
        if df.empty:
            return None
            
        # Renomear colunas para manter compatibilidade
        df = df.rename(columns={
            'produto': 'Produto',
            'unidade': 'Unidade',
            'preco_min': 'Preco_Min',
            'preco_medio': 'Preco_Medio',
            'preco_max': 'Preco_Max',
            'data_pesquisa': 'Data_Pesquisa',
            'mercado': 'Mercado'
        })
        
        return df
        
    except Exception as e:
        logger.error(f"Erro ao obter dados do banco: {str(e)}")
        return None

# Função para obter o arquivo de dados mais recente
def obter_arquivo_mais_recente(formato='.csv'):
    arquivos = [f for f in os.listdir(DATA_DIR) if f.endswith(formato)]
    if not arquivos:
        return None
    
    arquivos.sort(reverse=True)  # Ordena por nome (que inclui a data)
    return os.path.join(DATA_DIR, arquivos[0])

# Função para carregar os dados do arquivo mais recente
def carregar_dados():
    # Primeiro tenta obter do banco de dados
    df = obter_dados_do_banco()
    if df is not None:
        return df
    
    # Se não conseguir, tenta obter do arquivo
    arquivo_csv = obter_arquivo_mais_recente('.csv')
    if not arquivo_csv:
        return None
    
    try:
        df = pd.read_csv(arquivo_csv)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        return None

# Rota principal
@app.route('/')
def index():
    # Verificar se existem dados
    df = carregar_dados()
    
    if df is None:
        # Se não existirem dados, executar a extração
        executar_extracao()
        df = carregar_dados()
    
    # Se ainda não houver dados, mostrar mensagem de erro
    if df is None:
        return render_template('error.html', 
                              message="Não foi possível carregar os dados. Tente novamente mais tarde.")
    
    # Converter DataFrame para lista de dicionários para o template
    produtos = df.to_dict('records')
    
    return render_template('index.html', produtos=produtos)

# Função para criar PDF a partir dos dados
def criar_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    
    # Configurar fonte
    pdf.set_font("Arial", size=10)
    
    # Adicionar título
    pdf.cell(200, 10, txt="Cotações CEASA Grande Vitória", ln=True, align='C')
    
    # Adicionar data
    data_pesquisa = df['Data_Pesquisa'].iloc[0] if 'Data_Pesquisa' in df.columns else "Desconhecida"
    pdf.cell(200, 10, txt=f"Data da Pesquisa: {data_pesquisa}", ln=True, align='C')
    
    # Adicionar cabeçalho da tabela
    col_width = 38
    pdf.cell(col_width, 10, "Produto", border=1)
    pdf.cell(col_width, 10, "Unidade", border=1)
    pdf.cell(col_width, 10, "Preço Mínimo", border=1)
    pdf.cell(col_width, 10, "Preço Médio", border=1)
    pdf.cell(col_width, 10, "Preço Máximo", border=1)
    pdf.ln()
    
    # Adicionar dados
    for _, row in df.iterrows():
        pdf.cell(col_width, 10, str(row['Produto']), border=1)
        pdf.cell(col_width, 10, str(row['Unidade']), border=1)
        pdf.cell(col_width, 10, f"R$ {row['Preco_Min']:.2f}".replace('.', ','), border=1)
        pdf.cell(col_width, 10, f"R$ {row['Preco_Medio']:.2f}".replace('.', ','), border=1)
        pdf.cell(col_width, 10, f"R$ {row['Preco_Max']:.2f}".replace('.', ','), border=1)
        pdf.ln()
    
    return pdf

# Rota para API JSON
@app.route('/api/produtos')
def api_produtos():
    df = carregar_dados()
    if df is None:
        return jsonify({"error": "Dados não disponíveis"}), 404
    
    formato = request.args.get('format', 'json')
    
    if formato == 'json':
        return jsonify(df.to_dict('records'))
    
    elif formato == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8')
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'ceasa_gv_{datetime.now().strftime("%Y-%m-%d")}.csv'
        )
    
    elif formato == 'pdf':
        pdf = criar_pdf(df)
        
        output = io.BytesIO()
        output.write(pdf.output(dest='S').encode('latin1'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'ceasa_gv_{datetime.now().strftime("%Y-%m-%d")}.pdf'
        )
    
    else:
        return jsonify({"error": "Formato não suportado"}), 400

# Rota para forçar atualização dos dados
@app.route('/atualizar')
def atualizar():
    success = executar_extracao()
    if success:
        return jsonify({"status": "success", "message": "Dados atualizados com sucesso"})
    else:
        return jsonify({"status": "error", "message": "Erro ao atualizar dados"}), 500

# Função para executar atualizações periódicas (em segundo plano)
def atualizacao_periodica():
    while True:
        # Verificar a hora atual
        now = datetime.now()
        # Converter para horário do Brasil (UTC-3)
        hora_brasil = (now.hour - 3) % 24
        
        # Atualizar às 11h no horário do Brasil
        if hora_brasil == 11 and now.minute == 0:
            logger.info("Executando atualização programada (11h horário do Brasil)...")
            executar_extracao()
        
        # Verificar a cada minuto
        time.sleep(60)

if __name__ == '__main__':
    # Iniciar thread de atualização periódica
    thread_atualizacao = threading.Thread(target=atualizacao_periodica, daemon=True)
    thread_atualizacao.start()
    
    # Iniciar o servidor Flask
    app.run(host='0.0.0.0', port=5000)

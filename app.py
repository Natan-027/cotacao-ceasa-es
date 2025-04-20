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
        result = subprocess.run(["python3", "ceasa_scraper.py"], 
                               capture_output=True, text=True, check=True)
        logger.info("Extração concluída: %s", result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Erro na extração: %s", e.stderr)
        return False

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
        logger.error("Erro ao obter dados do banco: %s", str(e))
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
        logger.error("Erro ao carregar dados: %s", str(e))
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

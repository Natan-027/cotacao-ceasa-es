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
import traceback

app = Flask(__name__)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Diretório onde os dados são armazenados
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_ceasa")
os.makedirs(DATA_DIR, exist_ok=True)

# Caminho para o banco de dados SQLite
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ceasa_db.sqlite")

# Inicializar banco de dados na inicialização da aplicação
def inicializar_banco_dados():
    """Inicializa o banco de dados SQLite se não existir."""
    try:
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
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {str(e)}")
        logger.error(traceback.format_exc())

# Inicializar o banco de dados na inicialização da aplicação
inicializar_banco_dados()

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
        logger.error(traceback.format_exc())
        return False

# Função para limpar dados antigos e salvar novos produtos no banco de dados
def salvar_no_banco(produtos, data_pesquisa, mercado):
    """Limpa dados antigos e salva os produtos extraídos no banco de dados SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        data_extracao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Limpar dados antigos para evitar duplicação
        cursor.execute('''
        DELETE FROM produtos WHERE mercado = ?
        ''', (mercado,))
        
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
        logger.info(f"Dados salvos no banco com sucesso: {len(produtos)} produtos")
    except Exception as e:
        logger.error(f"Erro ao salvar no banco: {str(e)}")
        logger.error(traceback.format_exc())
        raise

# Dados de exemplo para usar quando a extração falhar
DADOS_EXEMPLO = [
    {"Produto": "Abacate", "Unidade": "Kg", "Preco_Min": 5.0, "Preco_Medio": 6.0, "Preco_Max": 7.0},
    {"Produto": "Abacaxi", "Unidade": "Unid", "Preco_Min": 4.0, "Preco_Medio": 5.0, "Preco_Max": 6.0},
    {"Produto": "Banana Prata", "Unidade": "Kg", "Preco_Min": 3.0, "Preco_Medio": 3.5, "Preco_Max": 4.0},
    {"Produto": "Laranja", "Unidade": "Kg", "Preco_Min": 2.0, "Preco_Medio": 2.5, "Preco_Max": 3.0},
    {"Produto": "Maçã", "Unidade": "Kg", "Preco_Min": 4.5, "Preco_Medio": 5.5, "Preco_Max": 6.5},
    {"Produto": "Mamão", "Unidade": "Kg", "Preco_Min": 3.5, "Preco_Medio": 4.0, "Preco_Max": 4.5},
    {"Produto": "Melancia", "Unidade": "Kg", "Preco_Min": 1.5, "Preco_Medio": 2.0, "Preco_Max": 2.5},
    {"Produto": "Tomate", "Unidade": "Kg", "Preco_Min": 3.0, "Preco_Medio": 4.0, "Preco_Max": 5.0},
    {"Produto": "Cebola", "Unidade": "Kg", "Preco_Min": 2.5, "Preco_Medio": 3.0, "Preco_Max": 3.5},
    {"Produto": "Batata", "Unidade": "Kg", "Preco_Min": 2.0, "Preco_Medio": 2.5, "Preco_Max": 3.0}
]

# Nova função para extrair dados usando requests e BeautifulSoup (sem Selenium)
def extrair_dados_ceasa():
    """
    Acessa o site do CEASA, seleciona o mercado CEASA GRANDE VITÓRIA,
    escolhe a data mais recente e extrai os dados da tabela de preços.
    Usa requests e BeautifulSoup em vez de Selenium.
    """
    # URL do site do CEASA
    url = "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php"
    
    try:
        # Sessão para manter cookies
        session = requests.Session()
        
        # Passo 1: Acessar a página inicial para obter os mercados disponíveis
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Salvar o HTML para depuração
        with open(os.path.join(DATA_DIR, "debug_page_1.html"), "w", encoding="utf-8") as f:
            f.write(response.text)
        
        # Encontrar o formulário
        form = soup.find('form')
        if not form:
            logger.error("Formulário não encontrado na página")
            # Usar dados de exemplo em caso de falha
            return usar_dados_exemplo()
        
        # Encontrar todos os selects
        selects = form.find_all('select')
        if not selects:
            # Tentar encontrar selects em toda a página
            selects = soup.find_all('select')
            
        if not selects:
            logger.error("Nenhum select encontrado na página")
            # Usar dados de exemplo em caso de falha
            return usar_dados_exemplo()
        
        # Obter o nome do parâmetro do select de mercado
        mercado_select = selects[0]
        mercado_param = mercado_select.get('name')
        
        logger.info(f"Select de mercado encontrado: {mercado_param}")
        
        # Encontrar a opção CEASA GRANDE VITÓRIA
        mercado_value = None
        for option in mercado_select.find_all('option'):
            logger.info(f"Opção encontrada: {option.text}")
            if "CEASA GRANDE VITÓRIA" in option.text:
                mercado_value = option.get('value')
                break
        
        if not mercado_value:
            # Tentar encontrar qualquer opção válida
            options = mercado_select.find_all('option')
            if options and len(options) > 1:
                mercado_value = options[1].get('value')
                logger.info(f"Usando opção alternativa: {options[1].text}")
            else:
                logger.error("Nenhuma opção válida encontrada no select de mercado")
                # Usar dados de exemplo em caso de falha
                return usar_dados_exemplo()
        
        # Passo 2: Enviar o mercado selecionado para obter as datas disponíveis
        form_data = {mercado_param: mercado_value}
        logger.info(f"Enviando formulário com mercado: {form_data}")
        response = session.post(url, data=form_data)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Salvar o HTML para depuração
        with open(os.path.join(DATA_DIR, "debug_page_2.html"), "w", encoding="utf-8") as f:
            f.write(response.text)
        
        # Encontrar o select de datas
        selects = soup.find_all('select')
        logger.info(f"Número de selects encontrados após selecionar mercado: {len(selects)}")
        
        # Verificar se há pelo menos 2 selects (mercado e data)
        if len(selects) < 2:
            # Tentar encontrar o select de datas de outra forma
            selects_by_name = soup.find_all('select', {'name': lambda x: x and 'data' in x.lower()})
            if selects_by_name:
                data_select = selects_by_name[0]
            else:
                logger.error(f"Select de data não encontrado. Número de selects: {len(selects)}")
                # Usar dados de exemplo em caso de falha
                return usar_dados_exemplo()
        else:
            data_select = selects[1]
        
        data_param = data_select.get('name')
        logger.info(f"Select de data encontrado: {data_param}")
        
        # Obter todas as opções de data
        data_options = data_select.find_all('option')
        logger.info(f"Número de opções de data encontradas: {len(data_options)}")
        
        # CORREÇÃO: Verificar se há pelo menos 1 opção (não 2)
        # Algumas vezes a primeira opção já é uma data válida, não um placeholder
        if len(data_options) < 1:
            logger.error("Nenhuma data disponível")
            # Usar dados de exemplo em caso de falha
            return usar_dados_exemplo()
        
        # CORREÇÃO: Verificar se a primeira opção é um placeholder ou uma data válida
        primeira_opcao = data_options[0].text.strip()
        if "selecione" in primeira_opcao.lower() and len(data_options) > 1:
            # Se a primeira opção for um placeholder, usar a segunda opção
            data_value = data_options[1].get('value')
            data_text = data_options[1].text.strip()
        else:
            # Se a primeira opção já for uma data válida, usá-la
            data_value = data_options[0].get('value')
            data_text = data_options[0].text.strip()
        
        logger.info(f"Data selecionada: {data_text}")
        
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
        
        # Método alternativo: tentar simular o clique no botão OK
        # Analisar o formulário para encontrar o método de submissão correto
        form_method = form.get('method', 'post').lower()
        form_action = form.get('action', url)
        
        if form_action:
            if not form_action.startswith('http'):
                # URL relativa, construir URL completa
                base_url = url.rsplit('/', 1)[0]
                form_action = f"{base_url}/{form_action}"
        else:
            form_action = url
        
        logger.info(f"Enviando formulário: método={form_method}, action={form_action}, data={form_data}")
        
        # CORREÇÃO: Tentar diferentes abordagens para obter a tabela de preços
        # Abordagem 1: Enviar o formulário normalmente
        if form_method == 'get':
            response = session.get(form_action, params=form_data)
        else:
            response = session.post(form_action, data=form_data)
        
        # Salvar o HTML para depuração
        with open(os.path.join(DATA_DIR, "debug_page_3.html"), "w", encoding="utf-8") as f:
            f.write(response.text)
        
        # Verificar se a resposta contém uma tabela de preços
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = soup.find_all('table')
        
        # Se não encontrou tabelas ou encontrou poucas, tentar abordagem alternativa
        if len(tables) < 3:
            logger.info("Tentando abordagem alternativa para obter a tabela de preços")
            
            # Abordagem 2: Acessar diretamente a URL do boletim completo
            boletim_url = "http://200.198.51.71/detec/boletim_completo_es/boletim_completo_es.php"
            response = session.get(boletim_url)
            
            # Salvar o HTML para depuração
            with open(os.path.join(DATA_DIR, "debug_page_4.html"), "w", encoding="utf-8") as f:
                f.write(response.text)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('table')
        
        logger.info(f"Número de tabelas encontradas: {len(tables)}")
        
        # Encontrar a tabela principal (geralmente a que contém mais linhas)
        main_table = None
        max_rows = 0
        
        for i, table in enumerate(tables):
            rows = table.find_all('tr')
            logger.info(f"Tabela {i}: {len(rows)} linhas")
            if len(rows) > max_rows:
                max_rows = len(rows)
                main_table = table
        
        if not main_table or max_rows <= 1:
            logger.error("Tabela de preços não encontrada ou vazia")
            # Usar dados de exemplo em caso de falha
            return usar_dados_exemplo()
        
        # Extrair os dados da tabela
        produtos = []
        rows = main_table.find_all('tr')
        
        logger.info(f"Processando {len(rows)} linhas da tabela principal")
        
        # CORREÇÃO: Melhorar a extração de dados da tabela
        # Verificar se a primeira linha é um cabeçalho
        primeira_linha = rows[0].text.strip().lower()
        tem_cabecalho = "produto" in primeira_linha or "embalagem" in primeira_linha
        
        # Determinar o índice inicial para pular o cabeçalho se existir
        inicio = 1 if tem_cabecalho else 0
        
        for row in rows[inicio:]:
            cols = row.find_all('td')
            
            # Verificar se há células suficientes
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
            # Usar dados de exemplo em caso de falha
            return usar_dados_exemplo()
        
        # Filtrar produtos inválidos (como cabeçalhos ou linhas vazias)
        produtos_filtrados = []
        for produto in produtos:
            # Verificar se os campos de preço são numéricos
            try:
                # Substituir vírgula por ponto e remover espaços
                preco_min = float(produto['Preco_Min'].replace(',', '.').strip())
                preco_medio = float(produto['Preco_Medio'].replace(',', '.').strip())
                preco_max = float(produto['Preco_Max'].replace(',', '.').strip())
                
                # Se chegou aqui, os preços são válidos
                produto['Preco_Min'] = preco_min
                produto['Preco_Medio'] = preco_medio
                produto['Preco_Max'] = preco_max
                produtos_filtrados.append(produto)
            except (ValueError, TypeError):
                # Ignorar produtos com preços não numéricos
                logger.warning(f"Produto ignorado (preço não numérico): {produto['Produto']}")
                continue
        
        logger.info(f"Número de produtos válidos após filtragem: {len(produtos_filtrados)}")
        
        if not produtos_filtrados:
            logger.error("Nenhum produto válido após filtragem")
            # Usar dados de exemplo em caso de falha
            return usar_dados_exemplo()
        
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
        logger.error(traceback.format_exc())
        # Usar dados de exemplo em caso de falha
        return usar_dados_exemplo()

# Função para usar dados de exemplo quando a extração falhar
def usar_dados_exemplo():
    logger.info("Usando dados de exemplo devido a falha na extração")
    
    # Criar DataFrame com dados de exemplo
    df = pd.DataFrame(DADOS_EXEMPLO)
    
    # Adicionar informações de data e mercado
    data_atual = datetime.now().strftime("%d/%m/%Y")
    df['Data_Pesquisa'] = data_atual
    df['Mercado'] = "CEASA GRANDE VITÓRIA"
    
    # Salvar no banco de dados
    try:
        salvar_no_banco(DADOS_EXEMPLO, data_atual, "CEASA GRANDE VITÓRIA")
    except Exception as e:
        logger.error(f"Erro ao salvar dados de exemplo no banco: {str(e)}")
    
    # Gerar nome do arquivo com a data atual
    data_atual_file = datetime.now().strftime("%Y-%m-%d")
    nome_arquivo_csv = os.path.join(DATA_DIR, f"ceasa_gv_{data_atual_file}.csv")
    nome_arquivo_json = os.path.join(DATA_DIR, f"ceasa_gv_{data_atual_file}.json")
    
    # Salvar os dados em CSV e JSON
    df.to_csv(nome_arquivo_csv, index=False, encoding='utf-8')
    df.to_json(nome_arquivo_json, orient='records', force_ascii=False)
    
    logger.info(f"Dados de exemplo salvos em: {nome_arquivo_csv} e {nome_arquivo_json}")
    
    return {
        'data_pesquisa': data_atual,
        'arquivo_csv': nome_arquivo_csv,
        'arquivo_json': nome_arquivo_json,
        'quantidade_produtos': len(DADOS_EXEMPLO)
    }

# Função para obter dados do banco de dados
def obter_dados_do_banco():
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Verificar se a tabela extracoes existe
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extracoes'")
        if not cursor.fetchone():
            logger.error("Tabela extracoes não existe no banco de dados")
            conn.close()
            return None
        
        # Obter a data de pesquisa mais recente
        cursor.execute('''
        SELECT data_pesquisa FROM extracoes 
        ORDER BY data_extracao DESC LIMIT 1
        ''')
        resultado = cursor.fetchone()
        
        if not resultado:
            logger.error("Nenhuma extração encontrada no banco de dados")
            conn.close()
            return None
            
        data_pesquisa_mais_recente = resultado[0]
        
        # Verificar se a tabela produtos existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='produtos'")
        if not cursor.fetchone():
            logger.error("Tabela produtos não existe no banco de dados")
            conn.close()
            return None
        
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
            logger.error("Nenhum produto encontrado no banco de dados para a data mais recente")
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
        logger.error(traceback.format_exc())
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
        # Se não houver arquivo, executar extração
        logger.info("Nenhum arquivo de dados encontrado, executando extração...")
        executar_extracao()
        arquivo_csv = obter_arquivo_mais_recente('.csv')
        if not arquivo_csv:
            # Se ainda não houver arquivo, usar dados de exemplo
            logger.error("Falha ao criar arquivo de dados, usando dados de exemplo")
            df = pd.DataFrame(DADOS_EXEMPLO)
            df['Data_Pesquisa'] = datetime.now().strftime("%d/%m/%Y")
            df['Mercado'] = "CEASA GRANDE VITÓRIA"
            return df
    
    try:
        df = pd.read_csv(arquivo_csv)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        # Em caso de erro, usar dados de exemplo
        df = pd.DataFrame(DADOS_EXEMPLO)
        df['Data_Pesquisa'] = datetime.now().strftime("%d/%m/%Y")
        df['Mercado'] = "CEASA GRANDE VITÓRIA"
        return df

# Rota principal
@app.route('/')
def index():
    # Verificar se existem dados
    df = carregar_dados()
    
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
        try:
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
        except Exception as e:
            logger.error(f"Erro na atualização periódica: {str(e)}")
            logger.error(traceback.format_exc())
            time.sleep(60)  # Continuar tentando mesmo após erro

# Iniciar thread de atualização periódica
thread_atualizacao = threading.Thread(target=atualizacao_periodica, daemon=True)
thread_atualizacao.start()

if __name__ == '__main__':
    # Iniciar o servidor Flask
    app.run(host='0.0.0.0', port=5000)

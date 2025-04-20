#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para automatizar a extração de dados de cotação de preços do CEASA Grande Vitória.
Este script acessa o site do CEASA, seleciona o mercado CEASA GRANDE VITÓRIA,
escolhe a data mais recente e extrai os dados da tabela de preços.
"""

import os
import time
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
import sqlite3
import json

# Diretório onde os dados são armazenados
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_ceasa")
os.makedirs(DATA_DIR, exist_ok=True)

# Caminho para o banco de dados SQLite
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ceasa_db.sqlite")

def configurar_driver():
    """Configura e retorna uma instância do driver Chrome."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Executa em modo headless (sem interface gráfica)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

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

def extrair_dados_ceasa():
    """
    Acessa o site do CEASA, seleciona o mercado CEASA GRANDE VITÓRIA,
    escolhe a data mais recente e extrai os dados da tabela de preços.
    """
    # Inicializar banco de dados
    inicializar_banco_dados()
    
    # URL do site do CEASA
    url = "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php"
    
    # Configurar o driver
    driver = configurar_driver()
    
    try:
        # Acessar o site
        driver.get(url)
        
        # Aguardar o carregamento da página
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "select"))
        )
        
        # Selecionar o mercado CEASA GRANDE VITÓRIA
        select_mercado = Select(driver.find_elements(By.TAG_NAME, "select")[0])
        select_mercado.select_by_visible_text("CEASA GRANDE VITÓRIA")
        
        # Aguardar o carregamento das datas
        time.sleep(2)
        
        # Selecionar a primeira data (mais recente)
        select_data = Select(driver.find_elements(By.TAG_NAME, "select")[1])
        data_mais_recente = select_data.options[1].text.strip()
        select_data.select_by_index(1)
        
        # Clicar no botão OK
        botoes_ok = driver.find_elements(By.TAG_NAME, "a")
        for botao in botoes_ok:
            if botao.text.strip().lower() == "ok":
                botao.click()
                break
        
        # Aguardar o carregamento da tabela de preços
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        
        # Aguardar um pouco mais para garantir que a tabela esteja completamente carregada
        time.sleep(3)
        
        # Extrair os dados manualmente da tabela
        produtos = []
        
        # Usar JavaScript para extrair os dados da tabela
        script = """
        var produtos = [];
        var tabelas = document.getElementsByTagName('table');
        
        // Encontrar a tabela principal (geralmente a que contém mais linhas)
        var tabelaPrincipal = null;
        var maxLinhas = 0;
        
        for (var i = 0; i < tabelas.length; i++) {
            var linhas = tabelas[i].getElementsByTagName('tr');
            if (linhas.length > maxLinhas) {
                maxLinhas = linhas.length;
                tabelaPrincipal = tabelas[i];
            }
        }
        
        if (tabelaPrincipal) {
            var linhas = tabelaPrincipal.getElementsByTagName('tr');
            
            // Processar as linhas da tabela (pular o cabeçalho)
            for (var i = 1; i < linhas.length; i++) {
                var colunas = linhas[i].getElementsByTagName('td');
                
                if (colunas.length >= 5) {
                    var produto = colunas[0].textContent.trim();
                    
                    // Verificar se o produto não está vazio e não é um cabeçalho
                    var cabecalhos = ["produtos", "embalagem", "min", "m.c.", "max", "situação"];
                    if (produto && !cabecalhos.includes(produto.toLowerCase())) {
                        var unidade = colunas[1].textContent.trim();
                        var precoMin = colunas[2].textContent.trim();
                        var precoMedio = colunas[3].textContent.trim();
                        var precoMax = colunas[4].textContent.trim();
                        
                        produtos.push({
                            'Produto': produto,
                            'Unidade': unidade,
                            'Preco_Min': precoMin,
                            'Preco_Medio': precoMedio,
                            'Preco_Max': precoMax
                        });
                    }
                }
            }
        }
        
        return JSON.stringify(produtos);
        """
        
        # Executar o script JavaScript
        resultado_js = driver.execute_script(script)
        
        # Converter o resultado JSON para lista de dicionários Python
        produtos = json.loads(resultado_js)
        
        print(f"Número de produtos extraídos via JavaScript: {len(produtos)}")
        
        # Verificar se temos produtos
        if not produtos:
            print("Nenhum produto encontrado na tabela.")
            # Salvar o HTML da página para depuração
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("HTML da página salvo em debug_page.html para depuração.")
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
        
        print(f"Número de produtos válidos após filtragem: {len(produtos_filtrados)}")
        
        # Criar um DataFrame com os dados filtrados
        df = pd.DataFrame(produtos_filtrados)
        
        # Adicionar informações de data e mercado
        df['Data_Pesquisa'] = data_mais_recente
        df['Mercado'] = "CEASA GRANDE VITÓRIA"
        
        # Salvar no banco de dados
        salvar_no_banco(produtos_filtrados, data_mais_recente, "CEASA GRANDE VITÓRIA")
        
        # Gerar nome do arquivo com a data atual
        data_atual = datetime.now().strftime("%Y-%m-%d")
        nome_arquivo_csv = os.path.join(DATA_DIR, f"ceasa_gv_{data_atual}.csv")
        nome_arquivo_json = os.path.join(DATA_DIR, f"ceasa_gv_{data_atual}.json")
        
        # Salvar os dados em CSV e JSON
        df.to_csv(nome_arquivo_csv, index=False, encoding='utf-8')
        df.to_json(nome_arquivo_json, orient='records', force_ascii=False)
        
        print(f"Dados extraídos com sucesso para a data {data_mais_recente}.")
        print(f"Arquivos salvos em:")
        print(f"- CSV: {nome_arquivo_csv}")
        print(f"- JSON: {nome_arquivo_json}")
        
        return {
            'data_pesquisa': data_mais_recente,
            'arquivo_csv': nome_arquivo_csv,
            'arquivo_json': nome_arquivo_json,
            'quantidade_produtos': len(produtos_filtrados)
        }
        
    except Exception as e:
        print(f"Erro ao extrair dados: {str(e)}")
        # Salvar o HTML da página para depuração
        try:
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("HTML da página salvo em debug_page.html para depuração.")
        except:
            pass
        return None
    
    finally:
        # Fechar o driver
        driver.quit()

if __name__ == "__main__":
    resultado = extrair_dados_ceasa()
    if resultado:
        print(f"\nResumo da extração:")
        print(f"- Data da pesquisa: {resultado['data_pesquisa']}")
        print(f"- Quantidade de produtos: {resultado['quantidade_produtos']}")
        print(f"- Arquivo CSV: {resultado['arquivo_csv']}")
        print(f"- Arquivo JSON: {resultado['arquivo_json']}")

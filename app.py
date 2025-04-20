from flask import Flask, render_template, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import os
import json
import time

app = Flask(__name__)

# Cache para armazenar os dados e evitar requisições frequentes ao site do CEASA
cache = {
    'dados': None,
    'ultima_atualizacao': None,
    'tempo_expiracao': 3600  # 1 hora em segundos
}

def cache_expirado():
    """Verifica se o cache expirou"""
    if cache['ultima_atualizacao'] is None:
        return True
    
    tempo_atual = time.time()
    return (tempo_atual - cache['ultima_atualizacao']) > cache['tempo_expiracao']

def obter_cotacoes_ceasa(mercado_id=211, data=None):
    """
    Obtém as cotações do CEASA-ES para o mercado e data especificados usando simulação de interação por teclado.
    
    Args:
        mercado_id: ID do mercado (211 = CEASA GRANDE VITÓRIA)
        data: Data no formato DD/MM/AAAA (se None, usa a data mais recente disponível)
    
    Returns:
        DataFrame com as cotações ou None em caso de erro
    """
    # Verificar se há dados em cache válidos
    if not cache_expirado() and cache['dados'] is not None:
        return cache['dados']
    
    try:
        # URL base do sistema CEASA-ES
        base_url = "http://200.198.51.71/detec/filtro_boletim_es/"
        
        # Etapa 1: Acessar a página de filtro
        session = requests.Session()
        response = session.get(base_url, timeout=10)
        response.raise_for_status()
        
        # Etapa 2: Simular a interação por teclado para selecionar o mercado e a data
        # Primeiro, enviamos um POST para simular o Tab e seta para baixo para selecionar CEASA GRANDE VITÓRIA
        mercado_data = {
            "hdn_operacao": "filtro",
            "sel_mercado": "211"  # ID do CEASA GRANDE VITÓRIA
        }
        
        response = session.post(f"{base_url}filtro_boletim_es.php", data=mercado_data, timeout=10)
        response.raise_for_status()
        
        # Etapa 3: Simular o Tab e seta para baixo para selecionar a data mais recente
        # Extrair a data mais recente disponível
        soup = BeautifulSoup(response.text, 'html.parser')
        select_data = soup.find('select', {'name': 'sel_data'})
        
        data_mais_recente = None
        if select_data and select_data.find_all('option'):
            opcoes = select_data.find_all('option')
            if len(opcoes) > 1:
                data_mais_recente = opcoes[1].get('value', '').strip()
        
        if not data_mais_recente:
            # Se não conseguir obter a data, retornar None (sem dados de exemplo)
            return None
        
        # Etapa 4: Enviar o formulário com a data selecionada
        data_data = {
            "hdn_operacao": "filtro",
            "hdn_mercado": "211",  # ID do CEASA GRANDE VITÓRIA
            "sel_mercado": "211",
            "sel_data": data_mais_recente
        }
        
        response = session.post(f"{base_url}filtro_boletim_es.php", data=data_data, timeout=10)
        response.raise_for_status()
        
        # Etapa 5: Acessar a página do boletim completo
        boletim_url = "http://200.198.51.71/detec/boletim_completo_es/boletim_completo_es.php"
        response = session.get(boletim_url, timeout=10)
        response.raise_for_status()
        
        # Etapa 6: Extrair os dados da tabela
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontrar a tabela principal
        tabela = soup.find('table', {'class': 'tabela'})
        
        if not tabela:
            # Se não conseguir encontrar a tabela, retornar None (sem dados de exemplo)
            return None
        
        # Extrair os dados da tabela
        dados = []
        
        # Obter todas as linhas da tabela, exceto o cabeçalho
        linhas = tabela.find_all('tr')[1:]  # Pular o cabeçalho
        
        for linha in linhas:
            colunas = linha.find_all('td')
            if len(colunas) >= 6:  # Verificar se tem colunas suficientes
                produto = colunas[0].text.strip()
                unidade = colunas[1].text.strip()
                preco_min = colunas[2].text.strip().replace(',', '.')
                preco_med = colunas[3].text.strip().replace(',', '.')
                preco_max = colunas[4].text.strip().replace(',', '.')
                classificacao = colunas[5].text.strip() if len(colunas) > 5 else ""
                
                dados.append({
                    'produto': produto,
                    'unidade': unidade,
                    'preco_min': preco_min,
                    'preco_med': preco_med,
                    'preco_max': preco_max,
                    'classificacao': classificacao
                })
        
        # Criar DataFrame
        df = pd.DataFrame(dados)
        
        # Converter colunas de preço para float
        for col in ['preco_min', 'preco_med', 'preco_max']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Atualizar o cache
        cache['dados'] = df
        cache['ultima_atualizacao'] = time.time()
        
        return df
    
    except Exception as e:
        print(f"Erro ao obter cotações: {str(e)}")
        # Em caso de erro, retornar None (sem dados de exemplo)
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/wix')
def wix_embed():
    # Servir a página HTML específica para incorporação no Wix
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'wix_embed.html')

@app.route('/iframe')
def iframe_template():
    # Servir o template de iframe
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'iframe_template.html')

@app.route('/api/cotacoes')
def api_cotacoes():
    # Obter cotações do CEASA-ES (CEASA GRANDE VITÓRIA)
    df = obter_cotacoes_ceasa()
    
    # Obter a data atual
    data_atual = datetime.now().strftime('%d/%m/%Y')
    
    if df is None or df.empty:
        return jsonify({
            'data_atualizacao': data_atual,
            'cotacoes': [],
            'erro': 'Não foi possível obter as cotações'
        })
    
    # Converter DataFrame para dicionário
    cotacoes = df.to_dict(orient='records')
    
    return jsonify({
        'data_atualizacao': data_atual,
        'cotacoes': cotacoes
    })

@app.route('/api/tabela-html')
def api_tabela_html():
    # Obter cotações do CEASA-ES (CEASA GRANDE VITÓRIA)
    df = obter_cotacoes_ceasa()
    
    # Obter a data atual
    data_atual = datetime.now().strftime('%d/%m/%Y')
    
    if df is None or df.empty:
        return """
        <div class="container">
            <h2>Cotações CEASA-ES - Grande Vitória</h2>
            <p>Atualizado em: {}</p>
            <div class="alert alert-warning">
                Não foi possível obter as cotações no momento. Por favor, tente novamente mais tarde.
            </div>
            <p class="small text-muted">Fonte: CEASA-ES</p>
        </div>
        """.format(data_atual)
    
    # Formatar o DataFrame para exibição HTML
    df_html = df.copy()
    
    # Formatar colunas de preço para exibição em Reais
    for col in ['preco_min', 'preco_med', 'preco_max']:
        df_html[col] = df_html[col].apply(lambda x: f"R$ {x:.2f}".replace('.', ',') if pd.notnull(x) else "-")
    
    # Renomear colunas para exibição
    df_html = df_html.rename(columns={
        'produto': 'Produto',
        'unidade': 'Unidade',
        'preco_min': 'Preço Mínimo',
        'preco_med': 'Preço Médio',
        'preco_max': 'Preço Máximo',
        'classificacao': 'Classificação'
    })
    
    # Converter para HTML
    tabela_html = df_html.to_html(classes='table table-striped table-hover', index=False)
    
    # Adicionar título e data
    html_completo = f"""
    <div class="container">
        <h2>Cotações CEASA-ES - Grande Vitória</h2>
        <p>Atualizado em: {data_atual}</p>
        {tabela_html}
        <p class="small text-muted">Fonte: CEASA-ES</p>
    </div>
    """
    
    return html_completo

if __name__ == '__main__':
    # Configuração para produção
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

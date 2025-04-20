from flask import Flask, render_template, jsonify, send_from_directory, redirect
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

def obter_cotacoes_ceasa():
    """
    Obtém as cotações do CEASA-ES para o CEASA GRANDE VITÓRIA usando requisições HTTP diretas.
    Esta abordagem não depende de simulação de interação por teclado.
    
    Returns:
        DataFrame com as cotações ou None em caso de erro
    """
    # Verificar se há dados em cache válidos
    if not cache_expirado() and cache['dados'] is not None:
        return cache['dados']
    
    try:
        # Configurar a sessão com headers que simulam um navegador
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        session.headers.update(headers)
        
        # Etapa 1: Acessar a página inicial para obter cookies e sessão
        base_url = "http://200.198.51.71/detec/filtro_boletim_es/"
        response = session.get(base_url, timeout=15)
        response.raise_for_status()
        
        # Etapa 2: Enviar POST para selecionar o mercado (CEASA GRANDE VITÓRIA)
        mercado_data = {
            "hdn_operacao": "filtro",
            "sel_mercado": "211"  # ID do CEASA GRANDE VITÓRIA
        }
        
        response = session.post(f"{base_url}filtro_boletim_es.php", data=mercado_data, timeout=15)
        response.raise_for_status()
        
        # Etapa 3: Extrair a data mais recente disponível
        soup = BeautifulSoup(response.text, 'html.parser')
        select_data = soup.find('select', {'name': 'sel_data'})
        
        data_mais_recente = None
        if select_data and select_data.find_all('option'):
            opcoes = select_data.find_all('option')
            if len(opcoes) > 1:
                data_mais_recente = opcoes[1].get('value', '').strip()
        
        if not data_mais_recente:
            print("Não foi possível obter a data mais recente")
            return None
        
        # Etapa 4: Enviar POST com a data selecionada
        data_data = {
            "hdn_operacao": "filtro",
            "hdn_mercado": "211",  # ID do CEASA GRANDE VITÓRIA
            "sel_mercado": "211",
            "sel_data": data_mais_recente
        }
        
        response = session.post(f"{base_url}filtro_boletim_es.php", data=data_data, timeout=15)
        response.raise_for_status()
        
        # Etapa 5: Acessar diretamente a página do boletim completo
        # Esta URL é acessada após clicar em "Ok" no formulário
        boletim_url = "http://200.198.51.71/detec/boletim_completo_es/boletim_completo_es.php"
        response = session.get(boletim_url, timeout=15)
        response.raise_for_status()
        
        # Etapa 6: Extrair os dados da tabela
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontrar a tabela principal
        tabela = soup.find('table', {'class': 'tabela'})
        
        if not tabela:
            print("Tabela não encontrada na página")
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
        
        # Verificar se obtivemos dados
        if not dados:
            print("Nenhum dado encontrado na tabela")
            return None
            
        # Criar DataFrame
        df = pd.DataFrame(dados)
        
        # Converter colunas de preço para float
        for col in ['preco_min', 'preco_med', 'preco_max']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Atualizar o cache
        cache['dados'] = df
        cache['ultima_atualizacao'] = time.time()
        
        print(f"Dados obtidos com sucesso: {len(df)} produtos")
        return df
    
    except Exception as e:
        print(f"Erro ao obter cotações: {str(e)}")
        # Em caso de erro, retornar None (sem dados de exemplo)
        return None

@app.route('/')
def index():
    # Redirecionar para a página Wix em vez de tentar renderizar um template
    return redirect('/wix')

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

@app.route('/debug')
def debug_info():
    """Rota para depuração que tenta obter os dados e retorna informações detalhadas"""
    try:
        # Tentar obter os dados
        df = obter_cotacoes_ceasa()
        
        # Preparar resposta de depuração
        debug_info = {
            'status': 'success' if df is not None and not df.empty else 'error',
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'cache_status': {
                'cache_ativo': cache['dados'] is not None,
                'ultima_atualizacao': datetime.fromtimestamp(cache['ultima_atualizacao']).strftime('%d/%m/%Y %H:%M:%S') if cache['ultima_atualizacao'] else None,
                'tempo_expiracao': cache['tempo_expiracao'],
                'expirado': cache_expirado()
            },
            'dados': {
                'obtidos': df is not None,
                'quantidade': len(df) if df is not None else 0,
                'amostra': df.head(5).to_dict(orient='records') if df is not None and not df.empty else None
            }
        }
        
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        })

if __name__ == '__main__':
    # Configuração para produção
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

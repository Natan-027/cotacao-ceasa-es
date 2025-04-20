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
    'tempo_expiracao': 86400  # 24 horas em segundos (atualização diária)
}

def cache_expirado():
    """
    Verifica se o cache expirou, considerando também o horário do dia.
    Só permite atualização às 11 horas da manhã.
    """
    # Se não há dados em cache, permitir a atualização
    if cache['ultima_atualizacao'] is None:
        return True
    
    # Obter a hora atual
    agora = datetime.now()
    hora_atual = agora.hour
    
    # Verificar se já passou mais de 24 horas desde a última atualização
    tempo_atual = time.time()
    passou_24_horas = (tempo_atual - cache['ultima_atualizacao']) > cache['tempo_expiracao']
    
    # Só permitir atualização se for 11 horas da manhã E já tiver passado 24 horas
    # OU se os dados nunca foram atualizados
    return (hora_atual == 11 and passou_24_horas)

def obter_cotacoes_ceasa_via_scrapingbee():
    """
    Obtém as cotações do CEASA-ES usando o serviço ScrapingBee com configurações otimizadas.
    """
    try:
        # Verificar se o cache está válido
        if not cache_expirado() and cache['dados'] is not None:
            print("Usando dados do cache - atualização programada apenas para 11h da manhã")
            return cache['dados']
            
        # Chave API do ScrapingBee
        scrapingbee_api_key = "LPD3U2VTEUZO4UAU37ZMZR6U87P39VCDY2B9NTI3EPK3Q15HVQL54D3VXHACEV17TE3AZ70XYU1Q6E8G"
        
        print(f"Iniciando requisição ao ScrapingBee...")
        
        # Etapa 1: Acessar a página inicial com configurações básicas
        # Removendo parâmetros que podem estar causando o erro 400
        url = "https://app.scrapingbee.com/api/v1/"
        params = {
            "api_key": scrapingbee_api_key,
            "url": "http://200.198.51.71/detec/filtro_boletim_es/",
            "cookies": True
        }
        
        print("Enviando requisição para a página inicial...")
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        
        print(f"Resposta recebida: Status {response.status_code}")
        
        # Extrair cookies da resposta
        cookies = response.cookies.get_dict()
        print(f"Cookies obtidos: {cookies}")
        
        # Etapa 2: Enviar POST para selecionar o mercado (CEASA GRANDE VITÓRIA)
        params = {
            "api_key": scrapingbee_api_key,
            "url": "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php",
            "cookies": True
        }
        
        data = {
            "hdn_operacao": "filtro",
            "sel_mercado": "211"  # ID do CEASA GRANDE VITÓRIA
        }
        
        print("Enviando POST para selecionar o mercado...")
        response = requests.post(url, params=params, data=data, cookies=cookies, timeout=60)
        response.raise_for_status()
        
        print(f"Resposta recebida: Status {response.status_code}")
        
        # Atualizar cookies
        cookies.update(response.cookies.get_dict())
        
        # Extrair a data mais recente disponível
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
        
        print(f"Data mais recente encontrada: {data_mais_recente}")
        
        # Etapa 3: Enviar POST com a data selecionada
        params = {
            "api_key": scrapingbee_api_key,
            "url": "http://200.198.51.71/detec/filtro_boletim_es/filtro_boletim_es.php",
            "cookies": True
        }
        
        data = {
            "hdn_operacao": "filtro",
            "hdn_mercado": "211",
            "sel_mercado": "211",
            "sel_data": data_mais_recente
        }
        
        print("Enviando POST com a data selecionada...")
        response = requests.post(url, params=params, data=data, cookies=cookies, timeout=60)
        response.raise_for_status()
        
        print(f"Resposta recebida: Status {response.status_code}")
        
        # Atualizar cookies
        cookies.update(response.cookies.get_dict())
        
        # Etapa 4: Acessar a página do boletim completo com configurações básicas
        params = {
            "api_key": scrapingbee_api_key,
            "url": "http://200.198.51.71/detec/boletim_completo_es/boletim_completo_es.php",
            "cookies": True
        }
        
        print("Acessando a página do boletim completo...")
        response = requests.get(url, params=params, cookies=cookies, timeout=90)
        response.raise_for_status()
        
        print(f"Resposta recebida: Status {response.status_code}")
        
        # Extrair os dados da tabela
        soup = BeautifulSoup(response.text, 'html.parser')
        tabela = soup.find('table', {'class': 'tabela'})
        
        if not tabela:
            print("Tabela não encontrada na página")
            print(f"Conteúdo da página: {response.text[:500]}...")
            return None
        
        print("Tabela encontrada, extraindo dados...")
        
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
        print(f"Erro ao obter cotações via ScrapingBee: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

def obter_cotacoes_ceasa():
    """
    Função principal para obter cotações.
    """
    # Verificar se há dados em cache válidos
    if not cache_expirado() and cache['dados'] is not None:
        print(f"Usando dados do cache - próxima atualização programada para 11h da manhã")
        return cache['dados']
    
    # Verificar se é hora de atualizar (11h da manhã)
    hora_atual = datetime.now().hour
    if hora_atual != 11 and cache['dados'] is not None:
        print(f"Não é hora de atualizar (hora atual: {hora_atual}). Usando dados do cache.")
        return cache['dados']
    
    # Se for 11h ou não houver dados em cache, obter novos dados
    print(f"Hora atual: {hora_atual}. Obtendo novos dados...")
    df = obter_cotacoes_ceasa_via_scrapingbee()
    if df is not None and not df.empty:
        return df
    
    # Se falhar e houver dados em cache, usar o cache mesmo expirado
    if cache['dados'] is not None:
        print("Falha ao obter novos dados. Usando dados do cache existente.")
        return cache['dados']
    
    # Se não houver dados em cache, retornar None
    print("Não foi possível obter dados e não há cache disponível")
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
        # Obter a hora atual
        hora_atual = datetime.now().hour
        
        # Verificar se há dados em cache
        dados_cache = cache['dados'] is not None
        
        # Verificar se o cache está expirado
        cache_exp = cache_expirado()
        
        # Preparar resposta de depuração
        debug_info = {
            'status': 'success' if dados_cache else 'error',
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'hora_atual': hora_atual,
            'atualizacao_programada': {
                'hora_programada': 11,
                'proxima_atualizacao': 'Hoje às 11:00' if hora_atual < 11 else 'Amanhã às 11:00',
                'atualizacao_permitida_agora': hora_atual == 11 or not dados_cache
            },
            'cache_status': {
                'cache_ativo': dados_cache,
                'ultima_atualizacao': datetime.fromtimestamp(cache['ultima_atualizacao']).strftime('%d/%m/%Y %H:%M:%S') if cache['ultima_atualizacao'] else None,
                'tempo_expiracao': cache['tempo_expiracao'],
                'expirado': cache_exp
            },
            'dados': {
                'obtidos': dados_cache,
                'quantidade': len(cache['dados']) if dados_cache else 0,
                'amostra': cache['dados'].head(5).to_dict(orient='records') if dados_cache else None
            }
        }
        
        return jsonify(debug_info)
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': error_traceback,
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        })

@app.route('/force-update')
def force_update():
    """Rota para forçar a atualização dos dados, ignorando a programação"""
    try:
        # Limpar o cache
        cache['dados'] = None
        cache['ultima_atualizacao'] = None
        
        # Obter novos dados
        df = obter_cotacoes_ceasa_via_scrapingbee()
        
        # Verificar se obteve dados
        if df is not None and not df.empty:
            return jsonify({
                'status': 'success',
                'message': 'Dados atualizados com sucesso',
                'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'quantidade': len(df)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Não foi possível obter novos dados',
                'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            })
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': error_traceback,
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        })

if __name__ == '__main__':
    # Configuração para produção
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

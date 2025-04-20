# Guia de Implementação da Solução com Proxy

Este documento explica como implementar e configurar a solução que utiliza serviços de proxy para acessar os dados do CEASA-ES.

## Visão Geral da Solução

A nova solução implementa uma abordagem robusta utilizando serviços de proxy intermediários para contornar o bloqueio que o site do CEASA-ES impõe às requisições vindas do Render.com. A implementação:

1. Utiliza múltiplos serviços de proxy (Piloterr e ScrapingBee) com fallback automático
2. Implementa um sistema de cache para reduzir o número de requisições
3. Simula um navegador real com headers e cookies apropriados
4. Inclui uma rota de depuração para facilitar a identificação de problemas

## Serviços de Proxy Utilizados

### Piloterr
- Oferece 50 requisições gratuitas
- Utilizado como primeira opção
- Documentação: https://www.piloterr.com/docs

### ScrapingBee
- Utilizado como backup caso o Piloterr falhe
- Documentação: https://www.scrapingbee.com/docs

## Configuração dos Serviços de Proxy

Para utilizar esta solução em produção, você precisará:

1. **Criar uma conta no Piloterr**:
   - Acesse https://www.piloterr.com/
   - Registre-se para obter uma chave API gratuita
   - Substitua `"DEMO_KEY"` no código por sua chave API real

2. **Criar uma conta no ScrapingBee (opcional, mas recomendado como backup)**:
   - Acesse https://www.scrapingbee.com/
   - Registre-se para obter uma chave API
   - Substitua `"DEMO_KEY"` no código por sua chave API real

## Implementação no Render.com

1. Faça o upload dos arquivos atualizados para o Render.com
2. Certifique-se de que as dependências estão corretamente instaladas:
   - requests
   - beautifulsoup4
   - pandas
   - flask
3. Configure as variáveis de ambiente no Render.com (opcional):
   - PILOTERR_API_KEY: Sua chave API do Piloterr
   - SCRAPINGBEE_API_KEY: Sua chave API do ScrapingBee

## Monitoramento e Manutenção

A solução inclui uma rota de depuração que fornece informações detalhadas sobre o processo de obtenção dos dados:

- Acesse `https://seu-app.onrender.com/debug` para ver informações sobre:
  - Status da última tentativa de obtenção de dados
  - Estado do cache
  - Quantidade de dados obtidos
  - Amostra dos dados

## Limitações e Considerações

1. **Limites de Requisições**:
   - O Piloterr oferece 50 requisições gratuitas
   - Após esse limite, você precisará adquirir um plano pago ou usar apenas o ScrapingBee

2. **Tempo de Resposta**:
   - As requisições através de proxies podem ser mais lentas que requisições diretas
   - O sistema de cache ajuda a mitigar esse problema

3. **Manutenção**:
   - O site do CEASA-ES pode mudar sua estrutura ou implementar novas medidas anti-bot
   - Nesse caso, a solução precisará ser atualizada

## Solução de Problemas

Se os dados não estiverem sendo exibidos:

1. Verifique a rota de depuração para identificar onde está ocorrendo o problema
2. Confirme que suas chaves API estão corretas e ativas
3. Verifique se você não excedeu o limite de requisições dos serviços de proxy
4. Verifique se o site do CEASA-ES está acessível e funcionando normalmente

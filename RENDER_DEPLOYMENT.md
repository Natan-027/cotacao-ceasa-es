# Guia de Implantação no Render.com

Este guia detalha o processo de implantação da aplicação de Cotações CEASA Grande Vitória no Render.com usando um repositório GitHub.

## Pré-requisitos

1. Uma conta no [GitHub](https://github.com/)
2. Uma conta no [Render.com](https://render.com/) (você pode se cadastrar gratuitamente)

## Passo a Passo

### 1. Preparar o Repositório GitHub

1. Faça login na sua conta GitHub
2. Crie um novo repositório (por exemplo, "ceasa-cotacoes")
3. Faça upload de todos os arquivos deste projeto para o seu repositório:
   - app.py
   - ceasa_scraper.py
   - requirements.txt
   - Procfile
   - runtime.txt
   - README.md
   - templates/index.html
   - templates/error.html

### 2. Conectar o Render.com ao GitHub

1. Acesse [Render.com](https://render.com/) e faça login
2. No dashboard, clique em "New" e selecione "Web Service"
3. Escolha a opção "Connect to GitHub"
4. Autorize o Render a acessar sua conta GitHub
5. Selecione o repositório que você criou

### 3. Configurar o Web Service

Configure o serviço com as seguintes opções:

- **Name**: ceasa-cotacoes (ou outro nome de sua preferência)
- **Environment**: Python
- **Region**: Escolha a região mais próxima do Brasil (geralmente US East)
- **Branch**: main (ou a branch principal do seu repositório)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`
- **Plan**: Free (para começar)

### 4. Configurações Avançadas (Opcional)

Expanda a seção "Advanced" e adicione as seguintes variáveis de ambiente:

- `PYTHON_VERSION`: 3.10.0
- `TZ`: America/Sao_Paulo (para garantir que o horário do Brasil seja usado corretamente)

### 5. Criar o Web Service

Clique no botão "Create Web Service" para iniciar o processo de implantação.

O Render irá:
1. Clonar seu repositório
2. Instalar as dependências
3. Iniciar a aplicação

### 6. Acessar a Aplicação

Após a conclusão da implantação (pode levar alguns minutos), você receberá um URL para acessar sua aplicação, como:
```
https://ceasa-cotacoes.onrender.com
```

Este URL estará disponível na página do seu serviço no dashboard do Render.

### 7. Configurar Implantação Automática

Por padrão, o Render configura implantação automática. Isso significa que sempre que você fizer alterações no seu repositório GitHub, o Render automaticamente reimplantará sua aplicação.

### 8. Monitoramento e Logs

Você pode monitorar sua aplicação e visualizar logs acessando seu serviço no dashboard do Render:

1. Faça login no Render.com
2. Selecione seu serviço
3. Clique na aba "Logs" para ver os logs da aplicação

### Solução de Problemas

Se sua aplicação não iniciar corretamente:

1. Verifique os logs para identificar o problema
2. Certifique-se de que todas as dependências estão listadas no arquivo requirements.txt
3. Verifique se o comando de inicialização (gunicorn app:app) está correto

### Considerações sobre o Plano Gratuito

No plano gratuito do Render:
- Sua aplicação ficará inativa após 15 minutos sem tráfego
- Quando receber uma nova solicitação, levará alguns segundos para reiniciar
- Há um limite de 750 horas de uso por mês

Para uma aplicação de produção que precisa estar sempre disponível, considere atualizar para um plano pago.

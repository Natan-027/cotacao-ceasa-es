# Correção para o Erro de Template no Render.com

Este documento explica a correção implementada para resolver o erro "TemplateNotFound: index.html" que ocorreu durante o deploy no Render.com.

## Problema Identificado

Ao analisar o log de erro fornecido, identifiquei que o problema estava relacionado à falta do arquivo de template `index.html` no ambiente de produção do Render.com:

```
jinja2.exceptions.TemplateNotFound: index.html
```

Este é um erro comum em aplicações Flask quando:
1. A pasta `templates` não é corretamente incluída no deploy
2. A estrutura de diretórios no ambiente de produção difere do ambiente de desenvolvimento

## Solução Implementada

Para resolver este problema, implementei uma solução simples e eficaz que elimina a dependência do arquivo `index.html`:

1. **Modificação da rota principal**: Alterei a função da rota principal (`/`) para redirecionar diretamente para a rota `/wix` em vez de tentar renderizar o template ausente.

```python
@app.route('/')
def index():
    # Redirecionar para a página Wix em vez de tentar renderizar um template
    return redirect('/wix')
```

Esta abordagem tem várias vantagens:
- Elimina a necessidade do arquivo `index.html`
- Simplifica a estrutura da aplicação
- Garante que os usuários sejam direcionados diretamente para a página principal de cotações
- Resolve o problema sem necessidade de modificar a estrutura de arquivos no Render.com

## Como Implementar a Correção

1. Substitua o arquivo `app.py` pelo novo arquivo fornecido
2. Faça o deploy novamente no Render.com
3. Não é necessário modificar nenhum outro arquivo ou estrutura

## Verificação

Após implementar esta correção, o erro "TemplateNotFound" não deve mais ocorrer, e a aplicação deve funcionar corretamente, redirecionando os usuários para a página de cotações quando acessarem a URL principal.

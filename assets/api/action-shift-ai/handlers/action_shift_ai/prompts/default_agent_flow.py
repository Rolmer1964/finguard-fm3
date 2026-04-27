prompt = """
PATH: {file_path}
FILE: {file_name}

Considerando que as diretrizes definidas pelo usuário têm caráter mandatório, altere o arquivo somente se necessário.
Se houver alterações, retorne o arquivo atualizado e completo.
Se não houver alterações, retorne em branco.

Diretrizes do usuário:
{user_prompt}

```{file_lang}
{content}
```

FORMATO DE SAÍDA OBRIGATÓRIO (JSON válido):

CRÍTICO - Regras de formatação JSON para evitar erros de parse:

1. ESTRUTURA:
   - Use apenas aspas duplas (") para strings
   - Não adicione texto antes ou depois do JSON
   - Não inclua comentários ou explicações

2. ESCAPING DE CARACTERES ESPECIAIS:
   - Nova linha: \\n (NUNCA quebra real)
   - Tab: \\t (NUNCA tab real)
   - Barra invertida: \\\\
   - Aspas duplas: \\"
   - Carriage return: \\r

3. CÓDIGO PYTHON:
   - Docstrings: \\"\\"\\\"texto\\"\\"\\\"
   - Indentação: use \\n + espaços (ex: "\\n    ")
   - Strings multilinha: use \\n entre linhas

4. CARACTERES ESPECIAIS:
   - Cirílico/Unicode: prefira escape Unicode (\\uXXXX)
   - Remova caracteres de controle (ASCII 0-31) exceto \\n, \\t, \\r
   - Emojis: use escape Unicode (\\uXXXX)

5. VALIDAÇÃO:
   - Antes de retornar, verifique se o JSON é válido
   - Teste mentalmente: consegue fazer json.loads() sem erro?

Exemplo de resposta CORRETA:
{{
  "path": "{file_path}",
  "content": "def example():\\n    \\"\\"\\\"Docstring here\\"\\"\\\"\\n    pass\\n",
  "reason": "Adicionada documentação conforme diretrizes do usuário."
}}

Exemplo de resposta INCORRETA (NÃO FAÇA ISSO):
{{
  "path": "{file_path}",
  "content": "def example():
    \"\"\"Docstring\"\"\"
    pass",
  "reason": "Documentação adicionada"
}}

Sua resposta (apenas o JSON válido):
"""

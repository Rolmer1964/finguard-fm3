prompt = """
PATH: {file_path}
FILE: {file_name}

De acordo com suas definições, altere o arquivo somente se necessário.
Se houver alterações, retorne o arquivo atualizado e completo.
Se não houver alterações, retorne em branco.

```{file_lang}
{content}
```

FORMATO DE SAÍDA OBRIGATÓRIO (JSON válido):

IMPORTANTE - Regras de formatação JSON:
1. Use aspas duplas (") para strings
2. Escape caracteres especiais: \\n (nova linha), \\t (tab), \\\\ (barra invertida), \\" (aspas)
3. NÃO inclua quebras de linha reais dentro de strings - use \\n
4. NÃO use caracteres de controle (ASCII < 32) exceto \\n, \\t, \\r
5. Para código Python com docstrings, escape as aspas triplas: \\"\\"\\\"

Exemplo de resposta válida:
{{
  "path": "{file_path}",
  "content": "def example():\\n    \\"\\"\\\"Docstring here\\"\\"\\\"\\n    pass",
  "reason": "Breve resumo com 15 palavras sobre porque precisa ser alterado."
}}

Sua resposta (apenas o JSON, sem texto adicional):
"""

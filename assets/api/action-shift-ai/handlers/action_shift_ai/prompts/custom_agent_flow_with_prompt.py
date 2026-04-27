prompt = """
PATH: {file_path}
FILE: {file_name}

De acordo com suas definições, altere o arquivo somente se necessário.
Se houver alterações, retorne o arquivo atualizado e completo.
Se não houver alterações, retorne em branco.

O usuário adicionou essas instruções que devem ser consideradas prioritárias:
{user_prompt}

```{file_lang}
{content}
```

FORMATO DE SAÍDA OBRIGATÓRIO (JSON válido):

IMPORTANTE - Regras de formatação JSON:
1. Use aspas duplas (") para strings
2. Escape caracteres especiais corretamente:
   - Nova linha: \\n (não quebra real)
   - Tab: \\t
   - Barra invertida: \\\\
   - Aspas duplas: \\"
3. Para código Python:
   - Docstrings com aspas triplas: \\"\\"\\\"texto\\"\\"\\\"
   - Indentação: use \\n seguido de espaços (não \\t)
4. NÃO inclua caracteres de controle (ASCII < 32) exceto \\n, \\t, \\r
5. Para caracteres Unicode/Cirílico: use escape Unicode (\\uXXXX) se necessário

Exemplo de resposta válida:
{{
  "path": "{file_path}",
  "content": "def example():\\n    \\"\\"\\\"Docstring here\\"\\"\\\"\\n    pass",
  "reason": "Breve resumo com 15 palavras sobre porque precisa ser alterado."
}}

Sua resposta (apenas o JSON, sem texto adicional antes ou depois):
"""

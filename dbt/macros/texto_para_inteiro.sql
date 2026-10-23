{# Converte texto em inteiro só quando o texto é um número; o resto vira nulo
   e aparece nos testes, em vez de derrubar a view inteira. #}
{% macro texto_para_inteiro(coluna) -%}
    case when trim({{ coluna }}) ~ '^-?\d+$' then trim({{ coluna }})::integer end
{%- endmacro %}

{% macro texto_para_decimal(coluna) -%}
    case when trim({{ coluna }}) ~ '^\d+(\.\d+)?$' then trim({{ coluna }})::numeric end
{%- endmacro %}

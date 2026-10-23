{# Schemas com nome limpo (staging, intermediate, marts), bom para projeto solo.
   Em ambiente compartilhado, voltar ao padrão <alvo>_<schema>. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}

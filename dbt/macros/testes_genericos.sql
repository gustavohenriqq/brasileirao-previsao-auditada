{# Testes genéricos próprios, sem pacote externo. #}

{% test combinacao_unica(model, colunas) %}
select {{ colunas | join(', ') }}, count(*) as repeticoes
from {{ model }}
group by {{ colunas | join(', ') }}
having count(*) > 1
{% endtest %}

{% test valor_minimo(model, column_name, minimo) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} < {{ minimo }}
{% endtest %}

{# Devolve as linhas que atendem a condição: uma falha por linha, para o
   aviso contar jogos e não valores distintos. #}
{% test linhas_onde(model, condicao) %}
select *
from {{ model }}
where {{ condicao }}
{% endtest %}

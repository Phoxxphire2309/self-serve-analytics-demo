-- Daily calendar the semantic layer (MetricFlow) needs for time-based metrics.
-- Covers 1992-01-01 to 2001-12-31, which spans all TPC-H dates.
{% if target.type == 'snowflake' %}
select
    dateadd(day, row_number() over (order by seq4()) - 1, '1992-01-01'::date) as date_day
from table(generator(rowcount => 3653))
{% else %}
select
    cast(range as date) as date_day
from range(date '1992-01-01', date '2002-01-01', interval 1 day)
{% endif %}

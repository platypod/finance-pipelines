{{ config(materialized='incremental', unique_key='beat_id', on_schema_change='fail', full_refresh=false) }}

select
  beat_id,
  beat_at,
  source,
  round(extract(epoch from (_ingested_at - beat_at))::numeric, 3)::numeric(12,3) as lag_seconds
from {{ source('bronze', 'heartbeat_raw') }}
{% if is_incremental() %}
where beat_at > (select coalesce(max(beat_at), '-infinity'::timestamptz) from {{ this }})
{% endif %}

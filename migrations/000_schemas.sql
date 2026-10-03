-- Medallion schemas + ops plumbing. Idempotent; run by `pp migrate` as the owner role.
create schema if not exists bronze;
create schema if not exists silver;
create schema if not exists gold;
create schema if not exists ops;

-- Roles are created by the database init (stack/src/finance). Grants are applied
-- only to roles that exist, so the same migration works on a bare local database.
--   finance_ingest    writes bronze            (+ ops run log)
--   finance_transform reads bronze, writes silver/gold (+ ops run log)
--   finance_grafana   reads gold only
do $$
declare
  r record;
begin
  for r in select * from (values
      ('finance_ingest',    array['bronze','ops'],                  array['bronze'],        array['ops'],           array[]::text[]),
      ('finance_transform', array['bronze','silver','gold','ops'],  array['bronze'],        array['ops'],           array['silver','gold']),
      ('finance_grafana',   array['gold'],                          array['gold'],          array[]::text[],        array[]::text[])
    ) as t(rolname, usage_schemas, read_schemas, rw_schemas, write_schemas)
  loop
    continue when not exists (select 1 from pg_roles where rolname = r.rolname);
    declare s text;
    begin
      foreach s in array r.usage_schemas loop
        execute format('grant usage on schema %I to %I', s, r.rolname);
      end loop;
      foreach s in array r.read_schemas loop
        execute format('grant select on all tables in schema %I to %I', s, r.rolname);
        execute format('alter default privileges in schema %I grant select on tables to %I', s, r.rolname);
      end loop;
      foreach s in array r.rw_schemas loop
        execute format('grant select, insert, update on all tables in schema %I to %I', s, r.rolname);
        execute format('grant usage on all sequences in schema %I to %I', s, r.rolname);
        execute format('alter default privileges in schema %I grant select, insert, update on tables to %I', s, r.rolname);
        execute format('alter default privileges in schema %I grant usage on sequences to %I', s, r.rolname);
      end loop;
      foreach s in array r.write_schemas loop
        execute format('grant select, insert, update, delete on all tables in schema %I to %I', s, r.rolname);
        execute format('alter default privileges in schema %I grant select, insert, update, delete on tables to %I', s, r.rolname);
      end loop;
      -- ingest owns bronze loads: append, and replace a file's rows when a parser is bumped (--reparse)
      if r.rolname = 'finance_ingest' then
        execute format('alter default privileges in schema bronze grant insert, delete on tables to %I', r.rolname);
        execute format('grant insert, delete on all tables in schema bronze to %I', r.rolname);
      end if;
    end;
  end loop;
end $$;

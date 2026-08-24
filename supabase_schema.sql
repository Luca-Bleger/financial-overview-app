-- Ejecutar en el SQL Editor de Supabase (Project > SQL Editor > New query).
-- Crea la tabla donde se acumulan los movimientos de todos los meses que
-- cada usuario vaya subiendo, con seguridad a nivel de fila (RLS) para que
-- nadie pueda ver ni modificar los movimientos de otra persona.

create table if not exists movimientos (
    id bigint generated always as identity primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    fecha date not null,
    descripcion text not null,
    importe numeric not null,
    categoria text not null,
    fuente text,
    creado_en timestamptz not null default now(),
    -- Evita duplicar el mismo movimiento si se sube el mismo archivo dos
    -- veces (misma clave que ya usa la app en memoria: fecha+descripcion+
    -- importe).
    unique (user_id, fecha, descripcion, importe)
);

alter table movimientos enable row level security;

create policy "Cada usuario ve solo sus movimientos"
    on movimientos for select
    using (auth.uid() = user_id);

create policy "Cada usuario inserta solo sus movimientos"
    on movimientos for insert
    with check (auth.uid() = user_id);

create policy "Cada usuario corrige solo sus movimientos"
    on movimientos for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Cada usuario borra solo sus movimientos"
    on movimientos for delete
    using (auth.uid() = user_id);

create index if not exists movimientos_user_id_idx on movimientos(user_id);

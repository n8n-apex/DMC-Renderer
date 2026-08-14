-- DMC Reference Catalog + Director Pipeline schema (Supabase/Postgres)
-- 2026-08-14. Authoritative catalog for Richard's reference corpus and the
-- Director's visual decisions. Local files remain a render cache; this is the
-- durable authority.

-- 1) Reference reports (the six Richard PDFs + any client deck)
create table if not exists ref_reports (
    id            bigint generated always as identity primary key,
    slug          text not null unique,          -- 'apex', 'buchagentur', ...
    display_name  text not null,
    source_pdf    text not null,                 -- filename
    is_client     boolean not null default false,-- true for client decks, false for Richard's
    page_count    int not null default 0,
    metadata      jsonb not null default '{}',
    created_at    timestamptz not null default now()
);

-- 2) Reference faces/pages (unified: legacy index rows + atlas faces)
create table if not exists ref_faces (
    id            bigint generated always as identity primary key,
    report_id     bigint not null references ref_reports(id) on delete cascade,
    page_no       int not null,                  -- physical page in the source PDF
    face_index    int not null default 0,        -- 0 for A4; 0/1 for A3 spread halves
    st_type       text not null,                 -- ST-01..ST-22, ST-FAZIT, OTHER
    role          text not null default '',      -- atlas editorial role if known
    format        text not null default 'a4',    -- 'a4' | 'a3'
    density       text not null default '',      -- sparse/balanced/dense (atlas measure)
    mechanism     text not null default '',      -- dominant visual mechanism
    devices       text not null default '',      -- comma list of visual devices
    axes          jsonb not null default '{}',   -- brand-agnostic axes snapshot
    argument      text not null default '',      -- extracted page argument (text)
    png_path      text not null default '',      -- local cache path (relative to repo)
    sha256        text not null default '',      -- content hash of the raster
    metadata      jsonb not null default '{}',   -- atlas/legacy raw row
    unique (report_id, page_no, face_index)
);

-- 3) Director decisions: what the selector chose and why
create table if not exists director_decisions (
    id            bigint generated always as identity primary key,
    client_slug   text not null,
    report_id     text not null default '',
    face_key      text not null,                 -- 'slot.07' or 'face.07'
    st_type       text not null,
    ref_face_id   bigint not null references ref_faces(id) on delete cascade,
    rationale     text not null,                 -- WHY this reference was selected
    visual_job    text not null default '',      -- what the element must explain
    brief         jsonb not null default '{}',   -- Director brief (geometry, evidence rules)
    generator_brief jsonb not null default '{}', -- fal/device prompt contract
    created_at    timestamptz not null default now()
);

-- 4) Run history: one row per render attempt, with review evidence
create table if not exists render_runs (
    id            bigint generated always as identity primary key,
    client_slug   text not null,
    report_id     text not null default '',
    build_id      text not null default '',
    state         text not null default 'started', -- started|review_candidate|review_required|shipped|rejected
    decisions     jsonb not null default '[]',     -- director_decisions ids for this run
    review        jsonb not null default '{}',     -- page scores / attempt records
    created_at    timestamptz not null default now(),
    finished_at   timestamptz
);

create index if not exists ref_faces_st_type_idx   on ref_faces(st_type);
create index if not exists ref_faces_report_idx    on ref_faces(report_id);
create index if not exists director_client_idx     on director_decisions(client_slug, report_id);
create index if not exists render_runs_client_idx  on render_runs(client_slug, report_id);

-- 5) PDF binaries (durable authority; Storage migration path later)
create table if not exists ref_pdf_files (
    report_id   bigint not null references ref_reports(id) on delete cascade,
    data        bytea not null,
    sha256      text not null,
    uploaded_at timestamptz not null default now(),
    primary key (report_id)
);

-- NOTE: PDF binaries go to Supabase STORAGE (bucket `references/`), not
-- Postgres bytea — the apex PDF is 721MB; pgbouncer bytea inserts time out.
-- Storage upload needs the project URL + service role key (dashboard →
-- Settings → API). Local rasters remain the render cache; Postgres holds
-- metadata + hashes (the catalog the selector queries).

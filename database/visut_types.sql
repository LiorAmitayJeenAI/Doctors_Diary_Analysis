-- Table: public.visit_types

-- DROP TABLE IF EXISTS public.visit_types;

CREATE TABLE IF NOT EXISTS public.visit_types
(
    visit_type_code character varying(5) COLLATE pg_catalog."default" NOT NULL,
    visit_type_name text COLLATE pg_catalog."default",
    calendar_short_name text COLLATE pg_catalog."default",
    source_description text COLLATE pg_catalog."default",
    source_short_description text COLLATE pg_catalog."default",
    CONSTRAINT visit_types_pkey PRIMARY KEY (visit_type_code)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.visit_types
    OWNER to jeen_pg_dev_admin;
BEGIN;

CREATE INDEX idx_schedules_analysis_run_id
    ON schedules (analysis_run_id);

CREATE INDEX idx_appointments_analysis_run_id
    ON appointments (analysis_run_id);

CREATE INDEX idx_visits_analysis_run_id
    ON visits (analysis_run_id);

CREATE INDEX idx_analysis_metrics_analysis_run_id
    ON analysis_metrics (analysis_run_id);

CREATE INDEX idx_recommendations_analysis_run_id
    ON recommendations (analysis_run_id);

-- Covers doctor_calendar_id lookups and "latest runs for a calendar".
-- A separate index on analysis_runs.doctor_calendar_id is not created
-- because it is already the leading column of this composite index.
CREATE INDEX idx_analysis_runs_doctor_calendar_id_created_at
    ON analysis_runs (doctor_calendar_id, created_at);

COMMIT;

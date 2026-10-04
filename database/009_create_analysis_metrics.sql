BEGIN;

CREATE TABLE analysis_metrics (
    analysis_metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    analysis_run_id    BIGINT NOT NULL REFERENCES analysis_runs (analysis_run_id),
    metrics_json       JSONB NOT NULL,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE analysis_metrics IS
    'תוצרים מספריים/מחושבים של הרצת ניתוח. Feature set עדיין מתפתח ולכן נשמר כ-JSONB.';

COMMENT ON COLUMN analysis_metrics.analysis_metric_id IS 'מפתח פנימי של רשומת המדדים.';
COMMENT ON COLUMN analysis_metrics.analysis_run_id IS 'FK אל analysis_runs.analysis_run_id.';
COMMENT ON COLUMN analysis_metrics.metrics_json IS 'מדדי הניתוח כ-JSONB. לא מפורק לעמודות בשלב זה.';
COMMENT ON COLUMN analysis_metrics.created_at IS 'מועד יצירת רשומת המדדים.';

COMMIT;

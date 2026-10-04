BEGIN;

CREATE TABLE recommendations (
    recommendation_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    analysis_run_id      BIGINT NOT NULL REFERENCES analysis_runs (analysis_run_id),
    recommendation_type  VARCHAR(100),
    title                VARCHAR(255),
    recommendation_text  TEXT NOT NULL,
    reason               TEXT,
    expected_impact      TEXT,
    confidence           NUMERIC(5, 4),
    evidence_json        JSONB,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT recommendations_confidence_range_chk
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

COMMENT ON TABLE recommendations IS
    'המלצות שנוצרו עבור הרצת ניתוח. evidence_json שומר את המדדים/העובדות שעליהם ההמלצה מבוססת.';

COMMENT ON COLUMN recommendations.recommendation_id IS 'מפתח פנימי של ההמלצה.';
COMMENT ON COLUMN recommendations.analysis_run_id IS 'FK אל analysis_runs.analysis_run_id.';
COMMENT ON COLUMN recommendations.recommendation_type IS 'סוג ההמלצה.';
COMMENT ON COLUMN recommendations.title IS 'כותרת ההמלצה.';
COMMENT ON COLUMN recommendations.recommendation_text IS 'גוף ההמלצה.';
COMMENT ON COLUMN recommendations.reason IS 'הסיבה להמלצה.';
COMMENT ON COLUMN recommendations.expected_impact IS 'השפעה צפויה.';
COMMENT ON COLUMN recommendations.confidence IS
    'רמת ביטחון בין 0 ל-1. NULL כאשר אין ערך.';
COMMENT ON COLUMN recommendations.evidence_json IS 'מדדים/עובדות שתומכים בהמלצה.';
COMMENT ON COLUMN recommendations.created_at IS 'מועד יצירת ההמלצה.';

COMMIT;

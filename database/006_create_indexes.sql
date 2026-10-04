BEGIN;

-- FK indexes for join paths from calendars to child tables.
CREATE INDEX idx_schedules_doctor_calendar_id
    ON schedules (doctor_calendar_id);

CREATE INDEX idx_appointments_doctor_calendar_id
    ON appointments (doctor_calendar_id);

CREATE INDEX idx_visits_doctor_calendar_id
    ON visits (doctor_calendar_id);

-- Analysis / lookup indexes.
CREATE INDEX idx_appointments_appointment_date
    ON appointments (appointment_date);

CREATE INDEX idx_appointments_member_id
    ON appointments (member_id);

CREATE INDEX idx_visits_customer_id
    ON visits (customer_id);

CREATE INDEX idx_visits_encounter_start_datetime
    ON visits (encounter_start_datetime);

-- Not created:
--   doctor_calendars.doctor_id — already the leading column of
--     UNIQUE (doctor_id, facility_code, role_code).
--   appointments.visit_type_code, appointments.booking_status —
--     low cardinality (a few distinct values); btree indexes would add little.

COMMIT;

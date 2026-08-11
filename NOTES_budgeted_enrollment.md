# Budgeted enrollment / capacity — notes

## `enrollment.budgeted_enrollment`
Static budget targets by school and grade. **Manually supplied** from the Enrollment Summary Google Sheet (or CSV), with a `year` column (`25-26`, `26-27`, …). See `load_budgeted_enrollment_26_27.py` for the 26–27 load pattern.

## `enrollment.budgeted_enrollment_capacity`
Built by this pipeline for **`views.enrollment_demographics`**.

**Inputs only:**
- `views.student_to_teacher` — live PowerSchool roster counts by school/grade for the active year
- `enrollment.budgeted_enrollment` — static budget for the active year

**Not used:** `intent_to_return_results`, `completed_registrations` (those were for an older new/returning forecast model).

**Output columns for demographics:** `school_name`, `grade_level`, `student_count`, `budgeted_enrollment` (plus `seats_remaining`, `percent_of_seats_filled`, `year`, `program_id`).

This job writes GCS only (`budgeted_enrollment_capacity.csv`); the morning bucket→BQ refresh loads the table.

Active year is set in `main.py` (`YEAR = "26-27"`).

**History:** We are not using `YearlyDataAppender` for capacity. `25-26` stays available via `enrollment.budgeted_enrollment_capacity_hardcode_8_18_25`. The live table is current-year only.

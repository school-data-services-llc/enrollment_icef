# Budgeted enrollment — next-year note

`icef-437920.enrollment.budgeted_enrollment` is **not** auto-refreshed from SchoolMint or PowerSchool.

## How values get there

Budget targets are **manually supplied** from the Enrollment Summary Google Sheet (grade × school **Budgeted Enrollment** on each school tab), then loaded into BigQuery—typically via a one-off CSV/script load (see `load_budgeted_enrollment_26_27.py` for the 26–27 pattern).

The table includes a `year` column (`25-26`, `26-27`, …). The enrollment capacity job should filter to the active year.

## When rolling to a new year

1. Confirm the Enrollment Summary sheet for that academic year (or export CSV).
2. Load grade-level + school-total budgeted rows into `enrollment.budgeted_enrollment` with the new `year`.
3. Keep prior years; do not overwrite them without tagging `year`.
4. Point `create_budgeted_enrollment()` at the new year filter.
5. Optionally update `google_sheets_hookups` if that pipeline should write the GCS/BQ feed again.

"""Extract 2026-27 budgeted enrollment from Enrollment Summary sheet and load to BQ."""
import pandas as pd
from google.cloud import bigquery
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import get_as_dataframe

CREDENTIALS = r"C:\Users\alysi\.gcp\icef-437920.json"
SHEET_ID = "1Vb2--b0S6Nu5uzJUEkNJ5mRI31OnLfI4AOSbKsAK0RA"
YEAR = "26-27"
TABLE_ID = "icef-437920.enrollment.budgeted_enrollment"

SCHOOL_TABS = [
    "Inglewood",
    "Innovation",
    "VP Elem.",
    "VP Middle",
    "VPHS",
    "Vista Elem.",
    "Vista Middle",
]

PROGRAM_ID_BY_TAB = {
    "Inglewood": 10392,
    "Innovation": 10393,
    "VP Elem.": 10394,
    "VP Middle": 10007,
    "VPHS": 10395,
    "Vista Elem.": 12239,
    "Vista Middle": 10396,
}

SCHOOL_ACRONYM = {
    10396: "IVMA",
    10393: "IILA",
    10392: "IIECA",
    10394: "VPES",
    12239: "IVEA",
    10007: "VPMS",
    10395: "VPHS",
}

GRADE_MAP = {
    "TK": -1,
    "K": 0,
    "Kinder.": 0,
    "Kindergarten": 0,
    "1": 1,
    "1st Grade": 1,
    "2": 2,
    "2nd Grade": 2,
    "3": 3,
    "3rd Grade": 3,
    "4": 4,
    "4th Grade": 4,
    "5": 5,
    "5th Grade": 5,
    "6": 6,
    "6th Grade": 6,
    "7": 7,
    "7th Grade": 7,
    "8": 8,
    "8th Grade": 8,
    "9": 9,
    "9th Grade": 9,
    "10": 10,
    "10th Grade": 10,
    "11": 11,
    "11th Grade": 11,
    "12": 12,
    "12th Grade": 12,
}


def open_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS, scope)
    return gspread.authorize(creds).open_by_key(SHEET_ID)


def _normalize_grade(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    text = str(value).strip()
    if text in GRADE_MAP:
        return GRADE_MAP[text]
    # numeric strings like "6.0"
    try:
        return int(float(text))
    except ValueError:
        return None


def extract_school_tabs(ss):
    rows = []
    for tab in SCHOOL_TABS:
        ws = ss.worksheet(tab)
        raw = get_as_dataframe(ws, evaluate_formulas=True, header=None)
        raw = raw.reset_index(drop=True)

        # Find header row containing "Grade" and "Budgeted Enrollment"
        header_idx = None
        for i, row in raw.iterrows():
            vals = [str(v).strip() if pd.notna(v) else "" for v in row.tolist()[:5]]
            if "Grade" in vals and any("Budgeted Enrollment" in v for v in vals):
                header_idx = i
                break
        if header_idx is None:
            raise RuntimeError(f"Could not find Grade/Budgeted Enrollment header on tab {tab}")

        body = raw.iloc[header_idx + 1 :, [0, 1]].copy()
        body.columns = ["grade_raw", "budgeted_enrollment"]
        body["budgeted_enrollment"] = pd.to_numeric(body["budgeted_enrollment"], errors="coerce")
        body = body.dropna(subset=["budgeted_enrollment"])

        program_id = PROGRAM_ID_BY_TAB[tab]
        for _, r in body.iterrows():
            grade_raw = r["grade_raw"]
            budget = int(r["budgeted_enrollment"])
            # blank grade_raw with a budget value = school total row
            if pd.isna(grade_raw) or str(grade_raw).strip() == "":
                grade = None
            else:
                grade = _normalize_grade(grade_raw)
                if grade is None:
                    # skip non-grade junk rows
                    continue
            rows.append(
                {
                    "grade": grade,
                    "budgeted_enrollment": budget,
                    "school": SCHOOL_ACRONYM[program_id],
                    "program_id": program_id,
                    "year": YEAR,
                }
            )
    return pd.DataFrame(rows)


def main():
    ss = open_sheet()
    df = extract_school_tabs(ss)
    df = df.sort_values(["program_id", "grade"], na_position="first").reset_index(drop=True)
    print(df.to_string(index=False))
    print(f"\nRows: {len(df)}  Total grade-level seats: {df.loc[df['grade'].notna(), 'budgeted_enrollment'].sum()}")
    print(f"School-total seats: {df.loc[df['grade'].isna(), 'budgeted_enrollment'].sum()}")

    client = bigquery.Client.from_service_account_json(CREDENTIALS, project="icef-437920")

    # Ensure year column exists
    client.query(
        f"ALTER TABLE `{TABLE_ID}` ADD COLUMN IF NOT EXISTS year STRING"
    ).result()

    # Backfill existing untagged rows as prior year
    client.query(
        f"UPDATE `{TABLE_ID}` SET year = '25-26' WHERE year IS NULL"
    ).result()

    # Replace any existing 26-27 rows, then append
    client.query(
        f"DELETE FROM `{TABLE_ID}` WHERE year = '{YEAR}'"
    ).result()

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=[
            bigquery.SchemaField("grade", "FLOAT"),
            bigquery.SchemaField("budgeted_enrollment", "INTEGER"),
            bigquery.SchemaField("school", "STRING"),
            bigquery.SchemaField("program_id", "INTEGER"),
            bigquery.SchemaField("year", "STRING"),
        ],
    )
    load_df = df.copy()
    load_df["grade"] = load_df["grade"].astype(float)  # NaN stays for totals
    job = client.load_table_from_dataframe(load_df, TABLE_ID, job_config=job_config)
    job.result()

    verify = client.query(
        f"""
        SELECT year, COUNT(*) AS n, SUM(IF(grade IS NOT NULL, budgeted_enrollment, 0)) AS grade_budget
        FROM `{TABLE_ID}`
        GROUP BY year
        ORDER BY year
        """
    ).to_dataframe()
    print("\nBQ after load:")
    print(verify.to_string(index=False))


if __name__ == "__main__":
    main()

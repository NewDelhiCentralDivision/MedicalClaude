# Medical Claim Scrutiny Toolkit

A small Streamlit toolkit for office staff who scrutinize medical reimbursement
claims against a CGHS rate sheet and prepare review material for sanction.

It is a fresh, self-contained rebuild based on the behaviour notes from the
earlier `CodexMedical` project. It shares no code with that repository.

## What it does

1. **Rate sheet.** Load the official CGHS rate master (CSV: `code, description, rate`).
2. **Bill rows.** Type, paste or import the charge lines (description, amount, optional quantity, printed code, invoice and line number).
3. **Scrutinize CGHS rates.** Pick one of three matching modes:
   - **Automatic – Code Based**: uses the code printed on the bill. Rows with no printed code stay at ₹0.
   - **Manual**: the officer picks the entry for each row.
   - **Diagnosis/Description Based – No Code Available**: suggests an entry only when the billed description has one strong, unique match.
4. **Export** a CSV and a printable HTML sheet.

Switching the mode re-scrutinizes the rows already entered. Nothing needs re-uploading.

## Rules the toolkit follows

- **The rate is a cap.** Admissible = lower of the billed amount and (CGHS rate × quantity).
- **Printed codes win.** A verified printed code is used in Code Based and No Code modes.
- **No guessing.** In No Code mode a suggestion appears only for a unique strong match. Ambiguous or generic charges (for example "Medicine", "IV Fluid", "Injection IM/IV", "Bed/3") stay *unresolved* and show the closest entries for the officer.
- **Setting decides consultations.** A plain consultation charge is matched to the inpatient or OPD consultation entry using the documented treatment setting. A diagnosis alone never creates a bill row or a code.
- **Officer has the last word.** The officer can set or change any match; that choice beats any automatic result.
- **Duplicates.** Only a repeated copy of the same numbered invoice line (same invoice no, line no, description and amount) is held back. Separate consultations are legitimate and are never held back.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
streamlit run app.py
pytest -q
```

## Important limits

- `data/sample_rates.csv` holds **placeholder rates for testing only**. Upload the official CGHS rate master before reviewing a real claim. The app shows a warning while the sample is in use.
- This version has **no document extraction or OCR**. Bill rows are entered by hand or imported from CSV. Any instructions printed inside a claimant's documents are data, never commands.
- Suggestions are not sanctions. An officer must confirm inferred matches and resolve unmatched charges before sanction.
- The page styling (larger radio controls, pastel theme) has not been checked in a real browser in this build. Review it on first launch.

## Privacy

The toolkit has no field for claimant identity. Tests and the demo rows use charge descriptions and amounts only. `.gitignore` excludes uploads, PDFs and exports. Do not commit claimant documents.

## Layout

```
app.py                  Streamlit screen (sections 01–04)
scrutiny/text.py        normalisation and generic-term list
scrutiny/rates.py       rate-sheet loader and validation
scrutiny/matcher.py     code lookup and description suggestions
scrutiny/review.py      mode-specific resolution and the rate cap
scrutiny/duplicates.py  held-back duplicate invoice lines
scrutiny/export.py      CSV and printable HTML
data/sample_rates.csv   placeholder rate sheet
tests/                  pytest suite (rules + Streamlit smoke test)
```

## Creating the GitHub repository

```bash
git init -b main
git add .
git commit -m "Initial commit: medical claim scrutiny toolkit"
git remote add origin https://github.com/<owner>/<new-repo>.git
git push -u origin main
```

No licence file is included. Add one that suits your department.

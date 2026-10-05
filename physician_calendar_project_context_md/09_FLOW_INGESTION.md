# תהליך: ingestion

## זהות

- שם ב־Langflow: `ingestion`
- מזהה: `4ed288ea-6d9f-4637-b1f5-fc6d8aeacc9b`
- תיאור ב־Langflow: ingestion
- עודכן לאחרונה בצילום: 2026-10-05
- גודל: 15 צמתים, 12 קשתות
- מתוכם 4 הערות על הקנבס

התהליך מעלה את קובצי האקסל למסד. אין בו חישוב עסקי ואין בו מודל שפה. הפלט הוא ריצת ניתוח חדשה עם שלושת המקורות שמורים ב־PostgreSQL.

## סדר הריצה

1. **Chat Input** (`ChatInput-IY38x`) מקבל את הודעת הצ'אט.
2. **Jeen Chat Payload Splitter** (`ParseStructuredPayload-d9Pps`) מפרק את הודעת Jeen לשדות: מזהה לקוח, JWT, הודעה, קבצים ומזהים.
3. **Jeen Bundle Excel Classifier** (`jeen_bundle_excel_classifier-WbT9X`) קורא כל קובץ XLSX, מזהה את שורת הכותרת, ומסווג כל קובץ כלו"ז, תורים או ביקורים.
4. **Raw Source Normalizer** (`raw_source_normalizer-q8oFi`) מנרמל את הייצוא הגולמי, ממפה כינויי כותרות של הלו"ז לסכמה הקנונית, ושומר קוד מתקן, מספר משרה ות"ז עובד.
5. **Source Files Validator V2** (`source_files_validator-74NqE`) בודק את שלושת מקורות הנתונים אחרי הנרמול. שלושתם חייבים להסכים על אותו קוד מתקן, אותו מספר משרה ואותה ת"ז עובד, כהגדרתם ב־`01_DOMAIN_GLOSSARY.md`.
6. **Source Data Preprocessor** (`source_data_preprocessor-Vp176`) ממפה את העמודות לשמות העמודות ב־PostgreSQL ומכין שלוש טבלאות מוכנות לטעינה: לו"ז, תורים וביקורים. עדיין בלי חישוב עסקי.
7. **Doctor Calendar Upsert V2** (`doctor_calendar_upsert-LDL4v`) מוצא או יוצר את יומן הרופא לפי קוד מתקן + מספר משרה + ת"ז עובד, ומונע התנגשות עם יומן של משרה אחרת או מתקן אחר.
8. **Create Analysis Run** (`create_analysis_run-jRqgJ`) יוצר ריצת ניתוח חדשה ליומן ומחזיר `analysis_run_id`.
9. **Doctor Analysis Bulk Loader** (`doctor_analysis_bulk_loader-fmyvA`) מקבל את מזהה הריצה ואת שלוש הטבלאות מה־Preprocessor, משייך אותן ליומן ולריצה, וטוען אותן בטרנזקציה אחת. כמות הרשומות שנשמרה חייבת להיות זהה לכמות שהתקבלה.
10. **Chat Output** (`ChatOutput-5dRIx`) מציג את תוצאת הטעינה.

## הערות על הקנבס

- התהליך הוא העלאת קובצי אקסל למסד.
- הולידציה הראשונה בודקת שהעמודות בקבצים נכונות.
- הולידציה השנייה בודקת התאמה בין עמודות הקבצים לעמודות המסד.
- ה־Preprocessor קורא את שלושת הקבצים התקינים, מנקה וממיר אותם למבנה ולטיפוסים של PostgreSQL, בלי חישוב עסקי.
- ה־Bulk Loader משייך את המקורות ל־`doctor_calendar_id` ול־`analysis_run_id`.

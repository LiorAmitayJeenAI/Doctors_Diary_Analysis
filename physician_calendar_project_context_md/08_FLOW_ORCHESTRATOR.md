# תהליך: analyzes doctor's schedules

## זהות

- שם ב־Langflow: `analyzes doctor's schedules`
- מזהה: `3ce49df0-9b3b-47dd-b050-440ed1133979`
- תיאור ב־Langflow: analyzes doctor's schedules
- עודכן לאחרונה בצילום: 2026-10-05
- גודל: 14 צמתים, 12 קשתות
- מתוכם 4 הערות על הקנבס, לא רכיבים שרצים

זה תהליך העל. הוא מקבל קלט צ'אט, קורא לשלושה תהליכי בן דרך `Jeen Langflow Run`, ומעביר את התוצאות לסוכן שמנסח את התשובה.

## מה רץ

1. **Chat Input** (`ChatInput-kHVk3`) מקבל את הודעת המשתמש ומעביר אותה לסוכן.
2. **Prompt Template** (`Prompt Template-moilJ`) מספק את תבנית ההנחיה לסוכן.
3. **Jeen Attachments** (`jeen_attached_file_paths-BUlFs`) אורז את נתוני Jeen: מזהה לקוח, JWT, הודעה, נתיבי קבצים ומזהי Jeen. אין אליו קשת נכנסת בגרף. ממנו יוצאות קשתות אל המפענח ואל שלוש קריאות התהליך.
4. **Parser** (`ParserComponent-DrBBy`) שולף טקסט לפי תבנית ומעביר אותו למודל.
5. **Jeen Language Model** (`JeenLanguageModel-WLGRs`) הוא מודל השפה של הסוכן. שם המודל המוגדר: `gpt-5.4`.
6. שלוש קריאות **Jeen Langflow Run** רצות על אותו מטען קבצים ומחזירות לסוכן תקציר בלבד, לא את מעטפת התשובה המלאה של Langflow.
7. **Agent** (`Agent-sSPli`) מקבל את המודל, ההנחיה, הודעת המשתמש ותוצאות שלוש הקריאות.
8. **Chat Output** (`ChatOutput-xnkAV`) מציג את תשובת הסוכן.

## שלוש הקריאות לתהליכי בן

| צומת | שם תצוגה | תהליך יעד |
|---|---|---|
| `JeenLangflowRun-qvNc8` | Jeen Langflow Run new | `b0ad63a3-def9-4f4d-ba67-df3e7fe67fb0` |
| `JeenLangflowRun-388gm` | Jeen Langflow Run | `cbdc04ca-422d-4461-a317-95acce7909d7` |
| `JeenLangflowRun-56QC0` | Jeen Langflow Run | `5949b7aa-9e45-4521-9f19-1e9c877dc864` |

רק `JeenLangflowRun-qvNc8` כותב בתיאור שלו שהוא קורא לתהליך ההמלצה. לשני הצמתים האחרים אין בתיאור שם של ingestion או analytics.

אף אחד משלושת יעדי הקריאה אינו אחד מהתהליכים המתועדים בקבצים `09`, `10` ו־`11`:

- ingestion: `4ed288ea-6d9f-4637-b1f5-fc6d8aeacc9b`
- analytics: `cab826db-8f2e-49d7-aedf-346da2ca875d`
- recommendation (1): `45a2f763-1f18-4358-bfeb-ff591b8233d8`

## הערות על הקנבס

ההערות מסמנות אזורים בשמות Agent, ingestion, analytics ו־recommendation. הן לא מחוברות בקשתות ולא קובעות לאיזה מזהה כל קריאה הולכת.

# תהליך: analytics

## זהות

- שם ב־Langflow: `analytics`
- מזהה: `cab826db-8f2e-49d7-aedf-346da2ca875d`
- תיאור ב־Langflow: analytics
- עודכן לאחרונה בצילום: 2026-10-05
- גודל: 32 צמתים, 44 קשתות
- מתוכם 13 הערות על הקנבס

זה צינור חישוב דטרמיניסטי. אין בו מודל שפה. הוא מקבל `analysis_run_id` קיים, טוען לו"ז, תורים, ביקורים ונתוני ייחוס, מחשב ראיות, ומסווג כל ממצא ל־Recommendation, Insight או Ignore. הסיווג נקבע כאן בקוד ובספים, לא בסוכני ההמלצה.

## כניסה

1. **Chat Input** (`ChatInput-z01g1`).
2. **Jeen JSON / structured output validation** (`JSONToData-ZaOAC`) מפרסר JSON ומתקן שגיאות תחביר נפוצות.
3. **Parser** (`ParserComponent-cKxVf`) שולף את הטקסט.
4. **Analysis Run ID Extractor** (`analysis_run_id_extractor-xnZOD`) מוציא רק את המזהה המספרי, גם אם הגיע כמספר וגם אם הגיע כטקסט עם תווית `analysis_run_id`.

## בסיס ואנלייזרים

**Calendar Context & Baseline** (`calendar_context_baseline-mSs0K`) טוען את הלו"ז הקבוע: ימי עבודה, שעות, סגמנטים, תדירות, היעדרויות ומספר המופעים האפשריים לכל יום. הוא גם מפריד מבנה סגמנטים רגיל ממבנה סגמנטים נדחפים, ומגדיר את חלון הניתוח. זה הבסיס לשאר החישובים, והוא מזין את כל האנלייזרים.

אלה רכיבי הניתוח, ומה כל אחד עושה היום:

- **Appointment Planning & Booking Analyzer** (`appointment_analytics-jZUS0`) — תורים מתוכננים. נכנסים לחישוב רק שורות שמצב היומן שלהן הוא פנוי או העדפה. מנתח סוגי ביקור, אי־הגעה, מבנה תורים ודפוסי זימון.
- **Actual Activity & Workload Analyzer** (`actual_visit_analytics-l63OD`) — פעילות שבוצעה: התחלות ביקור מתועדות, חפיפה ללו"ז הבסיס, וקצב התחלה עד המטופל הבא. לא מסיק משך ביקור.
- **Appointment Execution & Matching Analyzer** (`historical_performance_analyzer-kNP23`) — התאמה דטרמיניסטית מתור לביקור. ההתאמה מוגבלת למצב יומן פנוי או העדפה, ומותאמת לאיחור מקומי חוזר. אי־הגעה מופרדת ל־confirmed ול־probable. מכאן נגזר אם המטופל הגיע ומה הפער בין שעת התור להתחלת הביקור.
- **Urgent / Reserve & Pushed Pressure Analyzer** (`urgent_reserve_pressure_analyzer-STQ1C`) — בגרף החי הרכיב מנתח בנפרד ביקוש דחוף ולחץ של תורים נדחפים. ההערה על הקנבס אומרת שההבחנה בין דחוף לנדחף נשמרת. זה מצב המימוש הנוכחי. כלל התחום המעודכן בקבצים `01` עד `07` הוא שדחוף ונדחף הם אותו תור שנכנס בין שני תורים בלי הזמנה מראש ומסווג אחרת בקובץ התורים.
- **Daily Flow & Operational Pressure Analyzer** (`delay_operational_pressure_analyzer-iWeEY`) — איחורים, קצב סגמנטים רגילים ולחץ תפעולי במהלך היום. מקבל גם את פעילות הביקורים וגם את שכבת ההתאמה. איחור נשמר כתובנה ולא כהמלצה עצמאית.
- **Digital & Admin Window Analyzer** (`digital_admin_window_analyzer-nMbfT`) — חלונות שבהם פעילות דיגיטלית או אדמיניסטרטיבית נוטה להתרכז בתוך לו"ז הבסיס. הריכוז ההיסטורי הוא ראיה תומכת בלבד. מיקום הסגירה הסופי נבחר בהמשך לפי קיבולת פנויה ועומס.
- **Visit Type Allocation Analyzer** (`visit_type_allocation_analyzer-MeJyi`) — דפוסי שיבוץ חוזרים של סוג ביקור לפי יום ושעה בתוך לו"ז הבסיס. שמות סוגי הביקור נפתרים מטבלת `public.visit_types`.
- **Demand, Pattern Stability & Exception Analyzer** (`pattern_trend_analyzer-9f3TD`) — ביקוש, מגמות, חריגים וחזרתיות על פני שבועות, כדי שאירוע חד־פעמי לא יהפוך לראיה חוזרת. מקבל את תוצאות האנלייזרים שלמעלה.
- **Forecast Suite** (`forecast_capacity_planner-eXp1i`) — תחזית כיוון דטרמיניסטית ל־20 שבועות משבועות לוח מלאים. שבוע חסר נשמר כפער. שבוע עם היעדרות חלקית מנורמל רק לפי פעילות בימי הלו"ז. התחזית היא מידע תומך ולא יוצרת המלצה לבדה.
- **Persistent Visit-Type Load Forecaster** (`persistent_visit_type_load_forecaster-74s8R`) — עבור יום, שעה וסוג ביקור, מה ההסתברות שזה דפוס קבוע של עומס גבוה שמצדיק להעדיף את סוג הביקור בחלון. עושה ולידציית walk-forward ובוחר לכל היותר סוג ביקור אחד למשבצת. יושב על בסיס הלו"ז.
- **Decision KPI & Recommendation Evidence Analyzer** (`decision_kpi_analyzer-LVaqT`) — KPI וראיות להחלטה: הקצאת סוגי ביקור לוגית, ניצולת סגמנטים, ביקורים מאושרים בלי תור מראש, פעילות דיגיטלית מול טלפון או וידאו, ואי־הגעה. מקבל את הבסיס ואת שכבת ההתאמה.

## יציאה

**Analytics Feature Builder – Deterministic Actionable Contract** (`analytics_feature_builder-CSzAL`) אוסף את החישובים שמחוברים אליו, בונה את חוזה ההמלצה, ומסווג כל דפוס נתמך ל־Recommendation, Insight או Ignore לפי מדיניות ספים v1.5. מודל השפה לא קובע את הסיווג.

בחינת העדפה קיימת אינה המלצה. `Decision KPI` (`decision_kpi_analyzer-LVaqT`) לא מחשב התאמה כשהערך בשדה ההעדפה הוא רק מילה של מנגנון או היקף: מרובה, התאמה, הגבלה או למעט. "מרובה" אינו סוג ביקור, ולכן אינו נספר כ־0% התאמה. ה־Feature Builder מתעלם ממועמדי `preference_review` ולא מכניס אותם לחוזה ההמלצות. המלצה נשארת רק לפעולה קונקרטית.

יש שני צמתי **Chat Output**: `ChatOutput-hMZ5i` ו־`ChatOutput-8Iucw`. ה־Feature Builder מחובר לאחד מהם, ויש קשת בין שני פלטי הצ'אט.

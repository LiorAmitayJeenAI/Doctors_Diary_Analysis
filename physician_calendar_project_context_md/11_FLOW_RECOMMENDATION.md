# תהליך: recommendation (1)

## זהות

- שם ב־Langflow: `recommendation (1)`
- מזהה: `45a2f763-1f18-4358-bfeb-ff591b8233d8`
- תיאור ב־Langflow: recommendation
- עודכן לאחרונה בצילום: 2026-10-05
- גודל: 29 צמתים, 26 קשתות
- מתוכם 10 הערות על הקנבס

התהליך הופך ריצת analytics שהושלמה לדוח המלצות בעברית. הוא לא מחשב מחדש את המטריקות. Analytics כבר החליט מה המלצה, מה תובנה ומה להתעלם. שלושת הסוכנים מנסחים מועמדים שכבר אושרו.

## כניסה וטעינה

1. **Chat Input** (`ChatInput-Fa26d`).
2. **Jeen JSON / structured output validation** (`JSONToData-4p7vS`) מפצל את ה־JSON לשני מפענחים.
3. **Parser** (`ParserComponent-dqPtv`) מזין את **Analysis Run ID Extractor** (`analysis_run_id_extractor-SwwZH`), שמוציא מספר `analysis_run_id` נקי מטקסט או מ־JSON.
4. **Parser** (`ParserComponent-7mtQH`) מזין את **Jeen Language Model** (`JeenLanguageModel-EtD4f`). אותו מודל מחובר לשלושת הסוכנים.
5. **Recommendation Context Loader** (`recommendation_context_loader-BcO1B`) טוען מהמסד את תוצאת ה־Analytics של אותה ריצה, ובודק את מבנה החוזה.
6. **Recommendation Context Splitter** (`recommendation_context_splitter-nbpf8`) בונה שלושה קלטים קטנים, אחד לכל סוכן, וגם הקשר עסקי משותף לשלבי האיחוד והאכיפה. מועמדים שסומנו כלא־פעילים או כתמיכה בלבד לא נשלחים לסוכן.

## שלושת הסוכנים

כל סוכן מקבל את המודל, פרומפט משלו, ורק את פרוסת הנתונים של התחום שלו.

- **Allocation & Modality Recommendation Agent** (`Agent-3gAXo`) עם **Allocation & Modality Agent Prompt** (`TextInput-1fbJS`). מנסח המלצות של סוגי פעילות וביקור שכבר אושרו. כשמדברים על העדפה, הניסוח צריך לנקוב במנגנון (התאמה, הגבלה או למעט) ובסוגי הביקור. העדפה מרובה היא אותו מנגנון על כמה סוגי ביקור, לא מנגנון נפרד.
- **Capacity & Flow Recommendation Agent** (`Agent-Wh0Dh`) עם **Capacity & Flow Agent Prompt** (`TextInput-Krlry`). מטפל בפעולות קיבולת קונקרטיות, למשל קיצור סגמנט או העברת קיבולת. עומס ואיחור לבדם נשארים תובנות.
- **Reserve & Pressure Recommendation Agent** (`Agent-9FXbc`) עם **Reserve & Pressure Agent Prompt** (`TextInput-QYfS4`). מנסח את הטיפול בדחופים, עתודות, נדחפים ולחץ תפעולי לפי מה שעבר את הספים. בגרף החי הפרומפט וההערה עדיין מדברים על דחוף ונדחף כנושאים נפרדים. כלל התחום המעודכן הוא שמדובר באותו תור שנכנס בין שני תורים בלי הזמנה מראש. עתודה נשארת קיבולת מוגדרת, ויש לנקוב בסוג שלה: ת־עתודה, ט־עתודה, או עתודה מביטול. עתודה אינה סגירה.

## אחרי הסוכנים

1. **Recommendation Results Merger** (`recommendation_results_merger-l6Bee`) מאחד את ניסוחי הסוכנים בלי לשנות את דרגת ההחלטה שנקבעה ב־Analytics. מועמד להמלצה שסוכן דילג עליו מושלם בניסוח דטרמיניסטי. מוסר כפילויות, בוחר המלצת הקצאה אחת לחלון זמן, ומחבר שעות רצופות כשההמלצה זהה. הוא לא משלים מועמד מסוג `review_preference_window` או `review_preference_definition_or_window`.
2. **Recommendation Output Validator** (`recommendation_output_validator-Y5cty`) בודק שכל מועמד שחייב להופיע אכן מיוצג, ושאין המלצה בלי ראיה. מועמד שהוסתר בכוונה בגלל בלעדיות של הקצאה נחשב מטופל ולא משוחזר. מועמד של בחינת העדפה גם הוא לא משוחזר.
3. **Recommendation Business Rule Validator** (`recommendation_business_rule_validator-ESzo8`) מחזיר כל מועמד בדרגת Recommendation לפעולה ולרמת הדיוק שאושרו ב־Analytics. מותר לו לתקן ניסוח ושדות. אסור לו להוריד המלצה דטרמיניסטית לתובנה. אוכף את גבולות העסק: לא לשנות ימי עבודה או שעות עבודה, לא לחרוג מגבולות היומן, ולא להגדיל סגמנט מעבר למה שהמערכת מאפשרת. מינימום הסגמנט בהערת הקנבס הוא 5 דקות. הוא לא מסמן העדפה כטעונת שינוי או כקונפליקט אם לא ידועים גם המנגנון (התאמה, הגבלה או למעט) וגם סוגי הביקור.
4. **Recommendation Presenter** (`recommendation_presenter-zoUfr`) הופך את המבנה לדוח בעברית: מה נמצא ומה מומלץ, בלי ז'רגון של ספים ומטריקות. "בחינת ההעדפה הקיימת" לא מוצגת ולא נכנסת ללוח השבועי. ליד המלצה קונקרטית מצוינת העדפה קיימת רק כשידועים המנגנון וסוגי הביקור. אם זו העדפה מרובה, הניסוח הוא "העדפה מרובה מסוג התאמה" (או הגבלה, או למעט) יחד עם סוגי הביקור. אותו משפט לא חוזר בכל שעה של אותו יום. אין "סוג ביקור מרובה" ואין "התאמה של 0%".
5. **Chat Output** (`ChatOutput-kcNgX`) מציג את הדוח.

## מבנה הדוח

ההערה על רכיב ההצגה מתארת תשובה בעברית עם תמונת מצב, המלצות לפי ימים, תובנות מסודרות, ולו"ז מעודכן.

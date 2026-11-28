"""Fixed bot messages in the customer's chosen language (sign-up flow and short system replies).

The AI-written replies (horoscope, answers, guidance) follow the chosen language by themselves (see ai._language_rule).
These are the hand-written messages around them. Missing language or key -> English.
To correct a translation, edit the text below; keep the {placeholders} and *bold* / _italic_ marks.
"""

# The tap-to-choose language menu (WhatsApp allows at most 10 rows). (name, native name)
MENU_LANGS = [
    ("English", "English"), ("Hindi", "हिन्दी"), ("Kannada", "ಕನ್ನಡ"), ("Telugu", "తెలుగు"), ("Tamil", "தமிழ்"),
    ("Malayalam", "മലയാളം"), ("Marathi", "मराठी"), ("Bengali", "বাংলা"), ("Gujarati", "ગુજરાતી"), ("Punjabi", "ਪੰਜਾਬੀ"),
]
NATIVE = dict(MENU_LANGS)

MENU_BODY = "*CHOOSE YOUR LANGUAGE*"  # one line, capitals, no icon (client's request); the button opens the 10 languages
MENU_BODY_UNDER_IMAGE = "*CHOOSE YOUR LANGUAGE*"  # used right after the language image (image currently switched off)
MENU_BUTTON = "LANGUAGE OPTIONS"  # max 20 characters
MENU_TEXT_FALLBACK = (MENU_BODY.split("\n\n")[0] + "\n\n"
                      + "\n".join(f"[{i}] {n}" + (f" / {nat}" if nat != n else "") for i, (n, nat) in enumerate(MENU_LANGS, 1))
                      + "\n\nReply with the number (e.g. 3) or the language name.")

QUESTION_MENU_BODY = "*CHOOSE QUESTIONS OR TYPE YOUR OWN QUESTION*"
QUESTION_MENU_BUTTON = "CHOOSE QUESTIONS"  # max 20 characters
QUESTION_MENU_ITEMS = [
    ("q_daily", "Daily Prediction"),
    ("q_weekly", "Weekly Prediction"),
    ("q_monthly", "Monthly Prediction"),
    ("q_career", "Career Prediction"),
    ("q_business", "Business Prediction"),
    ("q_financial", "Financial Prediction"),
    ("q_health", "Health Prediction"),
    ("q_relationship", "Relationship Prediction"),
    ("q_custom", "Type your own question"),
]
TYPE_OWN_QUESTION = "Type your own question"
QUESTION_MENU_TITLES = {title for _, title in QUESTION_MENU_ITEMS}
QUESTION_MENU_TEXT_FALLBACK = (
    QUESTION_MENU_BODY + "\n\n"
    + "\n".join(f"[{i}] {title}" for i, (_, title) in enumerate(QUESTION_MENU_ITEMS, 1))
    + "\n\nReply with a number (e.g. 1) or type your own question."
)

PDF_BEFORE_LANGUAGE = ("🙏 Thank you! Please choose your language first, then send your birth chart PDF again.\n"
                       "ದಯವಿಟ್ಟು ಮೊದಲು ಭಾಷೆ ಆಯ್ಕೆ ಮಾಡಿ, ನಂತರ PDF ಕಳುಹಿಸಿ · पहले भाषा चुनें, फिर PDF भेजें")

# Images sent to a new client before the language menu (files in /static, served by the bot itself).
INTRO_IMAGES = ["static/welcome3.jpg", "static/instructions2.jpg"]
# "Choose Your Language" picture before the tap menu - switched off (set to "static/language.jpg" to bring it back).
LANGUAGE_IMAGE = ""

TITLE = "🙏 *Welcome to ASTROVINOD AI*"

T: dict[str, dict[str, str]] = {
    "English": {
        "subtitle": "_Your Personal Astrologer._",
        "welcome_body": ("I'm happy to assist you with your astrological questions and provide personalised insights based on "
                         "Vedic Astrology.\n\n🌟 Let's begin by setting up your birth profile. I'll ask you 4 quick details: your "
                         "name, date of birth, time of birth and place of birth.\n\n🔭 Once I receive your details, I will generate "
                         "your Vedic birth chart using precise astrological calculations and prepare your birth profile."),
        "q_full_name": "👉 *May I know your Full Name?*",
        "q_dob": "📅 Please share your *Date of Birth* (DD/MM/YYYY)\n_Example: 14/05/1992_",
        "q_birth_time": "⏰ What is your *Time of Birth*? (HH:MM AM/PM)\n_Example: 06:35 AM_",
        "q_birth_place": "📍 What is your *Place of Birth*? (City, State, Country)\n_Example: Mysuru, Karnataka, India_",
        "thanks_name": "Thank you, {first} ji! 🙏",
        "thanks": "Thank you! 🙏",
        "hint_full_name": "🙏 Please type your full name.",
        "hint_dob": "🙏 Please send your date of birth like *14/05/1992*.",
        "hint_birth_time": "🙏 Please send your time of birth like *06:35 AM* or *06:35 PM*.",
        "hint_birth_place": "🙏 Please send your place of birth like *Mysuru, Karnataka, India*.",
        "ampm": "Is your birth time *{t}* in the morning or evening?\nPlease reply like *{t} AM* or *{t} PM*.",
        "place_error": ("🙏 I couldn't find that place on the map. Please send it as *City, State, Country*\n"
                        "_Example: Mysuru, Karnataka, India_"),
        "place_confirm": ("📍 I found your place of birth as:\n*{place}*\n\n"
                          "Is this correct? Reply *YES*, or send the correct place (City, State, Country)."),
        "continue": "🙏 Let's continue.",
        "no_problem": "No problem. 🙏",
        "profile_head": "🙏 Thank you, {first} ji! Your birth profile:",
        "l_name": "Name", "l_dob": "Date of Birth", "l_tob": "Time of Birth", "l_pob": "Place of Birth",
        "generating": "🔭 Generating your Vedic birth chart and personalised horoscope. This takes 2-3 minutes…",
        "reset_hint": "_(Reply RESET anytime to correct your details.)_",
        "lang_changed": "✅ Done! From now on I will reply in *{name}*. 🙏",
        "welcome_back": ("🙏 Welcome back, {first} ji!\n\nAsk me any astrology question, ask for your *daily*, *weekly* or "
                         "*monthly* guidance, or share a chart image/PDF."),
        "kundli_reading": "📎 Thank you! Reading your Kundali now…",
        "kundli_format": "🙏 I can read a Kundali as a *PDF* or a clear photo. Or simply answer:",
        "kundli_none": "🙏 I couldn't find birth details in that file, so let's do it step by step.",
        "place_not_found": "🙏 I couldn't find your birthplace on the map. ",
        "type_own_question": "✍️ Please type your question and send it to me. I will answer based on your birth chart. 🙏",
        "menu_already_used": "🙏 You have already chosen an option from this menu. Please type your own question below and I will answer based on your birth chart.",
    },
    "Hindi": {
        "subtitle": "_आपके निजी ज्योतिषी।_",
        "welcome_body": ("वैदिक ज्योतिष के आधार पर आपके प्रश्नों का उत्तर देने और आपको व्यक्तिगत मार्गदर्शन देने में मुझे खुशी होगी।\n\n"
                         "🌟 आइए पहले आपकी जन्म प्रोफ़ाइल बनाते हैं। मैं आपसे 4 छोटी जानकारियाँ पूछूँगा: आपका नाम, जन्म तिथि, "
                         "जन्म समय और जन्म स्थान।\n\n🔭 जानकारी मिलते ही मैं सटीक गणना से आपकी वैदिक जन्म कुंडली बनाकर आपकी "
                         "जन्म प्रोफ़ाइल तैयार करूँगा।"),
        "q_full_name": "👉 *कृपया अपना पूरा नाम बताइए।*",
        "q_dob": "📅 कृपया अपनी *जन्म तिथि* बताइए (DD/MM/YYYY)\n_उदाहरण: 14/05/1992_",
        "q_birth_time": "⏰ आपका *जन्म समय* क्या है? (HH:MM AM/PM)\n_उदाहरण: 06:35 AM_",
        "q_birth_place": "📍 आपका *जन्म स्थान* क्या है? (शहर, राज्य, देश)\n_उदाहरण: Lucknow, Uttar Pradesh, India_",
        "thanks_name": "धन्यवाद, {first} जी! 🙏",
        "thanks": "धन्यवाद! 🙏",
        "hint_full_name": "🙏 कृपया अपना पूरा नाम लिखिए।",
        "hint_dob": "🙏 कृपया जन्म तिथि इस तरह भेजें: *14/05/1992*",
        "hint_birth_time": "🙏 कृपया जन्म समय इस तरह भेजें: *06:35 AM* या *06:35 PM*",
        "hint_birth_place": "🙏 कृपया जन्म स्थान इस तरह भेजें: *Lucknow, Uttar Pradesh, India*",
        "ampm": "क्या आपका जन्म समय *{t}* सुबह का है या शाम का?\nकृपया *{t} AM* या *{t} PM* लिखकर भेजें।",
        "place_error": ("🙏 मुझे यह स्थान नक्शे पर नहीं मिला। कृपया इसे *शहर, राज्य, देश* के रूप में भेजें\n"
                        "_उदाहरण: Lucknow, Uttar Pradesh, India_"),
        "place_confirm": ("📍 आपका जन्म स्थान मुझे यह मिला:\n*{place}*\n\n"
                          "क्या यह सही है? *हाँ* (YES) लिखें, या सही स्थान भेजें (शहर, राज्य, देश)।"),
        "continue": "🙏 चलिए आगे बढ़ते हैं।",
        "no_problem": "कोई बात नहीं। 🙏",
        "profile_head": "🙏 धन्यवाद, {first} जी! आपकी जन्म प्रोफ़ाइल:",
        "l_name": "नाम", "l_dob": "जन्म तिथि", "l_tob": "जन्म समय", "l_pob": "जन्म स्थान",
        "generating": "🔭 आपकी वैदिक जन्म कुंडली और व्यक्तिगत राशिफल तैयार हो रहा है। इसमें 2-3 मिनट लगते हैं…",
        "reset_hint": "_(विवरण सुधारने के लिए कभी भी RESET लिखें।)_",
        "lang_changed": "✅ ठीक है! अब से मैं *{name}* में जवाब दूँगा। 🙏",
        "welcome_back": ("🙏 फिर से स्वागत है, {first} जी!\n\nकोई भी ज्योतिष प्रश्न पूछिए, अपना *दैनिक*, *साप्ताहिक* या *मासिक* "
                         "मार्गदर्शन माँगिए, या कुंडली की फ़ोटो/PDF भेजिए।"),
        "kundli_reading": "📎 धन्यवाद! आपकी कुंडली पढ़ रहा हूँ…",
        "kundli_format": "🙏 मैं कुंडली *PDF* या साफ़ फ़ोटो के रूप में पढ़ सकता हूँ। या बस इसका उत्तर दीजिए:",
        "kundli_none": "🙏 उस फ़ाइल में जन्म विवरण नहीं मिला, चलिए एक-एक करके भरते हैं।",
        "place_not_found": "🙏 मुझे आपका जन्म स्थान नक्शे पर नहीं मिला। ",
        "type_own_question": "✍️ कृपया अपना प्रश्न लिखकर भेजें। मैं आपकी जन्म कुंडली के अनुसार उत्तर दूँगा। 🙏",
        "menu_already_used": "🙏 आप इस सूची से एक विकल्प पहले ही चुन चुके हैं। कृपया नीचे अपना प्रश्न लिखकर भेजें, मैं आपकी जन्म कुंडली के अनुसार उत्तर दूँगा।",
    },
    "Kannada": {
        "subtitle": "_ನಿಮ್ಮ ವೈಯಕ್ತಿಕ ಜ್ಯೋತಿಷಿ._",
        "welcome_body": ("ವೈದಿಕ ಜ್ಯೋತಿಷ್ಯದ ಆಧಾರದ ಮೇಲೆ ನಿಮ್ಮ ಪ್ರಶ್ನೆಗಳಿಗೆ ಉತ್ತರಿಸಲು ಮತ್ತು ವೈಯಕ್ತಿಕ ಮಾರ್ಗದರ್ಶನ ನೀಡಲು ನನಗೆ "
                         "ಸಂತೋಷವಾಗುತ್ತದೆ.\n\n🌟 ಮೊದಲು ನಿಮ್ಮ ಜನ್ಮ ವಿವರಗಳನ್ನು ಸಿದ್ಧಪಡಿಸೋಣ. ನಾನು 4 ಸಣ್ಣ ವಿವರಗಳನ್ನು ಕೇಳುತ್ತೇನೆ: "
                         "ನಿಮ್ಮ ಹೆಸರು, ಜನ್ಮ ದಿನಾಂಕ, ಜನ್ಮ ಸಮಯ ಮತ್ತು ಜನ್ಮ ಸ್ಥಳ.\n\n🔭 ವಿವರಗಳು ಸಿಕ್ಕ ತಕ್ಷಣ, ನಿಖರವಾದ "
                         "ಲೆಕ್ಕಾಚಾರದಿಂದ ನಿಮ್ಮ ವೈದಿಕ ಜಾತಕವನ್ನು ತಯಾರಿಸಿ ನಿಮ್ಮ ಜನ್ಮ ವಿವರಗಳನ್ನು ಸಿದ್ಧಪಡಿಸುತ್ತೇನೆ."),
        "q_full_name": "👉 *ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪೂರ್ಣ ಹೆಸರನ್ನು ತಿಳಿಸಿ.*",
        "q_dob": "📅 ದಯವಿಟ್ಟು ನಿಮ್ಮ *ಜನ್ಮ ದಿನಾಂಕ* ತಿಳಿಸಿ (DD/MM/YYYY)\n_ಉದಾಹರಣೆ: 14/05/1992_",
        "q_birth_time": "⏰ ನಿಮ್ಮ *ಜನ್ಮ ಸಮಯ* ಎಷ್ಟು? (HH:MM AM/PM)\n_ಉದಾಹರಣೆ: 06:35 AM_",
        "q_birth_place": "📍 ನಿಮ್ಮ *ಜನ್ಮ ಸ್ಥಳ* ಯಾವುದು? (ಊರು, ರಾಜ್ಯ, ದೇಶ)\n_ಉದಾಹರಣೆ: Mysuru, Karnataka, India_",
        "thanks_name": "ಧನ್ಯವಾದಗಳು, {first} ಅವರೇ! 🙏",
        "thanks": "ಧನ್ಯವಾದಗಳು! 🙏",
        "hint_full_name": "🙏 ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪೂರ್ಣ ಹೆಸರನ್ನು ಬರೆಯಿರಿ.",
        "hint_dob": "🙏 ದಯವಿಟ್ಟು ಜನ್ಮ ದಿನಾಂಕವನ್ನು ಹೀಗೆ ಕಳುಹಿಸಿ: *14/05/1992*",
        "hint_birth_time": "🙏 ದಯವಿಟ್ಟು ಜನ್ಮ ಸಮಯವನ್ನು ಹೀಗೆ ಕಳುಹಿಸಿ: *06:35 AM* ಅಥವಾ *06:35 PM*",
        "hint_birth_place": "🙏 ದಯವಿಟ್ಟು ಜನ್ಮ ಸ್ಥಳವನ್ನು ಹೀಗೆ ಕಳುಹಿಸಿ: *Mysuru, Karnataka, India*",
        "ampm": "ನಿಮ್ಮ ಜನ್ಮ ಸಮಯ *{t}* ಬೆಳಿಗ್ಗೆಯೋ ಅಥವಾ ಸಂಜೆಯೋ?\nದಯವಿಟ್ಟು *{t} AM* ಅಥವಾ *{t} PM* ಎಂದು ಕಳುಹಿಸಿ.",
        "place_error": ("🙏 ಆ ಸ್ಥಳ ನಕ್ಷೆಯಲ್ಲಿ ಸಿಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು *ಊರು, ರಾಜ್ಯ, ದೇಶ* ಎಂದು ಕಳುಹಿಸಿ\n"
                        "_ಉದಾಹರಣೆ: Mysuru, Karnataka, India_"),
        "place_confirm": ("📍 ನಿಮ್ಮ ಜನ್ಮ ಸ್ಥಳ ನನಗೆ ಹೀಗೆ ಸಿಕ್ಕಿದೆ:\n*{place}*\n\n"
                          "ಇದು ಸರಿಯೇ? *ಹೌದು* (YES) ಎಂದು ಉತ್ತರಿಸಿ, ಅಥವಾ ಸರಿಯಾದ ಸ್ಥಳವನ್ನು ಕಳುಹಿಸಿ (ಊರು, ರಾಜ್ಯ, ದೇಶ)."),
        "continue": "🙏 ಮುಂದುವರಿಯೋಣ.",
        "no_problem": "ಪರವಾಗಿಲ್ಲ. 🙏",
        "profile_head": "🙏 ಧನ್ಯವಾದಗಳು, {first} ಅವರೇ! ನಿಮ್ಮ ಜನ್ಮ ವಿವರಗಳು:",
        "l_name": "ಹೆಸರು", "l_dob": "ಜನ್ಮ ದಿನಾಂಕ", "l_tob": "ಜನ್ಮ ಸಮಯ", "l_pob": "ಜನ್ಮ ಸ್ಥಳ",
        "generating": "🔭 ನಿಮ್ಮ ವೈದಿಕ ಜಾತಕ ಮತ್ತು ವೈಯಕ್ತಿಕ ಭವಿಷ್ಯ ತಯಾರಾಗುತ್ತಿದೆ. ಇದಕ್ಕೆ 2-3 ನಿಮಿಷ ಬೇಕು…",
        "reset_hint": "_(ವಿವರ ತಿದ್ದಲು ಯಾವಾಗ ಬೇಕಾದರೂ RESET ಎಂದು ಕಳುಹಿಸಿ.)_",
        "lang_changed": "✅ ಸರಿ! ಇನ್ನು ಮುಂದೆ ನಾನು *{name}* ಭಾಷೆಯಲ್ಲಿ ಉತ್ತರಿಸುತ್ತೇನೆ. 🙏",
        "welcome_back": ("🙏 ಮತ್ತೆ ಸ್ವಾಗತ, {first} ಅವರೇ!\n\nಯಾವುದೇ ಜ್ಯೋತಿಷ್ಯ ಪ್ರಶ್ನೆ ಕೇಳಿ, ನಿಮ್ಮ *ದೈನಂದಿನ*, *ವಾರದ* ಅಥವಾ "
                         "*ಮಾಸಿಕ* ಮಾರ್ಗದರ್ಶನ ಕೇಳಿ, ಅಥವಾ ಜಾತಕದ ಫೋಟೋ/PDF ಕಳುಹಿಸಿ."),
        "kundli_reading": "📎 ಧನ್ಯವಾದಗಳು! ನಿಮ್ಮ ಜಾತಕವನ್ನು ಓದುತ್ತಿದ್ದೇನೆ…",
        "kundli_format": "🙏 ನಾನು ಜಾತಕವನ್ನು *PDF* ಅಥವಾ ಸ್ಪಷ್ಟ ಫೋಟೋ ರೂಪದಲ್ಲಿ ಓದಬಲ್ಲೆ. ಅಥವಾ ಸುಮ್ಮನೆ ಇದಕ್ಕೆ ಉತ್ತರಿಸಿ:",
        "kundli_none": "🙏 ಆ ಫೈಲ್‌ನಲ್ಲಿ ಜನ್ಮ ವಿವರಗಳು ಸಿಗಲಿಲ್ಲ, ಒಂದೊಂದಾಗಿ ತುಂಬೋಣ.",
        "place_not_found": "🙏 ನಿಮ್ಮ ಜನ್ಮ ಸ್ಥಳ ನಕ್ಷೆಯಲ್ಲಿ ಸಿಗಲಿಲ್ಲ. ",
        "type_own_question": "✍️ ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಬರೆದು ಕಳುಹಿಸಿ. ನಿಮ್ಮ ಜಾತಕದ ಆಧಾರದ ಮೇಲೆ ನಾನು ಉತ್ತರಿಸುತ್ತೇನೆ. 🙏",
        "menu_already_used": "🙏 ನೀವು ಈ ಪಟ್ಟಿಯಿಂದ ಈಗಾಗಲೇ ಒಂದು ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿದ್ದೀರಿ. ದಯವಿಟ್ಟು ಕೆಳಗೆ ನಿಮ್ಮ ಸ್ವಂತ ಪ್ರಶ್ನೆಯನ್ನು ಟೈಪ್ ಮಾಡಿ ಕಳುಹಿಸಿ.",
    },
    "Telugu": {
        "subtitle": "_మీ వ్యక్తిగత జ్యోతిష్యుడు._",
        "welcome_body": ("వేద జ్యోతిష్యం ఆధారంగా మీ ప్రశ్నలకు సమాధానం ఇవ్వడానికి, వ్యక్తిగత మార్గదర్శనం అందించడానికి నేను "
                         "సంతోషిస్తాను.\n\n🌟 ముందుగా మీ జన్మ వివరాలను సిద్ధం చేద్దాం. నేను 4 చిన్న వివరాలు అడుగుతాను: మీ పేరు, "
                         "పుట్టిన తేదీ, పుట్టిన సమయం మరియు పుట్టిన ప్రదేశం.\n\n🔭 వివరాలు అందగానే, ఖచ్చితమైన లెక్కలతో మీ వేద "
                         "జాతకాన్ని తయారు చేసి మీ జన్మ ప్రొఫైల్ సిద్ధం చేస్తాను."),
        "q_full_name": "👉 *దయచేసి మీ పూర్తి పేరు చెప్పండి.*",
        "q_dob": "📅 దయచేసి మీ *పుట్టిన తేదీ* చెప్పండి (DD/MM/YYYY)\n_ఉదాహరణ: 14/05/1992_",
        "q_birth_time": "⏰ మీ *పుట్టిన సమయం* ఎంత? (HH:MM AM/PM)\n_ఉదాహరణ: 06:35 AM_",
        "q_birth_place": "📍 మీ *పుట్టిన ప్రదేశం* ఏది? (ఊరు, రాష్ట్రం, దేశం)\n_ఉదాహరణ: Vijayawada, Andhra Pradesh, India_",
        "thanks_name": "ధన్యవాదాలు, {first} గారూ! 🙏",
        "thanks": "ధన్యవాదాలు! 🙏",
        "hint_full_name": "🙏 దయచేసి మీ పూర్తి పేరు రాయండి.",
        "hint_dob": "🙏 దయచేసి పుట్టిన తేదీని ఇలా పంపండి: *14/05/1992*",
        "hint_birth_time": "🙏 దయచేసి పుట్టిన సమయాన్ని ఇలా పంపండి: *06:35 AM* లేదా *06:35 PM*",
        "hint_birth_place": "🙏 దయచేసి పుట్టిన ప్రదేశాన్ని ఇలా పంపండి: *Vijayawada, Andhra Pradesh, India*",
        "ampm": "మీ పుట్టిన సమయం *{t}* ఉదయమా లేక సాయంత్రమా?\nదయచేసి *{t} AM* లేదా *{t} PM* అని పంపండి.",
        "place_error": ("🙏 ఆ ప్రదేశం మ్యాప్‌లో దొరకలేదు. దయచేసి *ఊరు, రాష్ట్రం, దేశం* అని పంపండి\n"
                        "_ఉదాహరణ: Vijayawada, Andhra Pradesh, India_"),
        "place_confirm": ("📍 మీ పుట్టిన ప్రదేశం నాకు ఇలా దొరికింది:\n*{place}*\n\n"
                          "ఇది సరైనదేనా? *అవును* (YES) అని జవాబు ఇవ్వండి, లేదా సరైన ప్రదేశం పంపండి (ఊరు, రాష్ట్రం, దేశం)."),
        "continue": "🙏 కొనసాగిద్దాం.",
        "no_problem": "పర్వాలేదు. 🙏",
        "profile_head": "🙏 ధన్యవాదాలు, {first} గారూ! మీ జన్మ వివరాలు:",
        "l_name": "పేరు", "l_dob": "పుట్టిన తేదీ", "l_tob": "పుట్టిన సమయం", "l_pob": "పుట్టిన ప్రదేశం",
        "generating": "🔭 మీ వేద జాతకం మరియు వ్యక్తిగత ఫలితాలు సిద్ధమవుతున్నాయి. దీనికి 2-3 నిమిషాలు పడుతుంది…",
        "reset_hint": "_(వివరాలు సరిచేయడానికి ఎప్పుడైనా RESET అని పంపండి.)_",
        "lang_changed": "✅ సరే! ఇకపై నేను *{name}* లో జవాబు ఇస్తాను. 🙏",
        "welcome_back": ("🙏 మళ్ళీ స్వాగతం, {first} గారూ!\n\nఏదైనా జ్యోతిష్య ప్రశ్న అడగండి, మీ *రోజువారీ*, *వారపు* లేదా "
                         "*నెలవారీ* మార్గదర్శనం అడగండి, లేదా జాతకం ఫోటో/PDF పంపండి."),
        "kundli_reading": "📎 ధన్యవాదాలు! మీ జాతకం చదువుతున్నాను…",
        "kundli_format": "🙏 నేను జాతకాన్ని *PDF* లేదా స్పష్టమైన ఫోటోగా చదవగలను. లేదా దీనికి సమాధానం ఇవ్వండి:",
        "kundli_none": "🙏 ఆ ఫైల్‌లో జన్మ వివరాలు దొరకలేదు, ఒక్కొక్కటిగా నింపుదాం.",
        "place_not_found": "🙏 మీ పుట్టిన ప్రదేశం మ్యాప్‌లో దొరకలేదు. ",
        "type_own_question": "✍️ దయచేసి మీ ప్రశ్నను టైప్ చేసి పంపండి. మీ జన్మ జాతకం ఆధారంగా నేను సమాధానం ఇస్తాను. 🙏",
        "menu_already_used": "🙏 మీరు ఈ జాబితా నుండి ఇప్పటికే ఒక ఎంపికను ఎంచుకున్నారు. దయచేసి క్రింద మీ స్వంత ప్రశ్నను టైప్ చేసి పంపండి.",
    },
    "Tamil": {
        "subtitle": "_உங்கள் தனிப்பட்ட ஜோதிடர்._",
        "welcome_body": ("வேத ஜோதிடத்தின் அடிப்படையில் உங்கள் கேள்விகளுக்கு பதிலளிக்கவும் தனிப்பட்ட வழிகாட்டுதல் வழங்கவும் "
                         "மகிழ்ச்சி அடைகிறேன்.\n\n🌟 முதலில் உங்கள் பிறப்பு விவரங்களை அமைப்போம். நான் 4 சிறிய விவரங்களைக் "
                         "கேட்பேன்: உங்கள் பெயர், பிறந்த தேதி, பிறந்த நேரம் மற்றும் பிறந்த இடம்.\n\n🔭 விவரங்கள் கிடைத்ததும், "
                         "துல்லியமான கணக்கீடுகளுடன் உங்கள் வேத ஜாதகத்தை தயாரித்து உங்கள் பிறப்பு சுயவிவரத்தை உருவாக்குவேன்."),
        "q_full_name": "👉 *தயவுசெய்து உங்கள் முழுப் பெயரைச் சொல்லுங்கள்.*",
        "q_dob": "📅 தயவுசெய்து உங்கள் *பிறந்த தேதி*யைச் சொல்லுங்கள் (DD/MM/YYYY)\n_உதாரணம்: 14/05/1992_",
        "q_birth_time": "⏰ உங்கள் *பிறந்த நேரம்* என்ன? (HH:MM AM/PM)\n_உதாரணம்: 06:35 AM_",
        "q_birth_place": "📍 உங்கள் *பிறந்த இடம்* எது? (ஊர், மாநிலம், நாடு)\n_உதாரணம்: Madurai, Tamil Nadu, India_",
        "thanks_name": "நன்றி, {first} அவர்களே! 🙏",
        "thanks": "நன்றி! 🙏",
        "hint_full_name": "🙏 தயவுசெய்து உங்கள் முழுப் பெயரை எழுதுங்கள்.",
        "hint_dob": "🙏 தயவுசெய்து பிறந்த தேதியை இப்படி அனுப்புங்கள்: *14/05/1992*",
        "hint_birth_time": "🙏 தயவுசெய்து பிறந்த நேரத்தை இப்படி அனுப்புங்கள்: *06:35 AM* அல்லது *06:35 PM*",
        "hint_birth_place": "🙏 தயவுசெய்து பிறந்த இடத்தை இப்படி அனுப்புங்கள்: *Madurai, Tamil Nadu, India*",
        "ampm": "உங்கள் பிறந்த நேரம் *{t}* காலையா மாலையா?\nதயவுசெய்து *{t} AM* அல்லது *{t} PM* என்று அனுப்புங்கள்.",
        "place_error": ("🙏 அந்த இடம் வரைபடத்தில் கிடைக்கவில்லை. தயவுசெய்து *ஊர், மாநிலம், நாடு* என்று அனுப்புங்கள்\n"
                        "_உதாரணம்: Madurai, Tamil Nadu, India_"),
        "place_confirm": ("📍 உங்கள் பிறந்த இடம் எனக்கு இப்படிக் கிடைத்தது:\n*{place}*\n\n"
                          "இது சரியா? *ஆம்* (YES) என்று பதில் அனுப்புங்கள், அல்லது சரியான இடத்தை அனுப்புங்கள் (ஊர், மாநிலம், நாடு)."),
        "continue": "🙏 தொடர்வோம்.",
        "no_problem": "பரவாயில்லை. 🙏",
        "profile_head": "🙏 நன்றி, {first} அவர்களே! உங்கள் பிறப்பு விவரங்கள்:",
        "l_name": "பெயர்", "l_dob": "பிறந்த தேதி", "l_tob": "பிறந்த நேரம்", "l_pob": "பிறந்த இடம்",
        "generating": "🔭 உங்கள் வேத ஜாதகமும் தனிப்பட்ட பலன்களும் தயாராகின்றன. இதற்கு 2-3 நிமிடங்கள் ஆகும்…",
        "reset_hint": "_(விவரங்களைத் திருத்த எப்போது வேண்டுமானாலும் RESET என்று அனுப்புங்கள்.)_",
        "lang_changed": "✅ சரி! இனி நான் *{name}* மொழியில் பதில் அளிப்பேன். 🙏",
        "welcome_back": ("🙏 மீண்டும் வரவேற்கிறேன், {first} அவர்களே!\n\nஎந்த ஜோதிடக் கேள்வியையும் கேளுங்கள், உங்கள் *தினசரி*, "
                         "*வாராந்திர* அல்லது *மாதாந்திர* வழிகாட்டுதலைக் கேளுங்கள், அல்லது ஜாதகப் புகைப்படம்/PDF அனுப்புங்கள்."),
        "kundli_reading": "📎 நன்றி! உங்கள் ஜாதகத்தைப் படித்துக்கொண்டிருக்கிறேன்…",
        "kundli_format": "🙏 நான் ஜாதகத்தை *PDF* அல்லது தெளிவான புகைப்படமாகப் படிக்க முடியும். அல்லது இதற்கு பதில் அளியுங்கள்:",
        "kundli_none": "🙏 அந்த கோப்பில் பிறப்பு விவரங்கள் கிடைக்கவில்லை, ஒவ்வொன்றாக நிரப்புவோம்.",
        "place_not_found": "🙏 உங்கள் பிறந்த இடம் வரைபடத்தில் கிடைக்கவில்லை. ",
        "type_own_question": "✍️ தயவுசெய்து உங்கள் கேள்வியை எழுதி அனுப்புங்கள். உங்கள் ஜாதகத்தின் அடிப்படையில் பதில் அளிக்கிறேன். 🙏",
        "menu_already_used": "🙏 இந்தப் பட்டியலிலிருந்து நீங்கள் ஏற்கனவே ஒரு விருப்பத்தைத் தேர்ந்தெடுத்துவிட்டீர்கள். தயவுசெய்து கீழே உங்கள் கேள்வியை எழுதி அனுப்புங்கள்.",
    },
    "Malayalam": {
        "subtitle": "_നിങ്ങളുടെ സ്വകാര്യ ജ്യോതിഷി._",
        "welcome_body": ("വേദ ജ്യോതിഷത്തിന്റെ അടിസ്ഥാനത്തിൽ നിങ്ങളുടെ ചോദ്യങ്ങൾക്ക് ഉത്തരം നൽകാനും വ്യക്തിപരമായ "
                         "മാർഗനിർദേശം നൽകാനും എനിക്ക് സന്തോഷമുണ്ട്.\n\n🌟 ആദ്യം നിങ്ങളുടെ ജനന വിവരങ്ങൾ തയ്യാറാക്കാം. ഞാൻ 4 "
                         "ചെറിയ വിവരങ്ങൾ ചോദിക്കും: നിങ്ങളുടെ പേര്, ജനന തീയതി, ജനന സമയം, ജനന സ്ഥലം.\n\n🔭 വിവരങ്ങൾ "
                         "ലഭിച്ചാലുടൻ, കൃത്യമായ കണക്കുകൂട്ടലുകളോടെ നിങ്ങളുടെ വേദ ജാതകം തയ്യാറാക്കി ജനന പ്രൊഫൈൽ ഒരുക്കും."),
        "q_full_name": "👉 *ദയവായി നിങ്ങളുടെ മുഴുവൻ പേര് പറയൂ.*",
        "q_dob": "📅 ദയവായി നിങ്ങളുടെ *ജനന തീയതി* പറയൂ (DD/MM/YYYY)\n_ഉദാഹരണം: 14/05/1992_",
        "q_birth_time": "⏰ നിങ്ങളുടെ *ജനന സമയം* എത്ര? (HH:MM AM/PM)\n_ഉദാഹരണം: 06:35 AM_",
        "q_birth_place": "📍 നിങ്ങളുടെ *ജനന സ്ഥലം* ഏതാണ്? (സ്ഥലം, സംസ്ഥാനം, രാജ്യം)\n_ഉദാഹരണം: Kochi, Kerala, India_",
        "thanks_name": "നന്ദി, {first}! 🙏",
        "thanks": "നന്ദി! 🙏",
        "hint_full_name": "🙏 ദയവായി നിങ്ങളുടെ മുഴുവൻ പേര് എഴുതൂ.",
        "hint_dob": "🙏 ദയവായി ജനന തീയതി ഇങ്ങനെ അയക്കൂ: *14/05/1992*",
        "hint_birth_time": "🙏 ദയവായി ജനന സമയം ഇങ്ങനെ അയക്കൂ: *06:35 AM* അല്ലെങ്കിൽ *06:35 PM*",
        "hint_birth_place": "🙏 ദയവായി ജനന സ്ഥലം ഇങ്ങനെ അയക്കൂ: *Kochi, Kerala, India*",
        "ampm": "നിങ്ങളുടെ ജനന സമയം *{t}* രാവിലെയോ വൈകുന്നേരമോ?\nദയവായി *{t} AM* അല്ലെങ്കിൽ *{t} PM* എന്ന് അയക്കൂ.",
        "place_error": ("🙏 ആ സ്ഥലം മാപ്പിൽ കണ്ടെത്താനായില്ല. ദയവായി *സ്ഥലം, സംസ്ഥാനം, രാജ്യം* എന്ന് അയക്കൂ\n"
                        "_ഉദാഹരണം: Kochi, Kerala, India_"),
        "place_confirm": ("📍 നിങ്ങളുടെ ജനന സ്ഥലം എനിക്ക് ഇങ്ങനെ ലഭിച്ചു:\n*{place}*\n\n"
                          "ഇത് ശരിയാണോ? *അതെ* (YES) എന്ന് മറുപടി അയക്കൂ, അല്ലെങ്കിൽ ശരിയായ സ്ഥലം അയക്കൂ (സ്ഥലം, സംസ്ഥാനം, രാജ്യം)."),
        "continue": "🙏 നമുക്ക് തുടരാം.",
        "no_problem": "സാരമില്ല. 🙏",
        "profile_head": "🙏 നന്ദി, {first}! നിങ്ങളുടെ ജനന വിവരങ്ങൾ:",
        "l_name": "പേര്", "l_dob": "ജനന തീയതി", "l_tob": "ജനന സമയം", "l_pob": "ജനന സ്ഥലം",
        "generating": "🔭 നിങ്ങളുടെ വേദ ജാതകവും വ്യക്തിഗത ഫലങ്ങളും തയ്യാറാകുന്നു. ഇതിന് 2-3 മിനിറ്റ് എടുക്കും…",
        "reset_hint": "_(വിവരങ്ങൾ തിരുത്താൻ എപ്പോൾ വേണമെങ്കിലും RESET എന്ന് അയക്കൂ.)_",
        "lang_changed": "✅ ശരി! ഇനി മുതൽ ഞാൻ *{name}* ഭാഷയിൽ മറുപടി നൽകും. 🙏",
        "welcome_back": ("🙏 വീണ്ടും സ്വാഗതം, {first}!\n\nഏത് ജ്യോതിഷ ചോദ്യവും ചോദിക്കൂ, നിങ്ങളുടെ *ദൈനംദിന*, *പ്രതിവാര* "
                         "അല്ലെങ്കിൽ *പ്രതിമാസ* മാർഗനിർദേശം ചോദിക്കൂ, അല്ലെങ്കിൽ ജാതകത്തിന്റെ ഫോട്ടോ/PDF അയക്കൂ."),
        "kundli_reading": "📎 നന്ദി! നിങ്ങളുടെ ജാതകം വായിക്കുകയാണ്…",
        "kundli_format": "🙏 എനിക്ക് ജാതകം *PDF* ആയോ വ്യക്തമായ ഫോട്ടോ ആയോ വായിക്കാം. അല്ലെങ്കിൽ ഇതിന് മറുപടി നൽകൂ:",
        "kundli_none": "🙏 ആ ഫയലിൽ ജനന വിവരങ്ങൾ കണ്ടെത്താനായില്ല, ഓരോന്നായി നൽകാം.",
        "place_not_found": "🙏 നിങ്ങളുടെ ജനന സ്ഥലം മാപ്പിൽ കണ്ടെത്താനായില്ല. ",
        "type_own_question": "✍️ ദയവായി നിങ്ങളുടെ ചോദ്യം ടൈപ്പ് ചെയ്ത് അയക്കൂ. നിങ്ങളുടെ ജാതകത്തിന്റെ അടിസ്ഥാനത്തിൽ ഞാൻ മറുപടി നൽകാം. 🙏",
        "menu_already_used": "🙏 ഈ പട്ടികയിൽ നിന്ന് നിങ്ങൾ ഇതിനകം ഒരു ഓപ്ഷൻ തിരഞ്ഞെടുത്തു. ദയവായി താഴെ നിങ്ങളുടെ ചോദ്യം ടൈപ്പ് ചെയ്ത് അയക്കൂ.",
    },
    "Marathi": {
        "subtitle": "_तुमचे वैयक्तिक ज्योतिषी._",
        "welcome_body": ("वैदिक ज्योतिषाच्या आधारे तुमच्या प्रश्नांची उत्तरे देण्यास आणि वैयक्तिक मार्गदर्शन करण्यास मला आनंद "
                         "होईल.\n\n🌟 आधी तुमची जन्म माहिती तयार करूया. मी 4 छोटी माहिती विचारेन: तुमचे नाव, जन्मतारीख, "
                         "जन्मवेळ आणि जन्मस्थान.\n\n🔭 माहिती मिळताच, अचूक गणनेने तुमची वैदिक जन्मकुंडली तयार करून तुमची "
                         "जन्म प्रोफाइल तयार करेन."),
        "q_full_name": "👉 *कृपया तुमचे पूर्ण नाव सांगा.*",
        "q_dob": "📅 कृपया तुमची *जन्मतारीख* सांगा (DD/MM/YYYY)\n_उदाहरण: 14/05/1992_",
        "q_birth_time": "⏰ तुमची *जन्मवेळ* काय आहे? (HH:MM AM/PM)\n_उदाहरण: 06:35 AM_",
        "q_birth_place": "📍 तुमचे *जन्मस्थान* कोणते? (शहर, राज्य, देश)\n_उदाहरण: Pune, Maharashtra, India_",
        "thanks_name": "धन्यवाद, {first} जी! 🙏",
        "thanks": "धन्यवाद! 🙏",
        "hint_full_name": "🙏 कृपया तुमचे पूर्ण नाव लिहा.",
        "hint_dob": "🙏 कृपया जन्मतारीख अशी पाठवा: *14/05/1992*",
        "hint_birth_time": "🙏 कृपया जन्मवेळ अशी पाठवा: *06:35 AM* किंवा *06:35 PM*",
        "hint_birth_place": "🙏 कृपया जन्मस्थान असे पाठवा: *Pune, Maharashtra, India*",
        "ampm": "तुमची जन्मवेळ *{t}* सकाळची की संध्याकाळची?\nकृपया *{t} AM* किंवा *{t} PM* असे पाठवा.",
        "place_error": ("🙏 ते ठिकाण नकाशावर सापडले नाही. कृपया *शहर, राज्य, देश* असे पाठवा\n"
                        "_उदाहरण: Pune, Maharashtra, India_"),
        "place_confirm": ("📍 तुमचे जन्मस्थान मला असे सापडले:\n*{place}*\n\n"
                          "हे बरोबर आहे का? *होय* (YES) असे उत्तर द्या, किंवा योग्य ठिकाण पाठवा (शहर, राज्य, देश)."),
        "continue": "🙏 चला पुढे जाऊया.",
        "no_problem": "काही हरकत नाही. 🙏",
        "profile_head": "🙏 धन्यवाद, {first} जी! तुमची जन्म माहिती:",
        "l_name": "नाव", "l_dob": "जन्मतारीख", "l_tob": "जन्मवेळ", "l_pob": "जन्मस्थान",
        "generating": "🔭 तुमची वैदिक जन्मकुंडली आणि वैयक्तिक भविष्य तयार होत आहे. यासाठी 2-3 मिनिटे लागतात…",
        "reset_hint": "_(माहिती दुरुस्त करण्यासाठी कधीही RESET पाठवा.)_",
        "lang_changed": "✅ ठीक आहे! आता मी *{name}* मध्ये उत्तर देईन. 🙏",
        "welcome_back": ("🙏 पुन्हा स्वागत आहे, {first} जी!\n\nकोणताही ज्योतिष प्रश्न विचारा, तुमचे *दैनिक*, *साप्ताहिक* किंवा "
                         "*मासिक* मार्गदर्शन मागा, किंवा कुंडलीचा फोटो/PDF पाठवा."),
        "kundli_reading": "📎 धन्यवाद! तुमची कुंडली वाचत आहे…",
        "kundli_format": "🙏 मी कुंडली *PDF* किंवा स्पष्ट फोटो स्वरूपात वाचू शकतो. किंवा फक्त याचे उत्तर द्या:",
        "kundli_none": "🙏 त्या फाइलमध्ये जन्म माहिती सापडली नाही, एकेक करून भरूया.",
        "place_not_found": "🙏 तुमचे जन्मस्थान नकाशावर सापडले नाही. ",
        "type_own_question": "✍️ कृपया तुमचा प्रश्न टाइप करून पाठवा. मी तुमच्या जन्मकुंडलीनुसार उत्तर देईन. 🙏",
        "menu_already_used": "🙏 तुम्ही या यादीतून आधीच एक पर्याय निवडला आहे. कृपया खाली तुमचा स्वतःचा प्रश्न टाइप करून पाठवा.",
    },
    "Bengali": {
        "subtitle": "_আপনার ব্যক্তিগত জ্যোতিষী।_",
        "welcome_body": ("বৈদিক জ্যোতিষের ভিত্তিতে আপনার প্রশ্নের উত্তর দিতে এবং ব্যক্তিগত পরামর্শ দিতে পেরে আমি আনন্দিত।\n\n"
                         "🌟 প্রথমে আপনার জন্ম প্রোফাইল তৈরি করি। আমি ৪টি ছোট তথ্য জানতে চাইব: আপনার নাম, জন্মতারিখ, "
                         "জন্মসময় এবং জন্মস্থান।\n\n🔭 তথ্য পেলেই, সঠিক গণনার মাধ্যমে আপনার বৈদিক জন্মকুণ্ডলী তৈরি করে "
                         "আপনার জন্ম প্রোফাইল প্রস্তুত করব।"),
        "q_full_name": "👉 *অনুগ্রহ করে আপনার পুরো নাম বলুন।*",
        "q_dob": "📅 অনুগ্রহ করে আপনার *জন্মতারিখ* বলুন (DD/MM/YYYY)\n_উদাহরণ: 14/05/1992_",
        "q_birth_time": "⏰ আপনার *জন্মসময়* কত? (HH:MM AM/PM)\n_উদাহরণ: 06:35 AM_",
        "q_birth_place": "📍 আপনার *জন্মস্থান* কোথায়? (শহর, রাজ্য, দেশ)\n_উদাহরণ: Kolkata, West Bengal, India_",
        "thanks_name": "ধন্যবাদ, {first}! 🙏",
        "thanks": "ধন্যবাদ! 🙏",
        "hint_full_name": "🙏 অনুগ্রহ করে আপনার পুরো নাম লিখুন।",
        "hint_dob": "🙏 অনুগ্রহ করে জন্মতারিখ এভাবে পাঠান: *14/05/1992*",
        "hint_birth_time": "🙏 অনুগ্রহ করে জন্মসময় এভাবে পাঠান: *06:35 AM* বা *06:35 PM*",
        "hint_birth_place": "🙏 অনুগ্রহ করে জন্মস্থান এভাবে পাঠান: *Kolkata, West Bengal, India*",
        "ampm": "আপনার জন্মসময় *{t}* সকাল না সন্ধ্যা?\nঅনুগ্রহ করে *{t} AM* বা *{t} PM* লিখে পাঠান।",
        "place_error": ("🙏 জায়গাটি মানচিত্রে খুঁজে পাইনি। অনুগ্রহ করে *শহর, রাজ্য, দেশ* এভাবে পাঠান\n"
                        "_উদাহরণ: Kolkata, West Bengal, India_"),
        "place_confirm": ("📍 আপনার জন্মস্থান আমি এভাবে পেয়েছি:\n*{place}*\n\n"
                          "এটি কি সঠিক? *হ্যাঁ* (YES) লিখে উত্তর দিন, অথবা সঠিক জায়গা পাঠান (শহর, রাজ্য, দেশ)।"),
        "continue": "🙏 চলুন এগিয়ে যাই।",
        "no_problem": "কোনো সমস্যা নেই। 🙏",
        "profile_head": "🙏 ধন্যবাদ, {first}! আপনার জন্ম তথ্য:",
        "l_name": "নাম", "l_dob": "জন্মতারিখ", "l_tob": "জন্মসময়", "l_pob": "জন্মস্থান",
        "generating": "🔭 আপনার বৈদিক জন্মকুণ্ডলী ও ব্যক্তিগত ফলাফল তৈরি হচ্ছে। এতে ২-৩ মিনিট লাগে…",
        "reset_hint": "_(তথ্য সংশোধন করতে যেকোনো সময় RESET পাঠান।)_",
        "lang_changed": "✅ ঠিক আছে! এখন থেকে আমি *{name}* ভাষায় উত্তর দেব। 🙏",
        "welcome_back": ("🙏 আবার স্বাগতম, {first}!\n\nযেকোনো জ্যোতিষ প্রশ্ন করুন, আপনার *দৈনিক*, *সাপ্তাহিক* বা *মাসিক* "
                         "নির্দেশনা চান, অথবা কুণ্ডলীর ছবি/PDF পাঠান।"),
        "kundli_reading": "📎 ধন্যবাদ! আপনার কুণ্ডলী পড়ছি…",
        "kundli_format": "🙏 আমি কুণ্ডলী *PDF* বা পরিষ্কার ছবি হিসেবে পড়তে পারি। অথবা শুধু এর উত্তর দিন:",
        "kundli_none": "🙏 ওই ফাইলে জন্ম তথ্য পাইনি, একে একে পূরণ করি।",
        "place_not_found": "🙏 আপনার জন্মস্থান মানচিত্রে খুঁজে পাইনি। ",
        "type_own_question": "✍️ অনুগ্রহ করে আপনার প্রশ্নটি লিখে পাঠান। আমি আপনার জন্মকুণ্ডলী অনুযায়ী উত্তর দেব। 🙏",
        "menu_already_used": "🙏 আপনি এই তালিকা থেকে ইতিমধ্যেই একটি বিকল্প বেছে নিয়েছেন। অনুগ্রহ করে নিচে আপনার নিজের প্রশ্নটি লিখে পাঠান।",
    },
    "Gujarati": {
        "subtitle": "_તમારા વ્યક્તિગત જ્યોતિષી._",
        "welcome_body": ("વૈદિક જ્યોતિષના આધારે તમારા પ્રશ્નોના જવાબ આપવામાં અને વ્યક્તિગત માર્ગદર્શન આપવામાં મને આનંદ થશે.\n\n"
                         "🌟 પહેલા તમારી જન્મ પ્રોફાઇલ તૈયાર કરીએ. હું 4 નાની વિગતો પૂછીશ: તમારું નામ, જન્મ તારીખ, જન્મ "
                         "સમય અને જન્મ સ્થળ.\n\n🔭 વિગતો મળતાં જ, ચોક્કસ ગણતરીથી તમારી વૈદિક જન્મકુંડળી બનાવીને તમારી "
                         "જન્મ પ્રોફાઇલ તૈયાર કરીશ."),
        "q_full_name": "👉 *કૃપા કરીને તમારું પૂરું નામ જણાવો.*",
        "q_dob": "📅 કૃપા કરીને તમારી *જન્મ તારીખ* જણાવો (DD/MM/YYYY)\n_ઉદાહરણ: 14/05/1992_",
        "q_birth_time": "⏰ તમારો *જન્મ સમય* શું છે? (HH:MM AM/PM)\n_ઉદાહરણ: 06:35 AM_",
        "q_birth_place": "📍 તમારું *જન્મ સ્થળ* કયું છે? (શહેર, રાજ્ય, દેશ)\n_ઉદાહરણ: Ahmedabad, Gujarat, India_",
        "thanks_name": "આભાર, {first} જી! 🙏",
        "thanks": "આભાર! 🙏",
        "hint_full_name": "🙏 કૃપા કરીને તમારું પૂરું નામ લખો.",
        "hint_dob": "🙏 કૃપા કરીને જન્મ તારીખ આ રીતે મોકલો: *14/05/1992*",
        "hint_birth_time": "🙏 કૃપા કરીને જન્મ સમય આ રીતે મોકલો: *06:35 AM* અથવા *06:35 PM*",
        "hint_birth_place": "🙏 કૃપા કરીને જન્મ સ્થળ આ રીતે મોકલો: *Ahmedabad, Gujarat, India*",
        "ampm": "તમારો જન્મ સમય *{t}* સવારનો છે કે સાંજનો?\nકૃપા કરીને *{t} AM* અથવા *{t} PM* લખીને મોકલો.",
        "place_error": ("🙏 તે સ્થળ નકશા પર મળ્યું નહીં. કૃપા કરીને *શહેર, રાજ્ય, દેશ* એ રીતે મોકલો\n"
                        "_ઉદાહરણ: Ahmedabad, Gujarat, India_"),
        "place_confirm": ("📍 તમારું જન્મ સ્થળ મને આ મળ્યું:\n*{place}*\n\n"
                          "શું આ સાચું છે? *હા* (YES) લખીને જવાબ આપો, અથવા સાચું સ્થળ મોકલો (શહેર, રાજ્ય, દેશ)."),
        "continue": "🙏 ચાલો આગળ વધીએ.",
        "no_problem": "કોઈ વાંધો નહીં. 🙏",
        "profile_head": "🙏 આભાર, {first} જી! તમારી જન્મ વિગતો:",
        "l_name": "નામ", "l_dob": "જન્મ તારીખ", "l_tob": "જન્મ સમય", "l_pob": "જન્મ સ્થળ",
        "generating": "🔭 તમારી વૈદિક જન્મકુંડળી અને વ્યક્તિગત ભવિષ્ય તૈયાર થઈ રહ્યું છે. આમાં 2-3 મિનિટ લાગે છે…",
        "reset_hint": "_(વિગતો સુધારવા માટે ક્યારેય પણ RESET મોકલો.)_",
        "lang_changed": "✅ બરાબર! હવેથી હું *{name}* માં જવાબ આપીશ. 🙏",
        "welcome_back": ("🙏 ફરી સ્વાગત છે, {first} જી!\n\nકોઈપણ જ્યોતિષ પ્રશ્ન પૂછો, તમારું *દૈનિક*, *સાપ્તાહિક* અથવા *માસિક* "
                         "માર્ગદર્શન માગો, અથવા કુંડળીનો ફોટો/PDF મોકલો."),
        "kundli_reading": "📎 આભાર! તમારી કુંડળી વાંચી રહ્યો છું…",
        "kundli_format": "🙏 હું કુંડળી *PDF* અથવા સ્પષ્ટ ફોટો તરીકે વાંચી શકું છું. અથવા ફક્ત આનો જવાબ આપો:",
        "kundli_none": "🙏 તે ફાઇલમાં જન્મ વિગતો મળી નહીં, એક પછી એક ભરીએ.",
        "place_not_found": "🙏 તમારું જન્મ સ્થળ નકશા પર મળ્યું નહીં. ",
        "type_own_question": "✍️ કૃપા કરીને તમારો પ્રશ્ન લખીને મોકલો. હું તમારી જન્મકુંડળી મુજબ જવાબ આપીશ. 🙏",
        "menu_already_used": "🙏 તમે આ યાદીમાંથી પહેલેથી જ એક વિકલ્પ પસંદ કરી લીધો છે. કૃપા કરીને નીચે તમારો પોતાનો પ્રશ્ન લખીને મોકલો.",
    },
    "Punjabi": {
        "subtitle": "_ਤੁਹਾਡੇ ਨਿੱਜੀ ਜੋਤਸ਼ੀ।_",
        "welcome_body": ("ਵੈਦਿਕ ਜੋਤਿਸ਼ ਦੇ ਆਧਾਰ 'ਤੇ ਤੁਹਾਡੇ ਸਵਾਲਾਂ ਦੇ ਜਵਾਬ ਦੇਣ ਅਤੇ ਨਿੱਜੀ ਮਾਰਗਦਰਸ਼ਨ ਦੇਣ ਵਿੱਚ ਮੈਨੂੰ ਖੁਸ਼ੀ ਹੋਵੇਗੀ।\n\n"
                         "🌟 ਪਹਿਲਾਂ ਤੁਹਾਡੀ ਜਨਮ ਪ੍ਰੋਫਾਈਲ ਤਿਆਰ ਕਰੀਏ। ਮੈਂ 4 ਛੋਟੀਆਂ ਜਾਣਕਾਰੀਆਂ ਪੁੱਛਾਂਗਾ: ਤੁਹਾਡਾ ਨਾਮ, ਜਨਮ "
                         "ਤਾਰੀਖ, ਜਨਮ ਸਮਾਂ ਅਤੇ ਜਨਮ ਸਥਾਨ।\n\n🔭 ਜਾਣਕਾਰੀ ਮਿਲਦੇ ਹੀ, ਸਹੀ ਗਣਨਾ ਨਾਲ ਤੁਹਾਡੀ ਵੈਦਿਕ ਜਨਮ ਕੁੰਡਲੀ "
                         "ਬਣਾ ਕੇ ਤੁਹਾਡੀ ਜਨਮ ਪ੍ਰੋਫਾਈਲ ਤਿਆਰ ਕਰਾਂਗਾ।"),
        "q_full_name": "👉 *ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਪੂਰਾ ਨਾਮ ਦੱਸੋ।*",
        "q_dob": "📅 ਕਿਰਪਾ ਕਰਕੇ ਆਪਣੀ *ਜਨਮ ਤਾਰੀਖ* ਦੱਸੋ (DD/MM/YYYY)\n_ਉਦਾਹਰਨ: 14/05/1992_",
        "q_birth_time": "⏰ ਤੁਹਾਡਾ *ਜਨਮ ਸਮਾਂ* ਕੀ ਹੈ? (HH:MM AM/PM)\n_ਉਦਾਹਰਨ: 06:35 AM_",
        "q_birth_place": "📍 ਤੁਹਾਡਾ *ਜਨਮ ਸਥਾਨ* ਕਿਹੜਾ ਹੈ? (ਸ਼ਹਿਰ, ਰਾਜ, ਦੇਸ਼)\n_ਉਦਾਹਰਨ: Amritsar, Punjab, India_",
        "thanks_name": "ਧੰਨਵਾਦ, {first} ਜੀ! 🙏",
        "thanks": "ਧੰਨਵਾਦ! 🙏",
        "hint_full_name": "🙏 ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਪੂਰਾ ਨਾਮ ਲਿਖੋ।",
        "hint_dob": "🙏 ਕਿਰਪਾ ਕਰਕੇ ਜਨਮ ਤਾਰੀਖ ਇਸ ਤਰ੍ਹਾਂ ਭੇਜੋ: *14/05/1992*",
        "hint_birth_time": "🙏 ਕਿਰਪਾ ਕਰਕੇ ਜਨਮ ਸਮਾਂ ਇਸ ਤਰ੍ਹਾਂ ਭੇਜੋ: *06:35 AM* ਜਾਂ *06:35 PM*",
        "hint_birth_place": "🙏 ਕਿਰਪਾ ਕਰਕੇ ਜਨਮ ਸਥਾਨ ਇਸ ਤਰ੍ਹਾਂ ਭੇਜੋ: *Amritsar, Punjab, India*",
        "ampm": "ਤੁਹਾਡਾ ਜਨਮ ਸਮਾਂ *{t}* ਸਵੇਰ ਦਾ ਹੈ ਜਾਂ ਸ਼ਾਮ ਦਾ?\nਕਿਰਪਾ ਕਰਕੇ *{t} AM* ਜਾਂ *{t} PM* ਲਿਖ ਕੇ ਭੇਜੋ।",
        "place_error": ("🙏 ਉਹ ਥਾਂ ਨਕਸ਼ੇ 'ਤੇ ਨਹੀਂ ਮਿਲੀ। ਕਿਰਪਾ ਕਰਕੇ *ਸ਼ਹਿਰ, ਰਾਜ, ਦੇਸ਼* ਇਸ ਤਰ੍ਹਾਂ ਭੇਜੋ\n"
                        "_ਉਦਾਹਰਨ: Amritsar, Punjab, India_"),
        "place_confirm": ("📍 ਤੁਹਾਡਾ ਜਨਮ ਸਥਾਨ ਮੈਨੂੰ ਇਹ ਮਿਲਿਆ:\n*{place}*\n\n"
                          "ਕੀ ਇਹ ਸਹੀ ਹੈ? *ਹਾਂ* (YES) ਲਿਖ ਕੇ ਜਵਾਬ ਦਿਓ, ਜਾਂ ਸਹੀ ਥਾਂ ਭੇਜੋ (ਸ਼ਹਿਰ, ਰਾਜ, ਦੇਸ਼)।"),
        "continue": "🙏 ਚਲੋ ਅੱਗੇ ਵਧੀਏ।",
        "no_problem": "ਕੋਈ ਗੱਲ ਨਹੀਂ। 🙏",
        "profile_head": "🙏 ਧੰਨਵਾਦ, {first} ਜੀ! ਤੁਹਾਡੀ ਜਨਮ ਜਾਣਕਾਰੀ:",
        "l_name": "ਨਾਮ", "l_dob": "ਜਨਮ ਤਾਰੀਖ", "l_tob": "ਜਨਮ ਸਮਾਂ", "l_pob": "ਜਨਮ ਸਥਾਨ",
        "generating": "🔭 ਤੁਹਾਡੀ ਵੈਦਿਕ ਜਨਮ ਕੁੰਡਲੀ ਅਤੇ ਨਿੱਜੀ ਭਵਿੱਖਫਲ ਤਿਆਰ ਹੋ ਰਿਹਾ ਹੈ। ਇਸ ਵਿੱਚ 2-3 ਮਿੰਟ ਲੱਗਦੇ ਹਨ…",
        "reset_hint": "_(ਜਾਣਕਾਰੀ ਠੀਕ ਕਰਨ ਲਈ ਕਦੇ ਵੀ RESET ਭੇਜੋ।)_",
        "lang_changed": "✅ ਠੀਕ ਹੈ! ਹੁਣ ਤੋਂ ਮੈਂ *{name}* ਵਿੱਚ ਜਵਾਬ ਦੇਵਾਂਗਾ। 🙏",
        "welcome_back": ("🙏 ਫਿਰ ਤੋਂ ਜੀ ਆਇਆਂ ਨੂੰ, {first} ਜੀ!\n\nਕੋਈ ਵੀ ਜੋਤਿਸ਼ ਸਵਾਲ ਪੁੱਛੋ, ਆਪਣਾ *ਰੋਜ਼ਾਨਾ*, *ਹਫ਼ਤਾਵਾਰੀ* ਜਾਂ "
                         "*ਮਹੀਨਾਵਾਰ* ਮਾਰਗਦਰਸ਼ਨ ਮੰਗੋ, ਜਾਂ ਕੁੰਡਲੀ ਦੀ ਫੋਟੋ/PDF ਭੇਜੋ।"),
        "kundli_reading": "📎 ਧੰਨਵਾਦ! ਤੁਹਾਡੀ ਕੁੰਡਲੀ ਪੜ੍ਹ ਰਿਹਾ ਹਾਂ…",
        "kundli_format": "🙏 ਮੈਂ ਕੁੰਡਲੀ *PDF* ਜਾਂ ਸਾਫ਼ ਫੋਟੋ ਵਜੋਂ ਪੜ੍ਹ ਸਕਦਾ ਹਾਂ। ਜਾਂ ਬੱਸ ਇਸ ਦਾ ਜਵਾਬ ਦਿਓ:",
        "kundli_none": "🙏 ਉਸ ਫਾਈਲ ਵਿੱਚ ਜਨਮ ਜਾਣਕਾਰੀ ਨਹੀਂ ਮਿਲੀ, ਇੱਕ-ਇੱਕ ਕਰਕੇ ਭਰੀਏ।",
        "place_not_found": "🙏 ਤੁਹਾਡਾ ਜਨਮ ਸਥਾਨ ਨਕਸ਼ੇ 'ਤੇ ਨਹੀਂ ਮਿਲਿਆ। ",
        "type_own_question": "✍️ ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਸਵਾਲ ਲਿਖ ਕੇ ਭੇਜੋ। ਮੈਂ ਤੁਹਾਡੀ ਜਨਮ ਕੁੰਡਲੀ ਅਨੁਸਾਰ ਜਵਾਬ ਦੇਵਾਂਗਾ। 🙏",
        "menu_already_used": "🙏 ਤੁਸੀਂ ਇਸ ਸੂਚੀ ਵਿੱਚੋਂ ਪਹਿਲਾਂ ਹੀ ਇੱਕ ਵਿਕਲਪ ਚੁਣ ਚੁੱਕੇ ਹੋ। ਕਿਰਪਾ ਕਰਕੇ ਹੇਠਾਂ ਆਪਣਾ ਸਵਾਲ ਲਿਖ ਕੇ ਭੇਜੋ।",
    },
}


def _lang(lang: str | None) -> str:
    lang = (lang or "").strip()
    return lang if lang in T else "English"


def t(key: str, lang: str | None = None, **kw) -> str:
    text = T[_lang(lang)].get(key) or T["English"][key]
    return text.format(**kw) if kw else text


def question(field: str, lang: str | None = None) -> str:
    return t("q_" + field, lang)


def hint(field: str, lang: str | None = None) -> str:
    return t("hint_" + field, lang)


def welcome(lang: str | None = None) -> str:
    """Sent after the language is chosen. The welcome IMAGE already greeted the client, so only the one line about
    the 4 details (middle paragraph of welcome_body) + the name question."""
    parts = t("welcome_body", lang).split("\n\n")
    intro = parts[1] if len(parts) > 1 else parts[0]
    return f"{intro}\n\n{question('full_name', lang)}"


def native_name(lang: str) -> str:
    return NATIVE.get(lang, lang)


def menu_choice(text: str) -> str:
    """'3' -> 'Kannada' (number from the language menu); '' if not a menu number."""
    s = (text or "").strip().strip(".)]").lstrip("[(")
    if s.isdigit() and 1 <= int(s) <= len(MENU_LANGS):
        return MENU_LANGS[int(s) - 1][0]
    return ""


def question_menu_choice(text: str) -> str:
    """'1' -> 'Daily Prediction' (number from the fallback questions menu); '' if not a menu number."""
    s = (text or "").strip().strip(".)]").lstrip("[(")
    if s.isdigit() and 1 <= int(s) <= len(QUESTION_MENU_ITEMS):
        return QUESTION_MENU_ITEMS[int(s) - 1][1]
    return ""


def is_type_own_question(text: str) -> bool:
    return (text or "").strip().lower() == TYPE_OWN_QUESTION.lower()

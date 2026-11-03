import os
import json
import re
from pathlib import Path

BASE_DIR = Path(os.environ.get("VOCAB_PROJECT_DIR", Path(__file__).parent.resolve()))

def get_template_path(track_id):
    folder_name = "elem" if track_id == "elem" else "junior"
    possible_roots = [
        Path(os.environ.get("VOCAB_PROJECT_DIR", "")),
        Path(__file__).parent.resolve(),
        BASE_DIR,
        Path.cwd()
    ]

    for root in possible_roots:
        if not root or not root.exists():
            continue
        candidate_folder = root / folder_name
        if candidate_folder.exists():
            pref_file = candidate_folder / ("2026_ew03.html" if track_id == "elem" else "2026_w05d5.html")
            if pref_file.exists():
                return pref_file
            html_files = sorted(list(candidate_folder.glob("*.html")))
            if html_files:
                return html_files[-1]

    raise FileNotFoundError(f"找不到 {folder_name}/ 目錄下的 HTML 範本檔案。")

# 常見無效 / Pro 圖示與其對應之 Font Awesome Free 最佳替代圖示
ICON_ALIASES = {
    # 針對本次問題
    "elephant": "fa-mountain",
    "fa-elephant": "fa-mountain",
    "sparkles": "fa-wand-magic-sparkles",
    "fa-sparkles": "fa-wand-magic-sparkles",
    # 動物類 (Font Awesome Free 無專屬 icon 之常見動物)
    "rabbit": "fa-paw",
    "fa-rabbit": "fa-paw",
    "butterfly": "fa-dove",
    "fa-butterfly": "fa-dove",
    "whale": "fa-fish",
    "fa-whale": "fa-fish",
    "dolphin": "fa-fish",
    "fa-dolphin": "fa-fish",
    "lion": "fa-paw",
    "fa-lion": "fa-paw",
    "tiger": "fa-paw",
    "fa-tiger": "fa-paw",
    "bear": "fa-paw",
    "fa-bear": "fa-paw",
    "monkey": "fa-paw",
    "fa-monkey": "fa-paw",
    "giraffe": "fa-paw",
    "fa-giraffe": "fa-paw",
    "dinosaur": "fa-dragon",
    "fa-dinosaur": "fa-dragon",
    "turtle": "fa-shield-halved",
    "fa-turtle": "fa-shield-halved",
    "snake": "fa-worm",
    "fa-snake": "fa-worm",
    "duck": "fa-feather",
    "fa-duck": "fa-feather",
    "balloon": "fa-heart",
    "fa-balloon": "fa-heart",
    "kite": "fa-wind",
    "fa-kite": "fa-wind",
    "sandwich": "fa-burger",
    "fa-sandwich": "fa-burger",
    "donut": "fa-cookie",
    "fa-donut": "fa-cookie",
}

# 國中教育會考核心單字詞性資料庫 (台灣教育部標準常用詞性)
JUNIOR_VOCAB_POS_MAP = {
    # W09 當週重點字
    "water": "n. | v.",
    "kite": "n.",
    "toy": "n.",
    "ball": "n.",
    "holiday": "n.",
    "jog": "v.",
    "program": "n.",
    "race": "n. | v.",
    "tie": "n. | v.",
    "suit": "n. | v.",
    "yo-yo": "n.",
    "fun": "n.",
    "swim": "v.",
    "baseball": "n.",
    "soccer": "n.",
    "surf": "v. | n.",
    "team": "n.",
    "after": "prep. | conj.",
    "swimsuit": "n.",
    "underwear": "n.",
    "basketball": "n.",
    "birthday": "n.",
    "date": "n. | v.",
    "week": "n.",
    "day": "n.",
    "ago": "adv.",
    "before": "prep. | conj. | adv.",
    "eve": "n.",
    "earrings": "n.",
    "sneakers": "n.",
    "january": "n.",
    "february": "n.",
    "march": "n.",
    "april": "n.",
    "hour": "n.",
    "noon": "n.",
    "once": "adv. | conj.",
    "soon": "adv.",
    "hard-working": "adj.",
    "skinny": "adj.",
    "may": "n.",
    "june": "n.",
    "july": "n.",
    "august": "n.",
    "still": "adv.",
    "then": "adv.",
    "twice": "adv.",
    "yet": "adv. | conj.",
    "naughty": "adj.",
    "curious": "adj.",
    # 其他國中高頻字彙
    "short": "adj.",
    "small": "adj.",
    "thin": "adj.",
    "clean": "adj. | v.",
    "dark": "adj. | n.",
    "dear": "adj. | n.",
    "else": "adv. | adj.",
    "fat": "adj. | n.",
    "monster": "n.",
    "record": "n. | v.",
    "warm": "adj. | v.",
    "cold": "adj. | n.",
    "cool": "adj. | v.",
    "hot": "adj.",
    "weather": "n.",
    "something": "pron.",
    "them": "pron.",
    "us": "pron.",
    "him": "pron.",
    "her": "pron. | adj.",
    "me": "pron.",
    "you": "pron.",
    "it": "pron.",
    "we": "pron.",
    "they": "pron.",
    "road": "n.",
    "scene": "n.",
    "rectangle": "n.",
    "run": "v. | n.",
    "walk": "v. | n.",
    "jump": "v. | n.",
    "eat": "v.",
    "drink": "v. | n.",
    "sleep": "v. | n.",
    "read": "v.",
    "write": "v.",
    "sing": "v.",
    "dance": "v. | n.",
    "play": "v. | n.",
    "study": "v. | n.",
    "learn": "v.",
    "teach": "v.",
    "speak": "v.",
    "talk": "v. | n.",
    "listen": "v.",
    "hear": "v.",
    "see": "v.",
    "look": "v. | n.",
    "watch": "v. | n.",
    "buy": "v.",
    "sell": "v.",
    "make": "v.",
    "cook": "v. | n.",
    "help": "v. | n.",
    "love": "v. | n.",
    "like": "v. | prep.",
    "hate": "v. | n.",
    "want": "v.",
    "need": "v. | n.",
    "know": "v.",
    "think": "v.",
    "feel": "v.",
    "tell": "v.",
    "ask": "v.",
    "answer": "v. | n.",
    "work": "v. | n.",
    "live": "v. | adj.",
    "stay": "v. | n.",
    "stand": "v. | n.",
    "sit": "v.",
    "wait": "v. | n.",
    "stop": "v. | n.",
    "start": "v. | n.",
    "begin": "v.",
    "finish": "v. | n.",
    "open": "v. | adj.",
    "close": "v. | adj.",
    "turn": "v. | n.",
    "move": "v. | n.",
    "change": "v. | n.",
    "show": "v. | n.",
    "give": "v.",
    "take": "v.",
    "bring": "v.",
    "get": "v.",
    "find": "v.",
    "keep": "v.",
    "put": "v.",
    "call": "v. | n.",
    "try": "v. | n.",
    "use": "v. | n.",
    "leave": "v.",
    "meet": "v. | n.",
    "fly": "v. | n.",
    "drive": "v. | n.",
    "ride": "v. | n.",
    "catch": "v. | n.",
    "hold": "v.",
    "send": "v.",
    "build": "v.",
    "draw": "v.",
    "paint": "v. | n.",
    "climb": "v. | n.",
    "shine": "v. | n.",
    "rain": "n. | v.",
    "snow": "n. | v.",
    "wind": "n.",
    "smile": "v. | n.",
    "laugh": "v. | n.",
    "cry": "v. | n.",
    "shout": "v. | n.",
    "wash": "v. | n.",
    "brush": "v. | n.",
    "touch": "v. | n.",
    "smell": "v. | n.",
    "taste": "v. | n.",
    "sound": "v. | n.",
    "wear": "v.",
    "dress": "n. | v.",
    "cross": "v. | n.",
    "pass": "v. | n.",
    "cut": "v. | n.",
    "break": "v. | n.",
    "fall": "v. | n.",
    "drop": "v. | n.",
    "lose": "v.",
    "win": "v. | n.",
    "pay": "v. | n.",
    "spend": "v.",
    "cost": "v. | n.",
    "save": "v.",
    "grow": "v.",
    "plant": "n. | v.",
    "feed": "v.",
    "ring": "v. | n.",
    "knock": "v. | n.",
    "push": "v. | n.",
    "pull": "v. | n.",
    "lock": "v. | n.",
    "pack": "v. | n.",
    "check": "v. | n.",
    "cheer": "v. | n.",
    "hope": "v. | n.",
    "wish": "v. | n.",
    "fear": "v. | n.",
    "worry": "v. | n.",
    "care": "v. | n.",
    "mind": "v. | n.",
    "forget": "v.",
    "remember": "v.",
    "understand": "v.",
    "believe": "v.",
    "agree": "v.",
    "decide": "v.",
    "choose": "v.",
    "prepare": "v.",
    "practice": "v. | n.",
    "exercise": "v. | n.",
    "invite": "v.",
    "visit": "v. | n.",
    "travel": "v. | n.",
    "arrive": "v.",
    "enter": "v.",
    "return": "v. | n.",
    "follow": "v.",
    "lead": "v. | n.",
    "guide": "v. | n.",
    "order": "v. | n.",
    "point": "v. | n.",
    "mark": "v. | n.",
    "score": "v. | n.",
    "set": "v. | n.",
    "hit": "v. | n.",
    "kick": "v. | n.",
    "throw": "v. | n.",
    "blow": "v. | n.",
    "hang": "v.",
    "fix": "v.",
    "repair": "v. | n.",
    "collect": "v.",
    "borrow": "v.",
    "lend": "v.",
    "share": "v. | n.",
    "protect": "v.",
    "waste": "v. | n.",
    "enjoy": "v.",
    "miss": "v.",
    "surprise": "v. | n.",
    "excite": "v.",
    "bore": "v.",
    "tire": "v.",
    "hurt": "v. | adj.",
    "burn": "v. | n.",
    "bite": "v. | n.",
    "hide": "v.",
    "fight": "v. | n.",
    "kill": "v.",
    "die": "v.",
    "born": "adj.",
    "happen": "v.",
    "appear": "v.",
    "disappear": "v.",
    "seem": "v.",
    "become": "v.",
    "belong": "v.",
    "mean": "v. | adj.",
    "matter": "v. | n.",
    "depend": "v.",
    "allow": "v.",
    "cause": "v. | n.",
    "create": "v.",
    "invent": "v.",
    "discover": "v.",
    "produce": "v.",
    "provide": "v.",
    "offer": "v. | n.",
    "suggest": "v.",
    "explain": "v.",
    "describe": "v.",
    "express": "v.",
    "repeat": "v. | n.",
    "remind": "v.",
    "warn": "v.",
    "promise": "v. | n.",
    "refuse": "v.",
    "accept": "v.",
    "receive": "v.",
    "admit": "v.",
    "avoid": "v.",
    "escape": "v. | n.",
    "fail": "v. | n.",
    "succeed": "v.",
    "manage": "v.",
    "afford": "v.",
    "imagine": "v.",
    "wonder": "v. | n.",
    "doubt": "v. | n.",
    "trust": "v. | n.",
    "respect": "v. | n.",
    "admire": "v.",
    "praise": "v. | n.",
    "blame": "v. | n.",
    "punish": "v.",
    "forgive": "v.",
    "apologize": "v.",
    "thank": "v.",
    "welcome": "v. | adj. | n.",
    "greet": "v.",
    "introduce": "v.",
    "shake": "v. | n.",
    "wave": "v. | n.",
    "nod": "v. | n.",
    "bow": "v. | n.",
    "hug": "v. | n.",
    "kiss": "v. | n.",
    "carry": "v.",
    "lift": "v. | n.",
    "pick": "v. | n.",
    "select": "v.",
    "gather": "v.",
    "spread": "v. | n.",
    "cover": "v. | n.",
    "fill": "v.",
    "empty": "adj. | v.",
    "pour": "v.",
    "spill": "v. | n.",
    "mix": "v. | n.",
    "stir": "v.",
    "boil": "v. | n.",
    "bake": "v.",
    "roast": "v. | adj.",
    "fry": "v. | n.",
    "grill": "v. | n.",
    "freeze": "v.",
    "melt": "v.",
    "smoke": "n. | v.",
    "breathe": "v.",
    "cough": "v. | n.",
    "sneeze": "v. | n.",
    "bleed": "v.",
    "heal": "v.",
    "cure": "v. | n.",
    "treat": "v. | n.",
    "operate": "v.",
    "examine": "v.",
    "test": "v. | n.",
    "measure": "v. | n.",
    "weigh": "v.",
    "count": "v. | n.",
    "calculate": "v.",
    "add": "v.",
    "subtract": "v.",
    "multiply": "v.",
    "divide": "v.",
    "equal": "adj. | v.",
    "match": "v. | n.",
    "fit": "v. | adj.",
    "differ": "v.",
    "compare": "v.",
    "prefer": "v.",
    "always": "adv.",
    "usually": "adv.",
    "often": "adv.",
    "sometimes": "adv.",
    "seldom": "adv.",
    "never": "adv.",
    "ever": "adv.",
    "already": "adv.",
    "just": "adv. | adj.",
    "almost": "adv.",
    "nearly": "adv.",
    "quite": "adv.",
    "very": "adv.",
    "too": "adv.",
    "so": "adv. | conj.",
    "well": "adv. | adj. | n.",
    "fast": "adj. | adv.",
    "hard": "adj. | adv.",
    "late": "adj. | adv.",
    "early": "adj. | adv.",
    "here": "adv.",
    "there": "adv.",
    "away": "adv.",
    "out": "adv. | prep.",
    "in": "prep. | adv.",
    "on": "prep. | adv.",
    "at": "prep.",
    "by": "prep. | adv.",
    "with": "prep.",
    "without": "prep.",
    "about": "prep. | adv.",
    "for": "prep. | conj.",
    "from": "prep.",
    "to": "prep.",
    "into": "prep.",
    "onto": "prep.",
    "through": "prep. | adv.",
    "across": "prep. | adv.",
    "along": "prep. | adv.",
    "around": "prep. | adv.",
    "behind": "prep. | adv.",
    "between": "prep.",
    "among": "prep.",
    "above": "prep. | adv.",
    "below": "prep. | adv.",
    "over": "prep. | adv.",
    "under": "prep. | adv.",
    "near": "prep. | adj. | adv.",
    "far": "adj. | adv.",
    "next": "adj. | adv.",
    "since": "prep. | conj. | adv.",
    "until": "prep. | conj.",
    "till": "prep. | conj.",
    "during": "prep.",
    "because": "conj.",
    "although": "conj.",
    "though": "conj. | adv.",
    "if": "conj.",
    "whether": "conj.",
    "while": "conj. | n.",
    "when": "conj. | adv.",
    "as": "prep. | conj. | adv.",
    "and": "conj.",
    "but": "conj. | prep.",
    "or": "conj.",
    "nor": "conj.",
    "either": "conj. | adv. | adj.",
    "neither": "conj. | adv. | adj.",
    "both": "adj. | pron. | conj.",
    "all": "adj. | pron. | adv.",
    "each": "adj. | pron.",
    "every": "adj.",
    "any": "adj. | pron.",
    "some": "adj. | pron.",
    "none": "pron.",
    "many": "adj. | pron.",
    "much": "adj. | pron. | adv.",
    "few": "adj. | pron.",
    "little": "adj. | adv.",
    "more": "adj. | adv. | pron.",
    "most": "adj. | adv. | pron.",
    "less": "adj. | adv. | pron.",
    "least": "adj. | adv. | pron.",
    "good": "adj.",
    "bad": "adj.",
    "big": "adj.",
    "large": "adj.",
    "huge": "adj.",
    "tall": "adj.",
    "high": "adj. | adv.",
    "low": "adj. | adv.",
    "long": "adj. | adv.",
    "wide": "adj.",
    "narrow": "adj.",
    "deep": "adj. | adv.",
    "shallow": "adj.",
    "heavy": "adj.",
    "light": "adj. | n. | v.",
    "thick": "adj.",
    "bright": "adj.",
    "sunny": "adj.",
    "cloudy": "adj.",
    "rainy": "adj.",
    "snowy": "adj.",
    "windy": "adj.",
    "stormy": "adj.",
    "foggy": "adj.",
    "wet": "adj.",
    "dry": "adj. | v.",
    "dirty": "adj.",
    "neat": "adj.",
    "messy": "adj.",
    "happy": "adj.",
    "glad": "adj.",
    "sad": "adj.",
    "angry": "adj.",
    "mad": "adj.",
    "afraid": "adj.",
    "scared": "adj.",
    "proud": "adj.",
    "brave": "adj.",
    "shy": "adj.",
    "nervous": "adj.",
    "calm": "adj. | v.",
    "excited": "adj.",
    "exciting": "adj.",
    "bored": "adj.",
    "boring": "adj.",
    "tired": "adj.",
    "tiring": "adj.",
    "interested": "adj.",
    "interesting": "adj.",
    "surprised": "adj.",
    "surprising": "adj.",
    "worried": "adj.",
    "rich": "adj.",
    "poor": "adj.",
    "cheap": "adj.",
    "expensive": "adj.",
    "easy": "adj.",
    "difficult": "adj.",
    "simple": "adj.",
    "safe": "adj. | n.",
    "dangerous": "adj.",
    "healthy": "adj.",
    "sick": "adj.",
    "ill": "adj.",
    "strong": "adj.",
    "weak": "adj.",
    "smart": "adj.",
    "clever": "adj.",
    "wise": "adj.",
    "stupid": "adj.",
    "silly": "adj.",
    "foolish": "adj.",
    "kind": "adj. | n.",
    "nice": "adj.",
    "friendly": "adj.",
    "polite": "adj.",
    "rude": "adj.",
    "cruel": "adj.",
    "honest": "adj.",
    "true": "adj.",
    "false": "adj.",
    "right": "adj. | adv. | n.",
    "wrong": "adj. | adv.",
    "correct": "adj. | v.",
    "same": "adj. | pron.",
    "different": "adj.",
    "similar": "adj.",
    "special": "adj.",
    "common": "adj.",
    "ordinary": "adj.",
    "strange": "adj.",
    "famous": "adj.",
    "popular": "adj.",
    "important": "adj.",
    "necessary": "adj.",
    "possible": "adj.",
    "impossible": "adj.",
    "main": "adj.",
    "primary": "adj.",
    "final": "adj. | n.",
    "last": "adj. | adv. | v.",
    "first": "adj. | adv. | n.",
    "second": "adj. | n.",
    "third": "adj. | n.",
    "busy": "adj.",
    "free": "adj. | v.",
    "ready": "adj.",
    "sure": "adj. | adv.",
    "certain": "adj.",
    "clear": "adj. | v.",
    "full": "adj.",
    "sweet": "adj. | n.",
    "sour": "adj.",
    "bitter": "adj.",
    "salty": "adj.",
    "delicious": "adj.",
    "yummy": "adj.",
    "fresh": "adj.",
    "stale": "adj.",
    "loud": "adj. | adv.",
    "quiet": "adj.",
    "silent": "adj.",
    "quick": "adj. | adv.",
    "slow": "adj. | v.",
    "sharp": "adj.",
    "soft": "adj.",
    "smooth": "adj.",
    "rough": "adj.",
    "flat": "adj. | n.",
    "straight": "adj. | adv.",
    "round": "adj. | prep. | adv. | n.",
    "square": "adj. | n.",
    "red": "adj. | n.",
    "blue": "adj. | n.",
    "yellow": "adj. | n.",
    "green": "adj. | n.",
    "orange": "adj. | n.",
    "purple": "adj. | n.",
    "pink": "adj. | n.",
    "brown": "adj. | n.",
    "black": "adj. | n.",
    "white": "adj. | n.",
    "gray": "adj. | n.",
    "grey": "adj. | n.",
    "gold": "n. | adj.",
    "silver": "n. | adj.",
}

def clean_zh_and_extract_pos(zh_raw):
    """
    從中文欄位中提取可能附帶的中英文詞性標記，並傳回 (clean_zh, extracted_pos)
    例如:
      "[介系詞] 在…以後(之後)" -> ("在…以後(之後)", "prep.")
      "游泳 (v.)" -> ("游泳", "v.")
      "矮的 adj." -> ("矮的", "adj.")
    """
    if not zh_raw:
        return "", ""
    text = zh_raw.strip()
    extracted_pos = ""

    cn_pos_map = {
        "動詞": "v.",
        "名詞": "n.",
        "形容詞": "adj.",
        "副詞": "adv.",
        "介系詞": "prep.",
        "連接詞": "conj.",
        "代名詞": "pron.",
        "感嘆詞": "int.",
        "受格": "pron."
    }

    # 1. 偵測中文括號中的詞性標籤 [介系詞], (動詞) 等
    m_cn = re.search(r'\[([^\]]+)\]|\(([^)]+)\)', text)
    if m_cn:
        inner = (m_cn.group(1) or m_cn.group(2) or "").strip()
        for k, v in cn_pos_map.items():
            if k in inner:
                extracted_pos = v
                text = text[:m_cn.start()] + text[m_cn.end():]
                text = text.strip()
                break

    # 2. 偵測英文詞性標籤 (如 n., v., adj., adv., prep., conj., pron., 或其組合)
    m_en = re.search(r'([a-zA-Z]+\.?(?:\s*[\/\|]\s*[a-zA-Z]+\.?)?)', text)
    if m_en:
        candidate = m_en.group(1).strip()
        low_c = candidate.lower().rstrip('.')
        if any(low_c.startswith(prefix) for prefix in ['n', 'v', 'adj', 'adv', 'prep', 'conj', 'pron']):
            extracted_pos = candidate
            text = text[:m_en.start()] + text[m_en.end():]
            text = text.strip()

    # 清理殘留的空白括號
    text = re.sub(r'[\(\[\{]\s*[\)\]\}]', '', text).strip()
    return text.strip(), extracted_pos

def normalize_pos_string(pos_str):
    """將詞性字串規範化為標準形式，如 'n. | v.'"""
    if not pos_str:
        return ""
    parts = re.split(r'[\/\|\,]+', pos_str)
    valid_map = {
        "n": "n.", "noun": "n.",
        "v": "v.", "verb": "v.",
        "adj": "adj.", "adjective": "adj.", "a": "adj.",
        "adv": "adv.", "adverb": "adv.",
        "prep": "prep.", "preposition": "prep.",
        "conj": "conj.", "conjunction": "conj.",
        "pron": "pron.", "pronoun": "pron.",
        "int": "int.", "interjection": "int.",
        "aux": "aux. v.", "modal": "aux. v."
    }
    normalized = []
    for p in parts:
        clean_p = p.strip().lower().rstrip('.')
        if clean_p in valid_map:
            val = valid_map[clean_p]
            if val not in normalized:
                normalized.append(val)
        elif p.strip():
            token = p.strip()
            if not token.endswith('.'):
                token += '.'
            if token not in normalized:
                normalized.append(token)
    return " | ".join(normalized) if normalized else ""

def determine_junior_pos(word, zh_clean="", extracted_pos="", sd=None):
    """
    精準推斷國中單字之詞性 (pos)
    優先順序:
      1. Gemini 生成的明確 pos
      2. 使用者輸入中文欄位附帶的中英文詞性
      3. 國中常用核心字庫 JUNIOR_VOCAB_POS_MAP
      4. 從 forms / grammar / examPoint 關鍵字推斷
      5. 中文釋義特徵推斷 (如 '的' -> adj, '地' -> adv)
      6. 預設 'n.'
    """
    # 1. Gemini explicit pos
    if sd and isinstance(sd, dict):
        g_pos = sd.get("pos", "")
        norm_g = normalize_pos_string(g_pos)
        if norm_g:
            return norm_g

    # 2. Extracted pos from user input
    if extracted_pos:
        norm_ext = normalize_pos_string(extracted_pos)
        if norm_ext:
            return norm_ext

    # 3. Built-in vocabulary map
    clean_w = word.strip().lower()
    if clean_w in JUNIOR_VOCAB_POS_MAP:
        return JUNIOR_VOCAB_POS_MAP[clean_w]

    # 4. Text corpus analysis from forms / grammar / examPoint
    if sd and isinstance(sd, dict):
        text_corpus = f"{sd.get('forms', '')} {sd.get('examPoint', '')} {sd.get('grammar', '')}"
        has_v = "動詞三態" in text_corpus or "不及物動詞" in text_corpus or "及物動詞" in text_corpus or "現在分詞" in text_corpus
        has_n = "名詞複數" in text_corpus or "可數名詞" in text_corpus or "不可數名詞" in text_corpus
        has_adj = "比較級" in text_corpus or "形容詞" in text_corpus or "多音節複合形容詞" in text_corpus
        has_adv = "時間副詞" in text_corpus or "頻率副詞" in text_corpus or "次數副詞" in text_corpus or "副詞" in text_corpus
        has_prep = "介系詞" in text_corpus
        has_conj = "連接詞" in text_corpus

        if has_adj and has_n:
            return "adj. | n."
        elif has_adj and has_v:
            return "adj. | v."
        elif has_v and has_n:
            return "n. | v."
        elif has_prep and has_conj:
            return "prep. | conj."
        elif has_adv and has_conj:
            return "adv. | conj."
        elif has_v:
            return "v."
        elif has_adj:
            return "adj."
        elif has_adv:
            return "adv."
        elif has_prep:
            return "prep."
        elif has_conj:
            return "conj."

    # 5. Chinese heuristics
    if zh_clean:
        if zh_clean.endswith("的") or "……的" in zh_clean:
            return "adj."
        if zh_clean.endswith("地") or zh_clean in ["仍然", "然後", "尚未", "兩次", "很快地", "很久"]:
            return "adv."

    # 6. Default fallback
    return "n."

_FA_FREE_ICONS_SET = None

def get_fa_free_icons():
    global _FA_FREE_ICONS_SET
    if _FA_FREE_ICONS_SET is None:
        possible_paths = [
            Path(__file__).parent / "fa_free_icons.json",
            Path.cwd() / "fa_free_icons.json",
            BASE_DIR / "fa_free_icons.json"
        ]
        for p in possible_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _FA_FREE_ICONS_SET = set(json.load(f))
                        break
                except Exception:
                    pass
        if _FA_FREE_ICONS_SET is None:
            _FA_FREE_ICONS_SET = set()
    return _FA_FREE_ICONS_SET

def sanitize_icon(raw_icon, word=""):
    """確保圖示名稱為有效之 FontAwesome Free 圖示，避免網頁出現空白"""
    if not raw_icon:
        raw_icon = ""
    clean = str(raw_icon).strip()
    if clean.startswith("fa-solid "):
        clean = clean.replace("fa-solid ", "").strip()
    if clean.startswith("fa-regular "):
        clean = clean.replace("fa-regular ", "").strip()

    # 1. 先查別名字典
    if clean in ICON_ALIASES:
        return ICON_ALIASES[clean]
    
    full_name = clean if clean.startswith("fa-") else f"fa-{clean}"
    if full_name in ICON_ALIASES:
        return ICON_ALIASES[full_name]

    # 2. 檢查官方 FA Free 集合
    free_set = get_fa_free_icons()
    if free_set:
        if full_name in free_set:
            return full_name
    else:
        if full_name.startswith("fa-"):
            return full_name

    # 3. 根據常用關鍵字備援
    w = str(word).strip().lower()
    if w in ("big", "huge", "large"):
        return "fa-mountain"
    if w in ("new", "fresh", "bright"):
        return "fa-wand-magic-sparkles"
    if w in ("small", "tiny", "little"):
        return "fa-seedling"
    if w in ("happy", "glad"):
        return "fa-face-smile"
    if w in ("sad", "sorry"):
        return "fa-face-frown"

    # 4. 保底圖示
    return "fa-star"

def is_date_header_line(line):
    """
    精準判斷該列是否為日期 / 週次標題列，避免單字包含「日期」（如 date、calendar、schedule）或例句含「2026」時被誤判為標題。
    """
    clean = line.strip()
    if not clean:
        return False

    # 若以 Tab 或多空格切割後欄位數 >= 3，絕對是單字資料列，絕非標題列
    parts = clean.split("\t")
    if len(parts) < 2:
        parts = [p.strip() for p in re.split(r'\s{2,}', clean) if p.strip()]

    if len(parts) >= 3:
        return False

    # 若剛好 2 個欄位，檢查是否為「英文單字 \t 中文釋義」，若是則為單字資料
    if len(parts) == 2:
        if re.match(r'^[a-zA-Z\s\-]+$', parts[0]) and re.search(r'[\u4e00-\u9fa5]', parts[1]):
            return False

    # 正式標題列特徵判斷：
    # 1. 包含 [W09] 或 ［Ｗ09］ 格式之週次標籤
    if re.search(r'[\[［]\s*[WwＷｗ]0*\d+\s*[\]］]', clean):
        return True

    # 2. 開頭為明確的標題前綴：日期：、日期:、週次：、週次:、Week:、Date:
    if re.match(r'^(?:日期|週次|Week|Date)\s*[：:]', clean, re.IGNORECASE):
        return True

    # 3. 開頭為「日期」或「週次」且緊接著週次或日期數字
    if re.match(r'^(?:日期|週次)\s+[\[［]?[WwＷｗ]0*\d+', clean):
        return True

    # 4. 開頭為年份日期格式：如 2026/11/09 或 2026-11-09
    if re.match(r'^\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}', clean):
        return True

    # 5. 純週次代碼：如 W09 或 [W09]
    if re.match(r'^[\[［]?[WwＷｗ]0*\d+[\]］]?\s*$', clean):
        return True

    return False

def parse_input_words(raw_text):
    """
    解析使用者輸入的文字檔 (Tab/多空格分隔)，精準支援兩種欄位格式：
    格式 A (5欄位): 分類 \t 單字 \t 中文 \t 搭配詞 \t 例句
    格式 B (4欄位): 單字 \t 中文 \t 搭配詞 \t 例句 (\t 分類)
    同時自動過濾「欄位標題列」(如 分類\t單字\t中文\t搭配詞\t例句)
    """
    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    week_title = "[W01]"
    parsed_words = []
    header_found = False

    for line in lines:
        # 1. Date / Week Header Line (僅在尚未確認標題時提取，且嚴格檢驗避免誤判單字)
        if not header_found and is_date_header_line(line):
            m = re.search(r'([\[［]?[WwＷｗ]0*\d+[\]］]?\s*.*?\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\s*(?:\([一二三四五六日]\))?(?:\s*~\s*(?:\d{4}[\/\-])?\d{1,2}[\/\-]\d{1,2})?)', line)
            if m:
                raw_title = m.group(1).strip()
            else:
                m_simple = re.search(r'([\[［]?[WwＷｗ]0*\d+[\]］]?)', line)
                if m_simple:
                    raw_title = m_simple.group(1).strip()
                else:
                    raw_title = re.sub(r'^(?:日期|週次|Week|Date)\s*[：:\s]\s*', '', line).strip()
            
            # 自動標準化週次標籤：[W010] 或 ［Ｗ010］ 統一標準化為 [W10]
            week_title = re.sub(
                r'[\[［]?[WwＷｗ]0*(\d+)[\]］]?',
                lambda x: f"[W{int(x.group(1)):02d}]",
                raw_title
            ).strip()
            header_found = True
            continue

        # 2. Split line by Tab or multiple spaces
        parts = line.split("\t")
        if len(parts) < 2:
            parts = [p.strip() for p in re.split(r'\s{2,}', line) if p.strip()]

        if not parts or len(parts) < 2:
            continue

        col0 = parts[0].strip().lower()
        col1 = parts[1].strip().lower()

        # 3. 強效過濾表格欄位標題列
        header_keywords_col0 = ["分類", "單字", "word", "words", "vocab", "vocabulary", "單字名稱", "目標單字"]
        header_keywords_col1 = ["單字", "中文", "詞性", "中文/詞性", "meaning", "chinese", "pos", "詞性與中文", "中文對應", "詞性標籤"]

        if col0 in header_keywords_col0 or col1 in header_keywords_col1 or "單字清單" in line or "欄位標題" in line:
            print(f"ℹ️ 自動跳過表格欄位標題列: '{line}'")
            continue

        # 4. 自動偵測欄位排列 (Format A vs Format B)
        if len(parts) >= 3 and re.search(r'[a-zA-Z]', parts[1]) and not re.search(r'^[a-zA-Z\s\-]+$', parts[0]):
            category = parts[0].strip()
            word = parts[1].strip()
            pos_cn = parts[2].strip()
            collocation_str = parts[3].strip() if len(parts) > 3 else ""
            sentence_str = parts[4].strip() if len(parts) > 4 else ""
        else:
            category = parts[4].strip() if len(parts) > 4 else ""
            word = parts[0].strip()
            pos_cn = parts[1].strip()
            collocation_str = parts[2].strip() if len(parts) > 2 else ""
            sentence_str = parts[3].strip() if len(parts) > 3 else ""

        collocation = parse_collocation(collocation_str)
        sentence = parse_sentence(sentence_str)

        parsed_words.append({
            "word": word,
            "posChinese": pos_cn,
            "collocation": collocation,
            "sentence": sentence,
            "category": category
        })

    return week_title, parsed_words

def parse_collocation(col_str):
    if not col_str:
        return {"en": "", "cn": "", "extraEn": "", "extraCn": ""}

    items = [item.strip() for item in col_str.split("/") if item.strip()]
    res = {"en": "", "cn": "", "extraEn": "", "extraCn": ""}

    def parse_single(s):
        m = re.search(r'^(.*?)\s*[\(（](.*?)[\)）]\s*$', s)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        m2 = re.search(r'^([a-zA-Z\s\-]+)\s+([\u4e00-\u9fa5]+.*?)$', s)
        if m2:
            return m2.group(1).strip(), m2.group(2).strip()
        return s, ""

    if len(items) >= 1:
        en, cn = parse_single(items[0])
        res["en"] = en
        res["cn"] = cn
    if len(items) >= 2:
        extraEn, extraCn = parse_single(items[1])
        res["extraEn"] = extraEn
        res["extraCn"] = extraCn

    return res

def parse_sentence(sen_str):
    if not sen_str:
        return {"en": "", "cn": ""}
    m = re.search(r'^(.*?)\s*[\(（](.*?)[\)）]\s*$', sen_str)
    if m:
        return {"en": m.group(1).strip(), "cn": m.group(2).strip()}
    m2 = re.search(r'^([a-zA-Z0-9\s\,\.\!\?\'\-]+?)\s*([\u4e00-\u9fa5].*?)$', sen_str)
    if m2:
        return {"en": m2.group(1).strip(), "cn": m2.group(2).strip()}
    return {"en": sen_str, "cn": ""}

def build_lightweight_prompt(track_id, words_text):
    if track_id == "junior":
        return build_lightweight_prompt_junior(track_id, words_text)
    return build_lightweight_prompt_elem(track_id, words_text)

def build_lightweight_prompt_elem(track_id, words_text):
    week_title, parsed_words = parse_input_words(words_text)
    word_list_formatted = "\n".join([
        f"{idx+1}. {item['word']} ({item['posChinese']}) - 分類: {item['category'] or '未指定'}"
        for idx, item in enumerate(parsed_words)
    ])

    prompt = f"""你是一位精通兒童美語教學與單字卡設計的專家。請根據下方提供的一週單字清單，為每個單字設計 4 個創意學習欄位：
1. posChinese: 包含中文與英文詞性縮寫的對應標籤（例如 "樹 n."、"帽子 n."、"灰色的 adj."、"重的是 adj."，若原始資料未附詞性請補上 n./v./adj./adv. 標籤，請勿顯示 IPA 音標）。
2. category: 大分類名稱（請沿用單字清單中的分類，或對應歸納出的 week_tags 主題之一）。
3. icon: 最符合單字語意且適合國小生認知的 FontAwesome v6.4 (free) 圖示 class 名稱（必須使用 FontAwesome Free 免費圖示，如 "fa-mountain", "fa-wand-magic-sparkles", "fa-tree", "fa-sun"，切勿使用 Pro 圖示如 fa-sparkles, fa-elephant）。
4. badge: 4字以內的可愛情境徽章標籤（如 "綠意盎然", "保暖遮陽"）。
5. themeTag: 4字以內的主題標籤（如 "自然植物", "穿著配件"）。
6. tip: 20~45 字的「趣味聯想記憶法」，必須以 `💡 ` 開頭（包含燈泡 Emoji 與空格）。內容需親切可愛。

同時請根據單字分類歸納 3~4 個大分類主題標籤 (week_tags)。

【輸出格式規範】
請直接回傳乾淨的 JSON 格式（用 ```json 與 ``` 包覆）：
{{
  "week_tags": ["自然與天氣", "衣物與配件", "形容詞"],
  "enrichments": [
    {{
      "word": "tree",
      "posChinese": "樹 n.",
      "category": "自然與天氣",
      "icon": "fa-tree",
      "badge": "綠意盎然",
      "themeTag": "自然植物",
      "tip": "💡 tree 是挺拔的大樹，小鳥最喜歡在樹枝上蓋窩唱歌囉！"
    }}
  ]
}}

【單字清單】：
{word_list_formatted}

請勿輸出任何多餘的解釋文字。"""

    return prompt, week_title, parsed_words

def build_lightweight_prompt_junior(track_id, words_text):
    week_title, parsed_words = parse_input_words(words_text)
    word_list_formatted = "\n".join([
        f"{idx+1}. {item['word']} ({item['posChinese']}) - 例句: {item['sentence']['en']} ({item['sentence']['cn']})"
        for idx, item in enumerate(parsed_words)
    ])

    prompt = f"""你是一位專業的國中英文會考輔導專家。請根據下方提供的一週單字清單，以「國中教育會考核心重點」為基準，為每個單字生成 `supplementaryData` 會考補充庫：

請以每個單字為 key（如 "warm"），生成包含以下五個欄位的物件：
- pos（詞性縮寫）：請根據國中教育會考規範，精準標註該單字與中文意思對應的詞性縮寫（如 n., v., adj., adv., prep., conj., pron.）。若該單字在國中階段兼具兩種常見核心詞性（例如 tie 兼具名詞與動詞、clean 兼具形容詞與動詞、dark 兼具形容詞與名詞、swim 兼具動詞與名詞、after 兼具介系詞與連接詞），請用直線符號分隔，如 "n. | v."、"adj. | v."、"v. | n."、"prep. | conj."、"adv. | conj."。
- forms（變化 / 格位 / 形態）：詳細列出該字的所有三態變化、名複、比較級最高級、詞性衍生字（如動詞轉名詞/形容詞/副詞）、反義詞等。
- examPoint（🎯 會考常考要點）：鎖定台灣國中會考常見考點（例如：連綴動詞搭配、後置修飾、反義字語境辨析、易混淆字、閱讀測驗高頻慣用語、介系詞搭配等），標題統一格式為 【會考核心...考點】：1. ... 2. ...。
- phrases（常用片語）：列出 3~4 個該單字最常考的慣用語或動詞片語（需附中文）。
- grammar（文法補充說明）：1~2 句精闢的文法提醒（例如：及物/不及物用法、接動名詞或不定詞、發音重音位移規則等）。

同時請根據單字分類歸納 4 個封面主題標籤 (category_tags)，格式如 `"🏷️ 主題名稱 (N字)"`。

【輸出格式規範】
請直接回傳乾淨的 JSON 格式（用 ```json 與 ``` 包覆）：
{{
  "category_tags": [
    "🏷️ 氣候與溫度形容詞 (4字)",
    "🏷️ 代名詞與受格 (3字)",
    "🏷️ 道路景緻與幾何 (3字)"
  ],
  "supplementaryData": {{
    "warm": {{
      "pos": "adj. | v.",
      "forms": "比較級 warmer ➔ 最高級 warmest；名詞 warmth (溫暖)；動詞 warm up (熱身)",
      "examPoint": "【會考核心連綴動詞考點】：1. keep warm 句型中 keep 為連綴動詞，後接形容詞 warm... 2. ...",
      "phrases": "warm up (熱身/暖和起來) / warm heart (熱心)",
      "grammar": "作動詞時可指使體溫或場所變暖和。"
    }}
  }}
}}

【單字清單】：
{word_list_formatted}

請勿輸出任何多餘的解釋文字。"""

    return prompt, week_title, parsed_words

def extract_json_data(enrichment_json_str):
    """強效解析 JSON：相容 markdown 圍欄、開頭語言標籤 (JSON\n)、包含多餘 HTML 等雜訊"""
    if not enrichment_json_str:
        return None
    clean_str = str(enrichment_json_str).strip()

    # 1. 優先嘗試正規表達式提取 ```json ... ```
    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_str, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 2. 尋找第 1 個 '{' 或 '['，使用 raw_decode 提取第一個完整合法的 JSON 物件
    idx_b = clean_str.find('{')
    idx_bk = clean_str.find('[')
    start_idx = -1
    if idx_b != -1 and idx_bk != -1:
        start_idx = min(idx_b, idx_bk)
    elif idx_b != -1:
        start_idx = idx_b
    elif idx_bk != -1:
        start_idx = idx_bk

    if start_idx != -1:
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(clean_str, start_idx)
            if isinstance(obj, (dict, list)):
                return obj
        except Exception:
            pass

        # 3. 備用方案：若 raw_decode 失敗，嘗試切片
        end_idx = max(clean_str.rfind('}'), clean_str.rfind(']'))
        if end_idx > start_idx:
            sub = clean_str[start_idx:end_idx+1].strip()
            try:
                return json.loads(sub)
            except Exception:
                pass

    return None

def assemble_html(track_id, week_title, parsed_words, enrichment_json_str):
    if track_id == "junior":
        return assemble_html_junior(week_title, parsed_words, enrichment_json_str)
    return assemble_html_elem(week_title, parsed_words, enrichment_json_str)

def assemble_html_elem(week_title, parsed_words, enrichment_json_str):
    extracted_categories = list(dict.fromkeys([item["category"] for item in parsed_words if item["category"]]))
    week_tags = extracted_categories if extracted_categories else ["日常生活", "實用單字", "情境學習"]

    enrichments_dict = {}

    if enrichment_json_str:
        data = extract_json_data(enrichment_json_str)
        if isinstance(data, dict):
            if "week_tags" in data and isinstance(data["week_tags"], list) and data["week_tags"]:
                week_tags = data["week_tags"]
            items = data.get("enrichments") or data.get("vocab_data") or []
            for it in items:
                if isinstance(it, dict) and "word" in it:
                    w_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', it["word"]).strip().lower()
                    enrichments_dict[w_clean] = it
        elif isinstance(data, list):
            for it in data:
                if isinstance(it, dict) and "word" in it:
                    w_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', it["word"]).strip().lower()
                    enrichments_dict[w_clean] = it

    vocab_data = []
    for item in parsed_words:
        w_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', item["word"]).strip().lower()
        e = enrichments_dict.get(w_clean, {})

        icon_val = sanitize_icon(e.get("icon", ""), item["word"])

        pos_cn = e.get("posChinese") or item["posChinese"]
        if not re.search(r'[a-zA-Z]+\.?', pos_cn):
            clean_zh, ext_pos = clean_zh_and_extract_pos(pos_cn)
            elem_pos = ext_pos or JUNIOR_VOCAB_POS_MAP.get(item["word"].lower(), "n.")
            pos_cn = f"{clean_zh} {elem_pos}".strip()
        category_val = item.get("category") or e.get("category") or week_tags[0]

        vocab_entry = {
            "word": item["word"],
            "posChinese": pos_cn,
            "category": category_val,
            "collocation": item["collocation"],
            "sentence": item["sentence"],
            "icon": icon_val,
            "badge": e.get("badge", "單字學習"),
            "themeTag": e.get("themeTag", "日常應用"),
            "tip": e.get("tip") or f"💡 記住 {item['word']} 的意思，平時多練習使用喔！"
        }
        vocab_data.append(vocab_entry)

    template_path = get_template_path("elem")
    template_code = template_path.read_text(encoding="utf-8")

    w_match = re.search(r'[WwＷｗ]0*(\d+)', week_title)
    w_tag = f"W{int(w_match.group(1)):02d}" if w_match else "W01"

    template_code = re.sub(
        r'<title>.*?</title>',
        f'<title>2026 一起背單字 (國小組) - [{w_tag}]</title>',
        template_code
    )

    template_code = re.sub(
        r'\[W\d+\]\s*\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\s*~\s*(?:\d{4}[\/\-])?\d{1,2}[\/\-]\d{1,2}',
        week_title,
        template_code
    )

    week_tags_json = json.dumps(week_tags, ensure_ascii=False)
    template_code = re.sub(
        r'const\s+WEEK_TAGS\s*=\s*\[[\s\S]*?\];',
        f'const WEEK_TAGS = {week_tags_json};',
        template_code
    )

    vocab_data_json = json.dumps(vocab_data, ensure_ascii=False, indent=2)
    template_code = re.sub(
        r'const\s+VOCAB_DATA\s*=\s*\[[\s\S]*?\];',
        f'const VOCAB_DATA = {vocab_data_json};',
        template_code
    )

    return template_code

def assemble_html_junior(week_title, parsed_words, enrichment_json_str):
    category_tags = []
    supp_data = {}

    if enrichment_json_str:
        data = extract_json_data(enrichment_json_str)
        if isinstance(data, dict):
            category_tags = data.get("category_tags") or data.get("categoryTags") or []
            supp_data = data.get("supplementaryData") or data.get("supplementary_data") or {}

    if not category_tags:
        extracted = list(dict.fromkeys([w["category"] for w in parsed_words if w["category"]]))
        category_tags = [f"🏷️ {c}" for c in extracted] if extracted else ["🏷️ 會考核心單字", "🏷️ 實用單字庫"]

    week_num = 1
    w_match = re.search(r'[WwＷｗ]0*(\d+)', week_title)
    if w_match:
        week_num = int(w_match.group(1))

    # 1. 優先建立 supp_data_map，讓單字可對照 Gemini 生成資料 (含 pos 詞性)
    supp_data_map = {}
    if isinstance(supp_data, dict):
        for k, v in supp_data.items():
            if isinstance(v, dict):
                k_str = str(k).strip()
                k_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', k_str).lower()
                supp_data_map[k_str] = v
                supp_data_map[k_str.lower()] = v
                supp_data_map[k_clean] = v

    raw_words_data = []
    final_supp_data = {}

    for item in parsed_words:
        w = item["word"]
        w_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', w).strip().lower()
        w_lower = str(w).strip().lower()
        sd = (
            supp_data_map.get(w_clean)
            or supp_data_map.get(w_lower)
            or supp_data_map.get(w.strip())
            or (supp_data.get(w) if isinstance(supp_data, dict) else {})
            or {}
        )

        clean_zh, extracted_pos = clean_zh_and_extract_pos(item["posChinese"])
        pos_val = determine_junior_pos(w, zh_clean=clean_zh, extracted_pos=extracted_pos, sd=sd)

        collocation_str = ""
        if item["collocation"]["en"]:
            collocation_str = f"{item['collocation']['en']} ({item['collocation']['cn']})"
            if item["collocation"]["extraEn"]:
                collocation_str += f" / {item['collocation']['extraEn']} ({item['collocation']['extraCn']})"

        raw_words_data.append({
            "week": week_num,
            "day": 5,
            "word": item["word"],
            "zh": clean_zh or item["posChinese"],
            "pos": pos_val,
            "category": item["category"] or "國中核心單字",
            "collocations": collocation_str,
            "sentence": item["sentence"]["en"],
            "sentenceZh": item["sentence"]["cn"]
        })

        final_supp_data[w] = {
            "pos": pos_val,
            "forms": sd.get("forms") or f"三態 / 變化 / 衍生詞",
            "examPoint": sd.get("examPoint") or f"【會考核心考點】：1. 掌握 {w} 的核心語意與主要例句搭配；2. 注意標點與修飾位置。",
            "phrases": sd.get("phrases") or (item["collocation"]["en"] + f" ({item['collocation']['cn']})") if item["collocation"]["en"] else f"{w} 的常用片語",
            "grammar": sd.get("grammar") or f"注意 {w} 在句中的詞性與用法。"
        }

    template_path = get_template_path("junior")
    template_code = template_path.read_text(encoding="utf-8")

    w_tag = f"W{week_num:02d}"
    template_code = re.sub(
        r'<title>.*?</title>',
        f'<title>2026 一起背單字 (國中組) - [{w_tag}] {week_title}</title>',
        template_code
    )

    template_code = re.sub(
        r'📅\s*[^\n<]+',
        f'📅 {week_title}',
        template_code
    )

    tag_spans = "\n".join([
        f'              <span class="px-4 md:px-5 py-2 md:py-2.5 rounded-xl bg-amber-50 text-amber-700 text-base md:text-xl font-bold border border-amber-200 shadow-sm">{tag}</span>'
        for tag in category_tags
    ])
    template_code = re.sub(
        r'<div class="flex flex-wrap justify-center gap-3 md:gap-3\.5 max-w-xl">[\s\S]*?</div>',
        f'<div class="flex flex-wrap justify-center gap-3 md:gap-3.5 max-w-xl">\n{tag_spans}\n            </div>',
        template_code
    )

    raw_words_json = json.dumps(raw_words_data, ensure_ascii=False, indent=2)
    template_code = re.sub(
        r'const\s+rawWords\s*=\s*\[[\s\S]*?\];',
        f'const rawWords = {raw_words_json};',
        template_code
    )

    supp_data_json = json.dumps(final_supp_data, ensure_ascii=False, indent=2)
    template_code = re.sub(
        r'const\s+supplementaryData\s*=\s*\{[\s\S]*?\};',
        f'const supplementaryData = {supp_data_json};',
        template_code
    )

    return template_code

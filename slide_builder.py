import os
import json
import re
from pathlib import Path

BASE_DIR = Path(os.environ.get("VOCAB_PROJECT_DIR", Path(__file__).parent.resolve()))

def parse_input_words(raw_text):
    """
    解析使用者輸入的文字檔 (Tab/多空格分隔)，精準提取：
    - week_title (如 [W07]2026/10/13~10/20)
    - parsed_words_list (包含 word, posChinese, collocation, sentence, category)
    同時自動過濾「欄位標題列」(如 單字\t中文\t搭配詞\t例句)
    """
    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    week_title = "[W01]"
    parsed_words = []

    for line in lines:
        # 1. Date / Week Header Line
        if line.startswith("[") or "2026" in line or "日期" in line:
            m = re.search(r'(\[?W\d+\]?.*?\d{4}/\d{1,2}/\d{1,2}~\d{1,2}/\d{1,2})', line)
            if m:
                week_title = m.group(1)
            elif "[" in line:
                week_title = line
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
        header_keywords_col0 = ["單字", "word", "words", "vocab", "vocabulary", "單字名稱", "目標單字"]
        header_keywords_col1 = ["中文", "詞性", "中文/詞性", "meaning", "chinese", "pos", "詞性與中文", "中文對應", "詞性標籤"]
        
        if col0 in header_keywords_col0 or col1 in header_keywords_col1 or "單字清單" in line or "欄位標題" in line:
            print(f"ℹ️ 自動跳過表格欄位標題列: '{line}'")
            continue

        word = parts[0].strip()
        pos_cn = parts[1].strip()

        collocation_str = parts[2].strip() if len(parts) > 2 else ""
        collocation = parse_collocation(collocation_str)

        sentence_str = parts[3].strip() if len(parts) > 3 else ""
        sentence = parse_sentence(sentence_str)

        category = parts[4].strip() if len(parts) > 4 else ""

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
        # 格式1: "hot weather (熱天氣)" 或 "hot weather （熱天氣）"
        m = re.search(r'^(.*?)\s*[\(（](.*?)[\)）]\s*$', s)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        # 格式2: "hot weather 熱天氣"
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
    """
    根據輸入單字與組別，生成極簡輕量的 Gemini Prompt (僅請 Gemini 輸出 JSON)
    """
    week_title, parsed_words = parse_input_words(words_text)
    word_list_formatted = "\n".join([
        f"{idx+1}. {item['word']} ({item['posChinese']})"
        for idx, item in enumerate(parsed_words)
    ])

    prompt = f"""你是一位精通兒童美語教學與單字卡設計的專家。請根據下方提供的一週單字清單，為每個單字設計 4 個創意學習欄位：
1. posChinese: 包含中文與英文詞性縮寫的對應標籤（例如 "熱的 adj."、"女孩 n."、"游泳 v."、"陽光明媚的 adj."，請勿顯示 IPA 音標）。
2. category: 大分類名稱（必須對應歸納出的 week_tags 主題之一）。
3. icon: 最符合單字語意且適合國小生認知的 FontAwesome v6.4 (free) 圖示 class 名稱（只需寫名稱本身，不要包含 `fa-solid` 前綴，如 "fa-sun", "fa-wind", "fa-cloud-showers-heavy"）。
4. badge: 4字以內的可愛情境徽章標籤（如 "烈日炎炎", "雨水濕潤"）。
5. themeTag: 4字以內的主題標籤（如 "夏日氣候", "自然微風"）。
6. tip: 20~45 字的「趣味聯想記憶法」，必須以 `💡 ` 開頭（包含燈泡 Emoji 與空格）。內容需親切可愛。

同時請根據單字分類歸納 3~4 個大分類主題標籤 (week_tags)。

【輸出格式規範】
請直接回傳乾淨的 JSON 格式（用 ```json 與 ``` 包覆）：
{{
  "week_tags": ["自然與天氣", "衣物與配件", "形容詞"],
  "enrichments": [
    {{
      "word": "hot",
      "posChinese": "熱的 adj.",
      "category": "自然與天氣",
      "icon": "fa-sun",
      "badge": "烈日炎炎",
      "themeTag": "夏日氣候",
      "tip": "💡 天氣好 hot 時要多補充水分，去游泳池玩水最消暑了！"
    }}
  ]
}}

【單字清單】：
{word_list_formatted}

請勿輸出任何多餘的解釋文字。"""

    return prompt, week_title, parsed_words

def assemble_html(track_id, week_title, parsed_words, enrichment_json_str):
    """
    將使用者解析的單字資料與 Gemini 回傳的 JSON 創意欄位縫合，並塞入本機 HTML 範本中
    """
    # 1. 解析 Gemini 回傳的 JSON
    week_tags = ["日常生活", "實用單字", "情境學習"]
    enrichments_dict = {}

    if enrichment_json_str:
        try:
            clean_str = enrichment_json_str.strip()
            m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_str, re.IGNORECASE)
            if m:
                clean_str = m.group(1).strip()
            
            data = json.loads(clean_str)
            if isinstance(data, dict):
                if "week_tags" in data and isinstance(data["week_tags"], list):
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
        except Exception as e:
            print(f"⚠️ 解析 Gemini JSON 提示: {e}")

    # 2. 縫合 VOCAB_DATA
    vocab_data = []
    for item in parsed_words:
        w_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', item["word"]).strip().lower()
        e = enrichments_dict.get(w_clean, {})

        icon_val = e.get("icon", "fa-star")
        if icon_val.startswith("fa-solid "):
            icon_val = icon_val.replace("fa-solid ", "")

        pos_cn = e.get("posChinese") or item["posChinese"]

        category_val = e.get("category") or item.get("category") or week_tags[0]

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

    # 3. 讀取本機 HTML 樣板
    folder_name = "elem" if track_id == "elem" else "junior"
    possible_roots = [
        Path(os.environ.get("VOCAB_PROJECT_DIR", "")),
        Path(__file__).parent.resolve(),
        BASE_DIR,
        Path.cwd()
    ]

    template_path = None
    for root in possible_roots:
        if not root or not root.exists():
            continue
        candidate_folder = root / folder_name
        if candidate_folder.exists():
            pref_file = candidate_folder / ("2026_ew03.html" if track_id == "elem" else "2026_w05d5.html")
            if pref_file.exists():
                template_path = pref_file
                break
            html_files = sorted(list(candidate_folder.glob("*.html")))
            if html_files:
                template_path = html_files[-1]
                break

    if not template_path or not template_path.exists():
        raise FileNotFoundError(f"找不到 {folder_name}/ 目錄下的 HTML 範本檔案。")

    template_code = template_path.read_text(encoding="utf-8")

    # 4. 替換 HTML 內容
    week_tag_match = re.search(r'\[?(W\d+)\]?', week_title)
    w_tag = week_tag_match.group(1).upper() if week_tag_match else "W01"

    template_code = re.sub(
        r'<title>.*?</title>',
        f'<title>2026 一起背單字 (國小組) - [{w_tag}]</title>',
        template_code
    )

    template_code = re.sub(
        r'\[W\d+\]\d{4}/\d{2}/\d{2}~\d{2}/\d{2}',
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

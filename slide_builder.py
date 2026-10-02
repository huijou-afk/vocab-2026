import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

def parse_input_words(raw_text):
    """
    解析使用者輸入的文字檔 (Tab/多空格分隔)，精準提取：
    - week_title (如 [W07]2026/10/13~10/20)
    - parsed_words_list (包含 word, posChinese, collocation, sentence, category)
    """
    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    week_title = "[W01]"
    parsed_words = []

    for line in lines:
        if line.startswith("[") or "2026" in line or "日期" in line:
            m = re.search(r'(\[?W\d+\]?.*?\d{4}/\d{1,2}/\d{1,2}~\d{1,2}/\d{1,2})', line)
            if m:
                week_title = m.group(1)
            elif "[" in line:
                week_title = line
            continue

        if line.startswith("單字清單") or line.startswith("word\t"):
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            parts = [p.strip() for p in re.split(r'\s{2,}', line) if p.strip()]

        if not parts or len(parts) < 2:
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
        m = re.search(r'^(.*?)\s*[\(（](.*?)[\)）]\s*$', s)
        if m:
            return m.group(1).strip(), m.group(2).strip()
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
1. icon: 最符合單字語意且適合國小生認知的 FontAwesome v6.4 (free) 圖示 class 名稱（只需寫名稱本身，不要包含 `fa-solid` 前綴，如 "fa-sun", "fa-wind", "fa-cloud-showers-heavy"）。
2. badge: 4字以內的可愛情境徽章標籤（如 "烈日炎炎", "雨水濕潤"）。
3. themeTag: 4字以內的主題標籤（如 "夏日氣候", "自然微風"）。
4. tip: 20~45 字的「趣味聯想記憶法」，必須以 `💡 ` 開頭（包含燈泡 Emoji 與空格）。內容需親切可愛。

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
    將使用者解析的單字資料與 Gemini 回傳的 JSON 4個創意欄位縫合，並塞入本機 HTML 範本中
    """
    # 1. 解析 Gemini 回傳的 JSON
    week_tags = ["日常生活", "實用單字", "情境學習"]
    enrichments_dict = {}

    if enrichment_json_str:
        try:
            # 清理 markdown codeblock 標籤
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
                        enrichments_dict[it["word"].strip().lower()] = it
            elif isinstance(data, list):
                for it in data:
                    if isinstance(it, dict) and "word" in it:
                        enrichments_dict[it["word"].strip().lower()] = it
        except Exception as e:
            print(f"⚠️ 解析 Gemini JSON 提示: {e}")

    # 2. 縫合 VOCAB_DATA
    vocab_data = []
    for item in parsed_words:
        w_key = item["word"].strip().lower()
        e = enrichments_dict.get(w_key, {})

        icon_val = e.get("icon", "fa-star")
        if icon_val.startswith("fa-solid "):
            icon_val = icon_val.replace("fa-solid ", "")

        pos_cn = e.get("posChinese", item["posChinese"])
        if not re.search(r'\b(adj|n|v|adv|prep|conj|pron)\b', pos_cn, re.I):
            # 如果 posChinese 沒有詞性標記，嘗試從單字原始詞性補上
            pass

        vocab_entry = {
            "word": item["word"],
            "posChinese": pos_cn,
            "category": e.get("category") or item.get("category") or week_tags[0],
            "collocation": item["collocation"],
            "sentence": item["sentence"],
            "icon": icon_val,
            "badge": e.get("badge", "單字學習"),
            "themeTag": e.get("themeTag", "日常應用"),
            "tip": e.get("tip") or f"💡 記住 {item['word']} 的意思，平時多練習使用喔！"
        }
        vocab_data.append(vocab_entry)

    # 3. 讀取本機 HTML 樣板
    template_path = BASE_DIR / "elem" / "2026_ew03.html"
    if track_id == "junior":
        # 如果國中組有預設範本，也可以在此處理
        template_path = BASE_DIR / "junior" / "2026_w05d5.html"

    if not template_path.exists():
        template_path = BASE_DIR / "elem" / "2026_ew03.html"

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

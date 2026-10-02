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

    for line in lines:
        # 1. Date / Week Header Line
        if line.startswith("[") or "2026" in line or "日期" in line or "週次" in line:
            m = re.search(r'(\[?W\d+\]?.*?\d{4}/\d{1,2}/\d{1,2}(?:\([一二三四五六日]\))?~?\d{0,4}/?\d{1,2}/?\d{1,2})', line)
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
3. icon: 最符合單字語意且適合國小生認知的 FontAwesome v6.4 (free) 圖示 class 名稱（只需寫名稱本身，不要包含 `fa-solid` 前綴，如 "fa-tree", "fa-hat-cowboy", "fa-shirt"）。
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

請以每個單字為 key（如 "warm"），生成包含以下四個欄位的物件：
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

def assemble_html(track_id, week_title, parsed_words, enrichment_json_str):
    if track_id == "junior":
        return assemble_html_junior(week_title, parsed_words, enrichment_json_str)
    return assemble_html_elem(week_title, parsed_words, enrichment_json_str)

def assemble_html_elem(week_title, parsed_words, enrichment_json_str):
    extracted_categories = list(dict.fromkeys([item["category"] for item in parsed_words if item["category"]]))
    week_tags = extracted_categories if extracted_categories else ["日常生活", "實用單字", "情境學習"]

    enrichments_dict = {}

    if enrichment_json_str:
        try:
            clean_str = enrichment_json_str.strip()
            m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_str, re.IGNORECASE)
            if m:
                clean_str = m.group(1).strip()
            
            data = json.loads(clean_str)
            if isinstance(data, dict):
                if "week_tags" in data and isinstance(data["week_tags"], list) and not extracted_categories:
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

    vocab_data = []
    for item in parsed_words:
        w_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', item["word"]).strip().lower()
        e = enrichments_dict.get(w_clean, {})

        icon_val = e.get("icon", "fa-star")
        if icon_val.startswith("fa-solid "):
            icon_val = icon_val.replace("fa-solid ", "")

        pos_cn = e.get("posChinese") or item["posChinese"]
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

def assemble_html_junior(week_title, parsed_words, enrichment_json_str):
    category_tags = []
    supp_data = {}

    if enrichment_json_str:
        try:
            clean_str = enrichment_json_str.strip()
            m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_str, re.IGNORECASE)
            if m:
                clean_str = m.group(1).strip()
            data = json.loads(clean_str)
            if isinstance(data, dict):
                category_tags = data.get("category_tags") or data.get("categoryTags") or []
                supp_data = data.get("supplementaryData") or data.get("supplementary_data") or {}
        except Exception as e:
            print(f"⚠️ 解析 Junior Gemini JSON 提示: {e}")

    if not category_tags:
        extracted = list(dict.fromkeys([w["category"] for w in parsed_words if w["category"]]))
        category_tags = [f"🏷️ {c}" for c in extracted] if extracted else ["🏷️ 會考核心單字", "🏷️ 實用單字庫"]

    week_num = 1
    w_match = re.search(r'W(\d+)', week_title, re.I)
    if w_match:
        week_num = int(w_match.group(1))

    raw_words_data = []
    for item in parsed_words:
        pos_val = "n."
        zh_text = item["posChinese"]
        pos_match = re.search(r'([a-zA-Z]+\.?(?:\s*\|\s*[a-zA-Z]+\.?)?)', zh_text)
        if pos_match:
            pos_val = pos_match.group(1).strip()
            zh_text = re.sub(r'[a-zA-Z]+\.?(?:\s*\|\s*[a-zA-Z]+\.?)?', '', zh_text).strip()

        collocation_str = ""
        if item["collocation"]["en"]:
            collocation_str = f"{item['collocation']['en']} ({item['collocation']['cn']})"
            if item["collocation"]["extraEn"]:
                collocation_str += f" / {item['collocation']['extraEn']} ({item['collocation']['extraCn']})"

        raw_words_data.append({
            "week": week_num,
            "day": 5,
            "word": item["word"],
            "zh": zh_text or item["posChinese"],
            "pos": pos_val,
            "category": item["category"] or "國中核心單字",
            "collocations": collocation_str,
            "sentence": item["sentence"]["en"],
            "sentenceZh": item["sentence"]["cn"]
        })

    supp_data_map = {}
    if isinstance(supp_data, dict):
        for k, v in supp_data.items():
            if isinstance(v, dict):
                k_str = str(k).strip()
                k_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', k_str).lower()
                supp_data_map[k_str] = v
                supp_data_map[k_str.lower()] = v
                supp_data_map[k_clean] = v

    final_supp_data = {}
    for item in parsed_words:
        w = item["word"]
        w_clean = re.sub(r'[^a-zA-Z0-9\s\-]', '', w).strip().lower()
        w_lower = str(w).strip().lower()
        sd = (
            supp_data_map.get(w_clean)
            or supp_data_map.get(w_lower)
            or supp_data_map.get(w.strip())
            or supp_data.get(w)
            or {}
        )
        final_supp_data[w] = {
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
        r'📅\s*\[W\d+\][^\n<]+',
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

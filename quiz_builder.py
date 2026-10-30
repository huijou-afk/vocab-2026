import re
from datetime import datetime
from pathlib import Path
from slide_builder import parse_input_words

def get_quiz_filename(text, custom_fn=None):
    """
    根據使用者輸入的國中單字資料標題或投影片檔名，推算 Blooket 考題檔名 (如 W08-5.csv)
    週一: WXX-1.csv, 週二: WXX-2.csv, ..., 週五: WXX-5.csv
    """
    # 0. 先看 custom_fn (例如 2026_w08d5, W08-5 等)
    if custom_fn:
        m_fn = re.search(r'[Ww](\d+)[-_]?[dD]?(\d)', str(custom_fn))
        if m_fn:
            return f"W{int(m_fn.group(1)):02d}-{int(m_fn.group(2))}.csv"

    week_str = "W01"
    day_num = 1

    if not text:
        return f"{week_str}-{day_num}.csv"

    # 1. 解析週次 [W08] -> W08
    m_w = re.search(r'[\[［]?[WwＷｗ]0*(\d+)[\]］]?', text)
    if m_w:
        week_str = f"W{int(m_w.group(1)):02d}"

    # 2. 解析星期幾 (一) ~ (日)
    w_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7, '天': 7}
    m_day = re.search(r'\(([\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u65e5天])\)', text)
    if m_day and m_day.group(1) in w_map:
        day_num = w_map[m_day.group(1)]
    else:
        # 若未直接標註星期，嘗試依日期 YYYY/MM/DD 計算星期
        m_date = re.search(r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})', text)
        if m_date:
            try:
                y, m, d = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
                day_num = datetime(y, m, d).isoweekday()
            except Exception:
                day_num = 1

    return f"{week_str}-{day_num}.csv"

def build_blooket_quiz_prompt(raw_text, filename=None):
    """
    根據國中單字資料組裝發送至 Gemini 新對話的 50 題 Blooket 考題 Prompt
    """
    if not filename:
        filename = get_quiz_filename(raw_text)
    week_title, parsed_words = parse_input_words(raw_text)

    # 格式化 10 個單字列表：單字 中文 搭配詞 例句
    formatted_word_lines = []
    for item in parsed_words:
        w = item.get("word", "").strip()
        cn = item.get("posChinese", "").strip()
        
        # 搭配詞字串
        col = item.get("collocation", {})
        col_parts = []
        if col.get("en") and col.get("cn"):
            col_parts.append(f"{col['en']} ({col['cn']})")
        if col.get("extraEn") and col.get("extraCn"):
            col_parts.append(f"{col['extraEn']} ({col['extraCn']})")
        col_str = " / ".join(col_parts) if col_parts else ""

        # 例句字串
        sen = item.get("sentence", {})
        sen_str = ""
        if sen.get("en"):
            if sen.get("cn"):
                sen_str = f"{sen['en']} ({sen['cn']})"
            else:
                sen_str = sen['en']

        line_str = f"{w}\t{cn}\t{col_str}\t{sen_str}".strip()
        formatted_word_lines.append(line_str)

    words_block = "\n".join(formatted_word_lines)

    prompt = f"""你是一位專業的國中英語教材設計師。我會提供 10 個英文單字、中文意思、搭配詞、例句。請根據這些單字，嚴格遵守以下規則產出csv表格（檔名：{filename})。

{words_block}

**規則：**
1. 請建立一個 50 題的表格，第一列第一欄為："Blooket Import Template"（注意："Blooket Import Template" 必須在同一列，切勿換行），其他欄位空白，即第一列完整內容固定為：`"Blooket Import Template",,,,,,,`。第二列欄位標題為：`Question #,Question Text,Answer 1,Answer 2,Answer 3,Answer 4,Time Limit (sec),Correct Answer(s)`
2. **所有題目的設定：** `Time Limit (sec)` 設為 **20**，`Correct Answer(s)` 設為 **1**（代表 Answer 1 永遠是正確答案），`Answer 4` 設為空白。
3. **題號 1-10 (英翻中)：**
   - Question Text: [英文單字]
   - Answer 1: [正確中文]
   - Answer 2 & 3: [從這10個單字中隨機挑選的其他錯誤中文]
4. **題號 11-20 (中翻英)：**
   - Question Text: [中文意思]
   - Answer 1: [正確英文單字]
   - Answer 2 & 3: [從這10個單字中隨機挑選的其他錯誤英文單字]
5. **題號 21-30 (聽力題)：**
   - Question Text: 固定為 "Find the correct answer 下面哪一個正確？"
   - Answer 1: [依序放入這10個英文單字]
   - Answer 2 & 3: [從這10個單字中隨機挑選的其他錯誤英文單字]
6. **題號 31-40 (例句填空)：**
   - 來源：例句內容產生考題。
   - Question Text: 將例句中的目標單字挖空變成 ______，並在題目下方附上完整中文翻譯（包含空格處）。
   範例：______like to read books in my free time. (______喜歡在空閒時間看書。)
   - Answer 1: [正確的目標英文單字]
   - Answer 2 & 3 (關鍵規則): **必須使用語意完全錯誤、邏輯不通的國中會考單字** (例如: Saturday, mother, enough ...)。
     - **絕對禁止**考文法 (如單複數變化或詞性)。
     - **優先使用**列表單字。
     - **允許使用**若列表單字皆可為答案，則允許使用列表以外的其他單字。
     - 選項中**不要**出現中文。
     - 範例: 若題目是 "The ____ is blue." (正解 ink)，錯誤選項請給 "banana", "pig" (明顯不是藍色的東西)。
7. **題號 41-50 (搭配詞考題)：**
   - 來源：根據提供的單字與搭配詞設計語意情境例句。
   - Question Text: 將例句中的目標搭配詞或單字挖空變成 ______，並在題目下方附上完整中文翻譯（包含空格處）。

   範例： The sky is getting dark, and ______ that it doesn't rain before we get home.（天色越來越暗了，______在我們到家前不要下雨。）
   - Answer 1: [正確的目標搭配詞]
   - Answer 2 & 3 (關鍵規則): **必須使用語意完全錯誤、邏輯不通的國中會考單字** (例如: Saturday, mother, enough ...)。
     - 必須使用語意完全錯誤、邏輯不通的國中會考單字或詞組。
     - 選項中絕對禁止出現中文，僅保留純英文選項。
     - 絕對禁止考純文法陷阱（如單複數、時態變化或同義近義詞辨析），重點在於語意邏輯是否合理。
     - 優先使用提供的列表單字/搭配詞作為干擾項；若列表單字放入後語意依然通順，則允許使用列表外的其他基礎國中英文單字（如：banana、Saturday、kitchen）。
     - 範例： 若目標為 natural beauty（自然美景），錯誤選項請給 beauty salon (美容院)、group work (分組合作) 或 kitchen table 等在該情境下明顯荒謬、不合邏輯的選項。

在產生題號 31-50 的干擾選項（Answer 2 與 Answer 3）時，必須從更廣泛的國中基礎單字庫中輪流抽樣，絕對禁止在多道題目中重複使用相同的錯誤選項，確保每題的干擾項具備高度獨立性與語意干擾效果。

【重要輸出規範】：
請將完整的 CSV 表格內容直接在對話框中用 ```csv 與 ``` 代碼區塊包覆輸出，請勿開啟或使用 Canvas 模式，亦請勿輸出任何多餘的解釋文字。請開始生成。"""

    return prompt, parsed_words

def clean_blooket_csv(raw_csv_text):
    """
    清洗 Gemini 輸出的 CSV 字串
    確保第一列為 "Blooket Import Template",,,,,,,
    第二列為 Question #,Question Text,Answer 1,Answer 2,Answer 3,Answer 4,Time Limit (sec),Correct Answer(s)
    """
    if not raw_csv_text:
        return ""

    text = raw_csv_text.strip()

    # 1. 提取 ```csv ... ``` 代碼區塊
    m = re.search(r'```(?:csv)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
    if m:
        text = m.group(1).strip()
    elif text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 2. 移除任何已存在的 BOM，由存檔時統一指定 utf-8-sig 輸出
    text = text.lstrip("\ufeff").strip()

    # 3. 尋找 Question # 標題行，確保前兩列結構 100% 正確
    m_header = re.search(r'Question\s*#\s*,\s*Question\s*Text', text, re.IGNORECASE)
    if m_header:
        text = '"Blooket Import Template",,,,,,,\n' + text[m_header.start():]
    else:
        # 若未找到 Question #，但有 Blooket 開頭，進行修復
        m_blooket = re.search(r'Blooket[\s\S]*?Import\s*Template[^\n]*\n', text, re.IGNORECASE)
        if m_blooket:
            text = '"Blooket Import Template",,,,,,,\n' + text[m_blooket.end():]

    # 4. 驗證基本結構
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 10:
        return ""

    return text

import json
import os
from datetime import datetime
from email.utils import parsedate_to_datetime

# ==========================================
# 파일 경로 설정
# ==========================================
INPUT_FILE = 'japanese_news.json'
OUTPUT_FILE = 'japanese_news_fixed.json'
# ==========================================

def fix_date_format(date_str):
    if not date_str:
        return datetime.now().astimezone().isoformat()
    
    # 1. RFC 1123 형식 처리 (예: Fri, 19 Dec 2025 16:50:00 +0900)
    if ',' in date_str:
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.isoformat()
        except:
            pass

    # 2. 일반 공백 형식 처리 (예: 2025-12-19 16:31:35) -> 이번 에러의 원인
    if ' ' in date_str and 'T' not in date_str:
        try:
            # 공백을 T로 바꾸고 기본 시간대(+09:00)를 붙여줌
            clean_date = date_str.replace(' ', 'T')
            if '+' not in clean_date and 'Z' not in clean_date:
                clean_date += "+09:00"
            return clean_date
        except:
            pass

    # 3. 이미 올바른 형식인 경우 또는 기타
    return date_str

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"파일을 찾을 수 없습니다: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'articles' in data:
        for article in data['articles']:
            old_date = article.get('publishedAt', '')
            new_date = fix_date_format(old_date)
            article['publishedAt'] = new_date
            
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 변환 완료: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
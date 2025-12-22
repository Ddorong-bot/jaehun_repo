import json
import os
from datetime import datetime
from email.utils import parsedate_to_datetime

# 파일 경로 설정
INPUT_FILE = 'japanese_news_fixed.json'
OUTPUT_FILE = 'japanese_news_final_v3.json'

def final_fix_v3(article):
    # 1. 날짜 형식 최종 교정 (ISO 8601)
    date_str = article.get('publishedAt', '')
    try:
        if ',' in date_str: # RFC 1123 (Fri, 19 Dec...)
            article['publishedAt'] = parsedate_to_datetime(date_str).isoformat()
        elif ' ' in date_str and 'T' not in date_str: # 공백 형식 (2025-12-19 16:31:35)
            article['publishedAt'] = date_str.replace(' ', 'T') + "+09:00"
    except:
        article['publishedAt'] = datetime.now().astimezone().isoformat()

    # 2. 카테고리 수정 (첫 글자만 대문자: Politics, Economy, Tech, Others)
    raw_category = article.get('categoryCode', 'others')
    # capitalize()는 첫 글자만 대문자로, 나머지는 소문자로 만듭니다.
    article['categoryCode'] = raw_category.capitalize() 
    
    return article

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"파일을 찾을 수 없습니다: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'articles' in data:
        print(f"총 {len(data['articles'])}건 데이터 수정 중 (Politics 형식)...")
        data['articles'] = [final_fix_v3(a) for a in data['articles']]
            
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 수정 완료: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
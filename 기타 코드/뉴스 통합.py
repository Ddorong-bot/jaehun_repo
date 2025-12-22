import pandas as pd
import feedparser
import os
import re
import json
import time
import hashlib
import requests
import unicodedata
import google.generativeai as genai
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from newspaper import Article, Config

# ==========================================
# [사용자 설정] 환경에 맞게 수정하세요
# ==========================================
# 1. 파일 경로
INPUT_EXCEL_FILENAME = "C:/Users/Choi/Desktop/일본 rss.xlsx"  # 언론사, RSS주소 컬럼 필요
OUTPUT_JSON_FILENAME = "C:/Users/Choi/Desktop/일본_뉴스_최종결과.json"

# 2. Gemini API 키
GEMINI_API_KEY = ""  # 여기에 API 키를 입력하세요

# 3. 수집 설정
DAYS_LIMIT = 1  # 며칠 전 뉴스까지 수집할지
SOURCE_TYPE = "RSS"  # 서버에 보낼 sourceType (대문자 권장)

# 4. 필터링 키워드 (해외/국제 뉴스 제외)
EXCLUDE_KEYWORDS = ['world', 'global', 'international', 'overseas', 'foreign', '국제', '해외', 'english']

# 5. 본문 제거 문구
GARBAGE_PHRASES = [
    "We use cookies", "cookie policy", "Accept all", "Manage preferences",
    "This website uses cookies", "All rights reserved", "로그인이 필요합니다",
    "무단 전재 및 재배포 금지", "기자 구독"
]
# ==========================================

# Gemini 설정
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('models/gemini-2.0-flash')
else:
    print("⚠️ 경고: GEMINI_API_KEY가 설정되지 않았습니다. 분류 기능이 작동하지 않을 수 있습니다.")
    model = None

def clean_html(raw_html):
    """HTML 태그 제거"""
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def normalize_text(text: str) -> str:
    """텍스트 정규화 (해시용)"""
    if not text: return ""
    text = str(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text

def compute_content_hash(title: str, content: str) -> str:
    """SHA-256 해시 생성"""
    payload = f"{normalize_text(title)}\n{normalize_text(content)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def normalize_date(date_str):
    """
    날짜를 ISO 8601 형식(YYYY-MM-DDTHH:mm:ss+HH:MM)으로 통일
    서버 400 에러 방지용 핵심 함수
    """
    if not date_str:
        return datetime.now().astimezone().isoformat()
    
    try:
        # 1. 이미 ISO 형식인 경우
        datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_str
    except ValueError:
        pass

    try:
        # 2. RSS/이메일 형식 (Fri, 19 Dec 2025...)
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        pass
    
    # 3. 파싱 실패 시 현재 시간 반환 (데이터 누락 방지)
    return datetime.now().astimezone().isoformat()

def classify_text_with_ai(title, content):
    """Gemini를 이용한 카테고리 분류"""
    if not model: return "others"
    
    summary_text = f"Title: {title}\nContent: {str(content)[:500]}"
    prompt = f"""
    Analyze the news article and classify into exactly one: [Politics, Economy, Tech, Others].
    Output ONLY the category name.
    Article: {summary_text}
    """
    
    for _ in range(2): # 재시도 로직
        try:
            response = model.generate_content(prompt)
            cat = response.text.strip().replace("'", "").replace('"', "").lower()
            if 'politics' in cat: return 'politics'
            if 'economy' in cat: return 'economy'
            if 'tech' in cat: return 'tech'
            return 'others'
        except:
            time.sleep(1)
    return "others"

def is_foreign_news(entry):
    """해외 뉴스 필터링"""
    link = entry.get('link', '').lower()
    title = entry.get('title', '').lower()
    for kw in EXCLUDE_KEYWORDS:
        if f'/{kw}/' in link or f'/{kw}.' in link or kw in title:
            return True
    if 'tags' in entry:
        for tag in entry.tags:
            if any(kw in tag.get('term', '').lower() for kw in EXCLUDE_KEYWORDS):
                return True
    return False

def get_full_article(url):
    """Newspaper3k + BeautifulSoup 하이브리드 수집"""
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1)'}
    try:
        # 1. Newspaper3k
        config = Config()
        config.browser_user_agent = headers['User-Agent']
        config.request_timeout = 10
        config.fetch_images = False
        
        article = Article(url, config=config)
        article.download()
        article.parse()
        content = article.text.strip()

        # 2. 내용이 너무 짧으면 BS4로 강제 수집
        if len(content) < 200:
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.content, 'html.parser')
            paras = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
            forced_content = '\n\n'.join(paras)
            if len(forced_content) > len(content):
                content = forced_content

        # 3. 정제
        lines = [line for line in content.split('\n') if not any(g in line for g in GARBAGE_PHRASES)]
        return '\n'.join(lines)
    except:
        return ""

def main():
    if not os.path.exists(INPUT_EXCEL_FILENAME):
        print(f"❌ 오류: 입력 파일('{INPUT_EXCEL_FILENAME}')이 없습니다.")
        return

    print(">>> 뉴스 수집 및 처리 시작...")
    df_urls = pd.read_excel(INPUT_EXCEL_FILENAME)
    
    cutoff_date = datetime.now() - timedelta(days=DAYS_LIMIT)
    articles_list = []
    
    processed_count = 0
    
    for _, row in df_urls.iterrows():
        press_name = row.get('언론사', 'Unknown')
        rss_url = row.get('RSS주소', '')
        
        if not rss_url or pd.isna(rss_url): continue
        
        print(f"\n📰 [{press_name}] 처리 중...")
        try:
            feed = feedparser.parse(rss_url)
        except:
            print(f"   - 접속 실패: {rss_url}")
            continue

        for entry in feed.entries:
            # 필터링
            if is_foreign_news(entry): continue
            
            # 날짜 확인
            date_parsed = entry.get('published_parsed', entry.get('updated_parsed'))
            if date_parsed and datetime(*date_parsed[:6]) < cutoff_date:
                continue

            link = entry.get('link', '')
            title = entry.get('title', '')
            raw_date = entry.get('published', entry.get('updated', ''))
            
            # 본문 수집
            content = get_full_article(link)
            if not content:
                content = "[요약] " + clean_html(entry.get('summary', ''))
            
            if len(content) < 50: continue # 너무 짧으면 건너뜀

            print(f"   Checking: {title[:20]}...")

            # 데이터 가공 (해시, 날짜, 분류)
            c_hash = compute_content_hash(title, content)
            fmt_date = normalize_date(raw_date)
            category = classify_text_with_ai(title, content) # 소문자로 반환됨
            
            # externalId 생성 (고유성 보장 노력)
            ext_id = f"{press_name}-{int(time.time())}-{processed_count}"

            # 최종 JSON 객체 구조 (ingest_sample.json 기준)
            article_obj = {
                "sourceType": SOURCE_TYPE,  # RSS (대문자)
                "contentHash": c_hash,
                "externalId": ext_id,       # 서버에서 요구할 수 있어 추가
                "sourceName": press_name,
                "categoryCode": category,   # politics (소문자)
                "url": link,
                "title": title,
                "content": content,
                "author": press_name,       # 작성자 없으면 언론사명
                "publishedAt": fmt_date,    # ISO 8601 형식
                "fetchedAt": datetime.now().astimezone().isoformat()
            }
            
            articles_list.append(article_obj)
            processed_count += 1
            time.sleep(0.5) # API 및 서버 부하 조절

    # 최종 저장
    final_data = {"articles": articles_list}
    
    with open(OUTPUT_JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ [완료] 총 {len(articles_list)}건 저장됨.")
    print(f"📁 파일 위치: {OUTPUT_JSON_FILENAME}")

if __name__ == "__main__":
    main()
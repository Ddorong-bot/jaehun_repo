import pandas as pd
import feedparser
import json
import time
import hashlib
import google.generativeai as genai
from datetime import datetime
from dateutil import parser as date_parser
from bs4 import BeautifulSoup
import os

# ==============================================================================
# [설정] 사용자 환경 설정
# ==============================================================================
# 1. Gemini API 키 (본인의 키 입력)
GEMINI_API_KEY = ""

# 2. 파일 경로 설정
INPUT_EXCEL_FILE = "C:/Users/Choi/Desktop/일본 rss.xlsx"           # 입력 엑셀 파일
FILE_ORIGINAL_JSON = "C:/Users/Choi/Desktop/1_original_news.json"    # [결과1] 원본 데이터 저장 파일
FILE_TRANSLATED_JSON = "C:/Users/Choi/Desktop/2_translated_results.json" # [결과2] 번역된 결과 데이터 저장 파일

# 3. Gemini 모델 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# ==============================================================================
# [Helper Functions] 데이터 가공용 함수들
# ==============================================================================

def clean_html(raw_html):
    """HTML 태그 제거"""
    if not raw_html: return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(strip=True)

def generate_local_id(title):
    """서버 없이도 관리할 수 있도록 제목 기반의 고유 ID 생성 (MD5)"""
    return hashlib.md5(title.encode('utf-8')).hexdigest()

def normalize_date(date_str):
    """날짜 형식을 ISO 8601 포맷으로 통일"""
    if not date_str:
        return datetime.now().astimezone().isoformat()
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.astimezone() 
        return dt.isoformat()
    except:
        return datetime.now().astimezone().isoformat()

def get_safe_category(text):
    """카테고리 분류 로직"""
    text = text.lower()
    if 'economy' in text or 'business' in text or 'money' in text:
        return 'business'
    if 'tech' in text or 'science' in text:
        return 'tech'
    return 'world' # 기본값

def get_ai_translation(title, content):
    """Gemini에게 번역 및 요약 요청"""
    prompt = f"""
    [역할] 전문 번역가
    [요청]
    1. 제목: 한국어로 번역 (translatedTitle)
    2. 본문: 전체 내용을 빠짐없이 한국어로 번역 (translatedContent)
    3. 요약: 핵심 내용을 한국어 3줄 이내로 요약 (summaryText)
    
    [원문]
    제목: {title}
    내용: {content}
    
    [출력 포맷] JSON Only (No Markdown)
    {{ "translatedTitle": "...", "translatedContent": "...", "summaryText": "..." }}
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except:
        return None

# ==============================================================================
# [Phase 1] RSS 수집 -> 가공 -> JSON 저장 (서버 전송 X)
# ==============================================================================
def phase1_collect_news():
    print("\n📰 [Phase 1] RSS 뉴스 수집 및 원본 저장 시작...")
    
    if not os.path.exists(INPUT_EXCEL_FILE):
        print(f"❌ 엑셀 파일이 없습니다: {INPUT_EXCEL_FILE}")
        return []
    
    df = pd.read_excel(INPUT_EXCEL_FILE)
    collected_articles = []
    
    for _, row in df.iterrows():
        press_name = row['언론사']
        rss_url = row['RSS주소']
        print(f"   ㄴ 수집 중: {press_name}...")
        
        try:
            feed = feedparser.parse(rss_url)
            # 테스트를 위해 언론사당 3개씩만 수집
            for entry in feed.entries[:3]:
                title = entry.title
                link = entry.link
                
                # 본문 추출
                if hasattr(entry, 'content'):
                    raw_content = entry.content[0].value
                elif hasattr(entry, 'summary'):
                    raw_content = entry.summary
                else:
                    raw_content = title
                
                content = clean_html(raw_content)[:1000] # 길이 제한
                
                # 로컬 ID 생성 (서버가 없으므로 직접 생성)
                local_id = generate_local_id(title)

                # 데이터 객체 생성 (서버 포맷과 유사하게 유지)
                article_obj = {
                    "articleId": local_id, # 나중에 매칭할 ID
                    "sourceType": "RSS",
                    "sourceName": press_name,
                    "categoryCode": get_safe_category(title + content),
                    "url": link,
                    "title": title,
                    "content": content,
                    "publishedAt": normalize_date(entry.get('published', '')),
                }
                collected_articles.append(article_obj)
        except Exception as e:
            print(f"      ⚠️ 에러: {e}")

    # 원본 파일 저장
    payload = {"articles": collected_articles}
    with open(FILE_ORIGINAL_JSON, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ [저장 1] 원본 파일 생성 완료 ({len(collected_articles)}개): {FILE_ORIGINAL_JSON}")
    
    return collected_articles

# ==============================================================================
# [Phase 2] 수집된 데이터 읽기 -> AI 번역 -> JSON 저장 (서버 전송 X)
# ==============================================================================
def phase2_translate_news(articles):
    if not articles:
        print("📭 번역할 뉴스가 없습니다.")
        return

    print("\n🤖 [Phase 2] AI 번역 및 결과 저장 시작...")
    
    translated_results = []

    for idx, item in enumerate(articles):
        article_id = item.get("articleId")
        print(f"   ▶ [{idx+1}/{len(articles)}] 번역 중... (ID: {article_id[:8]}...)")
        
        ai_data = get_ai_translation(item.get("title"), item.get("content"))
        
        if ai_data:
            # 결과 데이터 구성 (요청하신 포맷 준수)
            result_payload = {
                "articleId": article_id,
                "languageTarget": "ko",
                "translatedTitle": ai_data.get("translatedTitle"),
                "translatedContent": ai_data.get("translatedContent"),
                "summaryText": ai_data.get("summaryText"),
                "modelName": "gemini-2.0-flash",
                # 원본 정보도 같이 보고 싶다면 아래 주석 해제
                # "originalUrl": item.get("url"),
                # "publishedAt": item.get("publishedAt")
            }
            
            translated_results.append(result_payload)
            print("      ✅ 번역 성공")
        else:
            print("      ❌ AI 응답 실패")
        
        time.sleep(1) # API 과부하 방지

    # 번역된 파일 저장
    with open(FILE_TRANSLATED_JSON, 'w', encoding='utf-8') as f:
        json.dump(translated_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ [저장 2] 번역된 파일 생성 완료: {FILE_TRANSLATED_JSON}")
    print("🎉 모든 로컬 작업이 완료되었습니다!")

# ==============================================================================
# 메인 실행부
# ==============================================================================
if __name__ == "__main__":
    # 1. 수집하고 원본 저장 (서버 전송 안 함)
    collected_data = phase1_collect_news()
    
    # 2. 바로 번역하고 결과 저장 (서버 전송 안 함)
    # Phase 1에서 수집한 데이터를 바로 Phase 2로 넘겨줍니다.
    phase2_translate_news(collected_data)
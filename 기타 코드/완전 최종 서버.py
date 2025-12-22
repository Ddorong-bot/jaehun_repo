import pandas as pd
import feedparser
import requests
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
# 1. Gemini API 키 (새로 발급받은 키 입력)
GEMINI_API_KEY = ""

# 2. 파일 경로 설정
INPUT_EXCEL_FILE = "일본 rss.xlsx"           # 입력 엑셀 파일
FILE_ORIGINAL_JSON = "1_original_news.json"    # [결과1] 서버로 보낼 원본 데이터
FILE_TRANSLATED_JSON = "2_translated_results.json" # [결과2] 번역된 최종 결과 데이터

# 3. 서버 주소 설정
SERVER_HOST = "http://localhost:8080"
URL_INGEST = f"{SERVER_HOST}/api/admin/ingestion/articles:bulk"      # 원본 저장용
URL_PULL   = f"{SERVER_HOST}/api/llm/pull?languageTarget=ko&limit=10" # 번역 대상 가져오기용
URL_RESULT = f"{SERVER_HOST}/api/llm/results"                         # 번역 결과 저장용

# 4. Gemini 모델 설정
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

def compute_hash(title, content):
    """중복 방지를 위한 Content Hash 생성 (SHA-256)"""
    text = (str(title) + str(content)).encode('utf-8')
    return hashlib.sha256(text).hexdigest()

def normalize_date(date_str):
    """날짜 형식을 서버가 좋아하는 ISO 8601 포맷으로 통일"""
    if not date_str:
        return datetime.now().astimezone().isoformat()
    try:
        # dateutil이 대부분의 형식을 알아서 파싱해줌
        dt = date_parser.parse(date_str)
        # 시간대가 없으면 강제로 한국 시간(+09:00) 부여 (서버 에러 방지)
        if dt.tzinfo is None:
            dt = dt.astimezone() 
        return dt.isoformat()
    except:
        return datetime.now().astimezone().isoformat()

def get_safe_category(text):
    """서버 500 에러 방지를 위해 카테고리를 서버 허용 값(world, business)으로 매핑"""
    text = text.lower()
    if 'economy' in text or 'business' in text or 'money' in text or 'market' in text:
        return 'business'
    if 'tech' in text or 'science' in text:
        return 'tech'
    # 그 외(politics 등)는 안전하게 world로 매핑
    return 'world'

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
# [Phase 1] RSS 수집 -> 가공 -> JSON 저장 -> 서버 전송 (Ingest)
# ==============================================================================
def phase1_collect_and_ingest():
    print("\n📰 [Phase 1] 뉴스 수집 및 원본 서버 저장 시작...")
    
    # 1. 엑셀 읽기
    if not os.path.exists(INPUT_EXCEL_FILE):
        print(f"❌ 엑셀 파일이 없습니다: {INPUT_EXCEL_FILE}")
        return False
    
    df = pd.read_excel(INPUT_EXCEL_FILE)
    collected_articles = []
    
    # 2. RSS 수집 및 가공 loop
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
                
                # 본문 추출 시도
                if hasattr(entry, 'content'):
                    raw_content = entry.content[0].value
                elif hasattr(entry, 'summary'):
                    raw_content = entry.summary
                else:
                    raw_content = title
                
                content = clean_html(raw_content)[:1000] # 길이 제한
                
                # 데이터 객체 생성 (서버 포맷 준수)
                article_obj = {
                    "sourceType": "RSS",
                    "sourceName": press_name,
                    "categoryCode": get_safe_category(title + content), # 안전한 카테고리
                    "url": link,
                    "title": title,
                    "content": content,
                    "publishedAt": normalize_date(entry.get('published', '')), # 날짜 수정
                    "contentHash": compute_hash(title, content) # 해시 생성
                }
                collected_articles.append(article_obj)
        except Exception as e:
            print(f"      ⚠️ 에러: {e}")

    # 3. 원본 파일 저장 (csv2json 역할)
    payload = {"articles": collected_articles}
    with open(FILE_ORIGINAL_JSON, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ [저장 1] 원본 파일 생성 완료: {FILE_ORIGINAL_JSON}")

    # 4. 서버로 전송 (Ingest)
    print("🚀 서버로 원본 데이터 전송 중...")
    try:
        res = requests.post(URL_INGEST, json=payload)
        if res.status_code == 200:
            print("✅ 서버 Ingest 성공!")
            return True
        else:
            print(f"❌ 서버 Ingest 실패: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        print(f"❌ 서버 연결 실패: {e}")
        return False

# ==============================================================================
# [Phase 2] 서버 조회(Pull) -> AI 번역 -> JSON 저장 -> 서버 전송 (Result)
# ==============================================================================
def phase2_pull_translate_result():
    print("\n🤖 [Phase 2] 서버에서 데이터 가져오기 및 AI 번역 시작...")
    
    # 서버가 데이터를 처리할 시간을 잠시 줌
    time.sleep(2) 

    # 1. 서버에서 가져오기 (Pull)
    try:
        res = requests.get(URL_PULL)
        data = res.json()
        items = data.get("items", [])
    except Exception as e:
        print(f"❌ Pull 실패: {e}")
        return

    if not items:
        print("📭 번역할 뉴스가 없습니다 (서버 DB가 비어있거나 모두 처리됨).")
        return

    print(f"✅ {len(items)}개의 뉴스를 가져왔습니다. 번역을 진행합니다.")
    
    translated_results = []

    # 2. AI 번역 loop
    for idx, item in enumerate(items):
        article_id = item.get("articleId") # 서버가 부여한 ID (필수)
        print(f"   ▶ [{idx+1}/{len(items)}] 번역 중... (ID: {article_id})")
        
        ai_data = get_ai_translation(item.get("title"), item.get("content"))
        
        if ai_data:
            # 3. 결과 데이터 구성 (Result 포맷 준수)
            result_payload = {
                "articleId": article_id,
                "languageTarget": "ko",
                "translatedTitle": ai_data.get("translatedTitle"),
                "translatedContent": ai_data.get("translatedContent"),
                "summaryText": ai_data.get("summaryText"),
                "modelName": "gemini-2.0-flash"
            }
            
            # 리스트에 추가
            translated_results.append(result_payload)

            # 4. 서버로 결과 전송 (Result)
            try:
                post_res = requests.post(URL_RESULT, json=result_payload)
                if post_res.status_code == 200:
                    print("      ✅ 서버 저장 성공")
                else:
                    print(f"      ❌ 서버 저장 실패: {post_res.status_code}")
            except Exception as e:
                print(f"      ❌ 전송 오류: {e}")
        else:
            print("      ⚠️ AI 응답 실패")
        
        time.sleep(1) # API 과부하 방지

    # 5. 번역된 파일 저장
    with open(FILE_TRANSLATED_JSON, 'w', encoding='utf-8') as f:
        json.dump(translated_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ [저장 2] 번역된 파일 생성 완료: {FILE_TRANSLATED_JSON}")
    print("🎉 모든 프로세스가 성공적으로 완료되었습니다!")

# ==============================================================================
# 메인 실행부
# ==============================================================================
if __name__ == "__main__":
    # [1단계] 수집 -> 가공 -> 원본파일저장 -> 서버전송
    if phase1_collect_and_ingest():
        
        # [2단계] 서버조회 -> 번역 -> 번역파일저장 -> 서버저장
        phase2_pull_translate_result()
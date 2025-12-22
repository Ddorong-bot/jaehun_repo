import requests
import json
import google.generativeai as genai
import time

# ==========================================
# [설정] 본인의 API 키를 입력하세요
# ==========================================
GEMINI_API_KEY = ""

# 서버 주소
SERVER_HOST = "http://localhost:8080"
GET_URL = f"{SERVER_HOST}/api/llm/pull?languageTarget=ko&limit=10"
POST_URL = f"{SERVER_HOST}/api/llm/results"

# Gemini 모델 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')
# ==========================================

def get_ai_result(title, content):
    """
    Gemini에게 제목번역, 전체번역, 요약을 요청하고 JSON으로 받습니다.
    """
    prompt = f"""
    당신은 전문 번역가이자 뉴스 에디터입니다. 아래 내용을 요청에 맞게 처리해주세요.

    [원문 제목]
    {title}

    [원문 내용]
    {content}

    [요청사항]
    1. 제목을 한국어로 자연스럽게 번역하세요. (translatedTitle)
    2. 본문 **전체**를 빠짐없이 한국어로 번역하세요. (translatedContent)
    3. 내용을 한국어로 3줄 이내로 핵심 요약하세요. (summaryText)

    [출력 포맷]
    반드시 아래 JSON 형식으로만 출력하세요 (마크다운 없이):
    {{
        "translatedTitle": "...",
        "translatedContent": "...",
        "summaryText": "..."
    }}
    """
    try:
        response = model.generate_content(prompt)
        # 혹시 모를 마크다운 제거
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"⚠️ AI 처리 오류: {e}")
        return None

def main():
    # 1. 서버에서 원본 뉴스 가져오기 (GET)
    print("📡 [1단계] 뉴스 데이터 가져오는 중...")
    try:
        res = requests.get(GET_URL)
        items = res.json().get("items", [])
        if not items:
            print("📭 가져올 뉴스가 없습니다. (DB가 비었거나 모두 처리됨)")
            return
        print(f"✅ 총 {len(items)}개의 뉴스를 가져왔습니다.")
    except Exception as e:
        print(f"❌ 서버 연결 실패 (GET): {e}")
        return

    # 2. AI 변환 및 서버 전송 (POST)
    print("\n📡 [2단계] AI 번역 및 서버 전송 시작...")
    
    for item in items:
        article_id = item.get("articleId")
        print(f"▶ 처리 중: {article_id}")

        # (1) AI에게 작업 시키기
        ai_data = get_ai_result(item.get("title"), item.get("content"))
        
        if ai_data:
            # (2) 서버가 원하는 형식(curl 데이터) 그대로 만들기
            payload = {
                "articleId": article_id,               # 가져온 ID 그대로
                "languageTarget": "ko",                # 타겟 언어
                "translatedTitle": ai_data["translatedTitle"],
                "translatedContent": ai_data["translatedContent"], # 전체 번역
                "summaryText": ai_data["summaryText"],             # 요약
                "modelName": "gemini-2.0-flash"              # 사용한 모델명
            }

            # (3) 서버로 전송 (이 부분이 curl 명령어를 대신합니다)
            try:
                # requests.post는 curl -X POST와 동일한 역할을 합니다.
                send_res = requests.post(POST_URL, json=payload)
                
                if send_res.status_code == 200:
                    print("   ㄴ ✅ 저장 성공!")
                else:
                    print(f"   ㄴ ❌ 저장 실패: {send_res.status_code} - {send_res.text}")
            except Exception as e:
                print(f"   ㄴ ❌ 전송 오류: {e}")
        else:
            print("   ㄴ ⚠️ AI 응답 실패로 건너뜁니다.")
        
        time.sleep(1) # API 과부하 방지

if __name__ == "__main__":
    main()
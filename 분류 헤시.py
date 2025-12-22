import pandas as pd
import google.generativeai as genai
import time
import os
import hashlib
import re
import unicodedata

# ==========================================
# 사용자 설정
# ==========================================
# 1. Gemini API 키 입력
API_KEY = '' 

# 2. 파일 경로 설정
INPUT_FILENAME = 'C:/Users/user/Desktop/일본 뉴스 저장 결과.csv'       # 원본 파일
OUTPUT_FILENAME = 'C:/Users/user/Desktop/분류및해시결과.csv'   # 결과 파일 (이름 변경 추천)
# ==========================================

# Gemini 모델 설정
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('models/gemini-2.0-flash')

# ==========================================
# 해시 계산 함수 (변경 없음)
# ==========================================
def normalize_text(text: str) -> str:
    """
    텍스트 정규화: Unicode NFKC, 앞뒤 공백 제거, 연속 공백 축소
    """
    if not text:
        return ""
    text = str(text) 
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text

def compute_content_hash(title: str, content: str) -> str:
    """
    contentHash 계산 (SHA-256, hex 64자)
    """
    normalized_title = normalize_text(title)
    normalized_content = normalize_text(content)

    payload = f"{normalized_title}\n{normalized_content}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return digest

# ==========================================
# AI 분류 함수 (번역 함수는 삭제됨)
# ==========================================
def classify_text(title, content):
    """
    기사 내용을 보고 Politics, Economy, Tech, Others 중 하나로 분류
    """
    summary_text = f"Title: {title}\nContent: {str(content)[:500]}"
    
    prompt = f"""
    Analyze the following news article and classify it into exactly one of these 4 categories:
    [Politics, Economy, Tech, Others]
    
    - Output ONLY the category name. Do not add any explanation.
    - If it's about government, laws, diplomacy -> Politics
    - If it's about markets, stock, inflation, companies -> Economy
    - If it's about AI, software, gadgets, science -> Tech
    - Everything else -> Others

    Article:
    {summary_text}
    """

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            category = response.text.strip().replace("'", "").replace('"', "")
            for cat in ['Politics', 'Economy', 'Tech', 'Others']:
                if cat.lower() in category.lower():
                    return cat
            return "Others"
        except Exception as e:
            if attempt == 0:
                time.sleep(1)
            else:
                return "Others"

def main():
    # 1. 파일 읽기
    if not os.path.exists(INPUT_FILENAME):
        print(f"오류: '{INPUT_FILENAME}' 파일을 찾을 수 없습니다.")
        return

    if os.path.exists(OUTPUT_FILENAME):
        print(f"기존 작업 파일('{OUTPUT_FILENAME}')을 발견했습니다. 이어서 진행합니다.")
        try:
            df = pd.read_csv(OUTPUT_FILENAME)
        except:
            return
    else:
        print(f"새로운 작업을 시작합니다. ('{INPUT_FILENAME}' 로드)")
        try:
            df = pd.read_csv(INPUT_FILENAME)
        except UnicodeDecodeError:
            df = pd.read_csv(INPUT_FILENAME, encoding='cp949')

    # 필요한 컬럼 생성
    if '분류완료' not in df.columns:
        df['분류완료'] = False # '번역완료' 대신 '분류완료' 사용
    if '카테고리' not in df.columns:
        df['카테고리'] = ""
    if 'contentHash' not in df.columns:
        df['contentHash'] = "" 

    print("분류 및 해시 생성을 시작합니다... (번역 제외)\n")
    
    total_count = len(df)
    
    for index, row in df.iterrows():
        # 이미 작업된 행은 건너뜁니다.
        if row.get('분류완료') == True:
            continue

        title = row.get('제목', '')
        content = row.get('내용', '')
        
        print(f"[{index+1}/{total_count}] 작업 중... {str(title)[:20]}...")

        # 1) 해시 생성 (원문 기준)
        c_hash = compute_content_hash(str(title), str(content))
        
        # 2) 분류 (AI 사용)
        category = classify_text(title, content)
        print(f"   -> 분류: {category} | 해시: {c_hash[:10]}...")

        # 3) 저장 업데이트 (제목, 내용은 원본 유지)
        df.at[index, '카테고리'] = category
        df.at[index, 'contentHash'] = c_hash 
        df.at[index, '분류완료'] = True

        # 실시간 저장
        try:
            df.to_csv(OUTPUT_FILENAME, index=False, encoding='utf-8-sig')
        except PermissionError:
            print(f"   !! 저장 실패: 파일을 닫아주세요.")
        
        # API 호출 속도 조절 (번역을 안 하므로 딜레이를 조금 줄여도 됨)
        time.sleep(1) 

    try:
        df.to_csv(OUTPUT_FILENAME, index=False, encoding='utf-8-sig')
        print(f"\n[완료] 작업이 끝났습니다. '{OUTPUT_FILENAME}' 확인")
    except:
         print(f"\n[오류] 최종 저장 실패")

if __name__ == "__main__":
    main()
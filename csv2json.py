import pandas as pd
import json
import os

# ==========================================
# 사용자 설정
# ==========================================
INPUT_CSV_FILENAME = 'C:/Users/user/Desktop/번역및분류헤시결과.csv'  # 변환할 CSV 파일 경로
OUTPUT_JSON_FILENAME = 'C:/Users/user/Desktop/뉴스데이터.json'      # 저장할 JSON 파일 경로

# 수집 방식 설정 (RSS, SCRAPE, API 등)
# 기존 코드가 RSS를 통해 수집했으므로 기본값은 'RSS'로 설정합니다.
SOURCE_TYPE_DEFAULT = 'RSS' 
# ==========================================

def convert_csv_to_json():
    # 1. CSV 파일 읽기
    if not os.path.exists(INPUT_CSV_FILENAME):
        print(f"오류: '{INPUT_CSV_FILENAME}' 파일을 찾을 수 없습니다.")
        return

    try:
        # 인코딩 문제 발생 시 'cp949'로 시도
        try:
            df = pd.read_csv(INPUT_CSV_FILENAME, encoding='utf-8-sig')
        except UnicodeDecodeError:
            df = pd.read_csv(INPUT_CSV_FILENAME, encoding='cp949')
            
        print(f"'{INPUT_CSV_FILENAME}' 로딩 완료. JSON 변환을 시작합니다...")

        articles_list = []

        # 2. 데이터 변환 루프
        for index, row in df.iterrows():
            # 카테고리 소문자 변환 (Politics -> politics)
            category_raw = str(row.get('카테고리', 'others'))
            category_code = category_raw.lower() if category_raw and category_raw.lower() in ['politics', 'economy', 'tech', 'others'] else 'others'

            # 각 기사 객체 생성
            article = {
                "sourceName": str(row.get('언론사', '')),
                "sourceType": SOURCE_TYPE_DEFAULT,
                "categoryCode": category_code,
                "url": str(row.get('링크', '')),
                "title": str(row.get('제목', '')),
                "content": str(row.get('내용', '')),
                "publishedAt": str(row.get('뉴스 보도 날짜', '')),
                "contentHash": str(row.get('contentHash', '')),
                # 선택 사항: 수집 시간 (fetchedAt)
                #"fetchedAt": str(row.get('수집날짜', '')) 
            }
            
            articles_list.append(article)

        # 3. 최종 JSON 구조 생성
        final_data = {
            "articles": articles_list
        }

        # 4. JSON 파일로 저장
        with open(OUTPUT_JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)

        print(f"\n[완료] 총 {len(articles_list)}건의 기사가 '{OUTPUT_JSON_FILENAME}'로 저장되었습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    convert_csv_to_json()
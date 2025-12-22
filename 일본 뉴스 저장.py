import pandas as pd
import feedparser
import os
import re
from datetime import datetime, timedelta
import time
import requests
from bs4 import BeautifulSoup
from newspaper import Article, Config

# ==========================================
# [사용자 설정]
# ==========================================
# 입력 파일 경로 (언론사, RSS주소 컬럼이 있어야 함)
INPUT_FILENAME = "C:/Users/Choi/Desktop/일본 rss.xlsx"

# 결과 파일 경로 (글자 수 제한 없는 csv로 저장)
OUTPUT_FILENAME = 'C:/Users/Choi/Desktop/일본 뉴스 저장 결과.csv' 

# 며칠 전 뉴스까지 수집할지 설정
DAYS_LIMIT = 3

# [필터링 1] 해외/국제 뉴스 제외 키워드 (URL 및 태그 검사)
EXCLUDE_KEYWORDS = ['world', 'global', 'international', 'overseas', 'foreign', '국제', '해외', 'english']

# [필터링 2] 본문에서 제거할 불필요한 문구 (쿠키, 구독 권유 등)
GARBAGE_PHRASES = [
    "We use cookies", "cookie policy", "Accept all", "Manage preferences",
    "This website uses cookies", "All rights reserved", "로그인이 필요합니다",
    "무단 전재 및 재배포 금지", "기자 구독"
]
# ==========================================

def clean_html(raw_html):
    """HTML 태그 제거"""
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def is_foreign_news(entry):
    """
    URL이나 카테고리 정보를 분석해 해외 뉴스인지 판별
    True 반환 시 수집 제외
    """
    link = entry.get('link', '').lower()
    title = entry.get('title', '').lower()
    
    # 1. URL 및 제목 검사
    for keyword in EXCLUDE_KEYWORDS:
        if f'/{keyword}/' in link or f'/{keyword}.' in link: # URL 패턴
            return True
        if keyword in title: # 제목 패턴
            return True

    # 2. RSS 카테고리(Tags) 검사
    if 'tags' in entry:
        for tag in entry.tags:
            tag_term = tag.get('term', '').lower()
            for keyword in EXCLUDE_KEYWORDS:
                if keyword in tag_term:
                    return True
    return False

def get_full_article(url):
    """
    1차: Newspaper3k (구글봇 위장)
    2차: 실패/잘림 의심 시 BeautifulSoup으로 <p> 태그 강제 수집
    """
    # 구글봇 위장 헤더 (쿠키 팝업 우회에 효과적)
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
    }

    try:
        # -------------------------------------------------------
        # [1단계] Newspaper3k 시도
        # -------------------------------------------------------
        config = Config()
        config.browser_user_agent = headers['User-Agent']
        config.request_timeout = 15
        config.memoize_articles = False
        config.fetch_images = False
        
        article = Article(url, config=config)
        article.download()
        article.parse()
        
        content = article.text.strip()

        # -------------------------------------------------------
        # [2단계] 결과 검증 및 강제 수집 (BeautifulSoup)
        # -------------------------------------------------------
        # 본문이 200자 미만이면 '잘렸다'고 판단하고 강제 수집 시도
        if len(content) < 200: 
            # print(f"    (본문 누락 의심으로 강제 수집 시도...)")
            try:
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 모든 <p> 태그 긁어모으기
                paragraphs = soup.find_all('p')
                text_list = []
                for p in paragraphs:
                    text = p.get_text().strip()
                    # 30자 이상인 문장만 유효한 본문으로 간주 (메뉴 등 제외)
                    if len(text) > 30: 
                        text_list.append(text)
                
                forced_content = '\n\n'.join(text_list)
                
                # 강제 수집한 게 더 길면 교체
                if len(forced_content) > len(content):
                    content = forced_content
            except Exception:
                pass # 강제 수집 실패 시 1단계 결과 유지

        # -------------------------------------------------------
        # [3단계] 최종 정제 (쿠키 문구 등 삭제)
        # -------------------------------------------------------
        if content:
            lines = content.split('\n')
            cleaned_lines = []
            for line in lines:
                # 쓰레기 문구가 포함된 줄 제거
                if any(garbage in line for garbage in GARBAGE_PHRASES):
                    continue
                cleaned_lines.append(line)
            content = '\n'.join(cleaned_lines)

        if len(content) < 50: 
            return "" # 정제 후에도 너무 짧으면 실패 처리

        return content

    except Exception as e:
        # print(f"    [Error] {e}")
        return ""

def main():
    if not os.path.exists(INPUT_FILENAME):
        print(f"오류: '{INPUT_FILENAME}' 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        return
    
    df_urls = pd.read_excel(INPUT_FILENAME)
    print(f"'{INPUT_FILENAME}' 로딩 완료. 뉴스 수집 시작...\n")

    all_news = []
    cutoff_date = datetime.now() - timedelta(days=DAYS_LIMIT)

    for index, row in df_urls.iterrows():
        press_name = row.get('언론사', '알수없음')
        rss_url = row.get('RSS주소', '')

        if not rss_url or pd.isna(rss_url): continue

        print(f"\n>>> [{press_name}] 분석 중...")
        
        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            print(f"    RSS 접속 실패: {e}")
            continue

        country_info = feed.feed.get('language', 'Unknown')
        
        count = 0
        for entry in feed.entries:
            # 1. 해외 뉴스 필터링
            if is_foreign_news(entry):
                # print(f"    Pass (해외뉴스): {entry.get('title', '')}")
                continue

            # 2. 날짜 체크
            date_parsed = entry.get('published_parsed', entry.get('updated_parsed'))
            if date_parsed:
                if datetime(*date_parsed[:6]) < cutoff_date:
                    continue
            
            # 3. 본문 수집
            title = entry.get('title', '')
            link = entry.get('link', '')
            pub_date_str = entry.get('published', entry.get('updated', ''))
            
            print(f"    - 수집 중: {title[:30]}...")
            
            full_content = get_full_article(link)
            
            # 본문 수집 실패 시 요약본 사용
            if not full_content:
                rss_summary = entry.get('summary', entry.get('description', ''))
                final_content = "[요약본] " + clean_html(rss_summary)
            else:
                final_content = full_content

            all_news.append({
                '수집날짜': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '뉴스 보도 날짜': pub_date_str,
                '수집국가': country_info,
                '제목': title,
                '내용': final_content,
                '링크': link,
                '언론사': press_name
            })
            count += 1
            time.sleep(0.5) # 서버 부하 방지

        print(f"    => {count}건 수집 완료.")

    if all_news:
        df_result = pd.DataFrame(all_news)
        # 엑셀 대신 CSV로 저장 (글자수 제한 해결, 한글 깨짐 방지 utf-8-sig)
        df_result.to_csv(OUTPUT_FILENAME, index=False, encoding='utf-8-sig')
        print(f"\n[최종 완료] 총 {len(all_news)}건 저장 완료: {OUTPUT_FILENAME}")
    else:
        print("\n수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()
## 일본 뉴스 기사 수집 코드
<br>
1. `일본 rss.xlml` : 일본 언론사의 rss를 저장한 파일
  
<br>
2. `일본 뉴스 저장.py` : 일본 언론사의 RSS 주소를 읽어와 기사의 전체 본문과 제목을 긁어옴
- 결과물 : 일본 뉴스 저장 결과.csv

<br>
3. `분류 헤시.py` : 수집된 csv팡리을 읽어서 AI로 카테고리를 분류하고 고유 ID를 생성
- 결과물 : 번역및분류결과.csv  

<br>
4. `csv2json.py` : csv로 저장된 데이터를 서버에 올리기 쉽게 JSON 형식으로 변환
- 결과물 : 원본뉴스데이터.json

<br>
5. `날짜 수정.py` : 생성된 JSON파일에서 날짜 형식이 통일 되지 않아 통일 시키는 코드
- 결과물 : japanese_news_fixed.json<br><br>


`curl.exe -i -X POST "http://localhost:8080/api/admin/ingestion/articles:bulk" -H "Content-Type: application/json" --data-binary "@japanese_news_fixed.json"`를 통해 서버에 결과물을 저장  <br><br>


`curl.exe -i -X GET "http://localhost:8080/api/llm/pull?languageTarget=ko&limit=10"`로 서버에 올라간 결과물 확인  
  
  <br>
6. `번역 및 서버 저장.py` : 서버에서 번역할 기사를 가져와 AI API를 통해 번역을 진행하고 다시 서버로 보내는 코드
- 결과물 : ai_processed_results.json  <br><br>
  
  
`curl.exe -i -X POST "http://localhost:8080/api/llm/results"`로 번역된 파일을 다시 서버에 저장  


## json 파일 형식

```
{
  "articles": [
    {
      "sourceName": "...",
      "sourceType": "SCRAPE",
      "categoryCode": "...",
      "url": "...",
      "title": "...",
      "content": "...",
      "publishedAt": "...",
      "contentHash": "..."
    },
    {
      "sourceName": "...",
      "sourceType": "RSS",
      "categoryCode": "...",
      "url": "...",
      "title": "...",
      "content": "...",
      "publishedAt": "...",
      "contentHash": "..."
    }
  ]
}  
```

## 번역된 json 파일 형식
```
{  
  "articleId": "UUID",  
  "languageTarget": "ko",  
  "translatedTitle": "번역된 제목",  
  "translatedContent": "번역된 본문",  
  "summaryText": "요약 내용",  
  "modelName": "gpt-4",  
}  
```
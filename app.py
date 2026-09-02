import os
import re
import urllib.parse
import datetime
from datetime import datetime, timedelta, timezone
import feedparser
import streamlit as st
from google import genai
from groq import Groq

# 1. 페이지 기본 설정 및 디자인 스타일
st.set_page_config(page_title="우진산전 주간 뉴스 브리퍼", page_icon="🚅", layout="centered")

# 2. API 키 설정 (Streamlit Secrets 보안 영역에서 로드)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY.startswith("gsk_") else None

def get_kst_now():
    return datetime.now(timezone(timedelta(hours=9)))

# 3. 뉴스 수집 함수 (최근 7일)
def fetch_google_news(keyword="우진산전", max_results=10):
    query = f"{keyword} when:7d"
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    articles = []
    for entry in feed.entries[:max_results]:
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "date": getattr(entry, 'published', '최근 1주일 내')
        })
    return articles

# 4. HTML 리포트 생성 함수
def generate_report_html(content_text, keyword):
    kst_now = get_kst_now()
    today_str = kst_now.strftime("%Y년 %m월 %d일")
    
    # 구분선 제거 및 링크/볼드 마크다운 변환
    content_text = re.sub(r'^[=\-\*\_]{3,}\s*$', '', content_text, flags=re.MULTILINE)
    html_body = re.sub(r'\[(.*?)\]\((https?://[^\s\)]+)\)', r'<a href="\2" target="_blank" class="news-link">🔗 \1 ↗</a>', content_text)
    html_body = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_body)
    
    paragraphs = html_body.split('\n')
    formatted_p = []
    for p in paragraphs:
        p_str = p.strip()
        if not p_str: continue
        if p_str.startswith('###') or p_str.startswith('##'):
            clean_title = re.sub(r'^#+\s*', '', p_str)
            formatted_p.append(f'<h3 class="section-title">{clean_title}</h3>')
        elif p_str.startswith('1.') or p_str.startswith('2.') or p_str.startswith('3.') or p_str.startswith('•') or p_str.startswith('-'):
            clean_item = re.sub(r'^[\-\•]\s*', '', p_str)
            formatted_p.append(f'<div class="item-card">{clean_item}</div>')
        else:
            formatted_p.append(f'<p class="text-p">{p_str}</p>')
            
    final_body = "".join(formatted_p)

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <link rel="stylesheet" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
        <style>
            :root {{ --primary: #1e3a8a; --primary-light: #2563eb; --bg: #f8fafc; --card-bg: #ffffff; --text-main: #0f172a; --text-sub: #334155; --border: #e2e8f0; }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ font-family: "Pretendard Variable", Pretendard, sans-serif; background-color: var(--bg); color: var(--text-main); line-height: 1.75; padding: 20px; }}
            .wrapper {{ max-width: 800px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff; padding: 30px; border-radius: 16px; margin-bottom: 20px; }}
            .badge {{ display: inline-block; background: rgba(59, 130, 246, 0.2); color: #60a5fa; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 20px; margin-bottom: 10px; border: 1px solid rgba(96, 165, 250, 0.3); }}
            .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 6px; }}
            .header .meta-info {{ color: #94a3b8; font-size: 13px; }}
            .main-card {{ background: var(--card-bg); padding: 30px; border-radius: 16px; border: 1px solid var(--border); }}
            .section-title {{ font-size: 18px; font-weight: 700; color: var(--primary); margin: 24px 0 14px 0; display: flex; align-items: center; }}
            .main-card > .section-title:first-child {{ margin-top: 0; }}
            .section-title::before {{ content: ""; display: inline-block; width: 4px; height: 16px; background-color: var(--primary-light); border-radius: 2px; margin-right: 8px; }}
            .item-card {{ background: #f8fafc; border-left: 3px solid var(--primary-light); padding: 14px 18px; border-radius: 0 10px 10px 0; margin-bottom: 12px; font-size: 14.5px; }}
            .text-p {{ color: var(--text-sub); font-size: 14.5px; margin-bottom: 12px; }}
            .news-link {{ color: var(--primary-light); font-weight: 600; text-decoration: none; display: inline-block; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="header">
                <span class="badge">WEEKLY BRIEFING</span>
                <h1>🚅 우진산전 주간 동향 & 뉴스 브리핑</h1>
                <div class="meta-info">발행일자: {today_str} | 데이터 출처: 최근 7일간의 미디어 뉴스</div>
            </div>
            <div class="main-card">{final_body}</div>
        </div>
    </body>
    </html>
    """

# 5. UI 메인 화면 구성
st.title("🚅 우진산전 주간 뉴스 브리퍼")
st.caption("버튼을 누르면 버튼을 누른 시점 기준 최근 1주일(7일)간의 기사를 추려 AI 요약 리포트를 생성합니다.")

if st.button("🚀 최근 1주일 브리핑 생성", type="primary", use_container_width=True):
    with st.spinner("최근 1주일 간의 우진산전 기사를 수집하고 AI 리포트를 생성 중입니다..."):
        articles = fetch_google_news("우진산전", max_results=10)
        
        if not articles:
            st.error("최근 1주일 간 '우진산전' 관련 신규 기사를 찾지 못했습니다.")
        else:
            raw_news_text = ""
            for i, article in enumerate(articles, 1):
                raw_news_text += f"{i}. 기사 제목: {article['title']}\n   원문 URL: {article['link']}\n   발행일: {article['date']}\n\n"

            prompt = f"""
다음은 최근 1주일 간 수집된 [우진산전] 관련 주요 뉴스 기사들이다.
아래 뉴스들을 바탕으로 '우진산전 주간 기업 동향 브리핑 리포트'를 작성해 줘.

[요구사항]
1. 절대로 '----', '***', '===' 같은 구분선/수평선 기호를 넣지 말 것.
2. 각 기사 요약 끝에는 반드시 해당 기사의 원문 링크를 [기사 원문 읽기](원문 URL) 형태로 붙여줄 것.
3. 수집된 기사들을 내용의 연관성에 따라 2~3개 주요 이슈/테마(예: ### 1. 주요 수주 및 사업 성과, ### 2. 기술 개발 동향 등) 섹션 제목으로 분류하여 작성할 것.
4. 각 주요 기사별 핵심 내용을 2~3줄로 명확하게 요약할 것.
5. 맨 마지막에는 ### 3. 주간 종합 시사점 섹션 제목으로 최근 1주일 간의 요약을 작성해 줄 것.
6. 정제된 비즈니스 보고서 톤으로 작성할 것.

[뉴스 데이터]
{raw_news_text}
"""
            res_text = ""
            try:
                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                res_text = response.text
            except Exception:
                if groq_client:
                    try:
                        chat_completion = groq_client.chat.completions.create(
                            messages=[{"role": "system", "content": "유능한 산업 분석가 AI"}, {"role": "user", "content": prompt}],
                            model="openai/gpt-oss-20b"
                        )
                        res_text = chat_completion.choices[0].message.content
                    except Exception as e:
                        res_text = f"AI 브리핑 생성 실패: {str(e)}"
                else:
                    res_text = "AI API 키 설정 또는 호출 실패"

            html_report = generate_report_html(res_text, "우진산전")
            
            # 6. 화면 표시 및 다운로드 버튼 제공
            st.components.v1.html(html_report, height=750, scrolling=True)
            
            st.download_button(
                label="📥 HTML 보고서 파일 다운로드",
                data=html_report,
                file_name=f"우진산전_주간리포트_{get_kst_now().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True
            )
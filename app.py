import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
import feedparser
import streamlit as st
from google import genai
from groq import Groq

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="우진산전 기사 브리핑룸", 
    page_icon="🚅", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 2. API 키 설정 (Streamlit Secrets 보안 영역에서 로드)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY.startswith("gsk_") else None

def get_kst_now():
    return datetime.now(timezone(timedelta(hours=9)))

# 3. Streamlit 앱 자체 Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    
    .header-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    
    .header-title {
        font-size: 22px;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .header-desc {
        font-size: 13.5px;
        color: #94A3B8;
        line-height: 1.5;
    }
    
    .tag-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 14px;
    }
    
    .info-tag {
        background: rgba(59, 130, 246, 0.15);
        color: #60A5FA;
        border: 1px solid rgba(96, 165, 250, 0.3);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }

    div.stButton > button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 14px 20px !important;
        border-radius: 12px !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4) !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.6) !important;
    }

    div.stDownloadButton > button {
        background-color: #1E293B !important;
        color: #38BDF8 !important;
        border: 1px solid #0284C7 !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        padding: 10px 16px !important;
    }

    @media (max-width: 640px) {
        .header-card {
            padding: 18px;
        }
        .header-title {
            font-size: 19px;
        }
        .header-desc {
            font-size: 12.5px;
        }
    }
</style>
""", unsafe_allow_html=True)

# 4. 뉴스 수집 함수
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

# 5. HTML 리포트 생성 함수 (링크 변환 완전 세척 알고리즘)
def generate_report_html(content_text, keyword):
    kst_now = get_kst_now()
    today_str = kst_now.strftime("%Y년 %m월 %d일")
    
    # 1. 수평선 기호 제거
    content_text = re.sub(r'^[=\-\*\_]{3,}\s*$', '', content_text, flags=re.MULTILINE)
    
    # 2. AI가 생성해버린 엉킨 [기사 원문 읽기] 텍스트 잔여물 전면 삭제
    content_text = re.sub(r'\[\s*기사\s*원문\s*읽기\s*\]', '', content_text)
    
    # 3. 모든 형태의 URL(구글 뉴스 링크 포함)을 추출하여 1개의 단일 <a> 태그 버튼으로 치환
    def clean_url_replacer(match):
        raw_url = match.group(0).strip()
        # 괄호나 따옴표 등 URL 끝에 붙은 불필요 기호 세척
        clean_url = re.sub(r'[\)\>\s]+$', '', raw_url)
        clean_url = re.sub(r'^[\(\<]+', '', clean_url)
        return f'<br><a href="{clean_url}" target="_blank" class="news-link">🔗 기사 원문 읽기 ↗</a>'

    # URL 패턴 감지 및 하이퍼링크 화 (중복 URL 방지)
    html_body = re.sub(r'https?://[^\s\<\>"\']+', clean_url_replacer, content_text)
    
    # 4. 남아있는 비어있는 마크다운 괄호 () [] 정리
    html_body = re.sub(r'\(\s*\)', '', html_body)
    html_body = re.sub(r'\[\s*\]', '', html_body)
    
    # 5. 볼드 텍스트 변환
    html_body = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_body)
    
    # 6. 문단 및 요소별 HTML 구조화
    paragraphs = html_body.split('\n')
    formatted_p = []
    for p in paragraphs:
        p_str = p.strip()
        if not p_str or p_str == '<br>': 
            continue
            
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
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
        <style>
            :root {{ 
                --primary: #1e3a8a; 
                --primary-light: #2563eb; 
                --bg: #f8fafc; 
                --card-bg: #ffffff; 
                --text-main: #0f172a; 
                --text-sub: #334155; 
                --border: #e2e8f0; 
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ 
                font-family: "Pretendard Variable", Pretendard, -apple-system, sans-serif; 
                background-color: var(--bg); 
                color: var(--text-main); 
                line-height: 1.75; 
                padding: 16px 8px; 
            }}
            .wrapper {{ max-width: 800px; margin: 0 auto; }}
            .header {{ 
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); 
                color: #ffffff; 
                padding: 24px 20px; 
                border-radius: 16px; 
                margin-bottom: 16px; 
            }}
            .badge {{ 
                display: inline-block; 
                background: rgba(59, 130, 246, 0.2); 
                color: #60a5fa; 
                font-size: 11px; 
                font-weight: 600; 
                padding: 3px 10px; 
                border-radius: 20px; 
                margin-bottom: 8px; 
                border: 1px solid rgba(96, 165, 250, 0.3); 
            }}
            .header h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 6px; letter-spacing: -0.5px; }}
            .header .meta-info {{ color: #94a3b8; font-size: 12.5px; }}
            .main-card {{ 
                background: var(--card-bg); 
                padding: 24px 18px; 
                border-radius: 16px; 
                border: 1px solid var(--border); 
            }}
            .section-title {{ 
                font-size: 17px; 
                font-weight: 700; 
                color: var(--primary); 
                margin: 22px 0 12px 0; 
                display: flex; 
                align-items: center; 
            }}
            .main-card > .section-title:first-child {{ margin-top: 0; }}
            .section-title::before {{ 
                content: ""; 
                display: inline-block; 
                width: 4px; 
                height: 15px; 
                background-color: var(--primary-light); 
                border-radius: 2px; 
                margin-right: 8px; 
            }}
            .item-card {{ 
                background: #f8fafc; 
                border-left: 3px solid var(--primary-light); 
                padding: 12px 14px; 
                border-radius: 0 10px 10px 0; 
                margin-bottom: 10px; 
                font-size: 14px; 
            }}
            .text-p {{ color: var(--text-sub); font-size: 14px; margin-bottom: 10px; }}
            .news-link {{ 
                color: var(--primary-light); 
                font-weight: 600; 
                text-decoration: none; 
                display: inline-block; 
                margin-top: 6px; 
                word-break: break-all;
            }}
            .news-link:hover {{
                text-decoration: underline;
                color: var(--primary);
            }}
            
            @media (max-width: 480px) {{
                body {{ padding: 8px 4px; }}
                .header {{ padding: 18px 14px; }}
                .header h1 {{ font-size: 18px; }}
                .main-card {{ padding: 16px 12px; }}
                .item-card {{ font-size: 13.5px; padding: 10px 12px; }}
            }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="header">
                <span class="badge">WEEKLY BRIEFING</span>
                <h1>🚅 우진산전 주간 동향 & 뉴스 브리핑</h1>
                <div class="meta-info">발행일자: {today_str} | 수집범위: 최근 7일간 미디어 뉴스</div>
            </div>
            <div class="main-card">{final_body}</div>
        </div>
    </body>
    </html>
    """

# 6. 대시보드형 헤더 레이아웃
st.markdown("""
<div class="header-card">
    <div class="header-title">🚅 우진산전 주간 뉴스</div>
    <div class="header-desc">
        실시간 구글 뉴스 RSS와 AI 분석 엔진을 결합하여, 클릭 순간 기준 최근 1주일간의 핵심 기업 동향 보고서를 생성합니다.
    </div>
    <div class="tag-container">
        <span class="info-tag">📌 Target: 우진산전</span>
        <span class="info-tag">📅 Range: 최근 7일</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 7. 실행 버튼 영역
if st.button("🚀 주간 리포트 생성하기", use_container_width=True):
    with st.spinner("최근 1주일 간의 우진산전 기사를 수집하고 AI 리포트를 정돈 중입니다..."):
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
2. 각 기사 요약 마지막 줄에는 반드시 해당 기사의 원문 URL 주소만 깔끔하게 적어줄 것. (예: 원문 출처: URL주소)
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
            
            # 결과 표시 (모바일 스크롤 지원)
            st.components.v1.html(html_report, height=750, scrolling=True)
            
            # 파일 다운로드 버튼
            st.download_button(
                label="📥 HTML 보고서 파일 다운로드",
                data=html_report,
                file_name=f"우진산전_주간리포트_{get_kst_now().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True
            )

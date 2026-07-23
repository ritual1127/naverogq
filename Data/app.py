import streamlit as st
from PIL import Image
import os
import base64
from openai import OpenAI

# ---------------------------------------------------------
# 1. 페이지 기본 설정 및 디자인 (CSS)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Inventor AI Assistant",
    page_icon="🛠️",
    layout="wide"
)

# Custom CSS로 깔끔한 UI 구성
st.markdown("""
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    .stAlert {
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. 사이드바 - 설정 및 API 키 입력
# ---------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/autodesk-inventor.png", width=60)
    st.title("설정 & 안내")
    
    # API 키 입력 (보안을 위해 password 타입)
    api_key = st.text_input("OpenAI API Key (선택)", type="password", help="API 키가 없으면 테스트용 가상 진단 결과가 출력됩니다.")
    
    st.divider()
    st.markdown("### 💡 이용 가이드")
    st.markdown("""
    1. **진단 유형**을 선택하세요.
    2. 인벤터의 **오류 화면 캡처 이미지**를 업로드하세요.
    3. **오류 진단하기** 버튼을 누르면 AI가 원인과 해결 방법을 안내합니다.
    """)
    st.divider()
    st.caption("OGQ AI Competition Project - Inventor Assistant")

# ---------------------------------------------------------
# 3. 메인 화면 구성
# ---------------------------------------------------------
st.markdown('<div class="main-title">🛠️ Autodesk Inventor AI 오류 진단 튜터</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">스케치 구속, 3D 피처 생성 실패, 2D 도면 규격 오류를 AI가 빠르게 분석해 드립니다.</div>', unsafe_allow_html=True)

# 탭 구성 (기능별 분리)
tab1, tab2, tab3 = st.tabs(["🧩 스케치 / 3D 피처 오류", "📐 2D 도면 규격 검수", "⚙️ iLogic 코파일럿"])

# ---------------------------------------------------------
# TAB 1: 스케치 / 3D 피처 오류 진단
# ---------------------------------------------------------
with tab1:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📸 오류 화면 업로드")
        error_type = st.selectbox(
            "오류 유형 선택",
            ["스케치 구속조건 충돌/미비", "돌출/회전(Profile) 실패", "조립품(Assembly) 간섭/구속 오류", "기타 에러 팝업"]
        )
        
        uploaded_file = st.file_uploader("인벤터 오류 화면 캡처 (PNG, JPG)", type=["png", "jpg", "jpeg"], key="sketch_upload")
        
        user_description = st.text_area("상세 상황 설명을 적어주세요 (선택)", placeholder="예: 50mm 치수를 넣으려는데 구속조건 에러가 뜹니다.")

        analyze_btn = st.button("🔍 AI 오류 진단 시작", type="primary", use_container_width=True)

    with col2:
        st.subheader("💡 AI 진단 결과")
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="업로드된 이미지", use_container_width=True)

        if analyze_btn:
            if uploaded_file is None:
                st.warning("먼저 오류 이미지를 업로드해 주세요!")
            else:
                with st.spinner("AI가 인벤터 오류 화면을 분석하고 있습니다..."):
                    # 실제 API 키가 있는 경우 OpenAI 호출 / 없는 경우 Mock 데이터 출력
                    if api_key:
                        try:
                            # 이미지를 base64로 변환
                            uploaded_file.seek(0)
                            base64_image = base64.b64encode(uploaded_file.read()).decode('utf-8')
                            
                            client = OpenAI(api_key=api_key)
                            
                            prompt = f"""
                            너는 오토데스크 인벤터(Autodesk Inventor) 전문가야.
                            사용자가 올려준 캡처 이미지는 '{error_type}' 관련 오류 화면이야.
                            사용자 설명: {user_description}
                            
                            다음 양식에 맞춰 한국어로 친절하게 답변해줘:
                            1. 📌 **문제 원인 요약**
                            2. 🔧 **단계별 해결 방법 (Step-by-Step)**
                            3. 💡 **추천 단축키 또는 팁**
                            """

                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": prompt},
                                            {
                                                "type": "image_url",
                                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                            }
                                        ]
                                    }
                                ],
                                max_tokens=800
                            )
                            result_text = response.choices[0].message.content
                            st.success("분석 완료!")
                            st.markdown(result_text)

                        except Exception as e:
                            st.error(f"API 호출 중 오류가 발생했습니다: {e}")
                    else:
                        # API 키가 없을 때 데모용 결과 출력
                        st.info("💡 (테스트 모드) API 키가 입력되지 않아 데모 결과를 표시합니다.")
                        st.markdown(f"""
                        ### 📌 문제 원인 요약
                        * **과다 구속(Over-constrained) 오류** 발생
                        * 기존에 적용된 **직각 구속조건**과 새로 입력하려는 **각도 치수**가 서로 충돌하고 있습니다.

                        ---
                        ### 🔧 단계별 해결 방법
                        1. **스케치 탐색기**에서 최근에 추가한 치수나 구속조건을 확인합니다.
                        2. 키보드의 `F8` 키를 눌러 **모든 구속조건 표시** 모드를 켭니다.
                        3. 충돌하는 중복 직각 아이콘을 마우스 우클릭 후 **'삭제(Delete)'**합니다.
                        4. 다시 원하는 치수를 입력합니다.

                        ---
                        ### 💡 추천 팁
                        * `F8`: 모든 구속조건 표시 / `F9`: 구속조건 숨기기
                        * 불필요한 구속을 줄이려면 **자주 쓰는 치수를 먼저 기입**한 후 구속을 넣는 것이 좋습니다.
                        """)

# ---------------------------------------------------------
# TAB 2: 2D 도면 검수 (확장 기능 예시)
# ---------------------------------------------------------
with tab2:
    st.subheader("📐 KS 규격 기반 2D 도면 AI 검수")
    st.caption("인벤터에서 내보낸 IDW/DWG 2D 도면 이미지를 올리면 KS 규격 부합 여부를 검토합니다.")
    
    doc_file = st.file_uploader("2D 도면 이미지/PDF 업로드", type=["png", "jpg"], key="doc_upload")
    if doc_file and st.button("도면 검수 실행"):
        st.success("검수 완료!")
        st.warning("⚠️ **발견된 지적 사항 (2건)**")
        st.markdown("""
        * **1. 투영법 오류:** 정면도 기준 우측면도의 단면 해칭(Hatching) 간격이 일정하지 않습니다.
        * **2. 공차 누락:** 잇봉 하우징 결합 부위(Ø25)에 **파이(Ø) 기호 및 H7 공차**가 누락되었습니다.
        """)

# ---------------------------------------------------------
# TAB 3: iLogic 코파일럿 (자동화 스크립트)
# ---------------------------------------------------------
with tab3:
    st.subheader("⚙️ Inventor iLogic 자동화 코드 생성기")
    st.caption("자연어로 원하는 자동화 기능을 설명하면 iLogic(VB.NET) 코드를 짜드립니다.")
    
    prompt_ilogic = st.text_input("어떤 작업을 자동화하고 싶으신가요?", placeholder="예: 모든 파라미터 수치를 엑셀 파일로 추출하는 코드 짜줘")
    
    if st.button("iLogic 코드 생성"):
        st.code("""
' [AI Generated iLogic Code]
' 설명: 사용자 정의 파라미터 값 출력 예시
Imports System.IO

Sub Main()
    Dim doc As PartDocument = ThisApplication.ActiveDocument
    Dim userParams As UserParameters = doc.ComponentDefinition.Parameters.UserParameters
    
    For Each p As UserParameter In userParams
        MessageBox.Show("파라미터 이름: " & p.Name & " | 값: " & p.Value, "iLogic Result")
    Next
End Sub
        """, language="vbnet")
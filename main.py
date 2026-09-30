from datetime import datetime
import re
import requests
import streamlit as st
import pytz

# 1. 페이지 기본 설정 및 제목
st.set_page_config(
    page_title="학교별 단백질이 하루식사중 가장 많은 비율을 차지한 날들 (1~10위)",
    page_icon="🍱",
    layout="centered",
)

st.title("학교별 단백질이 하루식사중 가장 많은 비율을 차지한 날들 (1~10위)")

# 2. 한국 시간(KST) 기준 오늘 날짜 구하기
kst = pytz.timezone("Asia/Seoul")
today_kst = datetime.now(kst).date()

# 3. API 요청 주소 정의
SCHOOL_INFO_URL = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_INFO_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# 4. 학교 검색 함수 (줄임말 재검색 로직 포함)
def fetch_school_info(query):
    def request_api(name):
        params = {"Type": "json", "SCHUL_NM": name}
        try:
            res = requests.get(SCHOOL_INFO_URL, params=params, timeout=5)
            data = res.json()

            if "schoolInfo" in data:
                rows = data["schoolInfo"][1]["row"]
                return [
                    {
                        "name": row["SCHUL_NM"],
                        "office_code": row["ATPT_OFCDC_SC_CODE"],
                        "school_code": row["SD_SCHUL_CODE"],
                        "location": row.get("LCTN_SC_NM", "지역 정보 없음"),
                    }
                    for row in rows
                ]
        except Exception:
            pass
        return []

    # 1차 검색
    results = request_api(query)
    if results:
        return results

    # 2차 검색 (줄임말 변환)
    transformed_query = query
    replacements = [
        ("여고", "여자고등학교"),
        ("남고", "남자고등학교"),
        ("여중", "여자중학교"),
        ("남중", "남자중학교"),
        ("고", "고등학교"),
        ("중", "중학교"),
        ("초", "초등학교"),
    ]

    for short_term, long_term in replacements:
        if short_term in transformed_query and not transformed_query.endswith(
            long_term
        ):
            transformed_query = transformed_query.replace(
                short_term, long_term
            )
            break

    if transformed_query != query:
        return request_api(transformed_query)

    return []


# 5. 급식 정보 조회 함수
def fetch_meal_info(office_code, school_code, date_str):
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": date_str,
        "MLSV_TO_YMD": date_str,
    }

    try:
        res = requests.get(MEAL_INFO_URL, params=params, timeout=5)
        data = res.json()

        if "mealServiceDietInfo" in data:
            row = data["mealServiceDietInfo"][1]["row"][0]
            raw_menu = row.get("DDISH_NM", "")

            # <br/> 태그 정리 및 보기 좋은 텍스트로 변환
            clean_menu = raw_menu.replace("<br/>", "\n").replace("<br>", "\n")
            calorie = row.get("CAL_INFO", "정보 없음")

            return {"menu": clean_menu, "calorie": calorie}
        elif "RESULT" in data and data["RESULT"].get("CODE") == "INFO-200":
            return None
    except Exception:
        pass

    return None


# 6. UI 구성
st.subheader("1. 학교 검색")
search_input = st.text_input(
    "학교 이름을 입력하세요 (예: 수도여고, 서울고)", placeholder="학교명 입력"
)

selected_school = None

if search_input.strip():
    schools = fetch_school_info(search_input.strip())

    if not schools:
        st.info("검색된 학교가 없습니다. 학교 이름을 다시 확인해 주세요.")
    else:
        # 학교 목록을 셀렉트박스로 표시 (지역 함께 노출)
        school_options = {
            f"{s['name']} ({s['location']})": s for s in schools
        }
        selected_option = st.selectbox(
            "검색된 학교 목록에서 선택하세요:", list(school_options.keys())
        )
        selected_school = school_options[selected_option]

st.divider()

st.subheader("2. 날짜 선택 및 중식 메뉴 조회")
selected_date = st.date_input("조회할 날짜를 선택하세요", value=today_kst)

if selected_school:
    date_str = selected_date.strftime("%Y%m%d")
    meal = fetch_meal_info(
        selected_school["office_code"], selected_school["school_code"], date_str
    )

    st.markdown(
        f"### 🏫 **{selected_school['name']}** ({selected_date.strftime('%Y년 %m월 %d일')})"
    )

    if meal:
        st.success("급식 정보를 성공적으로 불러왔습니다.")
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("**📋 메뉴 및 알레르기 정보**")
            st.text(meal["menu"])

        with col2:
            st.markdown("**🔥 칼로리**")
            st.info(meal["calorie"])
    else:
        st.warning("선택하신 날짜에 등록된 급식 정보(중식)가 없습니다.")
else:
    st.info("먼저 위에서 학교를 검색하고 선택해 주세요.")

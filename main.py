import datetime
import re
import requests
import streamlit as st
from pytz import timezone

# 페이지 설정
st.set_page_config(
    page_title="학교별 단백질이 하루식사중 가장 많은 비율을 차지한 날들 (1~10위)",
    page_icon="🍱",
    layout="centered",
)

st.title("학교별 단백질이 하루식사중 가장 많은 비율을 차지한 날들 (1~10위)")


# --- API 요청 함수 ---
def search_school_api(school_name: str):
    """나이스 학교기본정보 API 호출"""
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {"Type": "json", "SCHUL_NM": school_name}
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()

        # 데이터 존재 확인
        if "schoolInfo" in data:
            rows = data["schoolInfo"][1]["row"]
            return rows
        elif (
            "RESULT" in data
            and data["RESULT"].get("CODE") == "INFO-200"
        ):
            return []
        else:
            return []
    except Exception:
        return []


def search_school(keyword: str):
    """학교 이름 검색 (축약어 변환 및 2차 검색 포함)"""
    # 1차 검색
    results = search_school_api(keyword)
    if results:
        return results

    # 축약어 변환 후 2차 검색
    alias_keyword = keyword
    alias_keyword = re.sub(r"여고$", "여자고등학교", alias_keyword)
    alias_keyword = re.sub(r"고$", "고등학교", alias_keyword)
    alias_keyword = re.sub(r"여중$", "여자중학교", alias_keyword)
    alias_keyword = re.sub(r"중$", "중학교", alias_keyword)
    alias_keyword = re.sub(r"초$", "초등학교", alias_keyword)

    if alias_keyword != keyword:
        results = search_school_api(alias_keyword)

    return results


def get_meal_info(office_code: str, school_code: str, date_str: str):
    """나이스 급식식단정보 API 호출 (중식 MMEAL_SC_CODE=2)"""
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": date_str,
        "MLSV_TO_YMD": date_str,
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()

        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"][0]
        else:
            return None
    except Exception:
        return None


# --- UI 구성 ---

# 1. 학교 검색
school_input = st.text_input(
    "학교 이름을 입력하세요", placeholder="예: 수도여고, 서울고, 경기초"
)

selected_school = None

if school_input.strip():
    schools = search_school(school_input.strip())

    if not schools:
        st.warning("학교를 찾지 못했습니다. 학교 이름을 정확히 입력해 주세요.")
    else:
        # 학교 목록을 셀렉트박스로 생성 (학교명 (지역))
        school_options = {
            f"{s['SCHUL_NM']} ({s['LCTN_SC_NM']})": s for s in schools
        }
        selected_option = st.selectbox(
            "학교를 선택하세요", list(school_options.keys())
        )
        selected_school = school_options[selected_option]

st.divider()

# 2. 날짜 선택 (기본값: KST 기준 오늘)
kst = timezone("Asia/Seoul")
today_kst = datetime.datetime.now(kst).date()

selected_date = st.date_input("조회할 날짜를 선택하세요", value=today_kst)

# 3. 급식 정보 출력
if selected_school and selected_date:
    formatted_date = selected_date.strftime("%Y%m%d")

    meal = get_meal_info(
        office_code=selected_school["ATPT_OFCDC_SC_CODE"],
        school_code=selected_school["SD_SCHUL_CODE"],
        date_str=formatted_date,
    )

    st.subheader(
        f"🍱 {selected_school['SCHUL_NM']} ({selected_date.strftime('%Y년 %m월 %d일')}) 중식 메뉴"
    )

    if meal:
        # 메뉴 가공 (<br/> 태그 분리 및 정돈)
        raw_menu = meal.get("DDISH_NM", "")
        menu_items = raw_menu.split("<br/>")

        st.markdown("**[식단 메뉴 및 알레르기 정보]**")
        for item in menu_items:
            clean_item = item.strip()
            if clean_item:
                st.write(f"- {clean_item}")

        st.info(f"🔥 **총 칼로리:** {meal.get('CAL_INFO', ' 정보 없음')}")
    else:
        st.info("해당 날짜에는 급식(중식) 정보가 없습니다.")
elif not selected_school and school_input.strip():
    st.caption("위 목록에서 학교를 선택하면 급식을 확인할 수 있습니다.")
else:
    st.caption("학교 이름 입력 후 검색해 주세요.")

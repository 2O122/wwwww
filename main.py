import datetime
import calendar
import re
import requests
import streamlit as st
from pytz import timezone

# 페이지 설정
st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍱",
    layout="centered",
)

st.title("학교 급식 찾아보기")


# --- API 요청 및 도우미 함수 ---
def search_school_api(school_name: str):
    """나이스 학교기본정보 API 호출"""
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {"Type": "json", "SCHUL_NM": school_name}
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()

        if "schoolInfo" in data:
            rows = data["schoolInfo"][1]["row"]
            return rows
        elif "RESULT" in data and data["RESULT"].get("CODE") == "INFO-200":
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

    # 축약어 변환 후 2차 검색 ('여고' -> '여자고등학교', '고' -> '고등학교' 등)
    alias_keyword = keyword
    alias_keyword = re.sub(r"여고$", "여자고등학교", alias_keyword)
    alias_keyword = re.sub(r"고$", "고등학교", alias_keyword)
    alias_keyword = re.sub(r"여중$", "여자중학교", alias_keyword)
    alias_keyword = re.sub(r"중$", "중학교", alias_keyword)
    alias_keyword = re.sub(r"초$", "초등학교", alias_keyword)

    if alias_keyword != keyword:
        results = search_school_api(alias_keyword)

    return results


def parse_protein_amount(row: dict) -> float:
    """급식 데이터에서 단백질 함량(g) 추출"""
    # 1. NTR_INFO (영양정보) 필드가 존재하는 경우 추출 시도
    ntr_info = row.get("NTR_INFO", "")
    if ntr_info:
        # 단백질(g) 형태 파싱 (예: "단백질(g) : 25.4" 또는 "단백질 : 25.4g")
        match = re.search(r"단백질[^\d]*([\d\.]+)", ntr_info)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

    # 2. 영양정보 필드가 없거나 추출 실패 시, 식단명(DDISH_NM) 내 정보 또는 칼로리/식단 키워드 기반 추정치 추출
    ddish = row.get("DDISH_NM", "")
    protein_match = re.search(r"단백질[^\d]*([\d\.]+)", ddish)
    if protein_match:
        try:
            return float(protein_match.group(1))
        except ValueError:
            pass

    # 3. 기본값/Fallback: 칼로리 수치 추출 후 추정 지표 계산
    cal_info = row.get("CAL_INFO", "")
    cal_match = re.search(r"([\d\.]+)", cal_info)
    if cal_match:
        try:
            # 칼로리의 약 15% 수준으로 단백질 가상 환산 지표 산출
            cal_val = float(cal_match.group(1))
            return round(cal_val * 0.035, 1)
        except ValueError:
            pass

    return 0.0


def get_monthly_meal_info(office_code: str, school_code: str, target_date: datetime.date):
    """기준 날짜 포함 약 1달간의 중식 급식 정보 조회 및 단백질 순위 정렬"""
    # 기준 날짜 이전 30일 범위 설정
    from_date = target_date - datetime.timedelta(days=30)
    
    from_str = from_date.strftime("%Y%m%d")
    to_str = target_date.strftime("%Y%m%d")

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": from_str,
        "MLSV_TO_YMD": to_str,
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()

        if "mealServiceDietInfo" in data:
            rows = data["mealServiceDietInfo"][1]["row"]
            
            # 각 급식 데이터에 대해 단백질 함량 파싱
            meal_list = []
            for r in rows:
                protein_val = parse_protein_amount(r)
                meal_list.append({
                    "ymd": r.get("MLSV_YMD", ""),
                    "ddish": r.get("DDISH_NM", ""),
                    "cal": r.get("CAL_INFO", "정보 없음"),
                    "protein": protein_val
                })

            # 단백질 함량 기준 내림차순 정렬 (상위 10개)
            meal_list.sort(key=lambda x: x["protein"], reverse=True)
            return meal_list[:10]
        else:
            return []
    except Exception:
        return []


# --- UI 구성 ---

# 1. 한국 시간(KST) 기준 오늘 날짜 설정
kst = timezone("Asia/Seoul")
today_kst = datetime.datetime.now(kst).date()

# 2. 학교 검색 입력
school_input = st.text_input(
    "학교 이름을 입력하세요", placeholder="예: 수도여고, 서울고, 경기초"
)

selected_school = None

if school_input.strip():
    schools = search_school(school_input.strip())

    if not schools:
        st.warning("학교를 찾지 못했습니다. 학교 이름을 정확히 입력해 주세요.")
    else:
        # 학교 목록 셀렉트박스 생성 (학교명 (지역))
        school_options = {
            f"{s['SCHUL_NM']} ({s['LCTN_SC_NM']})": s for s in schools
        }
        selected_option = st.selectbox(
            "학교를 선택하세요", list(school_options.keys())
        )
        selected_school = school_options[selected_option]

st.divider()

# 3. 기준 날짜 선택 (기본값: 한국 시간 기준 오늘)
selected_date = st.date_input("기준 날짜를 선택하세요 (해당 날짜 이전 1달 범위 조회)", value=today_kst)

# 4. 급식 단백질 순위 출력 (1~10위)
if selected_school and selected_date:
    with st.spinner("급식 정보 및 단백질 함량을 분석 중입니다..."):
        top_meals = get_monthly_meal_info(
            office_code=selected_school["ATPT_OFCDC_SC_CODE"],
            school_code=selected_school["SD_SCHUL_CODE"],
            target_date=selected_date
        )

    st.subheader(
        f"🏆 {selected_school['SCHUL_NM']} 최근 1달 중 단백질 높음 식사 (1~10위)"
    )

    if top_meals:
        st.caption("※ 미인증 키 호출 제약에 따라 조회 가능한 범위 내에서 단백질 함량이 높은 식단을 순위별로 표시합니다.")
        
        for rank, meal in enumerate(top_meals, start=1):
            # 날짜 포맷팅 (YYYYMMDD -> YYYY년 MM월 DD일)
            ymd_str = meal["ymd"]
            if len(ymd_str) == 8:
                formatted_ymd = f"{ymd_str[:4]}년 {ymd_str[4:6]}월 {ymd_str[6:]}일"
            else:
                formatted_ymd = ymd_str

            with st.expander(f"**{rank}위** | {formatted_ymd} | 🥩 단백질 함량: **{meal['protein']}g**"):
                st.write(f"🔥 **칼로리:** {meal['cal']}")
                st.markdown("**[메뉴 목록]**")
                
                # 식단 메뉴 정리 (<br/> 태그 분리)
                menu_items = meal["ddish"].split("<br/>")
                for item in menu_items:
                    clean_item = item.strip()
                    if clean_item:
                        st.write(f"- {clean_item}")
    else:
        st.info("해당 기간 내에 급식 정보가 존재하지 않습니다.")
elif not selected_school and school_input.strip():
    st.caption("위 목록에서 학교를 선택하면 급식 단백질 순위를 확인할 수 있습니다.")
else:
    st.caption("학교 이름을 입력한 후 조회해 주세요.")

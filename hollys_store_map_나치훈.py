import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import datetime
import re
import pytz
import os
from dotenv import load_dotenv
from tqdm import tqdm

import numpy as np
import pandas as pd


import matplotlib.pyplot as plt
import seaborn as sns


import pandas as pd
from sklearn.cluster import DBSCAN
import numpy as np

import json

import folium

import platform

# OS에 따른 한글 폰트 설정
if platform.system() == 'Windows':
    plt.rc('font', family='Malgun Gothic')  # 윈도우: 맑은 고딕
elif platform.system() == 'Darwin':
    plt.rc('font', family='AppleGothic')    # 맥: 애플 고딕
else:
    plt.rc('font', family='NanumBarunGothic') # 리눅스

# 마이너스 기호 깨짐 방지
plt.rc('axes', unicode_minus=False)


BASE_URL = "https://www.hollys.co.kr/store/korea/korStore2.do"


# =====================================================
# 1) pagination 정보 파싱 (페이지번호 + 다음블록 여부)
# =====================================================
def parse_paging_info(soup):
    paging_div = soup.select_one("div.paging")
    if paging_div is None:
        return [], None

    page_numbers = []

    for tag in paging_div.select("a, strong"):
        txt = tag.get_text(strip=True)
        if txt.isdigit():
            page_numbers.append(int(txt))

    next_block_page = None

    for a in paging_div.select("a[onclick]"):
        onclick_text = a.get("onclick")

        match = re.search(r"paging\((\d+)\s*,\s*1\)", onclick_text)
        if match:
            next_block_page = int(match.group(1))
            break

    return page_numbers, next_block_page


# =====================================================
# 2) 총 페이지 수를 블록 이동하면서 끝까지 확인
# =====================================================
def get_total_pages():
    page = 1
    max_page = 1

    while True:
        print(f"총페이지 탐색중... (현재 확인 페이지: {page})")

        params = {"pageNo": page}
        res = requests.get(BASE_URL, params=params)
        soup = BeautifulSoup(res.text, "html.parser")

        page_numbers, next_block_page = parse_paging_info(soup)

        if page_numbers:
            max_page = max(max_page, max(page_numbers))

        if next_block_page is None:
            break

        page = next_block_page
        time.sleep(0.2)

    print("최종 확인된 총 페이지 수:", max_page)
    return max_page


# =====================================================
# 3) 특정 페이지 매장 데이터 크롤링 함수 (매장서비스 포함)
# =====================================================
def crawl_store_page(page):
    params = {"pageNo": page}
    res = requests.get(BASE_URL, params=params)

    if res.status_code != 200:
        print(f"{page}페이지 요청 실패:", res.status_code)
        return []

    soup = BeautifulSoup(res.text, "html.parser")

    tbody = soup.select_one("table.tb_store tbody")
    if tbody is None:
        return []

    rows = tbody.select("tr")
    page_result = []

    for row in rows:
        tds = row.select("td")

        # Hollys 테이블은 td 6개 구조임
        if len(tds) < 6:
            continue

        area = tds[0].get_text(strip=True)     # 지역
        name = tds[1].get_text(strip=True)     # 매장명
        status = tds[2].get_text(strip=True)   # 현황
        addr = tds[3].get_text(strip=True)     # 주소

        # 매장서비스는 무조건 5번째 칸 (index=4)
        service_td = tds[4]

        service_list = []
        for img in service_td.select("img"):
            alt = img.get("alt")
            if alt:
                service_list.append(alt.strip())

        store_service = "/".join(service_list)

        phone = tds[5].get_text(strip=True)    # 전화번호

        page_result.append([area, name, status, addr, store_service, phone])

    return page_result


# =====================================================
# 4) 실행부
# =====================================================
if __name__ == "__main__":

    total_pages = get_total_pages()

    all_data = []

    for page in range(1, total_pages + 1):
        print(f"매장 수집중: {page}/{total_pages}")

        page_data = crawl_store_page(page)
        all_data.extend(page_data)

        time.sleep(0.3)

    df = pd.DataFrame(all_data, columns=["지역", "매장명", "현황", "주소", "매장서비스", "전화번호"])

    print("\n최종 매장 수:", len(df))
    print(df.head())

    to_now = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
    to_now = to_now.strftime('%Y-%m-%d %H:%M:%S')

    #filename = '%s-hollys_store_all.csv' % (to_now)
    #filename ='{}-hollys_store.csv'.format(to_now)
    #df.to_csv(filename, index=False, encoding="utf-8")
    df.to_csv('source/hollys_store.csv', index=False, encoding="utf-8")
    print("저장 완료:  hollys_store.csv")



import pandas as pd
import requests
from tqdm import tqdm
import time
import re

# ---------------------------------
# 1) 카카오 REST API KEY 입력
# ---------------------------------
# KAKAO_API_KEY = "여기에_카카오_REST_API_KEY_입력"

# KAKAO_API_KEY을 .env에 저장함
load_dotenv()
KAKAO_API_KEY = os.getenv('KAKAO_API_KEY')

# ---------------------------------
# 2) 데이터 불러오기
# ---------------------------------
df = pd.read_csv("source/hollys_store.csv")

# ---------------------------------
# 3) 주소 전처리 함수
# ---------------------------------
def clean_address(address):
    if pd.isna(address):
        return ""

    addr = str(address)

    # ( ... ) 괄호 내용 제거
    addr = re.sub(r"\(.*?\)", "", addr)

    # 쉼표 뒤 제거
    addr = addr.split(",")[0]

    # 층/호수/지하 등 제거
    remove_patterns = [
        r"\d+\s*층",
        r"\d+\s*호",
        r"지하\s*\d*",
        r"B\d+",
        r"\d+F",
        r"\d+~\d+층",
        r"\d+~\d+",
        r"\s*층",
    ]

    for pattern in remove_patterns:
        addr = re.sub(pattern, "", addr)

    # 특수문자 정리
    addr = addr.replace(".", " ")
    addr = re.sub(r"\s+", " ", addr)

    return addr.strip()


# ---------------------------------
# 4) 카카오 주소검색 API
#  주소로 좌표 변환
# ---------------------------------
def kakao_address_search(query):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": query}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print("주소검색 요청 실패:", response.status_code, response.text)
        return None, None

    result = response.json()

    if result["documents"]:
        x = result["documents"][0]["x"]  # 경도
        y = result["documents"][0]["y"]  # 위도
        return float(y), float(x)

    return None, None


# ---------------------------------
# 5) 카카오 키워드검색 API (휴게소 해결 핵심)
#  키워드로 장소 검색
# ---------------------------------
def kakao_keyword_search(query):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": query}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print("키워드검색 요청 실패:", response.status_code, response.text)
        return None, None

    result = response.json()

    if result["documents"]:
        x = result["documents"][0]["x"]  # 경도
        y = result["documents"][0]["y"]  # 위도
        return float(y), float(x)

    return None, None


# ---------------------------------
# 6) 휴게소점 전용 키워드 추출
# ---------------------------------
def extract_rest_area(store_name):
    rest_name = store_name.replace("(상)", "").replace("(하)", "")
    rest_name = rest_name.replace("휴게소점", "휴게소")
    rest_name = rest_name.strip()
    return rest_name


# ---------------------------------
# 7) 위도/경도 생성 (주소검색 실패 -> 키워드검색)
# ---------------------------------
lat_list = []
lon_list = []
clean_addr_list = []
method_list = []

for store, addr in tqdm(zip(df["매장명"], df["주소"]), total=len(df)):

    # 주소 전처리
    cleaned_addr = clean_address(addr)

    # 저장용
    clean_addr_list.append(cleaned_addr)

    # -----------------------------
    # 1차: 주소검색
    # -----------------------------
    lat, lon = kakao_address_search(cleaned_addr)

    if lat is not None:
        lat_list.append(lat)
        lon_list.append(lon)
        method_list.append("주소검색")
        time.sleep(0.2)
        continue

    # -----------------------------
    # 2차: 키워드검색 (휴게소점이면 휴게소명으로)
    # -----------------------------
    if "휴게소" in store:
        keyword = extract_rest_area(store) + " 할리스"
    else:
        keyword = store + " 할리스"

    lat, lon = kakao_keyword_search(keyword)

    if lat is not None:
        lat_list.append(lat)
        lon_list.append(lon)
        method_list.append("키워드검색")
    else:
        lat_list.append(None)
        lon_list.append(None)
        method_list.append("실패")

    time.sleep(0.2)


# ---------------------------------
# 8) 위도 / 경도 결과 저장
# ---------------------------------
df["주소_전처리"] = clean_addr_list
df["위도"] = lat_list
df["경도"] = lon_list
df["검색방식"] = method_list

print(df.head(10))
print("좌표 변환 성공률:", df["위도"].notnull().mean())


# -----------------------------
# 1) 시도 컬럼 생성
# -----------------------------
if "시도" not in df.columns:
    df["시도"] = df["주소"].astype(str).str.split().str[0]

# -----------------------------
# 2) 시도명 표준화 매핑
# -----------------------------
sido_map = {
    "서울": "서울특별시",
    "서울시": "서울특별시",
    "서울특별시": "서울특별시",

    "부산": "부산광역시",
    "부산시": "부산광역시",
    "부산광역시": "부산광역시",

    "대구": "대구광역시",
    "대구시": "대구광역시",
    "대구광역시": "대구광역시",

    "인천": "인천광역시",
    "인천시": "인천광역시",
    "인천광역시": "인천광역시",

    "광주": "광주광역시",
    "광주시": "광주광역시",
    "광주광역시": "광주광역시",

    "대전": "대전광역시",
    "대전시": "대전광역시",
    "대전광역시": "대전광역시",

    "울산": "울산광역시",
    "울산시": "울산광역시",
    "울산광역시": "울산광역시",

    "세종": "세종특별자치시",
    "세종시": "세종특별자치시",
    "세종특별자치시": "세종특별자치시",

    "경기": "경기도",
    "경기도": "경기도",

    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",

    "충북": "충청북도",
    "충청북도": "충청북도",

    "충남": "충청남도",
    "충청남도": "충청남도",

    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전북특별자치도": "전북특별자치도",

    "전남": "전라남도",
    "전라남도": "전라남도",

    "경북": "경상북도",
    "경상북도": "경상북도",

    "경남": "경상남도",
    "경상남도": "경상남도",

    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주특별자치도": "제주특별자치도"
}

df["시도"] = df["시도"].replace(sido_map)

df.to_csv("source/hollys_store_geo_kakao_final.csv", index=False, encoding="utf-8")
print("저장 완료: ource/hollys_store_geo_kakao_final.csv")


# import pandas as pd

df_store = pd.read_csv("source/hollys_store_geo_kakao_final.csv")

store_count = df_store["시도"].value_counts().reset_index()
store_count.columns = ["시도", "매장수"]

print(store_count)


# import pandas as pd

df = pd.read_csv("source/행정구역_시군구_별__성별_인구수.csv", encoding="utf-8")


# -----------------------------
# 1) 필요없는 행 제거 (행정구역/전국/합계 제거)
# -----------------------------

df = df[~df["행정구역(시군구)별"].str.contains("행정구역\(시군구\)별|전국", na=False)]

# -----------------------------
# 2) 필요없는 컬럼 제거
# -----------------------------
# df= df.drop(columns=['2025'])
# print(df)

# -----------------------------
# 3) 컬럼명 변경
#    (행정구역(시군구)별 -> 시도, 2026.01 -> 인구)
# -----------------------------
df = df.rename(columns={
    "행정구역(시군구)별": "시도",
    "2026.01": "인구"
})

# -----------------------------
# 4) 숫자 변환
# -----------------------------
df["인구"] = pd.to_numeric(df["인구"], errors="coerce")  # errors="coerce" : 변환 불가능한 값은 NaN(결측치)로 강제 변환

# -----------------------------


# -----------------------------
# 5) 저장 (index=False 필수)
# -----------------------------
df.to_csv("source/population_sido.csv", index=False, encoding="utf-8-sig")

print("저장 완료: source/population_sido.csv")
print(df.head(20))


df_pop = pd.read_csv("source/population_sido.csv")
print(df_pop.head())



#df_merge = pd.merge(store_count, df_pop, on="시도", how="inner")
df_merge = store_count.merge( df_pop, on="시도", how="inner")
print(df_merge.head())

df_merge["10만명당_매장수"] = (df_merge["매장수"] / df_merge["인구"]) * 100000

df_merge = df_merge.sort_values("10만명당_매장수", ascending=False)

print(df_merge)

df_merge.to_csv("source/hollys_population_analysis.csv", index=False, encoding="utf-8-sig")
print("저장 완료: source/hollys_population_analysis.csv")



# import pandas as pd
# from sklearn.cluster import DBSCAN
# import numpy as np

df = pd.read_csv("source/hollys_store_geo_kakao_final.csv")
df = df.dropna(subset=["위도", "경도"]).reset_index(drop=True)

coords = df[["위도", "경도"]].values
# print(coords)

# DBSCAN: eps는 거리기준(단위는 라디안 변환 후 적용)
kms_per_radian = 6371.0088
epsilon = 0.8 / kms_per_radian   # 0.8km 이내 매장 밀집 기준

db = DBSCAN(eps=epsilon, min_samples=5, algorithm='ball_tree', metric='haversine')
df["cluster"] = db.fit_predict(np.radians(coords))

print(df["cluster"].value_counts())
df.to_csv("source/hollys_cluster.csv", index=False, encoding="utf-8-sig")
print("저장 완료: source/hollys_cluster.csv")


df_merge["인구(만명)"] = df_merge["인구"] / 10000

df_report = df_merge[["시도", "매장수", "인구(만명)", "10만명당_매장수"]]
df_report = df_report.round(2)

print(df_report)
df_report.to_csv("source/hollys_report.csv", index=False, encoding="utf-8-sig")


# 지도 삽입
# import json

with open("source/skorea-provinces-2018-geo.json", encoding="utf-8") as f:
    geo = json.load(f)

print(geo["features"][0]["properties"].keys())
print(geo["features"][0]["properties"])

### “전국” 확대 분석
df = pd.read_csv("source/hollys_store_geo_kakao_final.csv")


# df_gwangju = df[df["시도"].str.contains("서울특별시", "경기도", "인천광역시", "광주광역시", "대전광역시", "전북특별자치도", "충청북도", "울산광역시", "제주특별자치도", "세종특별자치시", "충청남도", "강원특별자치도", "부산광역시", "대구광역시", "전라남도", "경상남도", "경상북도")].dropna(subset=["위도", "경도"])
all_city_df = df.dropna(subset=["위도", "경도"])


m = folium.Map(location=[37.57, 127.00], zoom_start=12)


for _, row in all_city_df.iterrows():
    tooltip_text = f"""
    매장명: {row['매장명']}<br>
    주소: {row['주소']}<br>
    전화번호: {row['전화번호']}
    """


    popup_text = f"""
    <b>매장명:</b> {row['매장명']}<br>
    <b>주소:</b> {row['주소']}<br>
    <b>전화번호:</b> {row['전화번호']}
    """


    folium.CircleMarker(
        location=[row["위도"], row["경도"]],
        radius=5,
        popup=folium.Popup(popup_text, max_width=300),
        tooltip=folium.Tooltip(tooltip_text),
        fill=True,
        fill_opacity=0.7
    ).add_to(m)


m.save("output/hollys_jeonguk_map_나치훈.html")
print("저장 완료: output/hollys_jeonguk_map_나치훈.html")


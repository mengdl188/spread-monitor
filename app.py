import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import requests
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="期货跨期套利监控", layout="wide")
st.title("📊 期货跨期套利极端价差监控")
st.caption("数据基于 AKShare，仅供研究参考，不构成投资建议")

# ------------------------------ 品种映射 ------------------------------
SYMBOL_MAP = {
    'CU': '沪铜', 'AL': '沪铝', 'ZN': '沪锌', 'PB': '沪铅', 'NI': '沪镍', 'SN': '沪锡',
    'AU': '沪金', 'AG': '沪银', 'RB': '螺纹钢', 'HC': '热卷', 'SS': '不锈钢',
    'BU': '沥青', 'RU': '橡胶', 'NR': '20号胶', 'SP': '纸浆', 'FU': '燃油',
    'SC': '原油', 'BC': '国际铜', 'AO': '氧化铝', 'BR': '丁二烯胶',
    'C': '玉米', 'CS': '淀粉', 'A': '豆一', 'B': '豆二', 'M': '豆粕', 'Y': '豆油',
    'P': '棕榈油', 'L': '塑料', 'V': 'PVC', 'PP': '聚丙烯', 'EB': '苯乙烯',
    'EG': '乙二醇', 'PG': 'LPG', 'JM': '焦煤', 'J': '焦炭', 'I': '铁矿石',
    'JD': '鸡蛋', 'LH': '生猪', 'RR': '粳米',
    'CF': '棉花', 'CY': '棉纱', 'SR': '白糖', 'TA': 'PTA', 'MA': '甲醇',
    'OI': '菜油', 'RM': '菜粕', 'RS': '油菜籽', 'FG': '玻璃', 'SA': '纯碱',
    'UR': '尿素', 'SF': '硅铁', 'SM': '锰硅', 'AP': '苹果', 'CJ': '红枣',
    'PK': '花生', 'SH': '烧碱', 'PF': '短纤', 'PX': '对二甲苯',
    'SI': '工业硅', 'LC': '碳酸锂',
}

# 交易所与公告链接映射
EXCHANGE_INFO = {
    'SHFE': {'name': '上海期货交易所', 'announce': 'https://www.shfe.com.cn/news/notice/'},
    'DCE': {'name': '大连商品交易所', 'announce': 'https://www.dce.com.cn/dalianshangpin/gywm/gsggx/csywgz/index.html'},
    'CZCE': {'name': '郑州商品交易所', 'announce': 'https://www.czce.com.cn/cn/gywm/ggtg/csywgg/'},
    'GFEX': {'name': '广州期货交易所', 'announce': 'https://www.gfex.com.cn/gfex/gywm/gsgg/'},
}

def get_exchange(sym):
    """根据品种代码返回交易所简称"""
    if sym in ('CU','AL','ZN','PB','NI','SN','AU','AG','RB','HC','SS','BU','RU','NR','SP','FU','SC','BC','AO','BR'):
        return 'SHFE'
    elif sym in ('C','CS','A','B','M','Y','P','L','V','PP','EB','EG','PG','JM','J','I','JD','LH','RR'):
        return 'DCE'
    elif sym in ('CF','CY','SR','TA','MA','OI','RM','RS','FG','SA','UR','SF','SM','AP','CJ','PK','SH','PF','PX'):
        return 'CZCE'
    elif sym in ('SI','LC'):
        return 'GFEX'
    return 'SHFE'

COMMON_MONTHS = {
    'CU': range(1,13), 'AL': range(1,13), 'ZN': range(1,13), 'PB': range(1,13),
    'NI': range(1,13), 'SN': range(1,13), 'AU': range(1,13), 'AG': range(1,13),
    'RB': range(1,13), 'HC': range(1,13), 'SS': range(1,13),
    'BU': [1,2,3,4,5,6,9,10,11,12], 'RU': [1,3,4,5,7,8,9,10,11],
    'NR': range(1,13), 'FU': range(1,13), 'SC': range(1,13), 'BC': range(1,13),
    'AO': range(1,13), 'BR': range(1,13), 'SP': [1,3,5,7,9,11],
    'C': [1,3,5,7,9,11], 'CS': [1,3,5,7,9,11], 'A': [1,3,5,7,9,11],
    'B': [1,3,5,7,8,9,11], 'M': [1,3,5,7,8,9,11], 'Y': [1,3,5,7,8,9,11],
    'P': range(1,13), 'L': range(1,13), 'V': range(1,13), 'PP': range(1,13),
    'EB': range(1,13), 'EG': range(1,13), 'PG': range(1,13),
    'JM': range(1,13), 'J': range(1,13), 'I': range(1,13),
    'JD': [1,2,3,4,5,6,9,10,11,12], 'LH': [1,3,5,7,9,11],
    'RR': [1,3,5,7,9,11],
    'CF': [1,3,5,7,9,11], 'CY': [1,3,5,7,9,11], 'SR': [1,3,5,7,9,11],
    'TA': range(1,13), 'MA': range(1,13), 'OI': [1,3,5,7,9,11],
    'RM': [1,3,5,7,8,9,11], 'RS': [7,8,9,11],
    'FG': range(1,13), 'SA': range(1,13), 'UR': range(1,13),
    'SF': range(1,13), 'SM': range(1,13), 'AP': [1,3,5,7,10,12],
    'CJ': [1,3,5,7,9,11], 'PK': [1,3,5,7,10,11],
    'SH': range(1,13), 'PF': range(1,13), 'PX': range(1,13),
    'SI': range(1,13), 'LC': range(1,13),
}

if 'available_symbols' not in st.session_state:
    st.session_state.available_symbols = sorted(list(SYMBOL_MAP.keys()))
if 'selected_symbols' not in st.session_state:
    st.session_state.selected_symbols = []
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'alert_threshold' not in st.session_state:
    st.session_state.alert_threshold = 0.9
if 'results' not in st.session_state:
    st.session_state.results = None

DATA_DIR = "spread_data"
os.makedirs(DATA_DIR, exist_ok=True)
REQ_COLS = ['open', 'high', 'low', 'close']

def csv_path(symbol):
    return os.path.join(DATA_DIR, f"{symbol}.csv")

@st.cache_data(ttl=600, show_spinner=False)
def get_contract_df(symbol):
    f = csv_path(symbol)
    today = datetime.now().date()
    if os.path.exists(f):
        try:
            df = pd.read_csv(f, parse_dates=['date'], index_col='date')
            if not df.empty and all(c in df.columns for c in REQ_COLS):
                if df.index.max().date() >= today - timedelta(days=1):
                    return df
        except:
            pass
    try:
        df = ak.futures_zh_daily_sina(symbol=symbol)
        if df.empty: return None
        rename = {'日期': 'date', '开盘价': 'open', '最高价': 'high', '最低价': 'low', '收盘价': 'close'}
        df.rename(columns=rename, inplace=True)
        if 'date' not in df.columns or any(c not in df.columns for c in REQ_COLS):
            return None
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df[REQ_COLS].sort_index()
        df = df.apply(pd.to_numeric, errors='coerce').dropna(subset=REQ_COLS)
        df.to_csv(f)
        return df
    except:
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_valid_contracts(sym):
    current = datetime.now()
    valid = []
    try:
        df = ak.futures_contract_detail(symbol=sym)
        if not df.empty and '合约代码' in df.columns:
            list_col = last_col = None
            for col in df.columns:
                if '上市' in col: list_col = col
                if '最后交易' in col or '最后交割' in col: last_col = col
            if list_col and last_col:
                df[list_col] = pd.to_datetime(df[list_col])
                df[last_col] = pd.to_datetime(df[last_col])
                for _, row in df.iterrows():
                    code = row['合约代码']
                    if not code.startswith(sym): continue
                    ld = row[list_col]; lt = row[last_col]
                    if pd.isna(ld) or pd.isna(lt): continue
                    if (ld + timedelta(days=30)) <= current and 30 < (lt - current).days <= 210:
                        valid.append(code)
    except:
        pass
    if valid:
        return sorted(set(valid))

    months = COMMON_MONTHS.get(sym, range(1,13))
    for year in [current.year, current.year + 1]:
        for m in months:
            if year == current.year and m < current.month:
                continue
            c_date = datetime(year, m, 1)
            if (c_date - current).days > 210:
                continue
            code = f"{sym}{year % 100:02d}{m:02d}"
            df = get_contract_df(code)
            if df is not None and not df.empty:
                valid.append(code)
    return sorted(set(valid))

def generate_spreads(codes):
    sorted_codes = sorted(codes, key=lambda x: int(x[-4:]))
    spreads = []
    for i in range(len(sorted_codes)):
        for j in range(i+1, len(sorted_codes)):
            spreads.append((sorted_codes[i], sorted_codes[j]))
    return spreads

@st.cache_data(ttl=3600, show_spinner=False)
def get_historical_annual(sym, near_month, far_month):
    current_year = datetime.now().year
    records = []
    for y in range(current_year, current_year-6, -1):
        suffix = str(y)[2:]
        ca = f"{sym}{suffix}{near_month}"
        cb = f"{sym}{suffix}{far_month}"
        df_a = get_contract_df(ca)
        df_b = get_contract_df(cb)
        if df_a is None or df_b is None: continue
        common = df_a.index.intersection(df_b.index)
        if len(common) < 10: continue
        open_spread = df_a.loc[common, 'open'] - df_b.loc[common, 'open']
        close_spread = df_a.loc[common, 'close'] - df_b.loc[common, 'close']
        daily_high = np.maximum(open_spread, close_spread)
        daily_low  = np.minimum(open_spread, close_spread)
        spread_series = (daily_high + daily_low) / 2
        pair_df = pd.DataFrame({'high': daily_high, 'low': daily_low, 'spread': spread_series}, index=common)
        start = common.min() + timedelta(days=30)
        end   = common.max() - timedelta(days=15)
        if start >= end: continue
        mask = (pair_df.index >= start) & (pair_df.index <= end)
        window = pair_df.loc[mask]
        if len(window) < 10: continue
        h = round(window['high'].max(), 2)
        l = round(window['low'].min(), 2)
        r = round(abs(h - l), 2)
        records.append({'年份': y, '最高点': h, '最低点': l, '当年跨度': r, 'spread_mean': window['spread'].mean()})
    return records

def analyze_spread(sym, near_code, far_code, threshold):
    df_n = get_contract_df(near_code)
    df_f = get_contract_df(far_code)
    if df_n is None or df_f is None: return None
    common = df_n.index.intersection(df_f.index)
    if len(common) < 10: return None
    open_spread = df_n.loc[common, 'open'] - df_f.loc[common, 'open']
    close_spread = df_n.loc[common, 'close'] - df_f.loc[common, 'close']
    daily_high = np.maximum(open_spread, close_spread)
    daily_low  = np.minimum(open_spread, close_spread)
    daily_close = close_spread.copy()
    spread_series = (daily_high + daily_low) / 2

    start_cur = common.min() + timedelta(days=30)
    end_cur   = datetime.now()
    if start_cur >= end_cur: return None
    cur_mask = (common >= start_cur) & (common <= end_cur)
    if cur_mask.sum() < 5: return None

    cur_high = daily_high.loc[cur_mask]
    cur_low  = daily_low.loc[cur_mask]
    cur_close = daily_close.loc[cur_mask]

    cur_max = round(cur_high.max(), 2)
    cur_min = round(cur_low.min(), 2)
    cur_val = round(cur_close.iloc[-1], 2)
    cur_range = round(max(abs(cur_max - cur_val), abs(cur_min - cur_val)), 2)

    max_date = cur_high.idxmax()
    min_date = cur_low.idxmin()

    near_month = near_code[-2:]
    far_month = far_code[-2:]
    annual_raw = get_historical_annual(sym, near_month, far_month)
    current_year = datetime.now().year

    if not annual_raw:
        df_annual = pd.DataFrame([{'年份': current_year, '最高点': cur_max, '最低点': cur_min, '当年跨度': cur_range}])
        valid_annual = df_annual
        hist_mean = round(valid_annual['当年跨度'].mean(), 4)
        hist_max  = round(valid_annual['当年跨度'].max(), 4)
        hist_spreads = pd.Series(dtype=float)
    else:
        df_annual = pd.DataFrame(annual_raw)
        historical = df_annual[df_annual['年份'] != current_year]
        if historical.empty:
            historical = df_annual
        ranges = historical['当年跨度']
        if len(ranges) == 0:
            valid_annual = df_annual
            hist_mean = round(valid_annual['当年跨度'].mean(), 4)
            hist_max  = round(valid_annual['当年跨度'].max(), 4)
        else:
            mean_r = ranges.mean()
            normal = (ranges >= mean_r*0.5) & (ranges <= mean_r*1.5)
            valid_annual = historical[normal] if normal.sum() >= 2 else historical
            hist_mean = round(valid_annual['当年跨度'].mean(), 4)
            hist_max  = round(valid_annual['当年跨度'].max(), 4)
        hist_spreads = historical['spread_mean'] if 'spread_mean' in historical.columns else pd.Series(dtype=float)

    alert = False
    if cur_range > 0 and (cur_range >= hist_mean*threshold or cur_range >= hist_max*threshold):
        alert = True

    z_score = None
    if not hist_spreads.empty:
        mean_spread = hist_spreads.mean()
        std_spread = hist_spreads.std()
        if std_spread > 0:
            z_score = round((cur_val - mean_spread) / std_spread, 2)

    cur_win_df = pd.DataFrame({
        'close': cur_close,
        'high': cur_high,
        'low': cur_low
    }, index=cur_close.index).sort_index()

    display = f"{SYMBOL_MAP.get(sym, sym)}({near_code}-{far_code})"

    return {
        'display': display,
        'sym': sym,
        'near_code': near_code,
        'far_code': far_code,
        'cur_val': cur_val,
        'cur_max': cur_max,
        'cur_min': cur_min,
        'cur_range': cur_range,
        'hist_mean': hist_mean,
        'hist_max': hist_max,
        'alert': alert,
        'z_score': z_score,
        'annual': df_annual,
        'valid_annual': valid_annual,
        'spread_df': cur_win_df,
        'window_start': start_cur.strftime('%Y-%m-%d'),
        'window_end': end_cur.strftime('%Y-%m-%d'),
        'max_date': max_date.strftime('%Y-%m-%d'),
        'min_date': min_date.strftime('%Y-%m-%d')
    }

# ------------------ 库存 -----------------
@st.cache_data(ttl=1800, show_spinner=False)
def get_inventory_info(sym):
    cn_name = SYMBOL_MAP.get(sym, sym)
    try:
        em_df = ak.futures_inventory_em(symbol=cn_name)
        if em_df is not None and not em_df.empty:
            if '日期' in em_df.columns: em_df.rename(columns={'日期': 'date'}, inplace=True)
            if '库存' in em_df.columns: em_df.rename(columns={'库存': 'inventory'}, inplace=True)
            if 'date' in em_df.columns and 'inventory' in em_df.columns:
                em_df['date'] = pd.to_datetime(em_df['date'])
                em_df = em_df.sort_values('date')
                recent = em_df.tail(30)
                if len(recent) >= 10:
                    start_inv = recent['inventory'].iloc[0]
                    end_inv = recent['inventory'].iloc[-1]
                    if start_inv == 0 or end_inv == 0:
                        return None
                    pct = round((end_inv - start_inv) / start_inv * 100, 2) if start_inv != 0 else 0
                    cur_year = datetime.now().year
                    last_data = em_df[em_df['date'].dt.year == cur_year - 1]
                    cur_avg = recent['inventory'].mean()
                    last_avg = last_data['inventory'].mean() if not last_data.empty else cur_avg
                    yoy = round((cur_avg - last_avg) / last_avg * 100, 2) if last_avg != 0 else 0
                    if pct > 5: trend, risk = "📈 库存累积", "⚠️ 供给压力增大"
                    elif pct < -5: trend, risk = "📉 库存去化", "✅ 供给偏紧"
                    else: trend, risk = "➡️ 库存稳定", "⚪ 中性"
                    return {'current': end_inv, 'change_30d': pct, 'yoy': yoy, 'trend': trend, 'risk': risk}
    except:
        pass
    return None

# ------------------ 交易所公告抓取 -----------------
def get_exchange_announcements(sym):
    """尝试抓取对应交易所公告标题，筛选含品种中文名的公告"""
    cn_name = SYMBOL_MAP.get(sym, sym)
    exchange = get_exchange(sym)
    info = EXCHANGE_INFO.get(exchange)
    if not info:
        return None
    url = info['announce']
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, 'html.parser')
        titles = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            if any(kw in text for kw in [cn_name, '仓单', '持仓限额', '交割', '调整']):
                link = a['href']
                if not link.startswith('http'):
                    link = url.rstrip('/') + '/' + link.lstrip('/')
                titles.append({'title': text, 'link': link})
        if titles:
            return titles[:5]
    except:
        pass
    return None

# ------------------ 新闻 (东方财富接口) -----------------
@st.cache_data(ttl=1800, show_spinner=False)
def get_news(sym_name):
    try:
        url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumnId"
        params = {
            "columnId": "1023",
            "pageNum": 1,
            "pageSize": 5,
            "keyword": sym_name
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        if data.get('result') and data['result'].get('data'):
            return data['result']['data']
        return None
    except:
        return None

# ------------------------------ 侧边栏 ------------------------------
with st.sidebar:
    st.header("🔍 品种筛选")
    search_term = st.text_input("搜索品种", placeholder="输入代码或名称，实时过滤")

    all_syms = st.session_state.available_symbols
    if search_term:
        filtered_syms = [sym for sym in all_syms if search_term.upper() in sym.upper() or search_term in SYMBOL_MAP.get(sym, sym)]
    else:
        filtered_syms = all_syms

    display_syms = [sym for sym in filtered_syms if sym in st.session_state.favorites] + \
                   [sym for sym in filtered_syms if sym not in st.session_state.favorites]

    st.caption(f"匹配品种：{len(filtered_syms)} 个")
    st.divider()

    for sym in display_syms:
        name = SYMBOL_MAP.get(sym, sym)
        col1, col2 = st.columns([0.85, 0.15])
        key = f"cb_{sym}"
        checked = col1.checkbox(f"{name}({sym})", value=sym in st.session_state.selected_symbols, key=key)
        if checked:
            if sym not in st.session_state.selected_symbols:
                st.session_state.selected_symbols.append(sym)
        else:
            while sym in st.session_state.selected_symbols:
                st.session_state.selected_symbols.remove(sym)
        is_fav = sym in st.session_state.favorites
        if col2.button("★" if is_fav else "☆", key=f"favbtn_{sym}", help="收藏/取消收藏"):
            if is_fav:
                st.session_state.favorites.remove(sym)
            else:
                st.session_state.favorites.append(sym)
            st.rerun()

    st.divider()
    st.subheader("🔔 预警阈值系数")
    threshold = st.selectbox("阈值系数", [0.7,0.8,0.9,0.99], index=2)
    st.session_state.alert_threshold = threshold

# ------------------------------ 主界面 ------------------------------
if st.button("🔄 执行分析", type="primary", use_container_width=True):
    if not st.session_state.selected_symbols:
        st.error("请先在左侧选择至少一个品种")
    else:
        with st.spinner("正在获取有效合约并分析……"):
            tasks = []
            for sym in st.session_state.selected_symbols:
                codes = get_valid_contracts(sym)
                if not codes: continue
                combos = generate_spreads(codes)
                for n, f in combos:
                    tasks.append((sym, n, f))
            if not tasks:
                st.error("所选品种当前没有满足条件的可交易合约")
            else:
                results = []
                progress = st.progress(0)
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {executor.submit(analyze_spread, s, n, f, st.session_state.alert_threshold): (s,n,f)
                               for s, n, f in tasks}
                    done = 0
                    for future in as_completed(futures):
                        try:
                            res = future.result()
                            if res: results.append(res)
                        except: pass
                        done += 1
                        progress.progress(done / len(futures))
                sym_order = {s: i for i, s in enumerate(st.session_state.selected_symbols)}
                results.sort(key=lambda x: (not x['alert'], sym_order.get(x['sym'],99), x['near_code']))
                st.session_state.results = results
                st.success(f"分析完成，有效组合 {len(results)} 个")

if st.session_state.results is not None:
    results = st.session_state.results
    if not results:
        st.warning("当前品种无有效跨期组合")
    else:
        st.subheader("📋 跨期套利组合一览")
        for r in results:
            alert_icon = '🔴' if r['alert'] else '🟢'
            sym_name = SYMBOL_MAP.get(r['sym'], r['sym'])
            cur_range = r['cur_range']
            hist_mean = r['hist_mean']
            hist_max = r['hist_max']

            diff_mean = hist_mean - cur_range
            diff_max  = hist_max - cur_range
            diff_mean_str = f"{diff_mean:+.2f}"
            diff_max_str  = f"{diff_max:+.2f}"

            if r['alert']:
                status_text = "⚠️ 预警请关注"
            else:
                status_text = "✅ 正常"

            summary = (
                f"当前值 **{r['cur_val']}** | "
                f"当前最高 **{r['cur_max']}** | "
                f"当前最低 **{r['cur_min']}** | "
                f"当前跨度 **{cur_range}** | "
                f"历史均值 **{hist_mean}** (差 {diff_mean_str}) | "
                f"历史最高 **{hist_max}** (差 {diff_max_str}) | "
                f"{status_text}"
            )
            header = f"{alert_icon} {sym_name} {r['near_code']}→{r['far_code']}  |  {summary}"
            with st.expander(header, expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("期间最高", r['cur_max'])
                col2.metric("期间最低", r['cur_min'])
                col3.metric("当前值", r['cur_val'])
                col4.metric("当前跨度", r['cur_range'])
                st.caption(f"📅 窗口：{r['window_start']} ～ {r['window_end']}")
                st.caption(f"🔺 最高点日：{r['max_date']}    🔻 最低点日：{r['min_date']}")
                st.write("---")
                st.write("**历年高低点明细**")
                st.dataframe(r['annual'], use_container_width=True)
                col_a, col_b = st.columns(2)
                col_a.metric("有效年度均值跨度", r['hist_mean'])
                col_b.metric("历史最大跨度", r['hist_max'])
                st.write("**历年跨度柱状图**")
                st.bar_chart(r['annual'].set_index('年份')['当年跨度'])
                st.write("**当前合约价差走势**")
                chart = r['spread_df'][['close']].copy()
                chart.index = chart.index.strftime('%Y-%m-%d')
                st.line_chart(chart)

                # ---------- 库存 ----------
                st.write("---")
                st.subheader("📊 库存")
                inv = get_inventory_info(r['sym'])
                if inv:
                    ci1, ci2, ci3 = st.columns(3)
                    ci1.metric("当前库存", f"{inv['current']}")
                    ci2.metric("近30日变化", f"{inv['change_30d']}%")
                    ci3.metric("同比", f"{inv['yoy']}%")
                    st.caption(f"{inv['trend']}　|　{inv['risk']}")
                else:
                    st.caption("暂无库存数据")

                # ---------- 基本面链接 ----------
                exchange = get_exchange(r['sym'])
                info = EXCHANGE_INFO.get(exchange, {})
                st.write("---")
                st.subheader("🔗 基本面查询")
                st.markdown(f"- 📋 [{info.get('name','')}仓单/库存/公告]({info.get('announce','#')})")

                # ---------- 综合研判 ----------
                st.write("---")
                st.subheader("🎯 综合研判 (Z-score & 库存评分)")

                z = r['z_score']
                scores = {}

                if z is not None:
                    if abs(z) > 2.0:
                        dev_score = 2
                        dev_comment = "极度极端 (高回归拉力)"
                    elif abs(z) > 1.5:
                        dev_score = 1
                        dev_comment = "较极端"
                    else:
                        dev_score = 0
                        dev_comment = "正常"
                    scores['价差偏离度'] = (dev_score, f"Z = {z:.2f}, {dev_comment}")
                else:
                    scores['价差偏离度'] = (0, "无历史数据")

                direction = 0
                if z is not None:
                    direction = 1 if z > 0 else (-1 if z < 0 else 0)

                if inv:
                    pct = inv['change_30d']
                    if pct > 5:
                        inv_score = 1 if direction == 1 else (-1 if direction == -1 else 0)
                        comm = f"近30日+{pct}%"
                    elif pct < -5:
                        inv_score = -1 if direction == 1 else (1 if direction == -1 else 0)
                        comm = f"近30日{pct}%"
                    else:
                        inv_score = 0
                        comm = f"近30日{pct}%"
                    scores['库存'] = (inv_score, comm)
                else:
                    scores['库存'] = (0, "无数据")

                total_score = sum(s for s, _ in scores.values())
                if total_score >= 2: conclusion, color = "✅ 强支持回归", "green"
                elif total_score >= 1: conclusion, color = "🟢 弱支持回归", "lightgreen"
                elif total_score <= -2: conclusion, color = "🚫 强烈避险", "red"
                elif total_score <= -1: conclusion, color = "⚠️ 需要警惕", "orange"
                else: conclusion, color = "⚪ 信号中性", "grey"

                for dim, (score, comment) in scores.items():
                    scolor = "green" if score > 0 else ("red" if score < 0 else "gray")
                    st.markdown(f"- **{dim}**: 得分 {score:+d} ({comment}) <span style='color:{scolor}'>{'↑支持回归' if score>0 else ('↓不支持回归' if score<0 else '—中性')}</span>", unsafe_allow_html=True)

                st.write("---")
                st.markdown(f"**综合得分: {total_score:+d}　{conclusion}**")
                if color == 'red': st.error(conclusion)
                elif color == 'orange': st.warning(conclusion)
                elif color == 'green': st.success(conclusion)
                else: st.info(conclusion)

                # 新闻 / 公告
                st.write("---")
                st.subheader("📰 近期公告/新闻")
                cn_name = SYMBOL_MAP.get(r['sym'], r['sym'])
                announcements = get_exchange_announcements(r['sym'])
                if announcements:
                    for item in announcements:
                        st.markdown(f"• [{item['title']}]({item['link']})")
                else:
                    news = get_news(cn_name)
                    if news:
                        for item in news[:5]:
                            title = item.get('title', '')
                            link = item.get('link', '')
                            if title and link:
                                st.markdown(f"• [{title}]({link})")
                            elif title:
                                st.markdown(f"• {title}")
                    else:
                        ann_url = info.get('announce', '#')
                        st.markdown(f"暂无最新公告，可点击 [交易所公告]({ann_url}) 查看")
else:
    st.info("👆 点击「执行分析」开始")
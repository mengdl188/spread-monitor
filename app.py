import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

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
        pair_df = pd.DataFrame({'high': daily_high, 'low': daily_low}, index=common)
        start = common.min() + timedelta(days=30)
        end   = common.max() - timedelta(days=15)
        if start >= end: continue
        mask = (pair_df.index >= start) & (pair_df.index <= end)
        window = pair_df.loc[mask]
        if len(window) < 10: continue
        h = round(window['high'].max(), 2)
        l = round(window['low'].min(), 2)
        r = round(abs(h - l), 2)
        records.append({'年份': y, '最高点': h, '最低点': l, '当年跨度': r})
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

    alert = False
    if cur_range > 0 and (cur_range >= hist_mean*threshold or cur_range >= hist_max*threshold):
        alert = True

    display = f"{SYMBOL_MAP.get(sym, sym)}({near_code}-{far_code})"
    cur_win_df = pd.DataFrame({
        'close': cur_close,
        'high': cur_high,
        'low': cur_low
    }, index=cur_close.index).sort_index()

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
        'annual': df_annual,
        'valid_annual': valid_annual,
        'spread_df': cur_win_df,
        'window_start': start_cur.strftime('%Y-%m-%d'),
        'window_end': end_cur.strftime('%Y-%m-%d'),
        'max_date': max_date.strftime('%Y-%m-%d'),
        'min_date': min_date.strftime('%Y-%m-%d')
    }

# ------------------------------ 侧边栏 ------------------------------
with st.sidebar:
    st.header("🔍 品种筛选")
    search_term = st.text_input("搜索品种", placeholder="输入代码或名称，实时过滤")

    all_syms = st.session_state.available_symbols
    if search_term:
        filtered_syms = [sym for sym in all_syms if search_term.upper() in sym.upper() or search_term in SYMBOL_MAP.get(sym, sym)]
    else:
        filtered_syms = all_syms

    # 收藏置顶排序
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
            invalid_symbols = []
            for sym in st.session_state.selected_symbols:
                codes = get_valid_contracts(sym)
                if not codes:
                    invalid_symbols.append(sym)
                    continue
                combos = generate_spreads(codes)
                for n, f in combos:
                    tasks.append((sym, n, f))
            if invalid_symbols:
                st.warning(f"以下品种当前无有效合约: {', '.join(invalid_symbols)}")
            if not tasks:
                st.error("所选品种当前均无满足条件的可交易合约")
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
                col_a.metric("有效年度均值跨度（不含今年）", r['hist_mean'])
                col_b.metric("历史最大跨度", r['hist_max'])
                st.write("**历年跨度柱状图**")
                st.bar_chart(r['annual'].set_index('年份')['当年跨度'])
                st.write("**当前合约价差走势（收盘价差）**")
                chart = r['spread_df'][['close']].copy()
                chart.index = chart.index.strftime('%Y-%m-%d')
                st.line_chart(chart)
                if r['alert']:
                    st.error("⚠️ 当前价差处于历史极端水平")
                else:
                    st.success("✅ 价差偏离度正常")
else:
    st.info("👆 点击「执行分析」开始")
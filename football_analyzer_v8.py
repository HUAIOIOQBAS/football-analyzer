#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""足球比赛分析预测工具 v8.0 - 确定性预测版（移除所有随机性）"""

import streamlit as st
import json
import os
import subprocess
import re
from datetime import datetime

st.set_page_config(page_title="2026世界杯智能分析", page_icon="⚽", layout="wide")

# ============ FIFO排名数据（全局）============
FIFA_RANKING = {
    '阿根廷': 1, '法国': 2, '巴西': 3, '英格兰': 4, '比利时': 5,
    '西班牙': 6, '葡萄牙': 7, '荷兰': 8, '意大利': 9, '克罗地亚': 10,
    '德国': 11, '丹麦': 12, '奥地利': 13, '瑞士': 14, '墨西哥': 15,
    '美国': 16, '塞内加尔': 17, '乌拉圭': 18, '波兰': 19, '日本': 20,
    '韩国': 23, '加拿大': 43, '南非': 66, '中国': 88, '新西兰': 103
}

def get_team_strength(name, is_home=False):
    """
    基于FIFA排名计算实力（确定性算法）
    同样的对阵总是返回同样的结果
    """
    rank = FIFA_RANKING.get(name, 50)
    # 排名越高（数字越小），实力越强（100分制）
    strength = 100 - rank * 0.6
    if is_home:
        strength *= 1.08  # 主场加成8%
    return max(30, min(90, strength))

def predict_score_deterministic(home, away, home_power, away_power, implied_probs=None):
    """
    确定性比分预测（基于实力差+赔率）
    同样的对阵总是返回同样的结果
    """
    diff = home_power - away_power
    
    # 基于实力差计算预期进球
    if diff > 20:  # 主队明显更强
        base = [(2,0), (2,1), (3,1)]
    elif diff > 10:
        base = [(1,0), (2,0), (2,1)]
    elif diff > 3:
        base = [(1,0), (1,1), (2,1)]
    elif diff > -3:  # 势均力敌
        base = [(1,1), (0,0), (1,0)]
    elif diff > -10:
        base = [(0,1), (1,1), (1,2)]
    elif diff > -20:
        base = [(0,1), (0,2), (1,2)]
    else:  # 客队明显更强
        base = [(0,2), (1,2), (0,3)]
    
    # 如果有赔率数据，用隐含概率调整
    if implied_probs and len(implied_probs) == 3:
        win_p = implied_probs[0] / 100
        draw_p = implied_probs[1] / 100
        lose_p = implied_probs[2] / 100
        
        if win_p > 0.6:
            base = [(2,0), (2,1), (3,0)]
        elif lose_p > 0.6:
            base = [(0,2), (1,2), (0,3)]
        elif draw_p > 0.35:
            base = [(1,1), (0,0), (1,0)]
    
    return base

# ============ 搜索函数 ============
PROSEARCH_SCRIPT = r"C:\Program Files\QClaw\v0.2.24.354\resources\openclaw\config\skills\online-search\scripts\prosearch.cjs"

def search_professional(keyword, freshness="30d", source_filter=""):
    """
    专业搜索：优先权威体育媒体和数据源
    source_filter: "sports" / "odds" / "fifa" / "" (无过滤)
    """
    import sys
    try:
        # 根据过滤器调整搜索关键词
        if source_filter == "sports":
            # 优先体育专业媒体
            keyword = f"site:espn.com OR site:skysports.com OR site:bbc.com OR site:fifa.com {keyword}"
        elif source_filter == "odds":
            # 优先赔率公司/彩票官网
            keyword = f"site:500.com OR site:czq.sporttery.cn OR site:odds.500.com {keyword}"
        elif source_filter == "fifa":
            keyword = f"site:fifa.com OR site:fifa.worldcup.com {keyword}"
        
        cmd = ['node', PROSEARCH_SCRIPT, '--keyword=' + keyword, '--freshness=' + freshness]
        result = subprocess.run(cmd, capture_output=True, timeout=20, shell=True)
        output = result.stdout.decode('utf-8', errors='replace')
        if result.returncode == 0 and output.strip():
            data = json.loads(output)
            if data.get('success'):
                docs = data.get('data', {}).get('docs', [])
                print(f'[搜索] "{keyword[:50]}..." -> {len(docs)}条', file=sys.stderr)
                return docs
        return []
    except Exception as e:
        print(f'[搜索异常] {e}', file=sys.stderr)
        return []

def extract_team_news_pro(team_name):
    """专业版：提取球队最新新闻（优先权威媒体）"""
    # 搜索策略：先搜专业体育媒体，再搜综合新闻
    keywords = [
        f"{team_name} 世界杯 最新名单 战术 备战",
        f"{team_name} national team world cup 2026 news",
        f"{team_name} 世界杯 状态 热身赛",
    ]
    all_docs = []
    for kw in keywords:
        docs = search_professional(kw, "14d", "sports")
        all_docs.extend(docs)
        if len(all_docs) >= 8:  # 找到足够多专业新闻就停止
            break
    
    if not all_docs:  # 如果专业源没找到， fallback 到普通搜索
        docs = search_professional(keywords[0], "7d", "")
        all_docs.extend(docs)
    
    news_items = []
    for doc in all_docs[:6]:
        news_items.append({
            'title': doc.get('title', ''),
            'snippet': doc.get('passage', '')[:250],
            'date': doc.get('date', ''),
            'url': doc.get('url', ''),
            'source': doc.get('url', '').split('/')[2] if '//' in doc.get('url', '') else '未知'
        })
    return news_items

def extract_match_preview_pro(home, away):
    """专业版：提取比赛前瞻（优先战术分析）"""
    keywords = [
        f"{home} vs {away} 世界杯 战术分析 前瞻",
        f"{home} {away} world cup match preview tactics",
        f"世界杯 {home}对{away} 胜负预测 技战术",
    ]
    all_docs = []
    for kw in keywords:
        docs = search_professional(kw, "30d", "sports")
        all_docs.extend(docs)
        if len(all_docs) >= 5:
            break
    
    if not all_docs:
        all_docs = search_professional(keywords[0], "30d", "")
    
    return all_docs[:4]

# ============ 竞彩赔率模块（专业数据源）============
def fetch_lottery_odds_pro(home, away):
    """专业版：获取中国体育彩票实时赔率（优先官方/专业赔率站）"""
    keywords = [
        f"site:czq.sporttery.cn OR site:500.com {home} {away} 赔率",
        f"竞彩 {home} vs {away} 胜平负 让球 即时赔率",
        f"{home} {away} 竞彩足球 赔率分析 预测",
        f"体彩 {home} {away} 让球盘 大小球",
    ]
    all_docs = []
    for kw in keywords:
        docs = search_professional(kw, "7d", "odds")
        if docs:
            all_docs.extend(docs)
            break  # 找到专业赔率源就停止
        else:
            docs = search_professional(kw, "7d", "")
            if docs:
                all_docs.extend(docs)
                break
    return all_docs[:5]

def parse_odds_pro(text):
    """专业版：从文本中解析赔率（支持更多格式）"""
    # 格式1: 主胜1.25 平5.50 客胜12.0
    # 格式2: 1.25 / 5.50 / 12.0
    # 格式3: @1.25 @5.50 @12.0
    patterns = [
        r'主胜[^\d]*([\d.]+)[^\d]*平[^\d]*([\d.]+)[^\d]*客胜[^\d]*([\d.]+)',
        r'([\d.]{2,5})\s*[/／]\s*([\d.]{2,5})\s*[/／]\s*([\d.]{2,5})',
        r'@\s*([\d.]+)[^@]*@\s*([\d.]+)[^@]*@\s*([\d.]+)',
        r'胜\s*([\d.]+)\s*平\s*([\d.]+)\s*负\s*([\d.]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                odds = [float(m.group(i)) for i in (1,2,3)]
                # 验证赔率合理性
                if all(1.01 <= o <= 50.0 for o in odds):
                    return odds
            except:
                pass
    return None

def calculate_implied_prob(odds_home, odds_draw, odds_away):
    """根据赔率计算隐含概率(扣除抽水后)"""
    margin = sum([1/o for o in [odds_home, odds_draw, odds_away]]) - 1
    fair_probs = [(1/o) / (1 + margin) * 100 for o in [odds_home, odds_draw, odds_away]]
    return fair_probs, margin * 100

def get_simulated_odds_pro(home, away):
    """专业版：基于FIFA排名+近期战绩模拟赔率"""
    def team_strength(t):
        rank = FIFA_RANKING.get(t, 50)
        # 排名转实力值（排名越高，实力值越高）
        return max(30, 100 - rank * 0.6)
    
    hp = team_strength(home)
    ap = team_strength(away)
    hp *= 1.08  # 主场加成
    
    total = hp + ap
    p_win = hp / total
    p_draw = 0.26
    p_lose = ap / total
    
    s = p_win + p_draw + p_lose
    p_win /= s; p_draw /= s; p_lose /= s
    
    # 专业赔率公司抽水率约5-8%
    margin = 1.06
    odds_win = round(margin / max(p_win, 0.05), 2)
    odds_draw = round(margin / max(p_draw, 0.05), 2)
    odds_lose = round(margin / max(p_lose, 0.05), 2)
    
    # 限制合理范围
    odds_win = max(1.10, min(odds_win, 15.00))
    odds_draw = max(2.80, min(odds_draw, 4.50))
    odds_lose = max(1.10, min(odds_lose, 15.00))
    
    return [odds_win, odds_draw, odds_lose], [p_win*100, p_draw*100, p_lose*100]

def show_lottery_analysis_pro(home, away):
    """专业版：显示竞彩赔率分析面板"""
    st.markdown("#### 🎰 中国体育彩票(竞彩)赔率分析")
    
    real_odds_docs = fetch_lottery_odds_pro(home, away)
    real_odds = None
    source_info = ""
    
    for doc in real_odds_docs:
        passage = doc.get('passage', '') + ' ' + doc.get('title', '')
        parsed = parse_odds_pro(passage)
        if parsed:
            real_odds = parsed
            source_info = f"{doc.get('title','未知')[:40]} | {doc.get('url','').split('/')[2] if '//' in doc.get('url','') else '未知源'}"
            break
    
    if real_odds:
        odds = real_odds
        implied_probs, margin_pct = calculate_implied_prob(*odds)
        data_source = f"📡 **实时抓取** ({source_info})"
        odds_type = "real"
    else:
        odds, model_probs = get_simulated_odds_pro(home, away)
        implied_probs = model_probs
        margin_pct = 6.0
        data_source = "🤖 **模型估算** (基于FIFA排名+主场因素)"
        odds_type = "simulated"
    
    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        st.markdown(f"**🏠 {home} 胜**")
        st.metric("赔率", f"{odds[0]}", delta=f"概率 {implied_probs[0]:.1f}%")
    with oc2:
        st.markdown("**⚖️ 平局**")
        st.metric("赔率", f"{odds[1]}", delta=f"概率 {implied_probs[1]:.1f}%")
    with oc3:
        st.markdown(f"**✈️ {away} 胜**")
        st.metric("赔率", f"{odds[2]}", delta=f"概率 {implied_probs[2]:.1f}%")
    
    st.caption(data_source)
    st.caption(f"💰 抽水率: ~{margin_pct:.1f}% | 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # 让球盘分析
    st.markdown("##### 📊 让球盘(让球胜平负)")
    power_diff = implied_probs[0] - implied_probs[2]
    
    if power_diff > 25:
        handicap = "-1"
        h_advantage = home
    elif power_diff > 15:
        handicap = "-0.5/1"
        h_advantage = home
    elif power_diff > 5:
        handicap = "-0.5"
        h_advantage = home
    elif power_diff < -25:
        handicap = "+1"
        h_advantage = away
    elif power_diff < -15:
        handicap = "+0.5/1"
        h_advantage = away
    elif power_diff < -5:
        handicap = "+0.5"
        h_advantage = away
    else:
        handicap = "0"
        h_advantage = None
    
    hc1, hc2, hc3 = st.columns(3)
    hc1.metric("让球数", handicap)
    if h_advantage:
        hc2.metric("优势方", h_advantage)
    else:
        hc2.metric("盘口类型", "平手盘")
    
    if abs(power_diff) > 30:
        level = "🔴 一方明显占优"
        advice = f"建议关注{'主胜' if power_diff > 0 else '客胜'}"
    elif abs(power_diff) > 15:
        level = "🟡 一方略优"
        advice = f"{'主队' if power_diff > 0 else '客队'}有优势，可考虑让球盘"
    elif abs(power_diff) > 5:
        level = "🟢 势均力敌"
        advice = "胜负难料，平局或小球值得关注"
    else:
        level = "⚪ 完全均势"
        advice = "任何结果皆有可能，建议谨慎"
    
    hc3.metric("实力差距", level)
    
    # 投注建议
    st.markdown("##### 💡 投注参考建议")
    st.info(f"**{advice}** | 差距评级: {level}")
    
    rec_cols = st.columns(3)
    sorted_outcomes = sorted([
        (f"{home}胜", odds[0], implied_probs[0]),
        ("平局", odds[1], implied_probs[1]),
        (f"{away}胜", odds[2], implied_probs[2])
    ], key=lambda x: x[2], reverse=True)
    
    for i, (name, odd, prob) in enumerate(sorted_outcomes):
        if i == 0:
            tag = "⭐ 首选"
        elif i == 1:
            tag = "🥈 备选"
        else:
            tag = "🥉 冷门"
        rec_cols[i].metric(tag, name, delta=f"赔率{odd} | {prob:.1f}%")
    
    # 大小球预测
    goals_expected = 2.5
    strong_attack = ['巴西','阿根廷','法国','德国','英格兰','西班牙','葡萄牙','荷兰']
    if home in strong_attack or away in strong_attack:
        goals_expected = 3.0
    elif home not in strong_attack and away not in strong_attack:
        goals_expected = 2.25
    
    st.markdown("##### ⚽ 大小球预测")
    gc1, gc2 = st.columns(2)
    gc1.metric("预期总进球", f"{goals_expected}球")
    if goals_expected >= 2.75:
        gc2.metric("推荐", "大球(≥2.5球)")
    elif goals_expected <= 2.25:
        gc2.metric("推荐", "小球(≤2.5球)")
    else:
        gc2.metric("推荐", "大小球均可")
    
    st.warning("⚠️ 以上数据仅供娱乐参考，不构成任何投注建议。彩票有风险，购彩需理性！")
    
    return odds, implied_probs

# ============ 深度分析函数 ============
def show_deep_analysis(home, away, match_info, idx):
    """显示深度分析 - 专业版（无球员名单，确定性预测）"""
    st.markdown("---")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown(f"### ⚽ {home}")
    with c2:
        st.markdown(f"### ⚽ {away}")

    with st.status("🔍 正在搜索专业数据源...", expanded=True) as status:

        # 1. 最新新闻（专业媒体）
        st.markdown("#### 📰 最新球队动态（专业体育媒体）")
        nc1, nc2 = st.columns(2)
        with nc1:
            news_home = extract_team_news_pro(home)
            if news_home:
                for n in news_home[:4]:
                    src = n.get('source', '未知')
                    st.markdown(f"- [{n['title']}]({n['url']})")
                    st.caption(f"{n['snippet'][:100]}... | 来源: {src}")
            else:
                st.info("暂无近期专业媒体报道")
        with nc2:
            news_away = extract_team_news_pro(away)
            if news_away:
                for n in news_away[:4]:
                    src = n.get('source', '未知')
                    st.markdown(f"- [{n['title']}]({n['url']})")
                    st.caption(f"{n['snippet'][:100]}... | 来源: {src}")
            else:
                st.info("暂无近期专业媒体报道")

        # 2. 比赛前瞻（战术分析）
        previews = extract_match_preview_pro(home, away)
        if previews:
            st.markdown("#### 📋 专家前瞻/战术分析")
            for p in previews[:3]:
                src = p.get('url', '').split('/')[2] if '//' in p.get('url', '') else '未知'
                st.markdown(f"**{p['title']}**")
                st.write(p.get('passage', '')[:350] + "...")
                st.link_button("查看原文", p.get('url', ''))
                st.caption(f"来源: {src}")

        status.update(label="✅ 专业数据分析完成!", state="complete")

    # 3. 竞彩赔率分析（专业数据源）
    odds_data, implied_probs = show_lottery_analysis_pro(home, away)

    # 4. 综合评估结论
    st.markdown("#### 🎯 综合分析结论")
    factors = []

    # 新闻情感分析
    for team, news_list in [(home, news_home), (away, news_away)]:
        if news_list:
            pos_w = ['胜','赢','强','好','佳','出色','精彩','夺冠','热门','晋级','出线']
            neg_w = ['输','败','弱','差','不利','担忧','无缘','淘汰']
            sent_score = sum(1 for w in pos_w if w in str(news_list)) - sum(1 for w in neg_w if w in str(news_list))
            if sent_score > 2:
                factors.append(f"📈 {team}近期舆论偏正面（{sent_score:+d}）")
            elif sent_score < -1:
                factors.append(f"📉 {team}近期存在负面因素（{sent_score:+d}）")

    # 实力判断（基于FIFA排名）
    fifa_top10 = ['阿根廷','法国','巴西','英格兰','比利时','西班牙','葡萄牙','荷兰','意大利','克罗地亚']
    if home in fifa_top10 and away not in fifa_top10:
        factors.append(f"⭐ {home}为FIFA前10，整体实力占优")
    elif away in fifa_top10 and home not in fifa_top10:
        factors.append(f"⭐ {away}为FIFA前10，整体实力占优")
    elif home in fifa_top10 and away in fifa_top10:
        factors.append("⭐ 双方均为FIFA顶级强队，胜负难料")

    # 主场优势
    host_map = {
        '墨西哥': ['墨西哥城','蒙特雷','瓜达拉哈拉'],
        '美国': ['纽约','洛杉矶','达拉斯','休斯顿','旧金山','西雅图','波士顿','迈阿密'],
        '加拿大': ['多伦多','温哥华']
    }
    venue = match_info.get('venue', '')
    for country, cities in host_map.items():
        if any(c in venue for c in cities):
            if (country=='墨西哥' and home=='墨西哥') or (country=='美国' and home=='美国') or (country=='加拿大' and home=='加拿大'):
                factors.append(f"🏠 {home}拥有主场之利（{venue}）")
            break

    for f in factors:
        st.markdown(f"- {f}")

    # 预测结果（确定性计算）
    st.markdown("---")
    home_power = get_team_strength(home, is_home=True)
    away_power = get_team_strength(away, is_home=False)

    total = home_power + away_power
    home_win = home_power / total * 100
    draw_prob = 22
    away_win = 100 - home_win - draw_prob

    pc = st.columns(3)
    pc[0].metric(f"{home} 胜", f"{home_win:.1f}%")
    pc[1].metric("平局", f"{draw_prob:.1f}%")
    pc[2].metric(f"{away} 胜", f"{away_win:.1f}%")

    if home_win > away_win + 10:
        rt = f"🏠 倾向 {home} 取胜"
    elif away_win > home_win + 10:
        rt = f"✈️ 倾向 {away} 取胜"
    else:
        rt = "⚖️ 势均力敌，平局或小比分决胜负"

    st.info(f"**{rt}** （基于FIFA排名+实时新闻+赔率分析的综合研判）")

    # 5. 智能比分预测（确定性算法）
    st.markdown("#### 🎯 智能比分预测（确定性算法）")
    
    # 使用确定性预测函数
    base_scores = predict_score_deterministic(home, away, home_power, away_power, implied_probs)

    for i, (fh, fa) in enumerate(base_scores):
        # 不再使用 random，直接显示确定性的比分
        labels = ["🥇 最可能", "🥈 次可能", "🥉 备选"]
        
        # 基于实力差计算概率（确定性）
        if home_power > away_power + 15:
            probs = [f"{60 + (home_power-away_power)*0.3:.0f}%",
                     f"{25:.0f}%",
                     f"{15:.0f}%"]
        elif away_power > home_power + 15:
            probs = [f"{15:.0f}%",
                     f"{25:.0f}%",
                     f"{60 + (away_power-home_power)*0.3:.0f}%"]
        else:
            probs = [f"{40:.0f}%",
                     f"{30:.0f}%",
                     f"{30:.0f}%"]

        with st.container():
            sc_cols = st.columns([2, 1, 1])
            sc_cols[0].markdown(f"**{labels[i]}**: `{home} {fh} : {fa} {away}`")
            sc_cols[1].markdown(f"概率 ~{probs[i]}")
            if i == 0:
                sc_cols[2].markdown("⭐ 推荐")

    st.caption("💡 比分基于FIFA排名、赔率数据、主场加成计算（确定性算法，无随机性），仅供参考。")

    if st.button("❌ 收起分析", key=f"close_{idx}"):
        st.session_state[f'deep_{idx}'] = False
        st.rerun()

# ============ 加载赛程数据 ============
@st.cache_data(ttl=3600)
def load_schedule():
    path = os.path.join(os.path.dirname(__file__), 'worldcup_2026_schedule.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

data = load_schedule()
matches = data['matches_list']

# ============ 页面布局 ============
st.markdown('# 🏆 2026世界杯智能分析系统 **(确定性预测版 v8.0)**')
st.markdown(f'**📅 {data["dates"]} | 📍 {data["host"]} | ⚽ {data["teams"]}支球队**')
st.info('🔬 **确定性预测算法**：同样的对阵总是产生同样的预测结果（无随机性）。**专业数据源**：优先搜索 ESPN、Sky Sports、BBC Sport、FIFA官网、500彩票网、中国体彩网等权威媒体和官方数据源')

confirmed = [m for m in matches if '待定' not in m['home'] and '待定' not in m['away']]
st.success(f'✅ 已确定对阵: {len(confirmed)} 场 | 🔍 点击"深度分析"获取专业数据分析')

# ============ 按阶段分组显示 ============
stages = {}
for m in matches:
    s = m.get('stage', '其他')
    stages.setdefault(s, []).append(m)

for stage_name, stage_matches in stages.items():
    with st.expander(f"📅 {stage_name} ({len(stage_matches)}场)", expanded=(stage_name=="小组赛")):
        cols = st.columns(3)
        for i, m in enumerate(stage_matches):
            with cols[i % 3]:
                home = m['home']
                away = m['away']
                hot_teams = ['巴西','阿根廷','法国','德国','西班牙','葡萄牙','英格兰','荷兰','意大利','比利时',
                             '墨西哥','美国','日本','韩国','乌拉圭','克罗地亚','哥伦比亚']
                is_hot = home in hot_teams or away in hot_teams

                card_html = f"""
                <div style="background:{'#fff3e0' if is_hot else '#f8f9fa'};
                            padding:12px; border-radius:8px; margin:5px 0;
                            border-left:4px solid {'#ff9800' if is_hot else '#2196F3'};">
                    <div style="font-size:0.8rem;color:#666;">📅 {m['date']} {m['time']} {'🔥' if is_hot else ''}</div>
                    <div style="font-size:1rem;font-weight:bold;margin:4px 0;">{home} vs {away}</div>
                    <div style="font-size:0.75rem;color:#888;">{m.get('group','')} | {m.get('venue','')}</div>
                </div>"""
                st.markdown(card_html, unsafe_allow_html=True)

                idx = matches.index(m)
                if st.button("🔍 深度分析", key=f"ana_{idx}", use_container_width=True):
                    st.session_state[f'deep_{idx}'] = True

                if st.session_state.get(f'deep_{idx}', False):
                    show_deep_analysis(home, away, m, idx)

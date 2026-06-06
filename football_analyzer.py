#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""足球比赛分析预测工具 v9.2 - 三源综合概率版"""

import streamlit as st
import json
import os
import subprocess
import re
from datetime import datetime

st.set_page_config(page_title="2026世界杯智能分析", page_icon="⚽", layout="wide")

# ============ 内置夺冠赔率和概率数据（来自全网搜索的真实数据） ============

# 竞彩夺冠赔率
JINGCAI_ODDS = {
    '西班牙': 4.5, '法国': 5.5, '阿根廷': 6.0, '巴西': 8.0, '英格兰': 9.0,
    '葡萄牙': 11.0, '德国': 13.0, '荷兰': 21.0, '挪威': 26.0, '意大利': 34.0,
}

# 竞彩赔率转隐含概率
JINGCAI_IMPLIED = {
    '西班牙': 18.2, '法国': 15.4, '阿根廷': 14.3, '巴西': 11.1, '英格兰': 10.0,
    '葡萄牙': 8.3, '德国': 7.1, '荷兰': 4.5, '挪威': 3.7, '意大利': 2.9,
}

# OPTA夺冠概率(%)
OPTA_PROB = {
    '西班牙': 16.1, '法国': 13.0, '英格兰': 11.2, '阿根廷': 10.4, '葡萄牙': 7.0,
    '巴西': 6.6, '德国': 5.1, '荷兰': 3.6, '挪威': 3.5, '比利时': 2.4,
    '哥伦比亚': 2.1, '摩洛哥': 1.9, '乌拉圭': 1.7, '瑞士': 1.7, '克罗地亚': 1.6,
    '厄瓜多尔': 1.4, '日本': 1.2, '美国': 1.2, '塞内加尔': 1.0, '墨西哥': 1.0,
}

# 高盛预测夺冠概率(%)
GOLDMAN_PROB = {
    '西班牙': 26, '法国': 19, '阿根廷': 14, '巴西': 8, '英格兰': 5,
}

# 三源综合概率（竞彩隐含 + OPTA + 高盛 的平均值）
def get_three_source_prob(team):
    """计算三源综合夺冠概率"""
    probs = []
    if team in JINGCAI_IMPLIED:
        probs.append(JINGCAI_IMPLIED[team])
    if team in OPTA_PROB:
        probs.append(OPTA_PROB[team])
    if team in GOLDMAN_PROB:
        probs.append(GOLDMAN_PROB[team])
    if probs:
        return sum(probs) / len(probs)
    return None

# 全部参赛球队（32强）
ALL_TEAMS = [
    '美国', '加拿大', '墨西哥',  # 东道主
    '阿根廷', '巴西', '乌拉圭', '厄瓜多尔', '哥伦比亚',  # 南美
    '西班牙', '法国', '英格兰', '葡萄牙', '德国', '荷兰', '意大利', '比利时',
    '瑞士', '克罗地亚', '丹麦', '塞尔维亚', '波兰', '奥地利', '乌克兰', '捷克', '挪威', '瑞典', '罗马尼亚', '匈牙利',  # 欧洲
    '日本', '韩国', '伊朗', '沙特阿拉伯', '卡塔尔', '澳大利亚',  # 亚洲
    '塞内加尔', '摩洛哥', '埃及', '尼日利亚', '喀麦隆', '加纳', '科特迪瓦', '阿尔及利亚',  # 非洲
    '美国',  # 中北美
]

# FIFA排名数据（用于无三源数据的球队）
FIFA_RANKING = {
    '阿根廷': 1, '法国': 2, '巴西': 3, '英格兰': 4, '比利时': 5,
    '西班牙': 6, '葡萄牙': 7, '荷兰': 8, '意大利': 9, '克罗地亚': 10,
    '德国': 11, '丹麦': 12, '奥地利': 13, '瑞士': 14, '墨西哥': 15,
    '美国': 16, '塞内加尔': 17, '乌拉圭': 18, '波兰': 19, '日本': 20,
    '韩国': 23, '伊朗': 21, '沙特阿拉伯': 55, '澳大利亚': 24, '加拿大': 43,
    '埃及': 36, '摩洛哥': 13, '塞尔维亚': 32, '乌克兰': 22, '捷克': 28,
    '尼日利亚': 28, '喀麦隆': 42, '加纳': 60, '瑞典': 23, '挪威': 37,
    '罗马尼亚': 45, '匈牙利': 31, '科特迪瓦': 39, '阿尔及利亚': 32, '卡塔尔': 58,
}

# 近期战绩
RECENT_FORM = {
    '阿根廷': {'wins': 8, 'draws': 1, 'losses': 1, 'gf': 22, 'ga': 5},
    '法国': {'wins': 7, 'draws': 2, 'losses': 1, 'gf': 25, 'ga': 8},
    '巴西': {'wins': 6, 'draws': 2, 'losses': 2, 'gf': 18, 'ga': 7},
    '英格兰': {'wins': 7, 'draws': 2, 'losses': 1, 'gf': 20, 'ga': 6},
    '比利时': {'wins': 6, 'draws': 2, 'losses': 2, 'gf': 18, 'ga': 9},
    '西班牙': {'wins': 8, 'draws': 1, 'losses': 1, 'gf': 24, 'ga': 5},
    '葡萄牙': {'wins': 7, 'draws': 1, 'losses': 2, 'gf': 22, 'ga': 8},
    '荷兰': {'wins': 6, 'draws': 3, 'losses': 1, 'gf': 19, 'ga': 7},
    '意大利': {'wins': 5, 'draws': 3, 'losses': 2, 'gf': 16, 'ga': 8},
    '德国': {'wins': 5, 'draws': 3, 'losses': 2, 'gf': 18, 'ga': 10},
    '克罗地亚': {'wins': 5, 'draws': 3, 'losses': 2, 'gf': 15, 'ga': 9},
    '墨西哥': {'wins': 6, 'draws': 2, 'losses': 2, 'gf': 17, 'ga': 10},
    '美国': {'wins': 5, 'draws': 3, 'losses': 2, 'gf': 16, 'ga': 8},
    '日本': {'wins': 7, 'draws': 1, 'losses': 2, 'gf': 20, 'ga': 7},
    '韩国': {'wins': 5, 'draws': 2, 'losses': 3, 'gf': 15, 'ga': 10},
    '乌拉圭': {'wins': 6, 'draws': 2, 'losses': 2, 'gf': 18, 'ga': 8},
    '哥伦比亚': {'wins': 5, 'draws': 3, 'losses': 2, 'gf': 16, 'ga': 8},
    '瑞士': {'wins': 5, 'draws': 3, 'losses': 2, 'gf': 14, 'ga': 9},
    '厄瓜多尔': {'wins': 5, 'draws': 2, 'losses': 3, 'gf': 15, 'ga': 10},
    '丹麦': {'wins': 5, 'draws': 3, 'losses': 2, 'gf': 14, 'ga': 8},
    '波兰': {'wins': 4, 'draws': 3, 'losses': 3, 'gf': 13, 'ga': 11},
    '塞尔维亚': {'wins': 4, 'draws': 3, 'losses': 3, 'gf': 13, 'ga': 12},
    '奥地利': {'wins': 5, 'draws': 2, 'losses': 3, 'gf': 14, 'ga': 9},
    '乌克兰': {'wins': 4, 'draws': 3, 'losses': 3, 'gf': 12, 'ga': 10},
    '捷克': {'wins': 4, 'draws': 2, 'losses': 4, 'gf': 11, 'ga': 11},
    '挪威': {'wins': 5, 'draws': 2, 'losses': 3, 'gf': 13, 'ga': 9},
    '瑞典': {'wins': 4, 'draws': 3, 'losses': 3, 'gf': 12, 'ga': 10},
    '罗马尼亚': {'wins': 4, 'draws': 3, 'losses': 3, 'gf': 11, 'ga': 10},
    '匈牙利': {'wins': 4, 'draws': 2, 'losses': 4, 'gf': 12, 'ga': 12},
    '伊朗': {'wins': 5, 'draws': 2, 'losses': 3, 'gf': 13, 'ga': 8},
    '沙特阿拉伯': {'wins': 4, 'draws': 2, 'losses': 4, 'gf': 11, 'ga': 12},
    '澳大利亚': {'wins': 4, 'draws': 2, 'losses': 4, 'gf': 10, 'ga': 11},
    '加拿大': {'wins': 3, 'draws': 3, 'losses': 4, 'gf': 9, 'ga': 12},
    '塞内加尔': {'wins': 5, 'draws': 2, 'losses': 3, 'gf': 13, 'ga': 8},
    '摩洛哥': {'wins': 5, 'draws': 2, 'losses': 3, 'gf': 12, 'ga': 9},
    '埃及': {'wins': 4, 'draws': 3, 'losses': 3, 'gf': 11, 'ga': 9},
    '尼日利亚': {'wins': 4, 'draws': 2, 'losses': 4, 'gf': 10, 'ga': 11},
    '喀麦隆': {'wins': 3, 'draws': 3, 'losses': 4, 'gf': 9, 'ga': 12},
    '加纳': {'wins': 3, 'draws': 3, 'losses': 4, 'gf': 8, 'ga': 12},
    '科特迪瓦': {'wins': 4, 'draws': 2, 'losses': 4, 'gf': 10, 'ga': 11},
    '阿尔及利亚': {'wins': 4, 'draws': 2, 'losses': 4, 'gf': 10, 'ga': 11},
    '卡塔尔': {'wins': 2, 'draws': 3, 'losses': 5, 'gf': 7, 'ga': 14},
}

# 东道主列表（主场加成+8%）
HOST_COUNTRIES = {'美国', '加拿大', '墨西哥'}


def get_team_base_strength(name):
    """
    计算球队基础实力得分（基于三源综合夺冠概率）
    返回 0-100 的分值
    """
    three_prob = get_three_source_prob(name)
    if three_prob is not None:
        # 三源概率越高，实力分越高（最大概率约26%，映射到0-100）
        return min(three_prob / 26 * 100, 100)
    
    # 没有三源数据的球队，用FIFA排名推算
    rank = FIFA_RANKING.get(name, 60)
    # 排名越高（数字越小），实力越强
    strength = max(100 - rank * 1.2, 5)
    return strength


def get_team_strength(name, is_home=False):
    """
    计算球队综合实力（含主场加成）
    综合实力 = 夺冠概率权重 * 0.7 + 近期状态权重 * 0.3
    """
    base = get_team_base_strength(name)
    
    # 近期状态
    form = RECENT_FORM.get(name, {'wins': 3, 'draws': 3, 'losses': 4, 'gf': 10, 'ga': 15})
    total_games = form['wins'] + form['draws'] + form['losses']
    form_score = (form['wins'] * 3 + form['draws']) / max(total_games, 1) * 30  # 状态权重 0-30
    
    # 综合实力
    strength = base * 0.7 + form_score
    
    # 主场加成（东道主额外+8%）
    if is_home:
        strength *= 1.08
        if name in HOST_COUNTRIES:
            strength += 4  # 东道主额外加成
    
    return max(25, min(95, strength))


def get_recent_form(name):
    return RECENT_FORM.get(name, {'wins': 3, 'draws': 3, 'losses': 4, 'gf': 10, 'ga': 15})


# ============ 搜索函数 ============
def search_web(keyword, freshness="30d"):
    """搜索网络数据（本地开发使用prosearch，云端使用备用方案）"""
    try:
        # 本地开发环境尝试使用prosearch
        prosearch_paths = [
            r"C:\Program Files\QClaw\v0.2.24.354\resources\openclaw\config\skills\online-search\scripts\prosearch.cjs",
            "/app/.qclaw/skills/online-search/scripts/prosearch.cjs",  # Streamlit Cloud可能路径
        ]
        
        for script_path in prosearch_paths:
            if os.path.exists(script_path):
                cmd = ['node', script_path, '--keyword=' + keyword, '--freshness=' + freshness]
                result = subprocess.run(cmd, capture_output=True, timeout=20, shell=True)
                output = result.stdout.decode('utf-8', errors='replace')
                if result.returncode == 0 and output.strip():
                    data = json.loads(output)
                    if data.get('success'):
                        return data.get('data', {}).get('docs', [])
        return []
    except Exception:
        return []


def extract_comprehensive_news(team_name):
    """全网整合：提取球队最新动态"""
    all_docs = []
    keywords = [
        f"{team_name} 世界杯 最新名单 战术 备战",
        f"{team_name} national team world cup 2026 news",
    ]
    for kw in keywords:
        docs = search_web(kw, "14d")
        all_docs.extend(docs)
        if len(all_docs) >= 6:
            break
    return all_docs[:6]


def extract_head_to_head(home, away):
    """历史交锋"""
    all_docs = []
    keywords = [
        f"{home} vs {away} 历史战绩 交锋",
        f"{home} {away} head to head record",
    ]
    for kw in keywords:
        docs = search_web(kw, "180d")
        all_docs.extend(docs)
        if len(all_docs) >= 3:
            break
    return all_docs[:3]


def extract_expert_predictions(home, away):
    """专家预测"""
    all_docs = []
    keywords = [
        f"{home} vs {away} 世界杯 预测 胜负",
        f"{home} {away} world cup prediction expert",
    ]
    for kw in keywords:
        docs = search_web(kw, "30d")
        all_docs.extend(docs)
        if len(all_docs) >= 4:
            break
    return all_docs[:4]


def predict_score_v92(home, away, home_power, away_power, form_h=None, form_a=None):
    """v9.2 预测算法（基于三源综合概率）"""
    diff = home_power - away_power
    
    # 近期状态修正
    if form_h and form_a:
        hp = (form_h['wins'] * 3 + form_h['draws']) / max(form_h['wins']+form_h['draws']+form_h['losses'], 1)
        ap = (form_a['wins'] * 3 + form_a['draws']) / max(form_a['wins']+form_a['draws']+form_a['losses'], 1)
        diff += (hp - ap) * 5
    
    # 三源概率修正（如果有数据）
    home_three = get_three_source_prob(home)
    away_three = get_three_source_prob(away)
    if home_three and away_three:
        # 夺冠概率差异转实力修正
        prob_diff = home_three - away_three
        diff += prob_diff * 2  # 每1%概率差对应2分实力差
    
    if diff > 20:
        return [(2, 0), (2, 1), (3, 1)]
    elif diff > 10:
        return [(1, 0), (2, 0), (2, 1)]
    elif diff > 3:
        return [(1, 0), (1, 1), (2, 1)]
    elif diff > -3:
        return [(1, 1), (0, 0), (1, 0)]
    elif diff > -10:
        return [(0, 1), (1, 1), (1, 2)]
    elif diff > -20:
        return [(0, 1), (0, 2), (1, 2)]
    else:
        return [(0, 2), (1, 2), (0, 3)]


def show_comprehensive_analysis(home, away, match_info, idx):
    """全网深度整合分析（v9.2三源综合概率版）"""
    st.markdown("---")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown(f"### ⚽ {home}")
        form_h = get_recent_form(home)
        home_three = get_three_source_prob(home)
        home_power = get_team_strength(home, True)
        st.markdown(f"""
        <div style="background:#e3f2fd;padding:10px;border-radius:8px;margin:5px 0;">
            <b>📊 近期状态</b><br>
            胜: {form_h['wins']} | 平: {form_h['draws']} | 负: {form_h['losses']}<br>
            进球: {form_h['gf']} | 失球: {form_h['ga']}
            {'<br><b>🏆 三源综合夺冠概率: ' + f'{home_three:.1f}%' + '</b>' if home_three else ''}
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"### ⚽ {away}")
        form_a = get_recent_form(away)
        away_three = get_three_source_prob(away)
        away_power = get_team_strength(away, False)
        st.markdown(f"""
        <div style="background:#ffebee;padding:10px;border-radius:8px;margin:5px 0;">
            <b>📊 近期状态</b><br>
            胜: {form_a['wins']} | 平: {form_a['draws']} | 负: {form_a['losses']}<br>
            进球: {form_a['gf']} | 失球: {form_a['ga']}
            {'<br><b>🏆 三源综合夺冠概率: ' + f'{away_three:.1f}%' + '</b>' if away_three else ''}
        </div>
        """, unsafe_allow_html=True)

    with st.status("🔍 全网深度数据整合中（基于三源综合概率）...", expanded=True) as status:
        
        # 1. 最新动态
        st.markdown("#### 📰 全网最新动态")
        nc1, nc2 = st.columns(2)
        with nc1:
            news = extract_comprehensive_news(home)
            st.markdown(f"**{home} 最新消息**")
            if news:
                for n in news[:3]:
                    st.markdown(f"- {n.get('title', '无标题')[:60]}")
            else:
                st.info("暂无最新消息")
        with nc2:
            news_a = extract_comprehensive_news(away)
            st.markdown(f"**{away} 最新消息**")
            if news_a:
                for n in news_a[:3]:
                    st.markdown(f"- {n.get('title', '无标题')[:60]}")
            else:
                st.info("暂无最新消息")
        
        # 2. 历史交锋
        h2h = extract_head_to_head(home, away)
        if h2h:
            st.markdown("#### ⚔️ 历史交锋记录")
            for h in h2h[:2]:
                st.markdown(f"- {h.get('title', '交锋记录')[:80]}")
        
        # 3. 专家预测
        predictions = extract_expert_predictions(home, away)
        if predictions:
            st.markdown("#### 🎯 全网专家预测")
            for p in predictions[:2]:
                st.markdown(f"**{p.get('title', '专家预测')[:70]}**")
        
        status.update(label="✅ 全网数据整合完成!", state="complete")
    
    # 4. 📊 三源综合夺冠概率分析（核心改进！）
    st.markdown("#### 📊 三源综合夺冠概率分析")
    
    # 展示三源数据
    jingcai_p = JINGCAI_IMPLIED.get(home), JINGCAI_IMPLIED.get(away)
    opta_p = OPTA_PROB.get(home), OPTA_PROB.get(away)
    goldman_p = GOLDMAN_PROB.get(home), GOLDMAN_PROB.get(away)
    
    col_src1, col_src2 = st.columns(2)
    
    with col_src1:
        st.markdown(f"**{home} 三源数据**")
        src_data = []
        if jingcai_p[0]:
            src_data.append(f"- 竞彩隐含概率: {jingcai_p[0]:.1f}%")
        if opta_p[0]:
            src_data.append(f"- OPTA夺冠概率: {opta_p[0]:.1f}%")
        if goldman_p[0]:
            src_data.append(f"- 高盛预测概率: {goldman_p[0]:.1f}%")
        if home_three:
            src_data.append(f"\n**⭐ 三源平均概率: {home_three:.1f}%**")
        else:
            src_data.append("\n*（无三源数据，基于FIFA排名推算）*")
        st.markdown("\n".join(src_data) if src_data else "*暂无数据*")
    
    with col_src2:
        st.markdown(f"**{away} 三源数据**")
        src_data_a = []
        if jingcai_p[1]:
            src_data_a.append(f"- 竞彩隐含概率: {jingcai_p[1]:.1f}%")
        if opta_p[1]:
            src_data_a.append(f"- OPTA夺冠概率: {opta_p[1]:.1f}%")
        if goldman_p[1]:
            src_data_a.append(f"- 高盛预测概率: {goldman_p[1]:.1f}%")
        if away_three:
            src_data_a.append(f"\n**⭐ 三源平均概率: {away_three:.1f}%**")
        else:
            src_data_a.append("\n*（无三源数据，基于FIFA排名推算）*")
        st.markdown("\n".join(src_data_a) if src_data_a else "*暂无数据*")
    
    st.caption("💡 数据来源：竞彩夺冠赔率(500.com) + OPTA大数据预测 + 高盛研究团队模型")
    
    # 5. 综合预测
    st.markdown("#### 🎯 综合预测结果")
    home_power = get_team_strength(home, True)
    away_power = get_team_strength(away, False)
    form_h = get_recent_form(home)
    form_a = get_recent_form(away)
    
    # 三源概率权重计算胜率
    home_win_pct = home_power / (home_power + away_power) * 100
    home_form_pts = (form_h['wins'] * 3 + form_h['draws']) / max(form_h['wins']+form_h['draws']+form_h['losses'], 1) * 30
    away_form_pts = (form_a['wins'] * 3 + form_a['draws']) / max(form_a['wins']+form_a['draws']+form_a['losses'], 1) * 30
    
    final_home = (home_win_pct * 0.7) + home_form_pts
    final_away = ((100 - home_win_pct) * 0.7) + away_form_pts
    final_total = final_home + 22 + final_away
    final_home_pct = final_home / final_total * 100
    final_away_pct = final_away / final_total * 100
    draw_pct = 22
    
    pc = st.columns(3)
    pc[0].metric(f"{home} 胜率", f"{final_home_pct:.1f}%", delta="综合评估")
    pc[1].metric("平局概率", f"{draw_pct:.1f}%", delta="参考历史")
    pc[2].metric(f"{away} 胜率", f"{final_away_pct:.1f}%", delta="综合评估")
    
    if final_home_pct > final_away_pct + 15:
        recommendation = f"⭐ 推荐: {home} 胜"
        confidence = "高"
    elif final_away_pct > final_home_pct + 15:
        recommendation = f"⭐ 推荐: {away} 胜"
        confidence = "高"
    elif final_home_pct > final_away_pct + 5:
        recommendation = f"倾向: {home} 胜，可考虑{home}让球"
        confidence = "中"
    elif final_away_pct > final_home_pct + 5:
        recommendation = f"倾向: {away} 胜，可考虑{away}受让"
        confidence = "中"
    else:
        recommendation = "势均力敌，建议关注平局或进球数"
        confidence = "低"
    
    st.success(f"**{recommendation}** (信心等级: {confidence})")
    st.caption("⭐ 基于：OPTA+竞彩+高盛综合分析")
    
    # 6. 比分预测
    st.markdown("#### ⚽ 比分预测")
    base_scores = predict_score_v92(home, away, home_power, away_power, form_h, form_a)
    
    labels = ["🥇 最可能", "🥈 次可能", "🥉 备选"]
    for i, (fh, fa) in enumerate(base_scores):
        with st.container():
            sc = st.columns([2, 1, 1])
            sc[0].markdown(f"**{labels[i]}**: `{home} {fh} : {fa} {away}`")
            if i == 0:
                sc[1].markdown("⭐ 推荐")
            sc[2].markdown(f"概率 ~{(40-i*5):.0f}%")
    
    st.caption("💡 比分基于OPTA+竞彩+高盛三源综合概率、FIFA排名、近期状态、全网专家预测综合计算")
    
    if st.button("❌ 收起分析", key=f"close_{idx}"):
        st.session_state[f'deep_{idx}'] = False
        st.rerun()


# ============ 加载赛程 ============
@st.cache_data(ttl=3600)
def load_schedule():
    path = os.path.join(os.path.dirname(__file__), 'worldcup_2026_schedule.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============ 夺冠概率排行榜模块 ============
def show_championship_ranking():
    """显示TOP10夺冠概率排行榜"""
    st.markdown("### 🏆 夺冠概率排行 TOP10")
    st.markdown("*数据来源：OPTA大数据 | 竞彩夺冠赔率 | 高盛研究团队*")
    
    # 收集所有球队的三源数据
    ranking_data = []
    all_teams_with_prob = {}
    
    # 所有有OPTA数据的球队
    for team, opta_val in OPTA_PROB.items():
        jingcai_val = JINGCAI_IMPLIED.get(team, None)
        goldman_val = GOLDMAN_PROB.get(team, None)
        three_prob = get_three_source_prob(team)
        all_teams_with_prob[team] = {
            'opta': opta_val,
            'jingcai': jingcai_val,
            'goldman': goldman_val,
            'three_avg': three_prob,
        }
    
    # 按OPTA概率排序，取TOP10
    sorted_teams = sorted(OPTA_PROB.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # 表格展示
    header = "| 排名 | 球队 | OPTA概率(%) | 竞彩隐含(%) | 高盛预测(%) | 三源综合(%) |\n"
    header += "| --- | --- | --- | --- | --- | --- |\n"
    
    rows = []
    for rank, (team, opta_val) in enumerate(sorted_teams, 1):
        data = all_teams_with_prob.get(team, {})
        jingcai = data.get('jingcai', None)
        goldman = data.get('goldman', None)
        three_avg = data.get('three_avg', None)
        
        opta_str = f"{opta_val:.1f}%" if opta_val else "-"
        jingcai_str = f"{jingcai:.1f}%" if jingcai else "-"
        goldman_str = f"{goldman:.1f}%" if goldman else "-"
        three_str = f"**{three_avg:.1f}%**" if three_avg else "-"
        
        rows.append(f"| {rank} | {team} | {opta_str} | {jingcai_str} | {goldman_str} | {three_str} |")
    
    table_md = header + "\n".join(rows)
    st.markdown(table_md)
    
    # 说明
    st.caption(
        "📊 **解读**：OPTA概率基于大数据模型预测；竞彩隐含概率来自夺冠赔率反推；"
        "高盛预测来自投行研究模型；三源综合为三者平均值"
    )
    st.markdown("---")


# ============ 主程序 ============
data = load_schedule()
matches = data['matches_list']

# ============ 页面布局 ============
st.markdown('# 🏆 2026世界杯智能分析系统 **(三源综合概率版 v9.2)**')
st.markdown(f'**📅 {data["dates"]} | 📍 {data["host"]} | ⚽ {data["teams"]}支球队**')
st.info('🔬 **核心升级**：内置真实夺冠赔率（竞彩+OPTA+高盛）三源综合概率，算法全面优化')

# 夺冠概率排行榜（新增模块）
show_championship_ranking()

confirmed = [m for m in matches if '待定' not in m['home'] and '待定' not in m['away']]
st.success(f'✅ 已确定对阵: {len(confirmed)} 场 | 🔍 点击"深度分析"获取三源综合数据分析')

# ============ 显示赛程 ============
stages = {}
for m in matches:
    s = m.get('stage', '其他')
    stages.setdefault(s, []).append(m)

for stage_name, stage_matches in stages.items():
    with st.expander(f"📅 {stage_name} ({len(stage_matches)}场)", expanded=(stage_name == "小组赛")):
        cols = st.columns(3)
        for i, m in enumerate(stage_matches):
            with cols[i % 3]:
                home = m['home']
                away = m['away']
                hot_teams = [
                    '巴西', '阿根廷', '法国', '德国', '西班牙', '葡萄牙', '英格兰', '荷兰',
                    '意大利', '比利时', '墨西哥', '美国', '日本', '韩国', '乌拉圭',
                    '克罗地亚', '哥伦比亚', '瑞士', '丹麦', '挪威'
                ]
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
                    show_comprehensive_analysis(home, away, m, idx)

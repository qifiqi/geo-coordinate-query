"""Address matching utilities."""

from __future__ import annotations

from typing import Any, Mapping


def address_similarity(input_addr, api_result):
    """计算用户输入地址与API返回地址的相似度（0~1）

    算法：
    1. 最长公共子序列(LCS)比率 —— 保留字符顺序，适合地址/地名混合输入
    2. 以较短串为基准归一化 —— 短地名匹配长地址时不会系统性偏低
    3. 省市区结构化字段加权 —— 提升行政区匹配的可信度
    """
    if not input_addr or not api_result:
        return 0.0

    def _clean(s):
        return str(s).replace(' ', '').replace('(', '').replace(')', '') \
                     .replace('（', '').replace('）', '') \
                     .replace('[', '').replace(']', '')

    # 取 API 返回的地址或名称
    api_addr = _clean(api_result.get('address', '') or api_result.get('name', ''))
    input_clean = _clean(input_addr)
    if not api_addr or not input_clean:
        return 0.0

    # --- 最长公共子序列(LCS)长度 ---
    m, n = len(input_clean), len(api_addr)
    # 空间优化：只保留两行
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if input_clean[i - 1] == api_addr[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)
    lcs_len = prev[n]

    # 以较短串为基准归一化（短地名 vs 长地址不会偏低）
    min_len = min(m, n)
    max_len = max(m, n)
    lcs_ratio = lcs_len / min_len if min_len > 0 else 0.0

    # 长度惩罚：两者长度差距越大，对比率打一定折扣
    length_factor = min_len / max_len if max_len > 0 else 1.0
    sequence_score = lcs_ratio * (0.7 + 0.3 * length_factor)

    # 包含关系加成：较短串完全包含在较长串中时，大幅提升分数
    shorter = input_clean if m <= n else api_addr
    longer = api_addr if m <= n else input_clean
    if shorter in longer:
        # 完全包含时，以占比为基准（如“黎黄陂路”在“武汉市江岸区黎黄陂路”中占 4/11）
        contain_ratio = len(shorter) / len(longer) if len(longer) > 0 else 1.0
        sequence_score = max(sequence_score, 0.85 + 0.15 * contain_ratio)

    # --- 结构化字段加权 ---
    bonus = 0.0
    province = api_result.get('province', '')
    city = api_result.get('city', '')
    district = api_result.get('district', '')
    if province and province in input_addr:
        bonus += 0.08
    if city and str(city) != '[]' and str(city) in input_addr:
        bonus += 0.08
    if district and district in input_addr:
        bonus += 0.14

    score = min(1.0, sequence_score * (0.70 + 0.30 * sequence_score) + bonus)
    return round(score, 2)


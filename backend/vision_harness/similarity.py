# /home/work/python/buildsight/backend/vision_harness/similarity.py

"""
材料与空间类型相似度评估模块
=============================
基于层次化类别体系的语义相似度计算。
不替代准确率，而是提供更柔性的模型质量评估视角。
"""

from typing import Dict, List, Tuple

# ═══════════════════════════════════════════════
# 层次化类别分组
# ═══════════════════════════════════════════════

# 每组内的材料彼此相似（同父类），组间不相似
MATERIAL_HIERARCHY: Dict[str, Dict[str, List[str]]] = {
    "wall_material": {
        "涂料类":    ["乳胶漆", "艺术漆", "微水泥"],
        "贴面类":    ["墙纸", "木饰面"],
        "石板类":    ["大理石", "瓷砖"],
        "特殊类":    ["玻璃", "石膏", "软硬包"],
    },
    "floor_material": {
        "木制品":    ["实木地板", "石塑地板", "防腐木"],
        "石材砖":    ["地砖", "大理石"],
        "无缝类":    ["微水泥"],
        "软质类":    ["地毯"],
    },
    "ceiling_material": {
        "吊顶类":    ["石膏板吊顶", "金属吊顶", "木饰吊顶"],
        "线条类":    ["石膏线条"],
        "涂料类":    ["涂料顶面"],
        "透光类":    ["玻璃顶"],
    },
    "space_type": {
        "居住空间":  ["客厅", "餐厅", "卧室", "书房"],
        "功能空间":  ["厨房", "卫生间", "储物间", "衣帽间"],
        "连接空间":  ["走廊", "阳台", "门厅"],
        "休闲空间":  ["休闲区"],
    },
}

# ═══════════════════════════════════════════════
# 组内默认相似度基数 & 跨组特例相似度
# ═══════════════════════════════════════════════

SAME_GROUP_BASE_SIMILARITY = 0.85  # 同一子类组的默认相似度

# 跨组相似度特例（override）：某些材料虽不同组但有语义关联
CROSS_GROUP_OVERRIDES: Dict[str, Dict[Tuple[str, str], float]] = {
    "wall_material": {
        ("大理石", "瓷砖"): 0.42,    # 都是硬质板材但纹理差异大（天然vs规则）
        ("墙纸", "乳胶漆"): 0.36,     # 贴面 vs 涂料 — 稍有关联
        ("木饰面", "软硬包"): 0.42,  # 木质vs软质，都有分块视觉效果
        ("艺术漆", "乳胶漆"): 0.60,   # 都有纯色效果，艺术漆多了肌理
        ("玻璃", "石膏"): 0.18,      # 透明vs立体造型，差异大
    },
    "floor_material": {
        ("实木地板", "石塑地板"): 0.78,  # 视觉相似但纹理重复性不同
        ("实木地板", "防腐木"): 0.66,    # 都是木板效果，但防腐木更粗糙风化
        ("地砖", "大理石"): 0.42,        # 规则砖缝vs天然流动纹路，差异明显
        ("微水泥", "地砖"): 0.24,          # 无缝vs网格，差异大
        ("微水泥", "涂料顶面"): 0.18,     # 跨字段比较无意义，保留低值
        ("地毯", "所有其他"): 0.06,       # 绒毛纤维独特，几乎无相似
    },
    "ceiling_material": {
        ("石膏板吊顶", "涂料顶面"): 0.66,  # 视觉上都是平整白色顶面
        ("金属吊顶", "石膏板吊顶"): 0.48,   # 都有吊顶造型，金属更规则
        ("木饰吊顶", "石膏板吊顶"): 0.42,  # 都有造型但材质不同
        ("石膏线条", "涂料顶面"): 0.30,    # 线条vs平顶，关联弱
        ("玻璃顶", "所有其他"): 0.12,       # 透明透光特性独特
    },
    "space_type": {
        ("客厅", "休闲区"): 0.54,          # 都有休闲座椅，布局风格接近
        ("卧室", "书房"): 0.42,            # 都属安静私密空间，但家具差异大
        ("卧室", "储物间"): 0.18,           # 都有收纳但功能完全不同
        ("走廊", "阳台"): 0.24,             # 都是通道但开放vs封闭差异大
        ("厨房", "卫生间"): 0.36,            # 都有橱柜台面+瓷砖，功能不同
        ("客厅", "餐厅"): 0.48,             # 都属公共活动区，家具不同
        ("储物间", "休闲区"): 0.12,          # 功能完全相反
    },
}

def _build_group_index(field: str) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    构建双向映射：
    - material_to_group: 材料名 → 组名
    - group_to_materials: 组名 → [材料列表]
    """
    hierarchy = MATERIAL_HIERARCHY.get(field, {})
    material_to_group = {}
    group_to_materials = {}
    for group_name, materials in hierarchy.items():
        group_to_materials[group_name] = materials
        for mat in materials:
            material_to_group[mat] = group_name
    return material_to_group, group_to_materials


def compute_material_similarity(
    predicted: str,
    expected: str,
    field: str,  # "wall_material" | "floor_material" | "ceiling_material" | "space_type"
) -> float:
    """
    计算单个字段预测值与期望值的相似度 (0.0 ~ 1.0)
    
    逻辑:
    1. 完全一致 → 1.0
    2. is-a 关系匹配 → 0.92（仅 space_type，粗粒度大类 ↔ 细粒度子类型）
    3. 同义词匹配 → 1.0 (复用 SYNONYM_GROUPS)
    4. 同一子类组 → SAME_GROUP_BASE_SIMILARITY
    5. 有跨组特例 → 特例值
    6. 否则 → 0.0
    """
    if not predicted or not expected:
        return 0.0
    
    p = predicted.strip()
    e = expected.strip()
    
    # ── 1. 完全相同 ──
    if p == e:
        return 1.0
    
    # ── 2. is-a 关系匹配（粗粒度大类 ↔ 细粒度子类型）──
    # 效果图识别输出十二大类，ground truth 可能是细粒度（如 主卧/次卧）
    # 通过 space_synonyms.CONTAINS_MAP 判断：一方是另一方的子类型 → 高相似度
    if field == "space_type":
        try:
            from space_synonyms import CONTAINS_MAP
            # p 是 e 的子类型（如 p="主卧", e="卧室"）
            if p in CONTAINS_MAP and e in CONTAINS_MAP[p]:
                return 0.92
            # e 是 p 的子类型（如 p="卧室", e="主卧"）
            if e in CONTAINS_MAP and p in CONTAINS_MAP[e]:
                return 0.92
        except ImportError:
            pass

    # ── 3. 同义词匹配（复用 material_library 的 SYNONYM_GROUPS）─
    from vision_harness.material_library import SYNONYM_GROUPS
    for group in SYNONYM_GROUPS:
        if p in group and e in group:
            return 1.0
    
    # ── 4. 层次化类别匹配 ──
    hierarchy = MATERIAL_HIERARCHY.get(field, {})
    material_to_group, _ = _build_group_index(field)
    
    pg = material_to_group.get(p)
    eg = material_to_group.get(e)
    
    # 4a. 同一子类组
    if pg and eg and pg == eg:
        return SAME_GROUP_BASE_SIMILARITY
    
    # 4b. 跨组特例
    overrides = CROSS_GROUP_OVERRIDES.get(field, {})
    # 查双向
    if (p, e) in overrides:
        return overrides[(p, e)]
    if (e, p) in overrides:
        return overrides[(e, p)]
    
    # 4c. 非同一组且无特例
    return 0.0

def evaluate_similarity(
    predicted: Dict[str, str],     # 模型预测结果
    expected: Dict[str, str],      # 人工标注（ground truth）
    field_weights: Dict[str, float] = None,  # 各字段权重
) -> Dict:
    """
    评估一次预测的综合相似度。
    
    返回:
    {
        "overall_similarity": 0.72,      # 加权平均
        "field_scores": {
            "space_type": 1.0,
            "wall_material": 0.75,
            "floor_material": 0.0,
            "ceiling_material": 0.75,
        },
        "field_weights_used": {...},
        "details": "空间类型准确，墙面材质相近，地面材质错误，顶面材质相近",
    }
    """
    if field_weights is None:
        field_weights = {
            "space_type": 0.15,
            "wall_material": 0.30,
            "floor_material": 0.30,
            "ceiling_material": 0.25,
        }
    
    fields = list(field_weights.keys())
    scores = {}
    
    for field in fields:
        p = predicted.get(field, "")
        e = expected.get(field, "")
        sim = compute_material_similarity(p, e, field)
        scores[field] = sim
        
    # 加权综合
    total_weight = sum(field_weights.values())
    overall = sum(scores[f] * field_weights[f] for f in fields) / total_weight
    
    return {
        "overall_similarity": round(overall, 4),
        "field_scores": scores,
        "field_weights_used": field_weights,
    }
   

def get_expect_pretect(name: str, data: dict) -> Tuple[dict, dict]:
    """
    从文件名中分离出预期标签
    
    Args:
        name: 文件名称
        data: 预测键值对（含冗余键值对）
    
    Returns:
        expection: [{"space_type": "..."}, {}, {}]
        prediction: [{"space_type": "..."}, {}, {}]
    """
    
    REGION = ["space_type", "ceiling_material", "wall_material", "floor_material"]
    
    # 获取 预期 结果
    filename = name.split(".")[0]
    labels = filename.split("_")
    expection = {REGION[i]: labels[i] for i in range(4)}
    
    # 获取 预测 结果
    prediction = {k: data[k] for k in REGION}
    
    return expection, prediction
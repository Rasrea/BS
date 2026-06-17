"""
空间名称同义词映射库
========================
用于 CAD 空间名与 AI 识别空间名的自动匹配。

功能：
1. 同义词映射（SYNONYM_MAP）：CAD 名称 → 标准化名称
2. 别名库（SPACE_ALIASES）：标准化名称 → 所有可能的别名单
3. 复合词拆分："客餐厅" → ["客厅", "餐厅"]，"主卧+书房" → ["主卧", "书房"]
4. 匹配决策：match_space_name(cad_name, ai_name) -> bool
5. 候选展开：get_matched_spaces(cad_name) -> list

使用示例：
    from space_synonyms import match_space_name, get_matched_spaces

    # 判断是否匹配
    match_space_name("客餐厅", "客厅")   # True
    match_space_name("主卧", "卧室")     # False（主卧 ≠ 普通次卧）
    match_space_name("生活阳台", "阳台") # True
"""

import re
from typing import List, Optional, Set

# ═══════════════════════════════════════════════════════════════════
# 1. 标准化同义词映射：CAD 空间名 → 标准化名称
# 用途：将各种变体名称统一归到标准名称下
# ═══════════════════════════════════════════════════════════════════
SYNONYM_MAP = {
    # ── 客厅 ──
    "客厅": "客厅",
    "客": "客厅",              # CAD 简写
    "起居室": "客厅",          # 同义
    "living room": "客厅",

    # ── 餐厅 ──
    "餐厅": "餐厅",
    "餐": "餐厅",              # CAD 简写
    "饭厅": "餐厅",            # 同义
    "dining room": "餐厅",
    "dining": "餐厅",

    # ── 客餐厅（复合空间） ──
    "客餐厅": "客餐厅",
    "客饭厅": "客餐厅",
    "客厅+餐厅": "客餐厅",
    "living+dining": "客餐厅",

    # ── 主卧 ──
    "主卧": "主卧",
    "主卧室": "主卧",          # 全称 → 简称
    "主人房": "主卧",          # 同义
    "master bedroom": "主卧",
    "master": "主卧",

    # ── 次卧 ──
    "次卧": "次卧",
    "次卧室": "次卧",          # 全称 → 简称
    "客房": "次卧",            # 功能等同次卧（非主卧的次要卧室）
    "北次卧": "次卧",          # 方位限定 → 标准
    "南次卧": "次卧",
    "小卧室": "次卧",
    "bedroom": "次卧",
    "guest bedroom": "次卧",

    # ── 儿童房 ──
    "儿童房": "儿童房",
    "小孩房": "儿童房",        # 同义
    "孩子房": "儿童房",
    "kid's room": "儿童房",
    "children's room": "儿童房",

    # ── 老人房 ──
    "老人房": "老人房",
    "长辈房": "老人房",
    "父母房": "老人房",
    "elderly room": "老人房",

    # ── 书房（可匹配CAD客房/次卧）──
    "书房": "次卧",            # 书房AI识别可匹配CAD客房/次卧
    "study room": "书房",
    "study": "书房",

    # ── 厨房 ──
    "厨房": "厨房",
    "kitchen": "厨房",

    # ── 西厨 ──
    "西厨": "西厨",
    "西式厨房": "西厨",
    "西厨房": "西厨",
    "western kitchen": "西厨",

    # ── 卫生间 ──
    "卫生间": "卫生间",
    "厕所": "卫生间",
    "洗手间": "卫生间",
    "浴室": "卫生间",
    "bathroom": "卫生间",
    "wc": "卫生间",
    "washroom": "卫生间",

    # ── 主卫 ──
    "主卫": "主卫",
    "主卫生间": "主卫",
    "主卧卫生间": "主卫",
    "主浴室": "主卫",
    "master bathroom": "主卫",

    # ── 客卫 ──
    "客卫": "客卫",
    "客卫生间": "客卫",
    "公卫": "客卫",
    "公共卫生间": "客卫",
    "次卫": "客卫",            # 次卫 = 公卫（相对主卫而言）
    "guest bathroom": "客卫",

    # ── 阳台 ──
    "阳台": "阳台",
    "balcony": "阳台",

    # ── 生活阳台 ──
    "生活阳台": "生活阳台",
    "生活阳台": "生活阳台",    # 生活阳台是阳台的子类，但业务上独立
    "洗衣阳台": "生活阳台",

    # ── 休闲阳台 ──
    "休闲阳台": "休闲阳台",
    "观景阳台": "休闲阳台",
    "景观阳台": "休闲阳台",

    # ── 阳光房 ──
    "阳光房": "阳光房",
    "sunroom": "阳光房",

    # ── 入户花园 ──
    "入户花园": "入户花园",
    "入户花园": "入户花园",
    "玄关花园": "入户花园",
    "entrance garden": "入户花园",

    # ── 门厅 / 入户花园 ──
    "门厅": "入户花园",        # 门厅 → 入户花园（与玄关统一）
    "玄关": "入户花园",        # 玄关 → 入户花园，可匹配CAD入户花园
    "entrance": "入户花园",
    "foyer": "入户花园",

    # ── 衣帽间 ──
    "衣帽间": "衣帽间",
    "衣帽间": "衣帽间",
    "walk-in closet": "衣帽间",
    "wardrobe": "衣帽间",

    # ── 淋浴房 ──
    "淋浴房": "淋浴房",
    "淋浴间": "淋浴房",
    "淋浴": "淋浴房",
    "shower room": "淋浴房",

    # ── 洗手台 ──
    "洗手台": "洗手台",
    "洗手盆": "洗手台",
    "洗漱台": "洗手台",
    "vanity": "洗手台",

    # ── 浴缸 ──
    "浴缸": "浴缸",
    "浴盆": "浴缸",
    "bathtub": "浴缸",

    # ── 走廊/过道 ──
    "走廊": "走廊",
    "过道": "走廊",
    "hallway": "走廊",
    "corridor": "走廊",

    # ── 储藏室 ──
    "储藏室": "储藏室",
    "储物间": "储藏室",
    "杂物间": "储藏室",
    "storage": "储藏室",
    "closet": "储藏室",

    # ── AI模型常输出的额外类型 ──
    "卧室": "次卧",              # AI输出无前綴"卧室"→安全降级为次卧
    "大厅": "客厅",              # AI输出 "大厅" → 客厅
    "大堂": "客厅",
    "用餐区": "餐厅",
    "就餐区": "餐厅",
    "厨房区": "厨房",
    "客卧": "次卧",
    "休息区": "休闲区",
    "休息室": "休闲区",
    "活动室": "休闲区",
    "娱乐室": "休闲区",
    "多功能室": "休闲区",
    "多功能房": "休闲区",
    "卧室1": "次卧",
    "卧室2": "次卧",
    "卧室3": "次卧",

    # ── 其他 ──
    "露台": "露台",
    "terrace": "露台",
    "院子": "庭院",
    "庭院": "庭院",
    "花园": "花园",
    "garden": "花园",
    "车库": "车库",
    "garage": "车库",
    "设备间": "设备间",
    "设备阳台": "设备间",
    "空调机位": "设备间",
    "电梯间": "电梯间",
    "楼梯间": "楼梯间",
}

# ═══════════════════════════════════════════════════════════════════
# 2. 别名库：标准化名称 → 所有可能的别名单
# 用途：给定一个标准空间名，可反查所有可能的写法
# ═══════════════════════════════════════════════════════════════════
SPACE_ALIASES = {
    "客厅": ["客厅", "客", "起居室", "living room", "living"],
    "餐厅": ["餐厅", "餐", "饭厅", "dining room", "dining"],
    "客餐厅": ["客餐厅", "客饭厅", "客厅+餐厅", "living+dining"],
    "主卧": ["主卧", "主卧室", "主人房", "master bedroom", "master"],
    "次卧": ["次卧", "次卧室", "客房", "北次卧", "南次卧", "小卧室", "书房", "卧室", "卧室1", "卧室2", "卧室3", "客卧", "bedroom", "guest bedroom"],
    "儿童房": ["儿童房", "小孩房", "孩子房", "kid's room", "children's room"],
    "老人房": ["老人房", "长辈房", "父母房", "elderly room"],
    "书房": ["书房", "study room", "study"],
    "厨房": ["厨房", "kitchen"],
    "西厨": ["西厨", "西式厨房", "西厨房", "western kitchen"],
    "卫生间": ["卫生间", "厕所", "洗手间", "浴室", "bathroom", "wc", "washroom"],
    "主卫": ["主卫", "主卫生间", "主卧卫生间", "主浴室", "master bathroom"],
    "客卫": ["客卫", "客卫生间", "公卫", "公共卫生间", "次卫", "guest bathroom"],
    "阳台": ["阳台", "balcony"],
    "生活阳台": ["生活阳台", "洗衣阳台"],
    "休闲阳台": ["休闲阳台", "观景阳台", "景观阳台"],
    "阳光房": ["阳光房", "sunroom"],
    "入户花园": ["入户花园", "玄关花园", "玄关", "门厅", "entrance garden"],
    "门厅": ["门厅", "玄关", "entrance", "foyer"],
    "衣帽间": ["衣帽间", "walk-in closet", "wardrobe"],
    "淋浴房": ["淋浴房", "淋浴间", "淋浴", "shower room"],
    "洗手台": ["洗手台", "洗手盆", "洗漱台", "vanity"],
    "浴缸": ["浴缸", "浴盆", "bathtub"],
    "走廊": ["走廊", "过道", "hallway", "corridor"],
    "储藏室": ["储藏室", "储物间", "杂物间", "storage", "closet"],
    "露台": ["露台", "terrace"],
    "庭院": ["院子", "庭院", "yard", "courtyard"],
    "花园": ["花园", "garden"],
    "车库": ["车库", "garage"],
    "设备间": ["设备间", "设备阳台", "空调机位"],
    "电梯间": ["电梯间", "elevator shaft"],
    "楼梯间": ["楼梯间", "stairwell"],
    "休闲区": ["休闲区", "休息区", "休息室", "活动室", "娱乐室", "多功能室", "多功能房", "棋牌室", "影音室", "健身房"],
}

# ═══════════════════════════════════════════════════════════════════
# 3. 复合空间模式：用于识别 "A+B" 或 "A+B+C" 这类复合空间名称
# ═══════════════════════════════════════════════════════════════════
COMPOUND_SEPARATORS = re.compile(r'[+＋+&＆+、,，/／]')

# 已知的复合空间名称 → 拆分子空间列表
COMPOUND_SPACE_MAP = {
    "客餐厅": ["客厅", "餐厅"],
    "客饭厅": ["客厅", "餐厅"],
    "客厅+餐厅": ["客厅", "餐厅"],
    "主卧+书房": ["主卧", "书房"],
    "主卧+衣帽间": ["主卧", "衣帽间"],
    "书房+衣帽间": ["书房", "衣帽间"],
    "客厅+书房": ["客厅", "书房"],
    "餐厅+厨房": ["餐厅", "厨房"],
    "厨餐厅": ["厨房", "餐厅"],
    "厨+餐": ["厨房", "餐厅"],
    "主卧+主卫": ["主卧", "主卫"],
    "阳台+洗衣": ["阳台", "生活阳台"],
}

# ═══════════════════════════════════════════════════════════════════
# 4. 包含关系映射（松匹配用）
# 例如 "生活阳台" 包含 "阳台"，所以如果 CAD 是 "生活阳台"、AI 是 "阳台"，也算匹配
# ═══════════════════════════════════════════════════════════════════
CONTAINS_MAP = {
    # 子类 → 父类（父类可以通过包含匹配）
    "生活阳台": ["阳台"],          # 生活阳台是阳台的一种
    "休闲阳台": ["阳台"],          # 休闲阳台也是阳台
    "主卫": ["卫生间"],            # 主卫是卫生间的一种
    "客卫": ["卫生间"],            # 客卫也是卫生间
    "公卫": ["卫生间"],
    "次卫": ["卫生间"],
    "西厨": [],              # 西厨独立，业务上不与厨房等同
    "淋浴房": ["卫生间"],          # 淋浴房属于卫浴范畴
    "洗手台": ["卫生间"],
    "北次卧": ["次卧", "卧室"],    # 北次卧是次卧的一种
    "入户花园": ["阳台", "花园"],
    "阳光房": ["阳台"],
    "儿童房": ["次卧", "卧室"],    # 儿童房可当次卧用
    "老人房": ["次卧", "卧室"],
    "客房": ["次卧", "卧室"],

    # ── 新增映射：AI模型不输出但CAD常见的空间 ──
    "露台": ["阳台"],
    "庭院": ["阳台", "花园"],
    "花园": ["阳台"],
    "设备间": ["阳台"],
    "设备阳台": ["阳台"],
    "空调机位": ["阳台"],
    "电梯间": ["走廊"],
    "楼梯间": ["走廊"],
    "电梯厅": ["走廊"],
    "前室": ["走廊"],
    "保姆房": ["次卧", "卧室"],
    "工人房": ["次卧", "卧室"],
    "家政间": ["储藏室", "阳台"],
    "杂物间": ["储藏室"],
    "茶室": ["书房"],
    "棋牌室": ["休闲区"],
    "影音室": ["休闲区"],
    "健身房": ["休闲区"],
    "瑜伽房": ["休闲区"],
}

# ═══════════════════════════════════════════════════════════════════
# 5. 非空间名称过滤列表（CAD 中可能解析出非房间名称的文本）
# ═══════════════════════════════════════════════════════════════════
NON_SPACE_PATTERNS = [
    r'^\d+$',                    # 纯数字（如 "1", "+100", "+300"）
    r'^[＋+]\d+$',               # +数字
    r'^\d+\*',                   # 尺寸标注（如 "300*300铝扣板"）
    r'铝扣板',                   # 装修材料
    r'吊顶',                     # 吊顶说明
    r'包水管',                   # 施工项目
    r'反光灯槽',                 # 施工项目
    r'电动窗帘盒',               # 施工项目
    r'窗台石',                   # 施工项目
    r'墨菲床',                   # 家具
    r'需预留',                   # 施工说明
    r'拆至上梁',                 # 施工说明
    r'osb板',                    # 材料名称
    r'led灯',                    # 电器说明
    r'浴霸',                     # 电器说明
    r'所有柜子',                 # 施工说明
    r'未命名空间',               # 占位名
    r'unknown',                  # 未知
    r'位置由.*确定',             # 安装说明
]


def is_valid_space_name(name: str) -> bool:
    """判断是否为有效的空间名称（过滤掉非房间名）"""
    if not name or name.strip() == "":
        return False
    name = name.strip()
    for pattern in NON_SPACE_PATTERNS:
        if re.search(pattern, name):
            return False
    return True


def normalize_name(name: str) -> Optional[str]:
    """
    标准化空间名称：将各种别名映射到标准名称。

    Args:
        name: 原始空间名称

    Returns:
        标准化后的名称，如果无法识别则返回 None
    """
    if not name or not is_valid_space_name(name):
        return None

    name = name.strip()

    # 直接映射
    if name in SYNONYM_MAP:
        return SYNONYM_MAP[name]

    # 弱匹配：名称包含某个标准名称的键（如 "北次卧" 包含 "次卧"）
    # 注意：只检查 raw_key 是否在 name 中（单向），避免 "卧室" 因在 "主卧室" 中而误匹配为 "主卧"
    for raw, std in sorted(SYNONYM_MAP.items(), key=lambda x: -len(x[0])):
        if raw in name:
            return std

    # 如果是复合名称，取第一个标准化的子空间
    parts = split_compound(name)
    if len(parts) > 1:
        first_std = normalize_name(parts[0])
        if first_std:
            return first_std

    return name  # 无法标准化时返回原名称


def split_compound(name: str) -> List[str]:
    """
    拆分复合空间名称。

    例如：
        "客餐厅"    → ["客厅", "餐厅"]
        "主卧+书房"  → ["主卧", "书房"]
        "客厅+餐厅"  → ["客厅", "餐厅"]
        "阳台"      → ["阳台"]  （非复合，原样返回）

    Args:
        name: 空间名称

    Returns:
        拆分后的子空间名称列表
    """
    if not name:
        return []

    name = name.strip()

    # 优先查内置复合映射
    if name in COMPOUND_SPACE_MAP:
        return COMPOUND_SPACE_MAP[name]

    # 尝试按分隔符拆分
    parts = COMPOUND_SEPARATORS.split(name)
    parts = [p.strip() for p in parts if p.strip()]

    # 如果拆分出多个部分，对每个部分标准化
    if len(parts) > 1:
        return parts

    # 检查是否是隐含复合词（如 "客餐厅" 不在 COMPOUND_SPACE_MAP 中的情况）
    # "客餐厅" = "客" + "餐" + "厅" → ["客厅", "餐厅"]
    if "客餐" in name and "厅" in name:
        return ["客厅", "餐厅"]

    return [name]


def _match_impl(cad_name: str, ai_name: str, _depth: int = 0) -> bool:
    """
    判断两个名称是否匹配的核心实现，带递归深度控制避免无限循环。

    匹配策略（按优先级）：
    1. 完全相等（trim 后）
    2. 同义词映射后相等
    3. 复合词拆分后任意子空间匹配（最多一层递归，_depth < 1）
    4. 包含关系匹配（如 "生活阳台" 匹配 "阳台"）
    5. 标准化后一个包含另一个
    6. 单字符匹配（如 "客" → "客厅"）

    Args:
        cad_name: CAD 解析出的空间名称
        ai_name: AI 识别出的空间名称
        _depth: 递归深度（内部使用，外部调用不要传）

    Returns:
        是否匹配
    """
    if not cad_name or not ai_name:
        return False

    cad_name = cad_name.strip()
    ai_name = ai_name.strip()

    if not is_valid_space_name(cad_name) or not is_valid_space_name(ai_name):
        return False

    # ── 策略 1：完全相等 ──
    if cad_name == ai_name:
        return True

    # ── 策略 2：同义词映射后相等 ──
    cad_std = normalize_name(cad_name)
    ai_std = normalize_name(ai_name)
    if cad_std and ai_std and cad_std == ai_std:
        return True

    # ── 策略 3：复合词拆分匹配（仅一层递归） ──
    if _depth < 1:
        cad_parts = split_compound(cad_name)
        ai_parts = split_compound(ai_name)

        for cp in cad_parts:
            for ap in ai_parts:
                if _match_impl(cp, ap, _depth + 1):
                    return True

    # ── 策略 4：包含关系匹配（单向 + 双向） ──
    # CAD 名是 AI 名的子类
    if cad_name in CONTAINS_MAP and ai_name in CONTAINS_MAP[cad_name]:
        return True
    # AI 名是 CAD 名的子类
    if ai_name in CONTAINS_MAP and cad_name in CONTAINS_MAP[ai_name]:
        return True

    # ── 策略 5：标准化后，一个包含另一个（仅适用于 >=2 字符的包含）
    #    避免 "厅" 因包含在 "客厅" 中而误匹配
    if cad_std and ai_std:
        if len(cad_std) >= 2 and len(ai_std) >= 2:
            if cad_std in ai_std or ai_std in cad_std:
                return True

    # ── 策略 6：单个字符匹配（如 "客" → "客厅"，"餐" → "餐厅"） ──
    # 仅当其中一个名称是单个汉字且另一个名称包含该汉字
    if len(cad_name) == 1 and len(ai_name) > 1:
        if cad_name in ai_name:
            return True
    if len(ai_name) == 1 and len(cad_name) > 1:
        if ai_name in cad_name:
            return True

    return False


def match_space_name(cad_name: str, ai_name: str) -> bool:
    """
    判断 CAD 空间名与 AI 识别空间名是否匹配。

    包装器函数，委托给带深度控制的 _match_impl。
    """
    return _match_impl(cad_name, ai_name, _depth=0)


def get_matched_spaces(cad_name: str) -> List[str]:
    """
    根据 CAD 空间名，返回所有可能匹配的 AI 空间标准名列表。

    例如：
        "客餐厅"  → ["客厅", "餐厅", "客餐厅"]
        "主卧"    → ["主卧"]
        "生活阳台" → ["生活阳台", "阳台"]
        "北次卧"  → ["次卧"]

    Args:
        cad_name: CAD 解析出的空间名称

    Returns:
        可能匹配的 AI 空间标准名列表（去重、保留顺序）
    """
    if not cad_name or not is_valid_space_name(cad_name):
        return []

    cad_name = cad_name.strip()
    results: List[str] = []
    seen: Set[str] = set()

    # 1. 标准化名称
    std = normalize_name(cad_name)
    if std and std not in seen:
        results.append(std)
        seen.add(std)

    # 2. 复合拆分
    parts = split_compound(cad_name)
    for part in parts:
        p_std = normalize_name(part)
        if p_std and p_std not in seen:
            results.append(p_std)
            seen.add(p_std)
        elif part not in seen:
            results.append(part)
            seen.add(part)

    # 3. 包含关系展开（子类 → 父类）
    if cad_name in CONTAINS_MAP:
        for parent in CONTAINS_MAP[cad_name]:
            p_std = normalize_name(parent) or parent
            if p_std not in seen:
                results.append(p_std)
                seen.add(p_std)

    # 4. 如果标准化名称在别名库中，也加入其同义词的标准名
    if std and std in SPACE_ALIASES:
        for alias in SPACE_ALIASES[std]:
            alias_std = normalize_name(alias)
            if alias_std and alias_std not in seen:
                results.append(alias_std)
                seen.add(alias_std)

    return results


def get_ai_matched_spaces(ai_name: str) -> List[str]:
    """
    根据 AI 识别空间名，返回所有可能匹配的 CAD 空间标准名列表。

    Args:
        ai_name: AI 识别出的空间名称

    Returns:
        可能匹配的 CAD 空间标准名列表
    """
    return get_matched_spaces(ai_name)


# ═══════════════════════════════════════════════════════════════════
# 便捷工具函数
# ═══════════════════════════════════════════════════════════════════

def batch_match(
    cad_names: List[str], ai_names: List[str]
) -> dict:
    """
    批量匹配 CAD 空间名与 AI 空间名。

    Args:
        cad_names: CAD 空间名列表
        ai_names: AI 空间名列表

    Returns:
        {
            "matched": [(cad_name, ai_name), ...],
            "unmatched_cad": [cad_name, ...],
            "unmatched_ai": [ai_name, ...],
        }
    """
    matched = []
    matched_cad = set()
    matched_ai = set()

    # 先做精确/同义匹配
    for i, cad in enumerate(cad_names):
        for j, ai in enumerate(ai_names):
            if match_space_name(cad, ai):
                matched.append((cad, ai))
                matched_cad.add(i)
                matched_ai.add(j)

    unmatched_cad = [
        cad_names[i] for i in range(len(cad_names)) if i not in matched_cad
    ]
    unmatched_ai = [
        ai_names[j] for j in range(len(ai_names)) if j not in matched_ai
    ]

    return {
        "matched": matched,
        "unmatched_cad": unmatched_cad,
        "unmatched_ai": unmatched_ai,
    }


def deduplicate_space_names(names: List[str]) -> List[str]:
    """
    对空间名列表去重（考虑同义词）。

    例如：["客厅", "客", "起居室"] → ["客厅"]
    """
    seen_std: Set[str] = set()
    result: List[str] = []
    for name in names:
        std = normalize_name(name)
        key = std or name
        if key not in seen_std:
            seen_std.add(key)
            result.append(name)
    return result


# ═══════════════════════════════════════════════════════════════════
# 自测代码
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 基本匹配测试
    test_cases = [
        ("客厅", "客厅", True),
        ("客", "客厅", True),
        ("客餐厅", "客厅", True),
        ("客餐厅", "餐厅", True),
        ("主卧", "主卧", True),
        ("主卧室", "主卧", True),
        ("生活阳台", "阳台", True),
        ("生活阳台", "生活阳台", True),
        ("休闲阳台", "阳台", True),
        ("北次卧", "次卧", True),
        ("主卫", "卫生间", True),
        ("客卫", "卫生间", True),
        ("厨房", "西厨", False),     # 厨房 ≠ 西厨（业务上视为不同空间）
        ("主卧", "次卧", False),     # 主卧 ≠ 次卧
        ("客厅", "厨房", False),     # 不同空间
        ("未命名空间", "客厅", False),  # 无效名称
        ("", "客厅", False),         # 空名称
        ("主卧+书房", "主卧", True),
        ("主卧+书房", "书房", True),
        ("主卧+书房", "客厅", False),
        ("入户花园", "花园", True),
        ("阳光房", "阳台", True),
        ("门厅", "玄关", True),
        ("客", "厅", False),         # 单字不匹配
    ]

    print("=" * 60)
    print("空间同义词映射库 - 自测")
    print("=" * 60)

    all_pass = True
    for cad, ai, expected in test_cases:
        result = match_space_name(cad, ai)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  {status}: match('{cad}', '{ai}') = {result} (expected {expected})")

    print(f"\n结果: {'全部通过 ✅' if all_pass else '存在失败 ❌'}")

    # get_matched_spaces 测试
    print("\n" + "=" * 60)
    print("get_matched_spaces 测试")
    print("=" * 60)
    test_names = ["客餐厅", "主卧", "生活阳台", "北次卧", "主卫", "入户花园", "主卧+书房"]
    for name in test_names:
        matches = get_matched_spaces(name)
        print(f"  '{name}' → {matches}")

    # 批量匹配测试
    print("\n" + "=" * 60)
    print("批量匹配测试")
    print("=" * 60)
    cad_list = ["客厅", "主卧", "次卧", "厨房", "卫生间", "生活阳台", "客餐厅"]
    ai_list = ["客厅", "主卧", "阳台", "餐厅"]
    batch_result = batch_match(cad_list, ai_list)
    print(f"  CAD: {cad_list}")
    print(f"  AI:  {ai_list}")
    print(f"  匹配: {batch_result['matched']}")
    print(f"  未匹配CAD: {batch_result['unmatched_cad']}")
    print(f"  未匹配AI: {batch_result['unmatched_ai']}")

    # 从数据库获取的实际空间名测试
    print("\n" + "=" * 60)
    print("实际 CAD 空间名匹配测试")
    print("=" * 60)
    real_cad = [
        "主卧", "主卫", "休闲阳台", "儿童房", "入户花园", "北次卧",
        "卫生间", "厨房", "客", "客卫", "客厅", "客房", "客餐厅",
        "次卧", "洗手台", "浴缸", "淋浴", "淋浴房", "生活阳台",
        "老人房", "衣帽间", "西厨", "门厅", "阳光房", "阳台", "餐", "餐厅",
    ]
    for cad in real_cad:
        matches = get_matched_spaces(cad)
        print(f"  '{cad}' → {matches}")

"""
数据库模块 - 基于 SQLite 实现家装报价系统数据持久化
首期5+1张核心表，JSONB字段使用 JSON 文本存储

注：当前环境无 sudo 权限安装 PostgreSQL，使用 SQLite 替代
后期切换 PostgreSQL 只需替换此模块为 asyncpg 实现
"""
import json
import time
import aiosqlite
from pathlib import Path
from typing import Optional

DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "cad_quote.db"


# ─────────────────── 建表 SQL ───────────────────

CREATE_TABLES_SQL = """
-- 1. 图纸记录表
CREATE TABLE IF NOT EXISTS drawing_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    file_hash TEXT DEFAULT '',
    upload_time TEXT NOT NULL,
    parse_status TEXT DEFAULT 'pending',
    cad_result_json TEXT DEFAULT '{}',
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0
);

-- 2. CAD解析结果表
CREATE TABLE IF NOT EXISTS cad_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drawing_id INTEGER NOT NULL,
    space_name TEXT DEFAULT '',
    length REAL DEFAULT 0,
    width REAL DEFAULT 0,
    height REAL DEFAULT 2.8,
    area REAL DEFAULT 0,
    base_quantity TEXT DEFAULT '{}',
    base_price REAL DEFAULT 0,
    rule_version TEXT DEFAULT 'v1.0',
    detail_json TEXT DEFAULT '{}',
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY (drawing_id) REFERENCES drawing_records(id)
);

-- 3. 效果图识别表
CREATE TABLE IF NOT EXISTS image_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drawing_id INTEGER DEFAULT 0,
    image_path TEXT NOT NULL,
    recognized_space TEXT DEFAULT '',
    material_info TEXT DEFAULT '{}',
    confidence REAL DEFAULT 0,
    confirm_status TEXT DEFAULT 'unconfirmed',
    manual_correction TEXT DEFAULT '',
    manual_correction_json TEXT DEFAULT '{}',
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0
);

-- 4. 报价汇总表
CREATE TABLE IF NOT EXISTS quote_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cad_result_id INTEGER DEFAULT 0,
    image_result_ids TEXT DEFAULT '[]',
    base_price REAL DEFAULT 0,
    material_diff_price REAL DEFAULT 0,
    process_add_price REAL DEFAULT 0,
    loss_price REAL DEFAULT 0,
    manage_fee REAL DEFAULT 0,
    tax_fee REAL DEFAULT 0,
    final_price REAL DEFAULT 0,
    project_name TEXT DEFAULT '',
    export_path TEXT DEFAULT '',
    quote_detail_json TEXT DEFAULT '[]',
    trace_json TEXT DEFAULT '{}',
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0
);

-- 5. 操作日志表
CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT DEFAULT '',
    run_status TEXT DEFAULT '',
    duration REAL DEFAULT 0,
    error_info TEXT DEFAULT '',
    operation_action TEXT DEFAULT '',
    lock_status TEXT DEFAULT '',
    trace_id TEXT DEFAULT '',
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0
);

-- 6. 系统配置表（定价/扣减规则等）
CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    description TEXT DEFAULT '',
    update_time TEXT NOT NULL
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_drawing_filename ON drawing_records(filename, create_time);
CREATE INDEX IF NOT EXISTS idx_cad_drawing_id ON cad_analysis_results(drawing_id);
CREATE INDEX IF NOT EXISTS idx_quote_create_time ON quote_records(create_time);
CREATE INDEX IF NOT EXISTS idx_log_task_type ON operation_logs(task_type, start_time);

-- 7. 施工工序表
CREATE TABLE IF NOT EXISTS construction_processes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    work_type TEXT NOT NULL DEFAULT '',
    standard_days REAL NOT NULL DEFAULT 1.0,
    description TEXT DEFAULT '',
    applicable_spaces TEXT DEFAULT '',
    color TEXT DEFAULT '#6366f1',
    unit_price REAL DEFAULT 0.0,
    unit TEXT DEFAULT '㎡',
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0
);

-- 8. 报价模板表
CREATE TABLE IF NOT EXISTS pricing_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT DEFAULT '',
    is_default INTEGER DEFAULT 0,
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0
);

-- 9. 计价分项明细表
CREATE TABLE IF NOT EXISTS pricing_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL DEFAULT 1,
    process_id INTEGER DEFAULT 0,
    work_type TEXT NOT NULL DEFAULT '',
    surface_type TEXT NOT NULL DEFAULT '',
    material_name TEXT DEFAULT '',
    material_code TEXT DEFAULT '',
    item_name TEXT NOT NULL,
    unit TEXT DEFAULT '㎡',
    unit_price REAL DEFAULT 0.0,
    unit_price_material REAL DEFAULT 0.0,
    unit_price_labor REAL DEFAULT 0.0,
    unit_price_aux REAL DEFAULT 0.0,
    sort_order INTEGER DEFAULT 0,
    description TEXT DEFAULT '',
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0
);

-- 10. 自定义视觉模型表[支持前端自定义模型操作]
CREATE TABLE IF NOT EXISTS custom_vl_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_key TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    model_type TEXT NOT NULL DEFAULT 'local',
    api_base_url TEXT DEFAULT '',
    api_token TEXT DEFAULT '',
    api_format TEXT DEFAULT 'openai',
    description TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 100,
    is_enabled INTEGER DEFAULT 1,
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0
);"""


# ─────────────────── 默认定价配置 ───────────────────

DEFAULT_SETTINGS = {
    "base_unit_price": "9374",       # 基础单价（元）
    "manage_fee_rate": "0.05",       # 管理费比例
    "tax_rate": "0.03",              # 税费比例
    "loss_rate": "0.03",             # 损耗比例
    "wall_area_factor": "2.5",       # 墙面面积 = 地面×系数
    "ceiling_factor": "0.8",         # 吊顶面积 = 地面×系数
    "switch_per_10sqm": "1.0",       # 每10㎡ 1个开关插座
    "garbage_per_30sqm": "1.0",      # 每30㎡ 1车垃圾
    "deduct_door": "0.85",           # 木门扣减系数
    "deduct_window": "0.70",         # 铝合金窗扣减系数
    "deduct_sliding_door": "0.50",   # 推拉门扣减系数
    "deduct_bg_wall": "0.50",        # 背景墙扣减系数
    "deduct_niche": "0.00",          # 壁龛扣减系数（0=不计, 增量另算）
    "deduct_pillar": "0.00",         # 立柱扣减系数
    "deduct_bay_window": "0.00",     # 飘窗扣减系数
    "niche_add_rate": "0.05",        # 壁龛增量
    "pillar_add_rate": "0.03",       # 立柱增量
    "bay_window_add_rate": "0.08",   # 飘窗增量
    "perimeter_factor": "1.15",       # 周长系数（矩形为1.0，不规则空间1.15）
    "deduct_door_window": "0.15",     # 门窗洞口扣减比例（通用）
    "deduct_wc_kitchen": "0.12",      # 卫生间/厨房扣减比例
    "deduct_balcony": "0.20",         # 阳台扣减比例
    "active_vl_model": "llava:7b",    # 当前视觉模型名称（llava:7b / qwen2.5:7b）
}


# ─────────────────── 数据库管理器 ───────────────────

class Database:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """打开数据库连接"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def init_db(self):
        """初始化建表 + 默认配置"""
        if not self._conn:
            await self.connect()
        await self._conn.executescript(CREATE_TABLES_SQL)
        # 插入默认配置
        now = _now()
        for key, val in DEFAULT_SETTINGS.items():
            await self._conn.execute(
                "INSERT OR IGNORE INTO system_settings (setting_key, setting_value, description, update_time) VALUES (?, ?, ?, ?)",
                (key, str(val), key, now)
            )
        await self._conn.commit()

        # 插入默认工序（仅首次）
        exists = await self.fetchone("SELECT COUNT(*) as cnt FROM construction_processes")
        if not exists or exists["cnt"] == 0:
            default_processes = [
                ("拆除工程", 1, "demolition", 3.0, "拆旧墙、铲除旧瓷砖、拆门窗", "", "#ef4444", 35.0, "㎡"),
                ("水电改造", 2, "plumbing_electric", 5.0, "布水管、电线管、强弱电箱安装", "卫生间,厨房,阳台", "#f97316", 120.0, "㎡"),
                ("防水工程", 3, "waterproofing", 2.0, "卫生间/厨房/阳台地面防水、闭水试验", "卫生间,厨房,阳台", "#eab308", 45.0, "㎡"),
                ("瓦工工程", 4, "tiling", 7.0, "地面找平、瓷砖铺贴、过门石安装", "", "#22c55e", 85.0, "㎡"),
                ("木工工程", 5, "woodwork", 5.0, "吊顶施工、背景墙基层、柜体制作", "", "#06b6d4", 75.0, "㎡"),
                ("油漆工程", 6, "painting", 4.0, "墙面腻子、打磨、乳胶漆、墙纸铺贴", "", "#3b82f6", 65.0, "㎡"),
                ("安装工程", 7, "installation", 3.0, "灯具、开关插座、洁具、五金安装", "", "#8b5cf6", 55.0, "项"),
                ("保洁收尾", 8, "cleaning", 1.0, "全屋保洁、垃圾清运", "", "#ec4899", 25.0, "㎡"),
                ("竣工验收", 9, "inspection", 1.0, "水电验收、整体验收、交付手续", "", "#6366f1", 0.0, "项"),
                ("软装进场", 10, "furnishing", 1.0, "家具、窗帘、装饰品安装摆放", "", "#a855f7", 0.0, "项"),
            ]
            for p in default_processes:
                name, sort_order, work_type, days, desc, spaces, color, uprice, unit = p
                await self.execute(
                    "INSERT INTO construction_processes (name, sort_order, work_type, standard_days, description, applicable_spaces, color, unit_price, unit, create_time, update_time) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (name, sort_order, work_type, days, desc, spaces, color, uprice, unit, _now(), _now())
                )
            await self._conn.commit()

        # 插入默认报价模板（仅首次）
        tpl_exists = await self.fetchone("SELECT COUNT(*) as cnt FROM pricing_templates")
        if not tpl_exists or tpl_exists["cnt"] == 0:
            now = _now()
            await self.execute(
                "INSERT INTO pricing_templates (name, label, description, is_default, create_time, update_time) VALUES (?,?,?,?,?,?)",
                ("standard", "标准型", "常规装修标准报价模板", 1, now, now)
            )
            await self.execute(
                "INSERT INTO pricing_templates (name, label, description, is_default, create_time, update_time) VALUES (?,?,?,?,?,?)",
                ("economic", "经济型", "经济适用型装修报价模板", 0, now, now)
            )
            await self._conn.commit()

        # 插入默认计价分项（仅首次）
        pi_exists = await self.fetchone("SELECT COUNT(*) as cnt FROM pricing_items")
        if not pi_exists or pi_exists["cnt"] == 0:
            now = _now()
            default_pricing_items = [
                # 墙面分项  (template_id=1 standard)
                (1, "wall", "乳胶漆墙面", "㎡", 45.0, 18.0, 27.0, 0.0, 1),
                (1, "wall", "瓷砖墙面", "㎡", 85.0, 45.0, 35.0, 5.0, 2),
                (1, "wall", "墙纸墙面", "㎡", 65.0, 30.0, 30.0, 5.0, 3),
                (1, "wall", "木饰面墙面", "㎡", 150.0, 90.0, 50.0, 10.0, 4),
                # 地面分项
                (1, "floor", "地砖铺贴", "㎡", 85.0, 45.0, 35.0, 5.0, 10),
                (1, "floor", "实木地板", "㎡", 180.0, 120.0, 50.0, 10.0, 11),
                (1, "floor", "复合地板", "㎡", 95.0, 60.0, 28.0, 7.0, 12),
                (1, "floor", "大理石地面", "㎡", 350.0, 260.0, 75.0, 15.0, 13),
                # 顶面分项
                (1, "ceiling", "石膏板吊顶", "㎡", 120.0, 60.0, 48.0, 12.0, 20),
                (1, "ceiling", "铝扣板吊顶", "㎡", 95.0, 50.0, 35.0, 10.0, 21),
                (1, "ceiling", "乳胶漆顶面", "㎡", 35.0, 15.0, 18.0, 2.0, 22),
                (1, "ceiling", "木饰面吊顶", "㎡", 160.0, 100.0, 48.0, 12.0, 23),
                # 通用分项
                (1, "all", "踢脚线安装", "m", 25.0, 12.0, 10.0, 3.0, 30),
                (1, "all", "门套安装", "套", 350.0, 200.0, 120.0, 30.0, 31),
                (1, "all", "窗套安装", "套", 280.0, 160.0, 95.0, 25.0, 32),
                # 经济型模板 (template_id=2)
                (2, "wall", "乳胶漆墙面", "㎡", 35.0, 12.0, 21.0, 2.0, 1),
                (2, "wall", "瓷砖墙面", "㎡", 65.0, 30.0, 30.0, 5.0, 2),
                (2, "floor", "地砖铺贴", "㎡", 65.0, 30.0, 30.0, 5.0, 10),
                (2, "floor", "复合地板", "㎡", 75.0, 45.0, 25.0, 5.0, 12),
                (2, "ceiling", "乳胶漆顶面", "㎡", 28.0, 10.0, 16.0, 2.0, 22),
                (2, "ceiling", "石膏板吊顶", "㎡", 95.0, 45.0, 40.0, 10.0, 20),
            ]
            for pi in default_pricing_items:
                tid, surface, name, unit, price, mat_price, labor_price, aux_price, sort = pi
                await self.execute(
                    "INSERT INTO pricing_items (template_id, surface_type, item_name, unit, unit_price, unit_price_material, unit_price_labor, unit_price_aux, sort_order, create_time, update_time) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (tid, surface, name, unit, price, mat_price, labor_price, aux_price, sort, now, now)
                )
            await self._conn.commit()

        # 迁移：为已有 custom_vl_models 表补充 api_format 字段
        cols = await self.fetchall("PRAGMA table_info(custom_vl_models)")
        col_names = {c["name"] for c in cols}
        if "api_format" not in col_names:
            await self._conn.execute(
                "ALTER TABLE custom_vl_models ADD COLUMN api_format TEXT DEFAULT 'openai'"
            )
            await self._conn.commit()

    # ─────────────────── 通用 ───────────────────

    async def execute(self, sql: str, params: tuple = ()):
        cur = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cur.lastrowid

    async def fetchone(self, sql: str, params: tuple = ()):
        cur = await self._conn.execute(sql, params)
        return await cur.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()):
        cur = await self._conn.execute(sql, params)
        return await cur.fetchall()

    # ──────── 图纸记录 ────────

    async def add_drawing(self, filename: str, file_path: str, file_size: int = 0):
        now = _now()
        rid = await self.execute(
            "INSERT INTO drawing_records (filename, file_path, file_size, upload_time, create_time, update_time) VALUES (?, ?, ?, ?, ?, ?)",
            (filename, file_path, file_size, now, now, now)
        )
        return rid

    async def update_drawing_parse(self, rid: int, status: str, cad_json: dict = None):
        now = _now()
        if cad_json:
            await self.execute(
                "UPDATE drawing_records SET parse_status=?, cad_result_json=?, update_time=? WHERE id=?",
                (status, json.dumps(cad_json, ensure_ascii=False), now, rid)
            )
        else:
            await self.execute(
                "UPDATE drawing_records SET parse_status=?, update_time=? WHERE id=?",
                (status, now, rid)
            )

    # ──────── CAD解析结果 ────────

    async def add_cad_result(self, drawing_id: int, space_name: str, area: float,
                             length: float = 0, width: float = 0, height: float = 2.8,
                             base_price: float = 0, detail: dict = None):
        now = _now()
        rid = await self.execute(
            "INSERT INTO cad_analysis_results (drawing_id, space_name, length, width, height, area, base_price, detail_json, create_time, update_time) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (drawing_id, space_name, length, width, height, area, base_price,
             json.dumps(detail or {}, ensure_ascii=False), now, now)
        )
        return rid

    async def get_cad_results(self, drawing_id: int):
        rows = await self.fetchall(
            "SELECT * FROM cad_analysis_results WHERE drawing_id=? AND is_deleted=0", (drawing_id,)
        )
        return [_row_to_dict(r) for r in rows]

    async def update_cad_detail_json(self, cad_id: int, detail: dict):
        """更新单个 CAD 结果的 detail_json 字段"""
        now = _now()
        await self.execute(
            "UPDATE cad_analysis_results SET detail_json=?, update_time=? WHERE id=?",
            (json.dumps(detail, ensure_ascii=False), now, cad_id)
        )

    async def batch_update_cad_detail(self, updates: list):
        """
        批量更新 detail_json。
        updates: [(cad_id, detail_dict), ...]
        """
        now = _now()
        for cad_id, detail in updates:
            await self.execute(
                "UPDATE cad_analysis_results SET detail_json=?, update_time=? WHERE id=?",
                (json.dumps(detail, ensure_ascii=False), now, cad_id)
            )

    # ──────── 效果图识别 ────────

    async def add_image_result(self, image_path: str, recognized_space: str = "",
                               material_info: dict = None, confidence: float = 0):
        now = _now()
        rid = await self.execute(
            "INSERT INTO image_analysis_results (image_path, recognized_space, material_info, confidence, create_time, update_time) VALUES (?,?,?,?,?,?)",
            (image_path, recognized_space, json.dumps(material_info or {}, ensure_ascii=False),
             confidence, now, now)
        )
        return rid

    async def update_image_confirm(self, rid: int, confirm_status: str, manual_correction: str = ""):
        now = _now()
        await self.execute(
            "UPDATE image_analysis_results SET confirm_status=?, manual_correction=?, update_time=? WHERE id=?",
            (confirm_status, manual_correction, now, rid)
        )

    async def get_image_results(self, ids: list = None):
        if ids:
            placeholders = ",".join("?" for _ in ids)
            rows = await self.fetchall(
                f"SELECT * FROM image_analysis_results WHERE id IN ({placeholders}) AND is_deleted=0", tuple(ids)
            )
        else:
            rows = await self.fetchall(
                "SELECT * FROM image_analysis_results WHERE is_deleted=0 ORDER BY id DESC LIMIT 50"
            )
        return [_row_to_dict(r) for r in rows]

    # ──────── 报价记录 ────────

    async def add_quote(self, cad_result_id: int, image_result_ids: list,
                        base_price: float, material_diff_price: float = 0,
                        process_add_price: float = 0, loss_price: float = 0,
                        manage_fee: float = 0, tax_fee: float = 0,
                        final_price: float = 0, quote_detail: list = None,
                        trace: dict = None, project_name: str = ""):
        now = _now()
        rid = await self.execute(
            """INSERT INTO quote_records 
            (cad_result_id, image_result_ids, base_price, material_diff_price, 
             process_add_price, loss_price, manage_fee, tax_fee, final_price,
             project_name, quote_detail_json, trace_json, create_time, update_time)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cad_result_id, json.dumps(image_result_ids), base_price, material_diff_price,
             process_add_price, loss_price, manage_fee, tax_fee, final_price,
             project_name, json.dumps(quote_detail or [], ensure_ascii=False),
             json.dumps(trace or {}, ensure_ascii=False), now, now)
        )
        return rid

    async def update_quote_export(self, rid: int, export_path: str):
        now = _now()
        await self.execute(
            "UPDATE quote_records SET export_path=?, update_time=? WHERE id=?",
            (export_path, now, rid)
        )

    async def update_quote_items(self, rid: int, items: list, totals: dict, trace_json: dict = None):
        """更新报价明细项及汇总金额"""
        now = _now()
        base_price = totals.get("base_price", 0)
        material_diff_price = totals.get("material_diff_price", 0)
        process_add_price = totals.get("process_add_price", 0)
        loss_price = totals.get("loss_price", 0)
        manage_fee = totals.get("manage_fee", 0)
        tax_fee = totals.get("tax_fee", 0)
        final_price = totals.get("final_price", 0)
        await self.execute(
            """UPDATE quote_records SET
               quote_detail_json=?, base_price=?, material_diff_price=?,
               process_add_price=?, loss_price=?, manage_fee=?, tax_fee=?,
               final_price=?, trace_json=?, update_time=?
               WHERE id=?""",
            (json.dumps(items, ensure_ascii=False),
             base_price, material_diff_price, process_add_price,
             loss_price, manage_fee, tax_fee, final_price,
             json.dumps(trace_json or {}, ensure_ascii=False), now, rid)
        )

    async def get_pricing_items(self, template_id: int = None):
        """获取定价分项，可选按模板筛选"""
        if template_id:
            rows = await self.fetchall(
                "SELECT * FROM pricing_items WHERE template_id=? AND is_deleted=0 ORDER BY sort_order",
                (template_id,)
            )
        else:
            rows = await self.fetchall(
                "SELECT * FROM pricing_items WHERE is_deleted=0 ORDER BY template_id, sort_order"
            )
        return [_row_to_dict(r) for r in rows]

    async def get_quote(self, rid: int):
        row = await self.fetchone(
            "SELECT * FROM quote_records WHERE id=? AND is_deleted=0", (rid,)
        )
        return _row_to_dict(row) if row else None

    async def get_quotes(self, page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        rows = await self.fetchall(
            """SELECT q.*, d.cad_result_json as cad_detail_json, d.filename as drawing_name
               FROM quote_records q
               LEFT JOIN drawing_records d ON q.cad_result_id = d.id
               WHERE q.is_deleted=0
               ORDER BY q.id DESC LIMIT ? OFFSET ?""",
            (page_size, offset)
        )
        total = await self.fetchone(
            "SELECT COUNT(*) as cnt FROM quote_records WHERE is_deleted=0"
        )
        items = []
        for r in rows:
            item = _row_to_dict(r)
            # 解析 cad_detail_json 获取空间数
            cdj = item.get('cad_detail_json', '{}')
            if isinstance(cdj, str):
                try:
                    cdj = json.loads(cdj)
                except:
                    cdj = {}
            if isinstance(cdj, dict):
                item['space_count'] = cdj.get('spaces_count', 0)
                item['total_area'] = cdj.get('total_area', 0)
                item['cad_detail_json'] = cdj
            items.append(item)
        return {
            "items": items,
            "total": total["cnt"] if total else 0,
            "page": page,
            "page_size": page_size
        }

    # ──────── 操作日志 ────────

    async def add_log(self, task_type: str, start_time: str = None,
                      end_time: str = "", run_status: str = "running",
                      duration: float = 0, error_info: str = "",
                      operation_action: str = "", lock_status: str = "",
                      trace_id: str = ""):
        now = _now()
        rid = await self.execute(
            "INSERT INTO operation_logs (task_type, start_time, end_time, run_status, duration, error_info, operation_action, lock_status, trace_id, create_time, update_time) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (task_type, start_time or now, end_time, run_status, duration,
             error_info, operation_action, lock_status, trace_id, now, now)
        )
        return rid

    async def update_log(self, rid: int, end_time: str, run_status: str,
                         duration: float, error_info: str = ""):
        await self.execute(
            "UPDATE operation_logs SET end_time=?, run_status=?, duration=?, error_info=?, update_time=? WHERE id=?",
            (end_time, run_status, duration, error_info, _now(), rid)
        )

    async def get_logs(self, page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        rows = await self.fetchall(
            "SELECT * FROM operation_logs WHERE is_deleted=0 ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        total = await self.fetchone(
            "SELECT COUNT(*) as cnt FROM operation_logs WHERE is_deleted=0"
        )
        return {
            "items": [_row_to_dict(r) for r in rows],
            "total": total["cnt"] if total else 0,
            "page": page,
            "page_size": page_size
        }

    # ──────── 施工工序 ────────

    async def get_processes(self):
        rows = await self.fetchall(
            "SELECT * FROM construction_processes WHERE is_deleted=0 ORDER BY sort_order ASC"
        )
        return [_row_to_dict(r) for r in rows]

    async def get_process(self, pid: int):
        row = await self.fetchone(
            "SELECT * FROM construction_processes WHERE id=? AND is_deleted=0", (pid,)
        )
        return _row_to_dict(row) if row else None

    async def add_process(self, name: str, sort_order: int, work_type: str = "",
                          standard_days: float = 1.0, description: str = "",
                          applicable_spaces: str = "", color: str = "#6366f1"):
        now = _now()
        return await self.execute(
            "INSERT INTO construction_processes (name, sort_order, work_type, standard_days, description, applicable_spaces, color, create_time, update_time) VALUES (?,?,?,?,?,?,?,?,?)",
            (name, sort_order, work_type, standard_days, description, applicable_spaces, color, now, now)
        )

    async def update_process(self, pid: int, **kwargs):
        allowed = {"name", "sort_order", "work_type", "standard_days", "description", "applicable_spaces", "color", "unit_price", "unit"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["update_time"] = _now()
        sets = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [pid]
        await self.execute(
            f"UPDATE construction_processes SET {sets} WHERE id=?", tuple(values)
        )

    async def delete_process(self, pid: int):
        now = _now()
        await self.execute(
            "UPDATE construction_processes SET is_deleted=1, update_time=? WHERE id=?", (now, pid)
        )

    # ──────── 系统配置 ────────

    async def get_settings(self) -> dict:
        rows = await self.fetchall("SELECT setting_key, setting_value FROM system_settings")
        return {r["setting_key"]: r["setting_value"] for r in rows}

    async def update_setting(self, key: str, value: str):
        await self.execute(
            "UPDATE system_settings SET setting_value=?, update_time=? WHERE setting_key=?",
            (value, _now(), key)
        )

    # ──────── 报价模板 ────────

    async def get_pricing_templates(self):
        rows = await self.fetchall(
            "SELECT * FROM pricing_templates WHERE is_deleted=0 ORDER BY id ASC"
        )
        return [_row_to_dict(r) for r in rows]

    async def get_default_template_id(self) -> int:
        row = await self.fetchone(
            "SELECT id FROM pricing_templates WHERE is_default=1 AND is_deleted=0"
        )
        return row["id"] if row else 1

    async def set_default_template(self, tid: int):
        now = _now()
        await self.execute(
            "UPDATE pricing_templates SET is_default=0, update_time=? WHERE is_default=1",
            (now,)
        )
        await self.execute(
            "UPDATE pricing_templates SET is_default=1, update_time=? WHERE id=?",
            (now, tid)
        )

    # ──────── 计价分项 ────────

    async def get_pricing_items(self, template_id: int = None):
        if template_id:
            rows = await self.fetchall(
                "SELECT * FROM pricing_items WHERE template_id=? AND is_deleted=0 ORDER BY sort_order ASC",
                (template_id,)
            )
        else:
            rows = await self.fetchall(
                "SELECT * FROM pricing_items WHERE is_deleted=0 ORDER BY template_id, sort_order ASC"
            )
        return [_row_to_dict(r) for r in rows]

    async def get_pricing_item(self, pid: int):
        row = await self.fetchone(
            "SELECT * FROM pricing_items WHERE id=? AND is_deleted=0", (pid,)
        )
        return _row_to_dict(row) if row else None

    async def add_pricing_item(self, template_id: int, surface_type: str, item_name: str,
                               unit: str = "㎡", unit_price: float = 0.0,
                               unit_price_material: float = 0.0,
                               unit_price_labor: float = 0.0,
                               unit_price_aux: float = 0.0,
                               sort_order: int = 0, description: str = ""):
        now = _now()
        return await self.execute(
            "INSERT INTO pricing_items (template_id, surface_type, item_name, unit, unit_price, unit_price_material, unit_price_labor, unit_price_aux, sort_order, description, create_time, update_time) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (template_id, surface_type, item_name, unit, unit_price, unit_price_material, unit_price_labor, unit_price_aux, sort_order, description, now, now)
        )

    async def update_pricing_item(self, pid: int, **kwargs):
        allowed = {"template_id", "surface_type", "item_name", "unit", "unit_price",
                   "unit_price_material", "unit_price_labor", "unit_price_aux",
                   "sort_order", "description"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["update_time"] = _now()
        sets = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [pid]
        await self.execute(
            f"UPDATE pricing_items SET {sets} WHERE id=?", tuple(values)
        )

    async def delete_pricing_item(self, pid: int):
        now = _now()
        await self.execute(
            "UPDATE pricing_items SET is_deleted=1, update_time=? WHERE id=?", (now, pid)
        )

    # ──────── 自定义视觉模型[增删改查] ────────

    async def get_custom_vl_models(self):
        rows = await self.fetchall(
            "SELECT * FROM custom_vl_models WHERE is_deleted=0 ORDER BY sort_order ASC, id ASC"
        )
        return [_row_to_dict(r) for r in rows]

    async def add_custom_vl_model(self, model_key: str, label: str,
                                   model_type: str = "local",
                                   api_base_url: str = "",
                                   api_token: str = "",
                                   api_format: str = "openai",
                                   description: str = "",
                                   sort_order: int = 100):
        now = _now()
        return await self.execute(
            """INSERT INTO custom_vl_models 
               (model_key, label, model_type, api_base_url, api_token, api_format, description, sort_order, create_time, update_time) 
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (model_key, label, model_type, api_base_url, api_token, api_format, description, sort_order, now, now)
        )

    async def update_custom_vl_model(self, mid: int, **kwargs):
        allowed = {"model_key", "label", "model_type", "api_base_url", "api_token",
                   "api_format", "description", "sort_order", "is_enabled"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["update_time"] = _now()
        sets = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [mid]
        await self.execute(
            f"UPDATE custom_vl_models SET {sets} WHERE id=?", tuple(values)
        )

    async def delete_custom_vl_model(self, mid: int):
        now = _now()
        await self.execute(
            "UPDATE custom_vl_models SET is_deleted=1, update_time=? WHERE id=?", (now, mid)
        )

    async def get_deleted_custom_vl_models(self):
        rows = await self.fetchall(
            "SELECT * FROM custom_vl_models WHERE is_deleted=1 ORDER BY update_time DESC"
        )
        return [_row_to_dict(r) for r in rows]

    async def restore_custom_vl_model(self, mid: int):
        now = _now()
        await self.execute(
            "UPDATE custom_vl_models SET is_deleted=0, update_time=? WHERE id=?", (now, mid)
        )

    async def hard_delete_custom_vl_model(self, mid: int):
        await self.execute("DELETE FROM custom_vl_models WHERE id=?", (mid,))


# ─────────────────── 工具函数 ───────────────────

def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row) -> dict:
    """将 sqlite3.Row 转为 dict，解析 JSON 字段"""
    d = dict(row)
    for field in ["cad_result_json", "detail_json", "material_info",
                   "manual_correction_json", "quote_detail_json", "trace_json",
                   "base_quantity"]:
        if field in d and isinstance(d[field], str) and d[field]:
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    # image_result_ids 是 JSON 字符串
    if "image_result_ids" in d and isinstance(d["image_result_ids"], str):
        try:
            d["image_result_ids"] = json.loads(d["image_result_ids"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


# 全局单例
db = Database()

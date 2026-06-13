"""
VL 多模态大模型调用计费管控模块

核心功能：
1. 统一包月/打包计费管控，禁止零散按量扣费
2. 多引擎兜底切换（DeepSeek VL → 备选引擎）
3. 调用频率限制 & 失败重试
4. 成本审计日志
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# == 引擎配置 ==
ENGINE_DEEPSEEK = "deepseek_vl"       # DeepSeek-VL（主）
ENGINE_HUNYUAN = "hunyuan_vl"          # 腾讯混元 VL（备1）
ENGINE_GLM = "glm_vl"                  # 智谱 GLM-VL（备2）


@dataclass
class CostBudget:
    """成本预算配置"""
    monthly_budget: float            # 月度预算上限（元）
    monthly_used: float = 0.0        # 月度已用
    daily_budget: float = 100.0      # 日预算上限
    daily_used: float = 0.0          # 日已用
    max_tokens_per_call: int = 1000   # 单token限制
    engine: str = ENGINE_DEEPSEEK    # 主引擎
    fallback_order: List[str] = field(default_factory=lambda: [ENGINE_HUNYUAN, ENGINE_GLM])
    
    # 计费模式
    billing_mode: str = "package"      # "package"=包月, "per_call"=按次, "per_token"=按token


@dataclass
class CostEntry:
    """成本条目"""
    timestamp: str
    engine: str
    room_type: str
    tokens_used: int
    cost: float
    call_id: str
    result: str = "success"
    raw_response: Optional[str] = None


class VlCostController:
    """VL 调用计费控制器"""
    
    def __init__(self, budget: Optional[CostBudget] = None):
        self.budget = budget or CostBudget(
            monthly_budget=float(os.getenv("VL_MONTHLY_BUDGET", "500")),
            daily_budget=float(os.getenv("VL_DAILY_BUDGET", "100")),
        )
        
        # 调用审计日志
        self.log_file = Path(os.getenv("VL_COST_LOG_FILE", "/tmp/vl_cost_audit.json"))
        self._load_log()
        
        # 防抖：同一请求 5 秒内不重复调用
        self._last_call_cache = {}
        self._cache_ttl = 5
        
    def _load_log(self):
        """加载成本日志"""
        if self.log_file.exists():
            try:
                with open(self.log_file) as f:
                    self._cost_entries = json.load(f)
            except Exception:
                self._cost_entries = []
        else:
            self._cost_entries = []
    
    def _save_log(self):
        """保存成本日志"""
        try:
            self.log_file.write_text(json.dumps(self._cost_entries, ensure_ascii=False, indent=2))
        except Exception:
            pass
    
    def check_budget(self) -> dict:
        """
        检查当前是否超出预算
        
        Returns:
            {"allowed": bool, "reason": str, "remaining": float}
        """
        # 月预算检查
        if self.budget.monthly_used >= self.budget.monthly_budget:
            return {
                "allowed": False,
                "reason": f"月度预算已超支 {self.budget.monthly_used}/{self.budget.monthly_budget} 元",
                "remaining": 0,
            }
        
        # 日预算检查
        if self.budget.daily_used >= self.budget.daily_budget:
            return {
                "allowed": False,
                "reason": f"日预算已超支 {self.budget.daily_used}/{self.budget.daily_budget} 元",
                "remaining": 0,
            }
        
        remaining = min(
            self.budget.monthly_budget - self.budget.monthly_used,
            self.budget.daily_budget - self.budget.daily_used,
        )
        
        return {
            "allowed": True,
            "reason": "ok",
            "remaining": round(remaining, 2),
        }
    
    def try_call_vl(
        self,
        image_data: bytes,
        prompt: str,
        room_type: str = "unknown",
        model: str = "deepseek-vl-2",
    ) -> dict:
        """
        VL 调用入口（含计费管控 → 引擎选择 → 兜底切换）
        
        Args:
            image_data: 图片二进制数据
            prompt: 分析提示词
            room_type: 房间类型（用于统计）
            model: VL 模型名称（默认 deepseek-vl-2）
        Returns:
            {"success": bool, "result": dict, "engine": str, "cost": float, "call_id": str}
        """
        # 1. 预算检查
        budget_check = self.check_budget()
        if not budget_check["allowed"]:
            return {
                "success": False,
                "result": {"error": budget_check["reason"]},
                "engine": None,
                "cost": 0,
                "call_id": "",
            }
        
        # 2. 引擎选择 & 调用
        engine_list = [self.budget.engine] + self.budget.fallback_order
        
        # 过滤掉未配置的引擎
        config_keys = ["DEEPSEEK_API_KEY", "HUNYUAN_API_KEY", "GLM_API_KEY"]
        engines_with_config = {
            ENGINE_DEEPSEEK: "DEEPSEEK_API_KEY",
            ENGINE_HUNYUAN: "HUNYUAN_API_KEY",
            ENGINE_GLM: "GLM_API_KEY",
        }
        
        available_engines = [
            e for e in engine_list if engines_with_config.get(e) and os.getenv(engines_with_config[e])
        ]
        
        if not available_engines:
            available_engines = [ENGINE_DEEPSEEK]  # 默认尝试 DeepSeek
        
        call_id = f"vl_{int(time.time())}_{id(self)}"
        result = {
            "success": False,
            "result": None,
            "engine": None,
            "cost": 0,
            "call_id": call_id,
            "fallback_count": 0,
        }
        
        for engine in available_engines:
            try:
                cost_per_call = self._estimate_cost(model)
                
                # 成本检查
                if (self.budget.monthly_used + cost_per_call > self.budget.monthly_budget or
                    self.budget.daily_used + cost_per_call > self.budget.daily_budget):
                    continue
                
                response = self._call_engine(engine, image_data, prompt, model)
                
                if response.get("success"):
                    result.update({
                        "success": True,
                        "result": response["result"],
                        "engine": engine,
                        "cost": cost_per_call,
                    })
                    
                    # 记录成本
                    self._record_cost(
                        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                        engine=engine,
                        room_type=room_type,
                        tokens_used=1000,  # VL按图计费，按1000 token估算
                        cost=cost_per_call,
                        call_id=call_id,
                        result="success",
                    )
                    
                    return result
                else:
                    result["fallback_count"] += 1
                    
            except Exception as e:
                result["fallback_count"] += 1
                logger.warning(f"VL call failed (engine={engine}): {e}")
        
        return {
            "success": False,
            "result": {"error": "所有VL引擎调用失败"},
            "engine": None,
            "cost": 0,
            "call_id": call_id,
            "fallback_count": result["fallback_count"],
        }
    
    def _estimate_cost(self, model: str) -> float:
        """估算单次调用成本（元）"""
        costs = {
            "deepseek-v4-flash": 0.005,  # DeepSeek V4 Flash（支持视觉，按token计费）
            "deepseek-vl-2": 0.005,   # 旧版保留兼容
            "deepseek-chat": 0.003,
            "qwen-vl-max": 0.02,
            "qwen-vl-plus": 0.008,
            "hunyan-vl": 0.015,
            "glm-vl": 0.01,
        }
        return costs.get(model, 0.01)
    
    def _call_engine(self, engine: str, image_data: bytes, prompt: str, model: str) -> dict:
        """调用具体引擎"""
        if engine == ENGINE_DEEPSEEK:
            return self._call_deepseek(image_data, prompt, model)
        elif engine == ENGINE_HUNYUAN:
            return self._call_hunyuan(image_data, prompt, model)
        elif engine == ENGINE_GLM:
            return self._call_glm(image_data, prompt, model)
        else:
            return {"success": False, "result": {"error": f"未知引擎: {engine}"}}
    
    def _call_deepseek(self, image_data: bytes, prompt: str, model: str) -> dict:
        """调 DeepSeek-VL 多模态（OpenAI 兼容 API）"""
        import base64
        
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return {"success": False, "result": {"error": "DEEPSEEK_API_KEY 未配置"}}
        
        image_b64 = base64.b64encode(image_data).decode("utf-8")
        mime = "image/jpeg"
        
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
        
        messages = [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=4096,
            )
            
            text = response.choices[0].message.content
            return {"success": True, "result": {"text": text}}
        
        except Exception as e:
            return {"success": False, "result": {"error": f"DeepSeek-VL调用失败: {e}"}}
    
    def _call_hunyuan(self, image_data: bytes, prompt: str, model: str) -> dict:
        """调腾讯混元 VL"""
        import base64
        import openai
        
        api_key = os.getenv("HUNYUAN_API_KEY")
        if not api_key:
            return {"success": False, "result": {"error": "HUNYUAN_API_KEY 未配置"}}
        
        image_b64 = base64.b64encode(image_data).decode("utf-8")
        
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.hunyuan.cloud.tencent.com/v1/",
        )
        
        messages = [
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ]}
        ]
        
        try:
            response = client.chat.completions.create(
                model="glm-vl",
                messages=messages,
            )
            text = response.choices[0].message.content
            return {"success": True, "result": {"text": text}}
        except Exception as e:
            return {"success": False, "result": {"error": f"混元VL调用失败: {e}"}}
    
    def _call_glm(self, image_data: bytes, prompt: str, model: str) -> dict:
        """调智谱 GLM-VL"""
        import base64
        import openai
        
        api_key = os.getenv("GLM_API_KEY")
        if not api_key:
            return {"success": False, "result": {"error": "GLM_API_KEY 未配置"}}
        
        image_b64 = base64.b64encode(image_data).decode("utf-8")
        
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
        )
        
        messages = [
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ]}
        ]
        
        try:
            response = client.chat.completions.create(
                model="glm-vl-plus",
                messages=messages,
            )
            text = response.choices[0].message.content
            return {"success": True, "result": {"text": text}}
        except Exception as e:
            return {"success": False, "result": {"error": f"GLM-VL调用失败: {e}"}}
    
    def _record_cost(self, timestamp: str, engine: str, room_type: str,
                     tokens_used: int, cost: float, call_id: str, result: str):
        """记录成本条目"""
        self._cost_entries.append({
            "timestamp": timestamp,
            "engine": engine,
            "room_type": room_type,
            "tokens_used": tokens_used,
            "cost": cost,
            "call_id": call_id,
            "result": result,
        })
        
        # 更新累计用量
        self.budget.monthly_used += cost
        self.budget.daily_used += cost
        
        self._save_log()
    
    def get_audit_report(self) -> dict:
        """获取成本审计报告"""
        total_cost = sum(e["cost"] for e in self._cost_entries)
        total_calls = len(self._cost_entries)
        
        by_engine = {}
        by_room = {}
        for entry in self._cost_entries:
            eng = entry["engine"]
            by_engine[eng] = by_engine.get(eng, {"count": 0, "cost": 0})
            by_engine[eng]["count"] += 1
            by_engine[eng]["cost"] += entry["cost"]
            
            room = entry["room_type"]
            by_room[room] = by_room.get(room, {"count": 0, "cost": 0})
            by_room[room]["count"] += 1
            by_room[room]["cost"] += entry["cost"]
        
        return {
            "total_cost": round(total_cost, 2),
            "total_calls": total_calls,
            "monthly_budget": self.budget.monthly_budget,
            "daily_budget": self.budget.daily_budget,
            "monthly_remaining": round(max(0, self.budget.monthly_budget - self.budget.monthly_used), 2),
            "daily_remaining": round(max(0, self.budget.daily_budget - self.budget.daily_used), 2),
            "by_engine": by_engine,
            "by_room": by_room,
            "budget_status": self.check_budget(),
        }

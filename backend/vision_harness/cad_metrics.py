import numpy as np


# 均方误差
def mse(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if y_true.shape != y_pred.shape:
        raise ValueError("y_true 和 y_pred 形状必须一致")

    return np.mean((y_true - y_pred) ** 2)


def evaluate_cad_evaluations(evaluations: list) -> dict:
    """
    从 evaluations 列表中提取每个房间的测试值与预测值，计算面积和周长的均方误差
    
    Args:
        evaluations: cad_test 接口返回的 evaluations 数组，每个元素包含：
            - name: 房间名称
            - predict_area / true_area: 面积预测值和真实值
            - predict_perimeter / true_perimeter: 周长预测值和真实值
    
    Returns:
        {
            "rooms": [{"name": ..., "abs_error_area": ..., "rel_error_area": ..., ...}, ...],
            "overall_mse": {"area_sqm": ..., "perimeter_m": ...}
        }
    """
    
    # 收集所有有真实值的数据
    rooms_with_data = []
    all_true_areas = []
    all_pred_areas = []
    all_true_perimeters = []
    all_pred_perimeters = []
    
    for item in evaluations:
        name = item.get("name", "未知房间")
        true_area = item.get("true_area")
        predict_area = item.get("predict_area")
        true_perim = item.get("true_perimeter")
        pred_perim = item.get("predict_perimeter")
        
        # 只处理有真实数据的房间
        if true_area is not None or true_perim is not None:
            room_entry = {
                "name": name,
                "abs_error_area": None,
                "rel_error_area": None,
                "abs_error_perimeter": None,
                "rel_error_perimeter": None,
            }
            
            if true_area is not None:
                true_area_f = float(true_area)
                pred_area_f = float(predict_area) if predict_area is not None else 0.0
                abs_err = abs(pred_area_f - true_area_f)
                rel_err = abs_err / abs(true_area_f) if true_area_f != 0 else None
                
                room_entry["abs_error_area"] = round(abs_err, 4)
                room_entry["rel_error_area"] = round(rel_err, 4) if rel_err is not None else None
                
                all_true_areas.append(true_area_f)
                all_pred_areas.append(pred_area_f)
            
            if true_perim is not None:
                true_perim_f = float(true_perim)
                pred_perim_f = float(pred_perim) if pred_perim is not None else 0.0
                abs_err = abs(pred_perim_f - true_perim_f)
                rel_err = abs_err / abs(true_perim_f) if true_perim_f != 0 else None
                
                room_entry["abs_error_perimeter"] = round(abs_err, 4)
                room_entry["rel_error_perimeter"] = round(rel_err, 4) if rel_err is not None else None
                
                all_true_perimeters.append(true_perim_f)
                all_pred_perimeters.append(pred_perim_f)
            
            rooms_with_data.append(room_entry)
    
    # 计算总体MSE
    overall_mse = {}
    
    if len(all_true_areas) > 0:
        y_true_area = np.array(all_true_areas)
        y_pred_area = np.array(all_pred_areas)
        overall_mse["area_sqm"] = round(mse(y_true_area, y_pred_area), 4)
    
    if len(all_true_perimeters) > 0:
        y_true_perim = np.array(all_true_perimeters)
        y_pred_perim = np.array(all_pred_perimeters)
        overall_mse["perimeter_m"] = round(mse(y_true_perim, y_pred_perim), 4)
    
    return {
        "rooms": rooms_with_data,
        "overall_mse": overall_mse
    }
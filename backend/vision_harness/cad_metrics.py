import numpy as np


# 局方误差
def mse(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if y_true.shape != y_pred.shape:
        raise ValueError("y_true 和 y_pred 形状必须一致")

    return np.mean((y_true - y_pred) ** 2)
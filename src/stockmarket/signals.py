from dataclasses import dataclass

@dataclass(frozen=True)
class Signal:
    action: str
    predicted_return: float
    net_edge: float
    confidence: float


def make_signal(predicted_return:float,buy_threshold:float=0.005,sell_threshold:float=-0.005,round_trip_cost:float=0.003)->Signal:
    if sell_threshold>=buy_threshold: raise ValueError("sell_threshold must be below buy_threshold")
    net_edge=predicted_return-round_trip_cost
    if net_edge>=buy_threshold: action="Buy"
    elif net_edge<=sell_threshold: action="Sell"
    else: action="Hold"
    confidence_scale=max(abs(buy_threshold),abs(sell_threshold),1e-9)
    confidence=min(abs(net_edge)/confidence_scale,1.0)
    return Signal(action,predicted_return,net_edge,confidence)

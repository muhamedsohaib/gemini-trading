import json
import os

import numpy as np


class QLearningOptimizer:
    """Historical prototype allocation selector; not approved for execution."""

    def __init__(
        self,
        q_table_file: str = "q_table.json",
        learning_rate: float = 0.1,
        discount_factor: float = 0.9,
        epsilon: float = 0.15,
    ) -> None:
        self.q_table_file = q_table_file
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.q_table = self.load_q_table()
        self.allocations = {
            0: {"label": "SKIP_TRADE", "risk_pct": 0.00},
            1: {"label": "CONSERVATIVE", "risk_pct": 0.25},
            2: {"label": "STANDARD", "risk_pct": 0.50},
            3: {"label": "AGGRESSIVE", "risk_pct": 1.00},
        }

    def load_q_table(self):
        if os.path.exists(self.q_table_file):
            try:
                with open(self.q_table_file, encoding="utf-8") as file_handle:
                    return json.load(file_handle)
            except Exception:
                return {}
        return {}

    def save_q_table(self) -> None:
        with open(self.q_table_file, "w", encoding="utf-8") as file_handle:
            json.dump(self.q_table, file_handle, indent=4)

    def get_state_key(
        self,
        regime: str,
        action_signal: str,
        confidence: float,
        bb_width: float,
    ) -> str:
        regime_clean = regime.split(" ")[0].strip()
        conf_bucket = (
            "HIGH_CONF"
            if confidence >= 80.0
            else "MED_CONF"
            if confidence >= 60.0
            else "LOW_CONF"
        )
        vol_bucket = "HIGH_VOL" if bb_width > 0.02 else "LOW_VOL"
        return f"{regime_clean}|{action_signal}|{conf_bucket}|{vol_bucket}"

    def select_action(self, state_key: str, max_risk_aed: float = 10.00):
        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0, 0.2, 0.5, 0.3]
            self.save_q_table()

        q_values = self.q_table[state_key]
        if np.random.uniform(0, 1) < self.epsilon:
            chosen_idx = int(np.random.choice([0, 1, 2, 3]))
            mode = "Exploration (Random Test)"
        else:
            chosen_idx = int(np.argmax(q_values))
            mode = "Exploitation (Optimal Learned Q-Value)"

        allocation_data = self.allocations[chosen_idx]
        capital_to_risk = round(max_risk_aed * allocation_data["risk_pct"], 2)
        return chosen_idx, capital_to_risk, allocation_data["label"], mode, q_values

    def update_q_value(self, state_key: str, action_idx: int, reward: float) -> None:
        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0, 0.0, 0.0, 0.0]

        current_q = self.q_table[state_key][action_idx]
        max_next_q = max(self.q_table[state_key])
        new_q = current_q + self.lr * (
            reward + self.gamma * max_next_q - current_q
        )
        self.q_table[state_key][action_idx] = round(new_q, 4)
        self.save_q_table()


def optimize_execution(
    regime: str,
    trade_plan: dict,
    confidence: float,
    bb_width: float,
    max_budget_aed: float = 10.00,
):
    optimizer = QLearningOptimizer()
    action_signal = trade_plan.get("action", "HOLD")

    if "HOLD" in action_signal:
        return trade_plan["action"], 0.00, trade_plan["target_entry"], "HOLD_STATE"

    state_key = optimizer.get_state_key(
        regime,
        action_signal,
        confidence,
        bb_width,
    )
    chosen_idx, capital_risked, _label, _mode, _values = optimizer.select_action(
        state_key,
        max_risk_aed=max_budget_aed,
    )
    final_action = "SKIP_RL_VETO" if chosen_idx == 0 else action_signal
    return final_action, capital_risked, trade_plan["target_entry"], state_key

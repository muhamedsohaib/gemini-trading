import os
import json
import numpy as np

class QLearningOptimizer:
    """
    Layer 5: Lightweight Reinforcement Learning Action Optimizer
    Uses Tabular Q-Learning to dynamically determine position sizing and execution aggressiveness.
    """
    def __init__(self, q_table_file="q_table.json", learning_rate=0.1, discount_factor=0.9, epsilon=0.15):
        self.q_table_file = q_table_file
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.q_table = self.load_q_table()
        
        # Available action allocations: 0% (Skip), 25% (Conservative), 50% (Standard), 100% (Aggressive)
        self.allocations = {
            0: {"label": "SKIP_TRADE", "risk_pct": 0.00, "desc": "RL Defensive Veto (0.00 AED)"},
            1: {"label": "CONSERVATIVE", "risk_pct": 0.25, "desc": "Low Risk Allocation (2.50 AED)"},
            2: {"label": "STANDARD", "risk_pct": 0.50, "desc": "Moderate Risk Allocation (5.00 AED)"},
            3: {"label": "AGGRESSIVE", "risk_pct": 1.00, "desc": "Max Budget Allocation (10.00 AED)"}
        }

    def load_q_table(self):
        if os.path.exists(self.q_table_file):
            try:
                with open(self.q_table_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_q_table(self):
        with open(self.q_table_file, "w") as f:
            json.dump(self.q_table, f, indent=4)

    def get_state_key(self, regime: str, action_signal: str, confidence: float, bb_width: float) -> str:
        """Discretizes continuous market metrics into a clean state string for Q-table lookup."""
        regime_clean = regime.split(" ")[0].strip()
        conf_bucket = "HIGH_CONF" if confidence >= 80.0 else "MED_CONF" if confidence >= 60.0 else "LOW_CONF"
        vol_bucket = "HIGH_VOL" if bb_width > 0.02 else "LOW_VOL"
        return f"{regime_clean}|{action_signal}|{conf_bucket}|{vol_bucket}"

    def select_action(self, state_key: str, max_risk_aed: float = 10.00):
        """Chooses the optimal capital allocation using an Epsilon-Greedy policy."""
        if state_key not in self.q_table:
            # Initialize Q-values for the 4 possible allocation actions [Skip, Conservative, Standard, Aggressive]
            # We give a slight optimistic initial bias to STANDARD (50%) and CONSERVATIVE (25%)
            self.q_table[state_key] = [0.0, 0.2, 0.5, 0.3]
            self.save_q_table()

        q_values = self.q_table[state_key]

        # Epsilon-greedy exploration vs exploitation
        if np.random.uniform(0, 1) < self.epsilon:
            chosen_idx = int(np.random.choice([0, 1, 2, 3]))
            mode = "Exploration (Random Test)"
        else:
            chosen_idx = int(np.argmax(q_values))
            mode = "Exploitation (Optimal Learned Q-Value)"

        allocation_data = self.allocations[chosen_idx]
        capital_to_risk = round(max_risk_aed * allocation_data["risk_pct"], 2)

        return chosen_idx, capital_to_risk, allocation_data["label"], mode, q_values

    def update_q_value(self, state_key: str, action_idx: int, reward: float):
        """Updates the learned Q-value based on actual trade PnL feedback."""
        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0, 0.0, 0.0, 0.0]

        current_q = self.q_table[state_key][action_idx]
        max_next_q = max(self.q_table[state_key])
        
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state_key][action_idx] = round(new_q, 4)
        self.save_q_table()

def optimize_execution(regime: str, trade_plan: dict, confidence: float, bb_width: float, max_budget_aed: float = 10.00):
    """
    Main interface for Layer 5. Takes Layer 3 & 4 outputs and returns precise execution parameters.
    """
    optimizer = QLearningOptimizer()
    action_signal = trade_plan.get("action", "HOLD")
    
    # If Layer 4 already says HOLD or HOLD_CASH, we risk 0 AED
    if "HOLD" in action_signal:
        print(f"\n🤖 --- Layer 5 RL Action Optimizer ---")
        print(f"   • State Key     : {regime.split(' ')[0]}|{action_signal}|--|--")
        print(f"   • RL Decision   : CAPITAL_PRESERVED (0.00 AED)")
        print(f"   • Reasoning     : Strategy playbook signaled HOLD. Zero risk allocated.")
        return trade_plan["action"], 0.00, trade_plan["target_entry"], "HOLD_STATE"

    state_key = optimizer.get_state_key(regime, action_signal, confidence, bb_width)
    chosen_idx, capital_risked, alloc_label, mode, q_vals = optimizer.select_action(state_key, max_risk_aed=max_budget_aed)

    # Override action if RL agent chooses 0% allocation (SKIP_TRADE)
    final_action = "SKIP_RL_VETO" if chosen_idx == 0 else action_signal
    
    print(f"\n🤖 --- Layer 5 RL Action Optimizer ---")
    print(f"   • State Key     : {state_key}")
    print(f"   • Policy Mode   : {mode}")
    print(f"   • Q-Value Array : {[round(v, 2) for v in q_vals]}")
    print(f"   • RL Allocation : [{alloc_label}] -> Risking {capital_risked:.2f} AED of {max_budget_aed:.2f} AED max budget")
    
    return final_action, capital_risked, trade_plan["target_entry"], state_key

if __name__ == "__main__":
    # Quick standalone simulation test
    dummy_plan = {"action": "BUY_DIP", "target_entry": 64159.0147, "take_profit": 65074.9653, "stop_loss": 63838.2196}
    optimize_execution("Ranging", dummy_plan, 89.5, 0.0141)
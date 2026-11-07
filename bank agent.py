import json
import time
import hashlib
import os
import re
import getpass
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# ==============================================================================
# 1. CONFIGURATION & MULTI-PROVIDER SECURITY
# ==============================================================================

class OperatingMode(Enum):
    SHADOW = "shadow"
    COPILOT = "copilot"
    AUTO = "auto"

class Config:
    MODE = OperatingMode.COPILOT
    MAX_STEPS = 5
    HIGH_RISK_THRESHOLD_USD = 10000
    MIN_IPV4_PREFIX = 32
    
    @staticmethod
    def get_api_key(provider: str = "groq") -> str:
        provider = provider.lower()
        env_var_map = {
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "azure": "AZURE_OPENAI_KEY",
            "custom": "CUSTOM_LLM_API_KEY"
        }
        
        if provider not in env_var_map:
            raise ValueError(f"Unsupported provider: {provider}")
            
        env_var_name = env_var_map[provider]
        key = os.getenv(env_var_name)
        
        if not key:
            print(f"\n[SECURITY] {env_var_name} not found in environment.")
            key = getpass.getpass(f"Please enter your {provider.upper()} API Key: ")
            if not key:
                raise ValueError(f"API Key for {provider} is required.")
                
        return key

# ==============================================================================
# 2. AUDIT LOGGING (Tamper-Evident & PII Compliant)
# ==============================================================================

class AuditLogger:
    def __init__(self):
        self.logs = []
        self.last_hash = "0" * 64 

    def _mask_pii(self, data: dict) -> dict:
        safe_data = json.dumps(data)
        safe_data = re.sub(r'\b\d{10,}\b', '****', safe_data) 
        return json.loads(safe_data)

    def log(self, action: str, details: dict, actor: str = "AI_AGENT"):
        timestamp = time.time()
        safe_details = self._mask_pii(details)
        
        payload = f"{timestamp}{actor}{action}{json.dumps(safe_details, sort_keys=True)}{self.last_hash}"
        current_hash = hashlib.sha256(payload.encode()).hexdigest()
        
        entry = {
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "details": safe_details,
            "hash": current_hash,
            "prev_hash": self.last_hash
        }
        self.logs.append(entry)
        self.last_hash = current_hash
        print(f"[AUDIT] {action} | Hash: {current_hash[:10]}...")

audit = AuditLogger()

# ==============================================================================
# 3. MOCK BACKEND TOOLS (The "Hands")
# ==============================================================================

class MockFraudEngine:
    def get_risk_score(self, account_id: str, amount: float) -> dict:
        score = 10 if amount > 5000 else 2
        if account_id == "ACC_SUSPICIOUS": score = 95
        return {"risk_score": score, "reason": "High velocity" if score > 50 else "Normal"}

class MockAMLChecker:
    def check_wallet(self, wallet_address: str) -> dict:
        if "mixer" in wallet_address.lower():
            return {"is_sanctioned": True, "entity": "Tornado Cash Mixer"}
        return {"is_sanctioned": False, "entity": "Unknown"}

class MockSIEM:
    def query_logs(self, ip_address: str) -> list:
        if ip_address.startswith("192.168"):
            return [{"event": "Internal Scan", "severity": "LOW"}]
        if ip_address == "10.10.10.10":
            return [{"event": "Brute Force Login", "severity": "HIGH"}, {"event": "Data Exfiltration", "severity": "CRITICAL"}]
        return []

class MockResponseSystem:
    def freeze_account(self, account_id: str, reason: str):
        return f"Account {account_id} frozen. Reason: {reason}"

    def block_ip(self, ip_address: str, prefix_len: int):
        if prefix_len < Config.MIN_IPV4_PREFIX:
            raise PermissionError(f"Security Violation: Cannot block subnet /{prefix_len}.")
        return f"IP {ip_address}/{prefix_len} blocked at firewall."

fraud_engine = MockFraudEngine()
aml_checker = MockAMLChecker()
siem = MockSIEM()
responder = MockResponseSystem()

# ==============================================================================
# 4. THE MULTI-AGENT BRAIN (Adversarial Debate)
# ==============================================================================

# Prompts for the three agents
PROSECUTOR_PROMPT = """
You are the PROSECUTOR. Your job is to find evidence of FRAUD, MONEY LAUNDERING, or HACKS.
Be aggressive. Look for high amounts, suspicious IPs, mixers, or unusual patterns.
Output your findings as a list of 'Red Flags'.
"""

DEFENDER_PROMPT = """
You are the DEFENDER. Your job is to find evidence that the transaction is LEGITIMATE.
Look for normal behavior, known merchants, internal transfers, or low-risk indicators.
Output your findings as a list of 'Mitigating Factors'.
"""

JUDGE_PROMPT = """
You are the JUDGE. You have heard the Prosecution (Red Flags) and the Defense (Mitigating Factors).
You must make a final ruling: 'FRAUD', 'LEGIT', or 'NEEDS_REVIEW'.
Provide a brief 'Verdict Reasoning'.
"""

class AgentRole:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt

    def think(self, context: str) -> str:
        """
        In a real app, this would call the LLM API with the specific system prompt.
        For this demo, we simulate the reasoning based on the context.
        """
        print(f"\n[{self.name}] Analyzing...")
        
        # Simulation Logic for Demo Purposes
        if self.name == "PROSECUTOR":
            if "ACC_SUSPICIOUS" in context or "Mixer" in context or "10.10.10.10" in context:
                return "RED FLAG: High risk account detected. RED FLAG: Known malicious IP or Mixer wallet."
            elif "15000" in context:
                return "RED FLAG: Unusually large transaction amount."
            else:
                return "No immediate red flags found."
                
        elif self.name == "DEFENDER":
            if "ACME Corp" in context or "Payroll" in context:
                return "MITIGATING FACTOR: Transaction is from a known payroll provider."
            elif "192.168" in context:
                return "MITIGATING FACTOR: IP address is internal/local network."
            else:
                return "No strong mitigating factors found."
                
        elif self.name == "JUDGE":
            # Simple logic to combine the two
            if "RED FLAG" in context and "MITIGATING" not in context:
                return json.dumps({"verdict": "FRAUD", "reasoning": "Overwhelming evidence of foul play with no mitigation."})
            elif "RED FLAG" in context and "MITIGATING" in context:
                return json.dumps({"verdict": "NEEDS_REVIEW", "reasoning": "Conflicting evidence requires human analyst."})
            else:
                return json.dumps({"verdict": "LEGIT", "reasoning": "No significant threats detected."})

# Initialize Agents
prosecutor = AgentRole("PROSECUTOR", PROSECUTOR_PROMPT)
defender = AgentRole("DEFENDER", DEFENDER_PROMPT)
judge = AgentRole("JUDGE", JUDGE_PROMPT)

# ==============================================================================
# 5. THE ORCHESTRATOR (Debate Loop)
# ==============================================================================

class SecurityAgent:
    def __init__(self):
        self.history = []

    def run_debate(self, initial_alert: str):
        print(f"\n--- STARTING ADVERSARIAL DEBATE FOR: {initial_alert} ---")
        
        # 1. Gather Evidence (Tools)
        # In a real app, the agents would call tools here. We'll simulate it.
        context = initial_alert
        
        # 2. The Debate
        prosecution_args = prosecutor.think(context)
        defense_args = defender.think(context)
        
        print(f"[PROSECUTOR]: {prosecution_args}")
        print(f"[DEFENDER]: {defense_args}")
        
        # 3. The Verdict
        combined_context = f"Prosecution: {prosecution_args} | Defense: {defense_args}"
        verdict_json_str = judge.think(combined_context)
        
        try:
            verdict = json.loads(verdict_json_str)
        except:
            verdict = {"verdict": "ERROR", "reasoning": "Failed to parse verdict"}
            
        print(f"\n[JUDGE VERDICT]: {verdict['verdict']}")
        print(f"[REASONING]: {verdict['reasoning']}")
        
        audit.log(action="DEBATE_VERDICT", details=verdict)
        
        # 4. Execution based on Verdict
        if verdict['verdict'] == "FRAUD":
            self.execute_action("freeze_account", {"account_id": "ACC_SUSPICIOUS", "reason": "Judge Verdict: Fraud"})
        elif verdict['verdict'] == "NEEDS_REVIEW":
            print("[SYSTEM] Case routed to Human Analyst Queue.")
            audit.log(action="ROUTED_TO_HUMAN", details={"reason": "Conflicting evidence"})

    def execute_action(self, tool_name: str, args: dict):
        print(f"\n[AGENT] Proposing Action: {tool_name}")
        
        # Guardrail Check
        if tool_name in ["freeze_account", "block_ip"]:
            print(f"[GUARDRAIL] ACTION REQUIRES HUMAN APPROVAL: {tool_name}")
            approval = input("Human Analyst: Approve? (y/n): ").lower()
            if approval != 'y':
                print("[GUARDRAIL] Action Denied by Human.")
                audit.log(action="HUMAN_DENY", details={"tool": tool_name})
                return
        
        # Execute Tool
        if tool_name == "freeze_account":
            result = responder.freeze_account(args['account_id'], args['reason'])
        elif tool_name == "block_ip":
            result = responder.block_ip(args['ip_address'], args.get('prefix_len', 32))
            
        print(f"[SYSTEM] Result: {result}")
        audit.log(action=f"EXECUTED_{tool_name.upper()}", details={**args, "result": result})

# ==============================================================================
# 6. MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("--- ENTERPRISE MULTI-AGENT SECURITY SYSTEM ---")
    
    # Initialize API Key (Even though we simulated thinking, this keeps it ready for real LLMs)
    try:
        api_key = Config.get_api_key("groq")
        print(f"[CONFIG] Authenticated with: GROQ")
    except ValueError:
        print("[CONFIG] Running in Simulation Mode (No API Key provided)")

    agent = SecurityAgent()
    
    print("\n=== SCENARIO 1: CLEAR FRAUD ===")
    agent.run_debate("Alert: $15,000 transfer from ACC_SUSPICIOUS to 0xMixerWallet")
    
    print("\n\n=== SCENARIO 2: AMBIGUOUS CASE ===")
    agent.run_debate("Alert: $500 transfer from ACC_101 to ACME Corp Payroll from IP 192.168.1.5")
    
    print("\n\n=== FINAL AUDIT LOG ===")
    for log in audit.logs:
        print(json.dumps(log, indent=2))
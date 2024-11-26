from typing import Dict, Any
from pydantic import BaseModel

class AccountGoals(BaseModel):
    primary_mission: str
    investment_criteria: Dict[str, Any]
    risk_tolerance: float  # 0-1
    target_allocation: Dict[str, float]
    allowed_assets: list[str]
    
class SitusAccount(BaseModel):
    name: str  # e.g. "elk"
    group: str  # e.g. "basin"
    address: str  # 0x... TBA address
    goals: AccountGoals 
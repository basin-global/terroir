from src.config.account_config import SitusAccount, AccountGoals

# Setup elk.basin account
elk_goals = AccountGoals(
    primary_mission="Maintain and expand elk habitat in the Roaring Fork Valley",
    investment_criteria={
        "environmental_impact": "high",
        "local_focus": True
    },
    risk_tolerance=0.3,
    target_allocation={
        "land_tokens": 0.6,
        "conservation_projects": 0.3,
        "liquidity": 0.1
    },
    allowed_assets=["LAND", "USDC", "ETH"]
)

elk_account = SitusAccount(
    name="elk",
    group="basin",
    address="0x...",  # TBA address
    goals=elk_goals
)

# Add to agent
agent.add_account(elk_account) 
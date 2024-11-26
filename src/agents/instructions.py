TERROIR_PURPOSE = """
Terroir is an AI system that manages situs accounts. Each account represents either:
- A place (like elk.basin or roaring-fork.basin)
- A purpose (like clean-air.earth or pollination.earth)
- An entity (like beaver.basin or orchid.basin)

Core Mission:
1. Grow assets under management (AUM) for each account
2. Eventually invest that AUM in real assets that benefit the account's namesake
3. Enable nature to own its own land, animals to own their own property, etc.

Key Principles:
1. Each account has its own specific mission and goals
2. Decisions must benefit the bioregion/entity the account represents
3. Follow BASIN and Situs protocols for all operations

Token Standards:
1. Certificates of Ensurance (ERC-1155):
   - Represents ensured natural capital
   - Each token ID maps to specific natural assets
   - Minted through Situs protocol
   - Can be fractionalized and traded

2. Ensure Nature Based Currency (ERC-20):
   - Native token for both BASIN and Situs protocols
   - Used for transactions and governance
   - Backed by natural capital
   - Facilitates value transfer between accounts
"""

ACCOUNT_TYPES = {
    "place": {
        "description": "Represents a specific geographical location or bioregion",
        "examples": ["elk.basin", "roaring-fork.basin"],
        "assets": ["Certificates of Ensurance for land, water rights, mineral rights"]
    },
    "purpose": {
        "description": "Represents an environmental function or service",
        "examples": ["clean-air.earth", "pollination.earth"],
        "assets": ["Certificates of Ensurance for ecosystem services"]
    },
    "entity": {
        "description": "Represents a specific species or natural entity",
        "examples": ["beaver.basin", "orchid.basin"],
        "assets": ["Certificates of Ensurance for habitat, corridors, food sources"]
    }
}

TOKEN_STANDARDS = {
    "ERC1155": {
        "name": "Certificates of Ensurance",
        "contract": "SitusEnsurance",
        "description": "Multi-token standard for representing ensured natural capital",
        "use_cases": [
            "Land titles",
            "Water rights",
            "Ecosystem services",
            "Species habitat"
        ]
    },
    "ERC20": {
        "name": "Ensure Nature Based Currency",
        "contracts": ["BasinToken", "SitusToken"],
        "description": "Fungible token for value transfer and governance",
        "use_cases": [
            "Transaction settlement",
            "Governance voting",
            "Natural capital backing",
            "Inter-account transfers"
        ]
    }
} 
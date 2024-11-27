from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    GITHUB_PERSONAL_ACCESS_TOKEN: str
    USER_AGENT: str
    DATABASE_URL: str
    NEYNAR_API_KEY: str
    NEYNAR_WEBHOOK_SECRET: str
    NEYNAR_SIGNER_UUID: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
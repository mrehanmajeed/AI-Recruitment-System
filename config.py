from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GMAIL_SENDER_EMAIL: str
    GMAIL_APP_PASSWORD: str
    HR_EMAIL: str
    CALENDLY_LINK: str
    SCORE_THRESHOLD: int = 70
    DATABASE_URL: str = "sqlite:///./talentflow.db"
    FIRM_NAME: str = "Sterling & Associates Law Firm"

    class Config:
        env_file = ".env"

settings = Settings()

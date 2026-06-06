import os
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048
QUALITY_THRESHOLD = 7.0

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

CATEGORIES = [
    "Renewable Energy",
    "Hydrogen Production & Technology",
    "Green Iron & Low-Carbon Feedstocks",
    "Circular Economy (Scrap)",
    "CCS & CCUS",
    "Steel Demand, Procurement & End Markets",
    "Steel Prices & Green Premiums",
    "Raw Material Prices",
    "Clean Energy Logistics & Storage",
    "Project Finance & Investment",
    "Trade, Tariffs & Regulations",
    "Climate Policy & Environment",
    "Corporate Offtake",
    "Partnerships & M&A",
    "Green Steel Projects & Plant Development",
]

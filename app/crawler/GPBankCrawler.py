from app.crawler.BankCrawler import BankCrawler


class GPBankCrawler(BankCrawler):
    BANK_CODE = "GPB"
    URL = "https://webgia.com/lai-suat/gpbank/"
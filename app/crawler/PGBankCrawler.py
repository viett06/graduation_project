from app.crawler.BankCrawler import BankCrawler


class PGBankCrawler(BankCrawler):
    BANK_CODE = "PGB"
    URL = "https://webgia.com/lai-suat/pgbank/"
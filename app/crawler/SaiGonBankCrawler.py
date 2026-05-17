from app.crawler.BankCrawler import BankCrawler


class SaiGonBankCrawler(BankCrawler):
    BANK_CODE = "SGB"
    URL = "https://webgia.com/lai-suat/saigonbank/"
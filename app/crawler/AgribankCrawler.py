from app.crawler.BankCrawler import BankCrawler


class AgribankCrawler(BankCrawler):
    BANK_CODE = "AGRIBANK"
    URL = "https://webgia.com/lai-suat/agribank/"
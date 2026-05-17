from app.crawler.BankCrawler import BankCrawler


class VIBCrawler(BankCrawler):
    BANK_CODE = "VIB"
    URL = "https://webgia.com/lai-suat/vib/"
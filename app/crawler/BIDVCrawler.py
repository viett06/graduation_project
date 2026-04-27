from app.crawler.BankCrawler import BankCrawler


class BIDVCrawler(BankCrawler):
    BANK_CODE = "BIDV"
    URL = "https://webgia.com/lai-suat/bidv/"
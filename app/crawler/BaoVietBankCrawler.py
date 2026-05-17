from app.crawler.BankCrawler import BankCrawler


class BaoVietBankCrawler(BankCrawler):
    BANK_CODE = "BVB"
    URL = "https://webgia.com/lai-suat/baovietbank/"
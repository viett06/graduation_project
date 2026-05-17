from app.crawler.BankCrawler import BankCrawler


class VRBankCrawler(BankCrawler):
    BANK_CODE = "VRB"
    URL = "https://webgia.com/lai-suat/vrbank/"

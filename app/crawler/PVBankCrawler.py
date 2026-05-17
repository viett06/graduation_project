from app.crawler.BankCrawler import BankCrawler


class PVComBankCrawler(BankCrawler):
    BANK_CODE = "PVB"
    URL = "https://webgia.com/lai-suat/pvcombank/"
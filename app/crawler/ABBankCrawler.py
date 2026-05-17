from app.crawler.BankCrawler import BankCrawler


class ABBankCrawler(BankCrawler):
    BANK_CODE = "ABB"
    URL = "https://webgia.com/lai-suat/abbank/"
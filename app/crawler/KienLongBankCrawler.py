from app.crawler.BankCrawler import BankCrawler


class KienLongBankCrawler(BankCrawler):
    BANK_CODE = "KLB"
    URL = "https://webgia.com/lai-suat/kienlongbank/"
from app.crawler.BankCrawler import BankCrawler


class HongLeongCrawler(BankCrawler):
    BANK_CODE = "HONGLEONG"
    URL = "https://webgia.com/lai-suat/hlbank/"
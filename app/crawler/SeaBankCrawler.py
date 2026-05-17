from app.crawler.BankCrawler import BankCrawler


class SeaBankCrawler(BankCrawler):
    BANK_CODE = "SSB"
    URL = "https://webgia.com/lai-suat/seabank/"
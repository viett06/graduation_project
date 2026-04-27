from app.crawler.BankCrawler import BankCrawler


class SCBCrawler(BankCrawler):
    BANK_CODE = "SCB"
    URL = "https://webgia.com/lai-suat/scb/"
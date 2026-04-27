from typing import List
from bs4 import BeautifulSoup
import re
from datetime import date
from .base import BaseCrawler


class AgribankWebGiaCrawler(BaseCrawler):

    def __init__(self, db_session):
        super().__init__("AGRIBANK", db_session)

    async def crawl(self):
        url = "https://webgia.com/lai-suat/agribank/"

        html = await self.fetch_html(url)

        if not html:
            return {"status": "failed"}

        rates = self.parse_rates(html)

        return {
            "status": "parsed",
            "rates_data": {
                "AGRIBANK": rates
            }
        }

    def parse_rates(self, html: str) -> List[dict]:

        soup = BeautifulSoup(html, "html.parser")
        rates = []

        table = soup.find("table")

        if not table:
            return rates

        rows = table.find_all("tr")[1:]

        for row in rows:

            cols = row.find_all("td")

            if len(cols) < 2:
                continue

            term_text = cols[0].get_text(" ", strip=True)

            code = cols[1].get("nb", "")
            decoded = self.decode_nb(code)

            rate = self.extract_rate(decoded)
            term = self.term_to_month(term_text)

            if term is not None and 0 < rate < 20:
                rates.append({
                    "term_month": term,
                    "rate": rate,
                    "min_amount": 0,
                    "max_amount": None,
                    "note": term_text,
                    "effective_date": date.today()
                })

        return rates

    def decode_nb(self, text):

        # bỏ chữ A-Z
        hex_text = re.sub(r"[A-Z]", "", text)

        chars = []

        for i in range(0, len(hex_text) - 1, 2):
            pair = hex_text[i:i+2]

            try:
                chars.append(chr(int(pair, 16)))
            except:
                pass

        return "".join(chars)

    def extract_rate(self, text):

        m = re.search(r"(\d+[.,]?\d*)", text)

        if m:
            return float(m.group(1).replace(",", "."))

        return 0

    def term_to_month(self, text):

        t = text.lower()

        if "không kỳ hạn" in t:
            return 0

        m = re.search(r"(\d+)\s*tháng", t)

        if m:
            return int(m.group(1))

        return None
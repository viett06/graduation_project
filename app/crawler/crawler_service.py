import asyncio

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
import logging

from app.crawler.VCBCrawler import VCBBankCrawler
from app.crawler.VietCapitalBankCrawler import VietCapitalBankCrawler
from app.crawler.PVBankCrawler import PVComBankCrawler
from app.crawler.HLBankCrawler import HongLeongCrawler
from app.crawler.ABBankCrawler import ABBankCrawler
from app.crawler.PGBankCrawler import PGBankCrawler
from app.crawler.BacABankCrawler import BacABankCrawler
from app.crawler.BaoVietBankCrawler import BaoVietBankCrawler
from app.crawler.GPBankCrawler import GPBankCrawler
from app.crawler.IndovinaBankCrawler import IndovinaBankCrawler
from app.crawler.KienLongBankCrawler import KienLongBankCrawler
from app.crawler.MBBankCrawler import MBBankCrawler
from app.crawler.NamABankCrawler import NamABankCrawler
from app.crawler.OCBCrawler import OCBCrawler
from app.crawler.AgribankCrawler import AgribankCrawler
from app.crawler.BIDVCrawler import BIDVCrawler
from app.crawler.HLBankCrawler import HongLeongCrawler
from app.crawler.MSBCrawler import MSBCrawler
from app.crawler.PublicBankCrawler import PublicBankCrawler
from app.crawler.SCBCrawler import SCBCrawler
from app.crawler.SHBCrawler import SHBCrawler
from app.crawler.SaiGonBankCrawler import SaiGonBankCrawler
from app.crawler.SeaBankCrawler import SeaBankCrawler
from app.crawler.TPBankCrawler import TPBankCrawler
from app.crawler.VCBNeoCrawler import VCBNeoCrawler
from app.crawler.VIBCrawler import VIBCrawler
from app.crawler.VPBankCrawler import VPBankCrawler
from app.crawler.VRBankCrawler import VRBankCrawler
from app.crawler.VietTinBankCrawler import VietTinBankCrawler
from app.models.interestRate import InterestRate
from app.models.bank import Bank
logger = logging.getLogger(__name__)


class CrawlerService:
    def __init__(self, db: Session):
        self.db = db
        self._rate_svc = None
        self._audit_svc = None

    @property
    def audit_svc(self):
        if not self._audit_svc:
            from app.service.auditLogService import AuditLogService
            self._audit_svc = AuditLogService(self.db)
        return self._audit_svc

    @property
    def rate_svc(self):
        if not self._rate_svc:
            from app.service.interestRateService import InterestRateService
            self._rate_svc = InterestRateService(self.db)
        return self._rate_svc

    def process_crawled_rates(self, bank_id: int, new_rates: List[dict], admin_id: int = 6):
        changes = {"updated": 0, "created": 0}

        current_rates_map = {
            (r.term_month, r.channel): r
            for r in self.db.query(InterestRate).filter(
                InterestRate.bank_id == bank_id,
                InterestRate.is_current == True
            ).all()
        }

        # for item in new_rates:
        #     term = item['term_month']
        #     channel = item['channel']
        #
        #     new_rate_val = Decimal(str(item['rate']))
        #
        #     existing = current_rates_map.get(
        #         (term, channel)
        #     )
        #
        #     if existing and float(existing.rate) == float(new_rate_val):
        #         continue

        try:
            for item in new_rates:
                term = item['term_month']
                channel = item['channel']

                new_rate_val = Decimal(str(item['rate']))

                existing = current_rates_map.get(
                    (term, channel)
                )

                # Không thay đổi
                if existing and float(existing.rate) == float(new_rate_val):
                    continue

                # Có thay đổi
                if existing:
                    existing.is_current = False
                    existing.updated_at = datetime.now()

                    self._log_rate_change(existing, admin_id)

                    self._create_new_rate_record(
                        bank_id,
                        item,
                        new_rate_val,
                        admin_id
                    )

                    changes["updated"] += 1

                # Chưa tồn tại
                else:
                    self._create_new_rate_record(
                        bank_id,
                        item,
                        new_rate_val,
                        admin_id
                    )

                    changes["created"] += 1

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing rates for bank_id {bank_id}: {e}")
            raise e
        return changes

    def _create_new_rate_record(self, bank_id, item, rate_val, admin_id):
        new_record = InterestRate(
            bank_id=bank_id,
            term_month=item['term_month'],
            rate=rate_val,
            channel=item['channel'],
            min_amount=item.get('min_amount', 0),
            max_amount=item.get('max_amount', None),
            effective_date=item.get('effective_date', datetime.now()),
            is_current=True,
            create_by=admin_id
        )
        self.db.add(new_record)

    def _log_rate_change(self, existing, admin_id):

        rate_id = existing.id

        self.rate_svc.delete_interest_rate_and_save_audit_log(admin_id, rate_id)

    async def crawl_and_update(
            self,
            bank_code: Optional[str] = None,
            admin_id: int =6
    ):


        # if bank_code is None or bank_code.upper() == "WEBGIA":
        #     crawler = WebGiaCrawler(self.db)

        crawler_map = {
            # "VCB": VCBBankCrawler,  # VCB.py
            # "BIDV": BIDVCrawler,  # BIDVCrawler.py
            # "CTG": VietTinBankCrawler,  # VietTinBankCrawler.py
            "MB": MBBankCrawler,  # MBBankCrawler.py
            # "VPB": VPBankCrawler,  # VPBankCrawler.py
            "TPB": TPBankCrawler,  # TPBankCrawler.py
            # "VIB": VIBCrawler,  # VIBCrawler.py
            "SHB": SHBCrawler,  # SHBCrawler.py
            # "SCB": SCBCrawler,  # SCBCrawler.py
            "MSB": MSBCrawler,  # MSBCrawler.py
            # "OCB": OCBCrawler,  # OCBCrawler.py
            "KLB": KienLongBankCrawler,  # KienLongBankCrawler.py
            "NAB": NamABankCrawler,  # NamABankCrawler.py
            "BVB": BaoVietBankCrawler,  # BaoVietBankCrawler.py
            "ABB": ABBankCrawler,  # ABBankCrawler.py
            "SSB": SeaBankCrawler,  # SeaBankCrawler.py (Trong ảnh là SeaBank)
            # "AGRIBANK": AgribankCrawler,  # AgribankCrawler.py
            "BACA": BacABankCrawler,  # BacABankCrawler.py
            "GPB": GPBankCrawler,  # GPBankCrawler.py
            "HLB": HongLeongCrawler,  # HLBankCrawler.py
            "IVB": IndovinaBankCrawler,  # IndovinaBankCrawler.py
            "PGB": PGBankCrawler,  # PGBankCrawler.py
            "PUBLIC": PublicBankCrawler,  # PublicBankCrawler.py
            "PVB": PVComBankCrawler,  # PVBankCrawler.py
            "SGB": SaiGonBankCrawler,  # SaiGonBankCrawler.py
            "VCBNEO": VCBNeoCrawler,  # VCBNeoCrawler.py
            "VCCB": VietCapitalBankCrawler,  # VietCapitalBankCrawler.py
            # "VRB": VRBankCrawler,  # VRBankCrawler.py
        }

        crawler_class = crawler_map.get(bank_code.upper())

        if not crawler_class:
            return {
                "status": "failed",
                "reason": f"No crawler config for {bank_code}"
            }

        crawler = crawler_class(self.db)

        # Crawl data
        try:
            result = await crawler.crawl()

        except Exception as e:
            logger.exception("Crawler crashed")
            return {
                "status": "failed",
                "reason": str(e)
            }

        if result.get("status") != "parsed":
            return result

        # Normalize output

        rates_data = result.get("rates_data")

        print(f"value data: {rates_data}")

        if not rates_data:
            # fallback cho crawler chỉ crawl 1 bank
            if "rates" in result and bank_code:
                rates_data = {
                    bank_code.upper(): result["rates"]
                }
            else:
                return {
                    "status": "failed",
                    "reason": "No rates data returned"
                }

        # Update DB
        total_changes = {}

        for b_code, rates in rates_data.items():

            bank = (
                self.db.query(Bank)
                .filter(Bank.code == b_code.upper())
                .first()
            )

            if not bank:
                logger.warning(f"Bank code {b_code} not found in DB")
                continue

            try:
                changes = self.process_crawled_rates(
                    bank_id = int(bank.id),
                    new_rates=rates,
                    admin_id=admin_id
                )

                total_changes[b_code] = changes

                # notify realtime
                if changes["updated"] > 0 or changes["created"] > 0:
                    await self._notify_update(b_code, changes)
                else:
                    logger.info(f"No rate changes for {b_code}")

            except Exception as e:
                logger.exception(f"Update failed for {b_code}")

                total_changes[b_code] = {
                    "status": "failed",
                    "reason": str(e)
                }

        # Return
        return {
            "status": "success",
            "data": total_changes
        }

    async def _notify_update(self, bank_code, changes):
        try:
            from app.core.socket.websocket import manager
            await manager.broadcast_rate_update(bank_code, changes)
        except Exception as e:
            logger.exception("Notify websocket failed")

    async def crawl_all_banks(self, admin_id: int = 6):
        """
        Automatically iterates through the list of supported banks
        to trigger the crawling and data update process.
        """
        results = {}

        # bank_codes = ["VCB", "BIDV", "CTG", "MB", "VPB", "TPB", "VIB", "SHB", "SCB", "MSB", "OCB", "KLB", "NAB", "BVB",
        #               "ABB", "SSB", "AGRIBANK", "BACA", "GPB", "HLB", "IVB", "PGB", "PUBLIC", "PVB", "SGB", "VCBNEO",
        #               "VCCB", "VRB"]
        bank_codes = ["MB", "TPB", "SHB", "MSB", "KLB", "NAB", "BVB", "ABB", "SSB", "BACA", "GPB", "HLB", "IVB", "PGB",
                      "PUBLIC", "PVB", "SGB", "VCBNEO", "VCCB"]
        logger.info(f"Starting automated crawl process for {len(bank_codes)} banks.")

        for bank_code in bank_codes:
            try:
                logger.info(f" Processing: {bank_code}")

                status = await self.crawl_and_update(
                    bank_code=bank_code,
                    admin_id=admin_id
                )

                results[bank_code] = status
                logger.info(f"Successfully updated: {bank_code}")

                # Politeness delay to prevent rate-limiting/IP blocking
                await asyncio.sleep(2)

            except Exception as e:
                # Catch errors for individual banks so the entire loop doesn't fail
                logger.error(f"Error crawling {bank_code}: {str(e)}")
                results[bank_code] = {"status": "failed", "error": str(e)}

                continue

        logger.info("Automated crawl cycle completed.")
        return results
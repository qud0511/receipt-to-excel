import pytest
from datetime import datetime
from app.schemas.receipt import ReceiptData
from app.schemas.template import Template
from app.schemas.job import JobProgress


def test_receipt_valid():
    r = ReceiptData(날짜="2024-01-15", 업체명="스타벅스", 품목="아메리카노",
                    금액=5500, 부가세=500, 결제수단="카드")
    assert r.비고 is None


def test_receipt_invalid_payment():
    with pytest.raises(Exception):
        ReceiptData(날짜="2024-01-15", 업체명="A", 품목="B",
                    금액=0, 부가세=0, 결제수단="비트코인")


def test_template_has_custom_prompt_false():
    t = Template(template_id="tpl_1", name="지출결의서",
                 fields=["날짜", "금액"], custom_prompt=None,
                 created_at=datetime.utcnow())
    assert t.has_custom_prompt is False


def test_template_has_custom_prompt_true():
    t = Template(template_id="tpl_1", name="지출결의서",
                 fields=["날짜"], custom_prompt="extract",
                 created_at=datetime.utcnow())
    assert t.has_custom_prompt is True


def test_job_defaults():
    j = JobProgress(job_id="j1", template_id="t1",
                    status="pending", total=10, done=0)
    assert j.failed_files == []
    assert j.pdf_url is None
    assert j.download_url is None

"""
실제 카드 단말기 영수증/매출전표 스타일의 샘플 이미지 생성.
출력: tests/fixtures/samples/
"""
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT_REGULAR = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"

OUT_DIR = Path("tests/fixtures/samples")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def _divider(draw: ImageDraw.Draw, y: int, width: int, style: str = "-") -> int:
    draw.text((10, y), style * 38, font=_font(11), fill="#333")
    return y + 18


def _row(draw: ImageDraw.Draw, y: int, label: str, value: str,
         width: int = 380, bold_val: bool = False) -> int:
    draw.text((14, y), label, font=_font(12), fill="#222")
    draw.text((width - 14, y), value,
              font=_font(12, bold=bold_val), fill="#111",
              anchor="ra")
    return y + 20


def _center(draw: ImageDraw.Draw, y: int, text: str, width: int,
            size: int = 13, bold: bool = False) -> int:
    draw.text((width // 2, y), text, font=_font(size, bold=bold),
              fill="#111", anchor="ma")
    return y + size + 6


def make_receipt(
    card_name: str,
    merchant: str,
    category: str,
    amount: int,
    vat: int,
    date: str,
    time_str: str,
    card_no: str,
    approval_no: str,
    installment: str = "일시불",
    output_name: str = "receipt.jpg",
) -> Path:
    W, margin = 380, 10
    bg = "#FFFEF9"

    # -- 1차 렌더링으로 높이 계산 --
    img = Image.new("RGB", (W, 1000), bg)
    draw = ImageDraw.Draw(img)
    y = margin

    y = _center(draw, y, "[ 매 출 전 표 ]", W, 15, bold=True); y += 4
    y = _center(draw, y, card_name, W, 13, bold=True); y += 2
    y = _divider(draw, y, W, "=")
    y = _row(draw, y, "가 맹 점 명", merchant, W)
    y = _row(draw, y, "업 종", category, W)
    y = _divider(draw, y, W)
    y = _row(draw, y, "승 인 일 시", f"{date} {time_str}", W)
    y = _row(draw, y, "카 드 번 호", card_no, W)
    y = _row(draw, y, "승 인 번 호", approval_no, W)
    y = _row(draw, y, "할 부", installment, W)
    y = _divider(draw, y, W)
    y = _row(draw, y, "공급가액", f"{amount - vat:,}원", W)
    y = _row(draw, y, "부  가  세", f"{vat:,}원", W)
    y = _divider(draw, y, W, "=")
    y = _row(draw, y, "합   계", f"{amount:,}원", W, bold_val=True); y += 4
    y = _divider(draw, y, W, "=")
    y = _center(draw, y + 4, "이용해 주셔서 감사합니다.", W, 12)
    y += margin + 10

    # -- 실제 크기로 재생성 --
    img = Image.new("RGB", (W, y), bg)
    draw = ImageDraw.Draw(img)
    y2 = margin

    y2 = _center(draw, y2, "[ 매 출 전 표 ]", W, 15, bold=True); y2 += 4
    y2 = _center(draw, y2, card_name, W, 13, bold=True); y2 += 2
    y2 = _divider(draw, y2, W, "=")
    y2 = _row(draw, y2, "가 맹 점 명", merchant, W)
    y2 = _row(draw, y2, "업 종", category, W)
    y2 = _divider(draw, y2, W)
    y2 = _row(draw, y2, "승 인 일 시", f"{date} {time_str}", W)
    y2 = _row(draw, y2, "카 드 번 호", card_no, W)
    y2 = _row(draw, y2, "승 인 번 호", approval_no, W)
    y2 = _row(draw, y2, "할 부", installment, W)
    y2 = _divider(draw, y2, W)
    y2 = _row(draw, y2, "공급가액", f"{amount - vat:,}원", W)
    y2 = _row(draw, y2, "부  가  세", f"{vat:,}원", W)
    y2 = _divider(draw, y2, W, "=")
    y2 = _row(draw, y2, "합   계", f"{amount:,}원", W, bold_val=True); y2 += 4
    y2 = _divider(draw, y2, W, "=")
    _center(draw, y2 + 4, "이용해 주셔서 감사합니다.", W, 12)

    out = OUT_DIR / output_name
    img.save(out, "JPEG", quality=92)
    print(f"  {out}")
    return out


def make_statement_pdf(receipts_data: list[dict]) -> Path:
    """여러 건을 한 PDF에 — 카드 이용내역서 스타일."""
    from PIL import Image as PilImage
    pages = []
    for r in receipts_data:
        tmp_name = f"_tmp_{r['output_name']}"
        data = {k: v for k, v in r.items() if k != "output_name"}
        p = make_receipt(**data, output_name=tmp_name)
        pages.append(PilImage.open(p).convert("RGB"))
        p.unlink()

    out = OUT_DIR / "lotte_card_statement.pdf"
    pages[0].save(out, save_all=True, append_images=pages[1:], format="PDF")
    print(f"  {out}")
    return out


if __name__ == "__main__":
    print("샘플 영수증 생성 중...")

    # 삼성카드
    make_receipt(
        card_name="삼성카드",
        merchant="스타벅스 강남대로점",
        category="음식점",
        amount=15400, vat=1400,
        date="2025-03-12", time_str="09:24:31",
        card_no="5432-12**-****-8901",
        approval_no="12345678",
        output_name="samsung_card_starbucks.jpg",
    )
    make_receipt(
        card_name="삼성카드",
        merchant="GS25 역삼점",
        category="편의점",
        amount=8700, vat=790,
        date="2025-03-14", time_str="19:05:12",
        card_no="5432-12**-****-8901",
        approval_no="87654321",
        output_name="samsung_card_gs25.jpg",
    )

    # 하나카드
    make_receipt(
        card_name="하나카드",
        merchant="교보문고 광화문점",
        category="서점",
        amount=32000, vat=2909,
        date="2025-03-10", time_str="14:37:45",
        card_no="4012-56**-****-3302",
        approval_no="22334455",
        output_name="hana_card_kyobo.jpg",
    )
    make_receipt(
        card_name="하나카드",
        merchant="이마트 성수점",
        category="대형마트",
        amount=87500, vat=7954,
        date="2025-03-11", time_str="11:22:09",
        card_no="4012-56**-****-3302",
        approval_no="55443322",
        installment="3개월",
        output_name="hana_card_emart.jpg",
    )

    # 우리카드
    make_receipt(
        card_name="우리카드",
        merchant="현대자동차 서초서비스센터",
        category="자동차정비",
        amount=142000, vat=12909,
        date="2025-03-08", time_str="10:15:33",
        card_no="9102-34**-****-5567",
        approval_no="99887766",
        installment="6개월",
        output_name="woori_card_hyundai.jpg",
    )
    make_receipt(
        card_name="우리카드",
        merchant="올리브영 홍대점",
        category="드럭스토어",
        amount=45600, vat=4145,
        date="2025-03-09", time_str="16:48:20",
        card_no="9102-34**-****-5567",
        approval_no="11223344",
        output_name="woori_card_oliveyoung.jpg",
    )

    # 롯데카드 — 여러 건을 PDF 한 장에
    print("  롯데카드 이용내역 PDF 생성 중...")
    make_statement_pdf([
        dict(card_name="롯데카드", merchant="롯데마트 서울역점", category="대형마트",
             amount=65000, vat=5909, date="2025-03-05", time_str="13:20:00",
             card_no="1234-78**-****-4411", approval_no="44556677", output_name="p1.jpg"),
        dict(card_name="롯데카드", merchant="CGV 건대입구", category="영화관",
             amount=22000, vat=2000, date="2025-03-06", time_str="20:05:00",
             card_no="1234-78**-****-4411", approval_no="77665544", output_name="p2.jpg"),
        dict(card_name="롯데카드", merchant="배달의민족 (BBQ치킨)", category="음식배달",
             amount=28000, vat=2545, date="2025-03-07", time_str="18:55:00",
             card_no="1234-78**-****-4411", approval_no="33221100", output_name="p3.jpg"),
    ])

    print(f"\n완료. 파일 목록:")
    for f in sorted(OUT_DIR.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size // 1024}KB)")

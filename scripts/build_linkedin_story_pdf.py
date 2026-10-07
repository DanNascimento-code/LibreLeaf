from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas


WIDTH, HEIGHT = 1080, 1920
OUTPUT = Path("output/pdf/libreleaf-linkedin-story.pdf")

BG = HexColor("#101512")
SURFACE = HexColor("#17201B")
CREAM = HexColor("#F3EBD9")
MUTED = HexColor("#AFAE9E")
GREEN = HexColor("#77A683")
GOLD = HexColor("#D3A85F")
LINE = HexColor("#2B3A31")


def line(canvas: Canvas, text: str, x: float, y: float, size: int, color=CREAM, font="Helvetica"):
    canvas.setFillColor(color)
    canvas.setFont(font, size)
    canvas.drawString(x, y, text)


def wrapped(canvas: Canvas, text: str, x: float, y: float, width: float, size: int, leading: int, color=MUTED, font="Helvetica") -> float:
    words = text.split()
    rows: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            rows.append(current)
            current = word
    if current:
        rows.append(current)
    for row in rows:
        line(canvas, row, x, y, size, color, font)
        y -= leading
    return y


def background(canvas: Canvas, page: int, label: str):
    canvas.setFillColor(BG)
    canvas.rect(0, 0, WIDTH, HEIGHT, fill=1, stroke=0)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(2)
    canvas.line(72, 1780, WIDTH - 72, 1780)
    line(canvas, "LIBRELEAF", 72, 1820, 24, GOLD, "Helvetica-Bold")
    line(canvas, label.upper(), WIDTH - 72 - stringWidth(label.upper(), "Helvetica-Bold", 17), 1823, 17, MUTED, "Helvetica-Bold")
    line(canvas, f"{page:02d} / 06", 72, 68, 16, MUTED, "Helvetica-Bold")
    canvas.setFillColor(GREEN)
    canvas.circle(WIDTH - 84, 79, 8, fill=1, stroke=0)


def title(canvas: Canvas, kicker: str, heading: list[str], body: str):
    line(canvas, kicker.upper(), 72, 1645, 19, GREEN, "Helvetica-Bold")
    y = 1540
    for row in heading:
        line(canvas, row, 72, y, 76, CREAM, "Helvetica-Bold")
        y -= 91
    wrapped(canvas, body, 76, y - 20, 860, 28, 42)


def pill(canvas: Canvas, text: str, x: float, y: float, width: float):
    canvas.setFillColor(SURFACE)
    canvas.roundRect(x, y, width, 58, 29, fill=1, stroke=0)
    line(canvas, text, x + 24, y + 19, 18, CREAM, "Helvetica-Bold")


def card(canvas: Canvas, number: str, heading: str, body: str, y: float):
    canvas.setFillColor(SURFACE)
    canvas.roundRect(72, y, WIDTH - 144, 250, 28, fill=1, stroke=0)
    line(canvas, number, 104, y + 177, 26, GOLD, "Helvetica-Bold")
    line(canvas, heading, 174, y + 176, 31, CREAM, "Helvetica-Bold")
    wrapped(canvas, body, 174, y + 123, 750, 23, 34)


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(OUTPUT), pagesize=(WIDTH, HEIGHT), pageCompression=1)
    canvas.setTitle("LibreLeaf - LinkedIn Project Story")
    canvas.setAuthor("Dan Nascimento")

    background(canvas, 1, "Project story")
    title(
        canvas,
        "Ethical web scraping",
        ["A book price", "comparison engine"],
        "LibreLeaf turns a title or ISBN into verified, edition-specific offers from public bookstore pages.",
    )
    pill(canvas, "PYTHON", 72, 930, 170)
    pill(canvas, "FASTAPI", 258, 930, 190)
    pill(canvas, "WEB SCRAPING", 464, 930, 250)
    pill(canvas, "3 LANGUAGES", 730, 930, 260)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(8)
    canvas.roundRect(725, 260, 250, 500, 20, fill=0, stroke=1)
    canvas.line(750, 700, 845, 650)
    canvas.line(845, 650, 950, 710)
    line(canvas, "Discover.", 72, 650, 39, MUTED, "Helvetica-Bold")
    line(canvas, "Compare.", 72, 590, 39, CREAM, "Helvetica-Bold")
    line(canvas, "Read.", 72, 530, 39, GREEN, "Helvetica-Bold")
    canvas.showPage()

    background(canvas, 2, "The problem")
    title(
        canvas,
        "Why this matters",
        ["The same title", "is not the same book."],
        "Paperback, hardcover, translation, revision and eBook prices cannot be compared safely by title alone.",
    )
    card(canvas, "01", "Identify", "Resolve the requested title or validate the submitted ISBN.", 900)
    card(canvas, "02", "Verify", "Accept a store result only when its product data matches the exact ISBN.", 610)
    card(canvas, "03", "Compare", "Normalize visible prices without hiding unknown shipping or condition.", 320)
    canvas.showPage()

    background(canvas, 3, "The scraper")
    title(
        canvas,
        "Inside the", "".split(),
        "",
    )
    line(canvas, "scraping pipeline", 72, 1449, 76, CREAM, "Helvetica-Bold")
    pipeline = [
        ("REQUEST", "Descriptive user agent, pacing, retry and timeout"),
        ("PARSE", "HTML and JSON-LD parsed with Beautiful Soup"),
        ("MATCH", "Exact ISBN validation prevents edition mixing"),
        ("NORMALIZE", "Prices become integer minor units in one Offer model"),
        ("PERSIST", "Timestamped observations stored in SQLite"),
    ]
    y = 1230
    for index, (head, body) in enumerate(pipeline, 1):
        canvas.setFillColor(GREEN if index < 5 else GOLD)
        canvas.circle(105, y + 25, 28, fill=1, stroke=0)
        line(canvas, str(index), 97, y + 15, 20, BG, "Helvetica-Bold")
        line(canvas, head, 165, y + 35, 22, GOLD, "Helvetica-Bold")
        wrapped(canvas, body, 165, y - 5, 760, 24, 34)
        if index < len(pipeline):
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(3)
            canvas.line(105, y - 45, 105, y - 125)
        y -= 235
    canvas.showPage()

    background(canvas, 4, "Real sources")
    title(
        canvas,
        "Zero retailer keys",
        ["Public prices.", "Exact editions."],
        "Sources are included only when LibreLeaf can return an actual price and verify the requested ISBN.",
    )
    card(canvas, "BR", "Brazil", "Estante Virtual + Livraria da Vila", 900)
    card(canvas, "US", "United States", "ThriftBooks new and used offers", 610)
    card(canvas, "AR", "Argentina", "LibrosRef prices in Argentine pesos", 320)
    canvas.showPage()

    background(canvas, 5, "Engineering")
    title(
        canvas,
        "Built beyond", 
        ["a scraping script"],
        "LibreLeaf is a deployable product with a tested service layer, web UI, CLI and responsible failure handling.",
    )
    metrics = [("51", "automated tests"), ("89%", "statement coverage"), ("3", "UI languages"), ("4", "live price sources")]
    positions = [(72, 920), (555, 920), (72, 600), (555, 600)]
    for (value, label), (x, y) in zip(metrics, positions, strict=True):
        canvas.setFillColor(SURFACE)
        canvas.roundRect(x, y, 420, 250, 26, fill=1, stroke=0)
        line(canvas, value, x + 35, y + 125, 68, GOLD, "Helvetica-Bold")
        line(canvas, label, x + 38, y + 70, 23, MUTED, "Helvetica-Bold")
    pill(canvas, "FASTAPI + JINJA", 72, 300, 270)
    pill(canvas, "SQLITE", 360, 300, 170)
    pill(canvas, "PYTEST", 548, 300, 170)
    pill(canvas, "RUFF", 736, 300, 150)
    canvas.showPage()

    background(canvas, 6, "Explore")
    title(
        canvas,
        "Open source",
        ["Built for readers.", "Designed to grow."],
        "A portfolio project focused on responsible collection, data integrity and a useful reader experience.",
    )
    canvas.setFillColor(SURFACE)
    canvas.roundRect(72, 910, WIDTH - 144, 190, 30, fill=1, stroke=0)
    line(canvas, "LIVE APP", 112, 1030, 19, GREEN, "Helvetica-Bold")
    line(canvas, "libreleaf-books.vercel.app", 112, 960, 31, CREAM, "Helvetica-Bold")
    canvas.linkURL("https://libreleaf-books.vercel.app", (72, 910, WIDTH - 72, 1100), relative=0)
    canvas.setFillColor(SURFACE)
    canvas.roundRect(72, 680, WIDTH - 144, 190, 30, fill=1, stroke=0)
    line(canvas, "SOURCE CODE", 112, 800, 19, GREEN, "Helvetica-Bold")
    line(canvas, "github.com/DanNascimento-code/LibreLeaf", 112, 730, 29, CREAM, "Helvetica-Bold")
    canvas.linkURL("https://github.com/DanNascimento-code/LibreLeaf", (72, 680, WIDTH - 72, 870), relative=0)
    line(canvas, "Python · FastAPI · Beautiful Soup · SQLite · Jinja", 72, 550, 24, MUTED)
    line(canvas, "Dan Nascimento", 72, 390, 35, CREAM, "Helvetica-Bold")
    line(canvas, "Software Development · Web Scraping · Data Products", 72, 342, 22, GOLD, "Helvetica-Bold")
    canvas.save()


if __name__ == "__main__":
    build()

"""
Poori tarah automatic allotment checker (koi popup / human input nahi).

Flow (har PAN ke liye):
  registrar page kholo -> IPO select karo (VERIFY karke) -> PAN bharo ->
  CAPTCHA ka screenshot -> OCR (kai preprocessing variants + voting) ->
  submit -> result padho. Captcha galat nikla toh naya captcha leke dobara
  (max MAX_ATTEMPTS baar).

SAFETY RULE (galti na ke barabar rakhne ke liye): agar IPO select hone ka
pakka saboot nahi mila, ya result page par IPO ka naam nahi dikha, toh hum
andaaza nahi lagate — status "AUTO_FAILED" aata hai (app me "COULD NOT
VERIFY"), kabhi galat ALLOTTED / NOT ALLOTTED nahi.

HONEST NOTE: registrar sites (KFintech, MUFG Intime, Maashitla ...) ke exact
HTML elements is dev sandbox se inspect nahi ho paye (browser/network
restricted). Isliye selectors "flexible" hain. Pehli real deploy ke baad
agar koi step fail ho toh result ka `debug_step` batata hai ki kahan atka.
"""
import io
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image, ImageFilter, ImageOps, ImageStat
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

MAX_ATTEMPTS = 8
OCR_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
STOP_WORDS = {"ltd", "limited", "ipo", "pvt", "private", "india", "industries", "the", "and", "of", "sme"}


# ----------------------------- OCR helpers -----------------------------
def _preprocess_variants(image_bytes):
    """Ek captcha image se kai alag-alag saaf kiye hue versions banata hai."""
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    w, h = img.size
    img = img.resize((max(w, 1) * 3, max(h, 1) * 3), Image.LANCZOS)
    img = ImageOps.autocontrast(img)

    variants = [img]
    for thr in (100, 130, 160, 190):
        v = img.point(lambda x, t=thr: 0 if x < t else 255)
        v = v.filter(ImageFilter.MedianFilter(3))  # chhote noise dots hatao
        variants.append(v)
        variants.append(ImageOps.invert(v))

    padded = []
    for v in variants:
        bg = 255 if ImageStat.Stat(v).mean[0] > 127 else 0
        padded.append(ImageOps.expand(v, border=12, fill=bg))
    return padded


def _ocr_one(args):
    v, psm = args
    try:
        raw = pytesseract.image_to_string(
            v, config=f"--psm {psm} -c tessedit_char_whitelist={OCR_WHITELIST}"
        )
    except Exception:
        return ""
    t = re.sub(r"[^A-Za-z0-9]", "", raw)
    return t if 3 <= len(t) <= 8 else ""


def _ocr_candidates(image_bytes):
    jobs = [(v, psm) for v in _preprocess_variants(image_bytes) for psm in (7, 8)]
    with ThreadPoolExecutor(max_workers=4) as ex:
        return [t for t in ex.map(_ocr_one, jobs) if t]


def _best_guess(cands):
    """Captcha ki length fixed hoti hai: sabse common length chuno, phir har
    position par character-wise majority vote."""
    if not cands:
        return ""
    length = Counter(len(c) for c in cands).most_common(1)[0][0]
    same = [c for c in cands if len(c) == length]
    return "".join(Counter(c[i] for c in same).most_common(1)[0][0] for i in range(length))


def _ocr_captcha(image_bytes):
    return _best_guess(_ocr_candidates(image_bytes))


# ----------------------------- page helpers -----------------------------
def _ipo_keywords(ipo_name):
    n = re.sub(r"\(.*?\)", " ", ipo_name)
    n = re.sub(r"[^A-Za-z0-9\s]", " ", n).lower()
    words = [w for w in n.split() if w not in STOP_WORDS and len(w) > 1]
    if not words:
        words = n.split()[:1]
    return words[:2]


def _first_visible(page, selectors):
    for sel in selectors:
        try:
            loc = page.locator(sel)
            for i in range(min(loc.count(), 5)):
                el = loc.nth(i)
                if el.is_visible():
                    return el
        except Exception:
            continue
    return None


def _select_ipo(page, ipo_name):
    """IPO select karo. True tabhi jab selection ka saboot ho."""
    words = _ipo_keywords(ipo_name)
    if not words:
        return False

    def matches(txt):
        t = txt.lower()
        return all(w in t for w in words)

    # 1) normal <select>
    try:
        selects = page.locator("select")
        for i in range(selects.count()):
            sel = selects.nth(i)
            options = sel.locator("option")
            for j in range(options.count()):
                label = (options.nth(j).inner_text() or "").strip()
                if label and matches(label):
                    sel.select_option(index=j)
                    return True
    except Exception:
        pass

    # 2) custom dropdown (React/Angular combobox)
    triggers = [
        "[role='combobox']",
        "input[placeholder*='company' i]",
        "input[placeholder*='ipo' i]",
        "input[placeholder*='select' i]",
        "[class*='select__control']",
        "[class*='dropdown' i]",
    ]
    for sel in triggers:
        try:
            el = _first_visible(page, [sel])
            if not el:
                continue
            el.click(timeout=2000)
            page.keyboard.type(words[0], delay=60)
            page.wait_for_timeout(800)
            opt = page.locator("[role='option'], li, [class*='option' i]").filter(
                has_text=re.compile(".*".join(map(re.escape, words)), re.IGNORECASE)
            ).first
            if opt.count() > 0:
                opt.click(timeout=2000)
                return True
        except Exception:
            continue
    return False


def _classify_result(body_text, ipo_words):
    """Returns (status, message) ya (None, reason) agar abhi pakka nahi."""
    low = body_text.lower()

    if re.search(r"invalid\s*captcha|incorrect\s*captcha|wrong\s*captcha|captcha\s*(is\s*)?(not\s*)?(match|valid|correct)|enter\s*(the\s*)?valid\s*captcha|captcha\s*mismatch", low):
        return None, "captcha_rejected"

    # Result page par IPO ka naam dikhna chahiye — warna galat IPO ka result ho sakta hai
    if not all(w in low for w in ipo_words):
        return None, "ipo_name_not_on_result_page"

    num = re.search(
        r"(?:allot\w*\s+(?:shares?|quantity|qty)|(?:shares?|quantity|qty)\s+allot\w*)\s*[:\-]?\s*(\d[\d,]*)",
        low,
    )
    if num:
        shares = int(num.group(1).replace(",", ""))
        if shares > 0:
            return "ALLOTTED", f"{shares} shares allotted (registrar ke result page se)"
        return "NON_ALLOTTEE", "0 shares allotted (registrar ke result page se)"

    if re.search(r"non[\s-]?allot|not\s+allot|unsuccessful|better\s+luck|no\s+shares\s+(have\s+been\s+)?allot", low):
        return "NON_ALLOTTEE", "Registrar ke page par Non-Allotted likha hai"

    if re.search(r"no\s+record|record\s+not\s+found|not\s+applied|no\s+application|application\s+not\s+found|data\s+not\s+(found|available)|no\s+data\s+found", low):
        return "NOT_APPLIED", "Registrar ke paas is PAN ka koi application record nahi mila"

    if re.search(r"congratulation|has\s+been\s+allot|shares?\s+(have\s+been\s+)?allotted|status\s*[:\-]?\s*allotted", low):
        return "ALLOTTED", "Registrar ke page par Allotted likha hai"

    return None, "result_text_not_understood"


# ----------------------------- one PAN -----------------------------
def _short(err):
    """Playwright errors multi-line hote hain — sirf pehli line, chhoti."""
    lines = str(err).strip().splitlines()
    return (lines[0] if lines else "unknown error")[:160]


def _check_one_pan(browser, pan, ipo_name, url):
    out = {"status": "AUTO_FAILED", "message": "", "debug_step": "start"}
    words = _ipo_keywords(ipo_name)
    last_reason = "no_attempt"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        page = browser.new_page()
        try:
            out["debug_step"] = f"attempt{attempt}:open_page"
            try:
                page.goto(url, timeout=30000, wait_until="networkidle")
            except Exception:
                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                except Exception as nav_err:
                    # Site khuli hi nahi — captcha wale retry se koi fayda nahi
                    out["message"] = "Registrar ki site khul nahi paayi: " + _short(nav_err)
                    return out
            page.wait_for_timeout(1500)

            # PAN option (kuch sites par radio/label hota hai)
            try:
                page.locator("label:has-text('PAN'), input[type='radio'][value*='PAN' i]").first.click(timeout=1500)
            except Exception:
                pass

            out["debug_step"] = f"attempt{attempt}:select_ipo"
            if not _select_ipo(page, ipo_name):
                out["message"] = "IPO dropdown se select nahi ho paya (safety ke liye result nahi liya)"
                return out  # retry se fayda nahi, structure hi match nahi hua

            out["debug_step"] = f"attempt{attempt}:fill_pan"
            pan_field = _first_visible(page, [
                "input[placeholder*='PAN' i]", "input[name*='pan' i]", "input[id*='pan' i]",
                "input[type='text']",
            ])
            if not pan_field:
                out["message"] = "PAN field nahi mila"
                return out
            pan_field.fill(pan.upper().strip())

            out["debug_step"] = f"attempt{attempt}:captcha"
            captcha_img = _first_visible(page, [
                "img[src*='captcha' i]", "img[id*='captcha' i]", "img[alt*='captcha' i]",
                "[class*='captcha' i] img", "canvas",
            ])
            if captcha_img:
                guess = _ocr_captcha(captcha_img.screenshot())
                if len(guess) < 3:
                    last_reason = "ocr_empty"
                    continue
                cap_input = _first_visible(page, [
                    "input[placeholder*='captcha' i]", "input[name*='captcha' i]",
                    "input[id*='captcha' i]", "input[aria-label*='captcha' i]",
                ])
                if not cap_input:
                    out["message"] = "Captcha dikha par captcha input box nahi mila"
                    return out
                cap_input.fill(guess)

            out["debug_step"] = f"attempt{attempt}:submit"
            btn = _first_visible(page, [
                "button[type='submit']", "button:has-text('Submit')", "button:has-text('Search')",
                "input[type='submit']", "input[value*='Search' i]", "input[value*='Submit' i]",
            ])
            if not btn:
                out["message"] = "Submit button nahi mila"
                return out
            btn.click(timeout=3000)

            out["debug_step"] = f"attempt{attempt}:read_result"
            status, msg = None, "no_response"
            for _ in range(16):  # max ~8 sec, slow registrar ke liye bhi
                page.wait_for_timeout(500)
                status, msg = _classify_result(page.inner_text("body"), words)
                if status or msg == "captcha_rejected":
                    break
            if status:
                out["status"], out["message"] = status, msg
                return out
            last_reason = msg  # captcha_rejected / ipo_name_not_on_result_page / ...

        except Exception as e:
            last_reason = f"error:{_short(e)}"
        finally:
            try:
                page.close()
            except Exception:
                pass

    out["message"] = f"{MAX_ATTEMPTS} koshish ke baad bhi verify nahi hua ({last_reason})"
    return out


# ----------------------------- public API -----------------------------
def check_pans_auto(accounts, ipo_name, registrar_url):
    """accounts: [{"id","name","pan"}]. Ek hi browser me sab PAN ek-ek karke
    check hote hain (memory bachane ke liye). Returns {id: {status, message, debug_step}}."""
    results = {}
    if not (PLAYWRIGHT_AVAILABLE and OCR_AVAILABLE):
        for a in accounts:
            results[a["id"]] = {"status": "AUTO_FAILED", "message": "Playwright/Tesseract installed nahi hai", "debug_step": "deps"}
        return results

    url = "https://ipostatus.kfintech.com" if "kfintech" in (registrar_url or "").lower() else registrar_url
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
            try:
                for a in accounts:
                    results[a["id"]] = _check_one_pan(browser, a["pan"], ipo_name, url)
            finally:
                browser.close()
    except Exception as e:
        for a in accounts:
            results.setdefault(a["id"], {"status": "AUTO_FAILED", "message": f"Browser start nahi hua: {_short(e)}", "debug_step": "launch"})
    return results


# Backward-compatible single-PAN helper
def check_kfintech_pan_auto(pan, ipo_name):
    r = check_pans_auto([{"id": "x", "pan": pan}], ipo_name, "https://ipostatus.kfintech.com")["x"]
    return {"status": "NOT_ALLOTTED" if r["status"] == "NON_ALLOTTEE" else r["status"],
            "message": r["message"], "debug_step": r["debug_step"]}


if __name__ == "__main__":
    print(check_pans_auto([{"id": "1", "pan": "ABCDE1234F"}], "Test IPO", "https://ipostatus.kfintech.com"))

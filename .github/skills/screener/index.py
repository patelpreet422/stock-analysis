import sys
import json
import argparse
from urllib.parse import urljoin
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

USER_AGENT = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


def _get_soup(url: str):
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed. Install it with: pip install playwright")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT["User-Agent"])
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        rendered_html = page.content()
        final_url = page.url
        browser.close()
        return final_url, BeautifulSoup(rendered_html, "html.parser")


def _normalize_url(url_or_path: str) -> str:
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        return url_or_path
    return urljoin("https://www.screener.in/", url_or_path.lstrip("/"))


def _unique_items(items, key_fn):
    seen = set()
    unique = []
    for item in items:
        k = key_fn(item)
        if k in seen:
            continue
        seen.add(k)
        unique.append(item)
    return unique


def _extract_link_title(anchor):
    # Explore cards often contain title + description in the same anchor; prefer heading text.
    title_node = anchor.find(["h2", "h3", "h4", "strong"])
    if title_node:
        return title_node.get_text(" ", strip=True)

    text = anchor.get_text(" ", strip=True)
    return " ".join(text.split())


def _extract_ratios_from_soup(soup: BeautifulSoup):
    ratios = {}
    ratio_ul = soup.find("ul", id="top-ratios")
    if not ratio_ul:
        return ratios

    for li in ratio_ul.find_all("li"):
        name = li.find("span", class_="name")
        if not name:
            continue

        value_container = li.find("span", class_="value") or li
        value_text = value_container.get_text(" ", strip=True)
        value_text = " ".join(value_text.split())

        ratio_name = name.get_text(strip=True)
        if ratio_name:
            ratios[ratio_name] = value_text

    return ratios


def _count_ratio_values_with_digits(ratios: dict) -> int:
    count = 0
    for value in ratios.values():
        text = str(value)
        if any(ch.isdigit() for ch in text):
            count += 1
    return count


def _normalize_metric_label(label: str) -> str:
    # Buttons in Screener rows may append a trailing "+" in the visible text.
    return " ".join(label.replace("+", " ").split()).strip().lower()


def _extract_generic_table(table):
    """Extract a standard period-over-period Screener table into headers + rows.

    Each row is: {"metric": <label>, <period>: <value>, ...}
    """
    if not table:
        return {"headers": [], "rows": []}

    headers = []
    head = table.find("thead")
    if head:
        first_row = head.find("tr")
        if first_row:
            headers = [th.get_text(" ", strip=True) for th in first_row.find_all(["th", "td"])]

    rows = []
    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        values = [c.get_text(" ", strip=True) for c in cells]
        label = values[0]
        if not label:
            continue
        row = {"metric": label}
        for idx, val in enumerate(values[1:], start=1):
            key = headers[idx] if idx < len(headers) and headers[idx] else f"value_{idx}"
            row[key] = val
        rows.append(row)

    return {"headers": headers, "rows": rows}


def _extract_ranges_table(table):
    """Parse Screener's small ranges-table (10y/5y/3y/1y growth summary).

    Returns (label, {period: value}) or (None, {}) if not recognisable.
    """
    if not table:
        return None, {}
    label = None
    th = table.find("th")
    if th:
        label = th.get_text(" ", strip=True)
    values = {}
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) == 2:
            key = tds[0].get_text(" ", strip=True).rstrip(":").strip()
            val = tds[1].get_text(" ", strip=True)
            if key:
                values[key] = val
    return label, values


def _extract_sales_rows_from_profit_loss(soup: BeautifulSoup):
    """Backward-compatible helper: returns the Sales row(s) only.

    Retained for consumers that rely on the legacy `sales_data` field.
    """
    section = soup.find("section", id="profit-loss")
    if not section:
        return {"error": "Profit & Loss section not found"}
    table = section.find("table")
    if not table:
        return {"error": "Profit & Loss table not found"}
    extracted = _extract_generic_table(table)
    sales_rows = [r for r in extracted["rows"]
                  if _normalize_metric_label(r.get("metric", "")) == "sales"]
    if sales_rows:
        return sales_rows
    return {"error": "Sales row not found in Profit & Loss table"}


def _get_rendered_soup(url: str):
    try:
        return _get_soup(url)
    except Exception:
        return None

def _build_sitemap(soup: BeautifulSoup):
    """Screener does not use <nav id="company-nav">; sections live as <section id="…">.

    Walk the top-level sections and return them with their visible heading.
    """
    sections = []
    for s in soup.find_all("section", id=True):
        heading_node = s.find(["h1", "h2", "h3"])
        heading = heading_node.get_text(" ", strip=True) if heading_node else s.get("id", "")
        sections.append({"section": heading or s["id"], "anchor": f"#{s['id']}"})
    return sections


def _extract_growth_blocks(profit_loss_section):
    """Pull the four ranges-table summaries after the main P&L table.

    Keys are snake_case of the visible heading.
    """
    blocks = {}
    if not profit_loss_section:
        return blocks
    tables = profit_loss_section.find_all("table")
    # First table is the main P&L; remaining .ranges-table entries carry growth/ROE/CAGR.
    for table in tables[1:]:
        classes = table.get("class") or []
        if "ranges-table" not in classes:
            continue
        label, values = _extract_ranges_table(table)
        if not label:
            continue
        key = "_".join(label.lower().split())
        blocks[key] = {"label": label, "values": values}
    return blocks


def _extract_documents(docs_section, actual_url):
    """Parse the Documents section. Each `.documents` block has an h3 heading
    (Announcements, Annual reports, Credit ratings, Concalls) and <li> entries.
    """
    out = {
        "announcements": [],
        "annual_reports": [],
        "credit_ratings": [],
        "concalls": [],
    }
    if not docs_section:
        return out

    key_map = {
        "announcements": "announcements",
        "annual reports": "annual_reports",
        "credit ratings": "credit_ratings",
        "concalls": "concalls",
    }

    for block in docs_section.find_all("div", class_="documents"):
        heading_node = block.find(["h2", "h3", "h4"])
        if not heading_node:
            continue
        heading = heading_node.get_text(" ", strip=True).lower()
        key = key_map.get(heading)
        if not key:
            continue

        if key == "concalls":
            # Concalls li rows bundle period (first text child) + multiple links (Transcript/PPT/Notes/REC).
            for li in block.find_all("li"):
                period = ""
                for node in li.contents:
                    if getattr(node, "name", None) is None:
                        text = str(node).strip()
                        if text:
                            period = text
                            break
                    elif node.name not in {"a", "button"}:
                        text = node.get_text(" ", strip=True)
                        if text:
                            period = text
                            break
                files = []
                for a in li.find_all("a"):
                    href = a.get("href")
                    text = a.get_text(" ", strip=True)
                    if href and text:
                        files.append({"type": text, "url": urljoin(actual_url, href)})
                for btn in li.find_all("button"):
                    text = btn.get_text(" ", strip=True)
                    if text and text.lower() in {"transcript", "notes", "ppt", "rec", "ai summary"}:
                        # buttons without hrefs are tracked so the agent knows what exists.
                        if not any(f.get("type", "").lower() == text.lower() for f in files):
                            files.append({"type": text, "url": None})
                if files or period:
                    out[key].append({"period": period or "Unknown", "files": files})
        else:
            for li in block.find_all("li"):
                a = li.find("a")
                if not a:
                    continue
                href = a.get("href")
                title_parts = []
                for node in a.contents:
                    if getattr(node, "name", None) is None:
                        text = str(node).strip()
                        if text:
                            title_parts.append(text)
                    elif node.name in {"span", "strong", "b"}:
                        text = node.get_text(" ", strip=True)
                        if text:
                            title_parts.append(text)
                title = " ".join(" ".join(title_parts).split()) or a.get_text(" ", strip=True)
                if href and title and "search" not in title.lower():
                    out[key].append({"title": title, "url": urljoin(actual_url, href)})
    return out


def _parse_number(text):
    """Parse a Screener value like '₹ 1,365' or '18,47,111 Cr.' into a float.

    Returns None when parsing fails.
    """
    if not text:
        return None
    s = str(text).strip()
    # strip currency, percent, commas, units
    for token in ["₹", "Rs", "Rs.", "Cr.", "Cr", "%"]:
        s = s.replace(token, "")
    s = s.replace(",", "").strip()
    # High / Low patterns are "1,612 / 1,267"
    if "/" in s:
        s = s.split("/")[0].strip()
    try:
        return float(s)
    except ValueError:
        return None


def _derive_ratios(top_ratios: dict, profit_loss: dict, balance_sheet: dict) -> dict:
    """Compute common valuation ratios not shown explicitly on the Screener top bar.

    Market Cap / Sales, Price to Book, EV / EBITDA (when borrowings + cash available).
    """
    derived = {}
    mcap = _parse_number(top_ratios.get("Market Cap"))
    cmp = _parse_number(top_ratios.get("Current Price"))
    bv = _parse_number(top_ratios.get("Book Value"))

    if cmp is not None and bv not in (None, 0):
        derived["Price to Book"] = round(cmp / bv, 2)

    # Most recent Sales figure from P&L (prefer TTM, else last period)
    pl_rows = profit_loss.get("rows", []) if isinstance(profit_loss, dict) else []
    headers = profit_loss.get("headers", []) if isinstance(profit_loss, dict) else []
    sales_row = next((r for r in pl_rows
                      if _normalize_metric_label(r.get("metric", "")) == "sales"), None)
    if sales_row and headers:
        last_key = "TTM" if "TTM" in headers else headers[-1]
        ttm_sales = _parse_number(sales_row.get(last_key))
        if mcap and ttm_sales:
            derived["Market Cap / Sales"] = round(mcap / ttm_sales, 2)

    # EV/EBITDA approximation: EV = Mcap + Borrowings − Cash; EBITDA from Operating Profit TTM
    bs_rows = balance_sheet.get("rows", []) if isinstance(balance_sheet, dict) else []
    bs_headers = balance_sheet.get("headers", []) if isinstance(balance_sheet, dict) else []
    latest_bs_key = bs_headers[-1] if bs_headers else None
    borrow = None
    if latest_bs_key:
        borrow_row = next((r for r in bs_rows
                           if _normalize_metric_label(r.get("metric", "")) == "borrowings"), None)
        if borrow_row:
            borrow = _parse_number(borrow_row.get(latest_bs_key))
    op_profit_row = next((r for r in pl_rows
                          if _normalize_metric_label(r.get("metric", "")) == "operating profit"), None)
    if mcap and borrow is not None and op_profit_row and headers:
        last_key = "TTM" if "TTM" in headers else headers[-1]
        ebitda = _parse_number(op_profit_row.get(last_key))
        if ebitda and ebitda != 0:
            ev = mcap + borrow
            derived["EV / EBITDA (approx)"] = round(ev / ebitda, 2)

    return derived


def fetch_screener_data(symbol_or_id: str, consolidated: bool = False):
    """Fetches and parses company data and documents from Screener.in"""

    base_url = f"https://www.screener.in/company/{symbol_or_id.upper()}/"
    url = base_url + "consolidated/" if consolidated else base_url

    try:
        actual_url, soup = _get_soup(url)
    except Exception as e:
        return json.dumps({"error": f"Failed to connect to Screener.in: {str(e)}"})

    payload = {
        "query_id": symbol_or_id.upper(),
        "source_url": actual_url,
        "summary": "",
        "ratios": {},
        "derived_ratios": {},
        "sitemap_sections": [],
        "sales_data": [],
        "quarterly_results": {"headers": [], "rows": []},
        "profit_loss": {"headers": [], "rows": []},
        "balance_sheet": {"headers": [], "rows": []},
        "cash_flow": {"headers": [], "rows": []},
        "ratios_history": {"headers": [], "rows": []},
        "growth_metrics": {},
        "shareholding": {"quarterly": {"headers": [], "rows": []},
                         "yearly": {"headers": [], "rows": []}},
        "documents": {
            "announcements": [],
            "annual_reports": [],
            "credit_ratings": [],
            "concalls": [],
        },
    }

    # 1. Summary
    about_div = soup.find("div", class_="about")
    if about_div:
        payload["summary"] = " ".join(p.get_text(strip=True) for p in about_div.find_all("p"))

    # 2. Top ratios bar
    payload["ratios"] = _extract_ratios_from_soup(soup)

    # 3. Sitemap (from <section id=...> elements)
    payload["sitemap_sections"] = _build_sitemap(soup)

    # 4. Quarterly, P&L, Balance Sheet, Cash Flow, Ratios history
    def _first_table(section_id):
        sec = soup.find("section", id=section_id)
        return sec.find("table") if sec else None, sec

    q_table, _ = _first_table("quarters")
    payload["quarterly_results"] = _extract_generic_table(q_table)

    pl_table, pl_section = _first_table("profit-loss")
    payload["profit_loss"] = _extract_generic_table(pl_table)
    payload["growth_metrics"] = _extract_growth_blocks(pl_section)

    bs_table, _ = _first_table("balance-sheet")
    payload["balance_sheet"] = _extract_generic_table(bs_table)

    cf_table, _ = _first_table("cash-flow")
    payload["cash_flow"] = _extract_generic_table(cf_table)

    r_table, _ = _first_table("ratios")
    payload["ratios_history"] = _extract_generic_table(r_table)

    # 5. Shareholding — typically two tables (quarterly, yearly)
    sh_section = soup.find("section", id="shareholding")
    if sh_section:
        sh_tables = sh_section.find_all("table")
        if len(sh_tables) >= 1:
            payload["shareholding"]["quarterly"] = _extract_generic_table(sh_tables[0])
        if len(sh_tables) >= 2:
            payload["shareholding"]["yearly"] = _extract_generic_table(sh_tables[1])

    # 6. Legacy sales_data field (single row for backward compat)
    payload["sales_data"] = _extract_sales_rows_from_profit_loss(soup)

    # 7. Documents
    docs_section = soup.find("section", id="documents")
    payload["documents"] = _extract_documents(docs_section, actual_url)

    # 8. Fallbacks: consolidated pages sometimes hide ratios/P&L for anonymous users.
    if consolidated and _count_ratio_values_with_digits(payload["ratios"]) < 3:
        fallback = _get_rendered_soup(base_url)
        if fallback:
            _, standalone_soup = fallback
            alt_ratios = _extract_ratios_from_soup(standalone_soup)
            if _count_ratio_values_with_digits(alt_ratios) > _count_ratio_values_with_digits(payload["ratios"]):
                payload["ratios"] = alt_ratios

    pl_is_error = isinstance(payload["profit_loss"], dict) and not payload["profit_loss"].get("rows")
    if consolidated and pl_is_error:
        fallback = _get_rendered_soup(base_url)
        if fallback:
            _, standalone_soup = fallback
            alt_pl_section = standalone_soup.find("section", id="profit-loss")
            alt_pl_table = alt_pl_section.find("table") if alt_pl_section else None
            alt_pl = _extract_generic_table(alt_pl_table)
            if alt_pl.get("rows"):
                payload["profit_loss"] = alt_pl
                payload["sales_data"] = _extract_sales_rows_from_profit_loss(standalone_soup)
                payload["growth_metrics"] = _extract_growth_blocks(alt_pl_section)

    # 9. Derived valuation ratios (P/B, MC/Sales, EV/EBITDA)
    payload["derived_ratios"] = _derive_ratios(
        payload["ratios"], payload["profit_loss"], payload["balance_sheet"]
    )

    return json.dumps(payload, indent=2)


def fetch_screener_explore_data(sector_filter: str = None, per_category_limit: int = 15):
    """Fetch existing Screener screens and sectors from the Explore page."""
    explore_url = "https://www.screener.in/explore/"
    try:
        source_url, soup = _get_soup(explore_url)
    except Exception as e:
        return json.dumps({"error": f"Failed to connect to Screener Explore: {str(e)}"})

    screen_items = []
    sector_items = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue

        title = _extract_link_title(a)
        if not title:
            continue

        full_url = _normalize_url(href)
        heading = a.find_previous(["h2", "h3"])
        category = heading.get_text(" ", strip=True) if heading else "Other"

        if "/screens/" in href:
            screen_items.append({
                "category": category,
                "title": title,
                "url": full_url,
            })
        elif "/market/" in href and href.rstrip("/") != "/market":
            sector_items.append({
                "name": title,
                "url": full_url,
            })

    screen_items = _unique_items(screen_items, lambda x: (x["title"], x["url"]))
    sector_items = _unique_items(sector_items, lambda x: (x["name"], x["url"]))

    grouped = {}
    for item in screen_items:
        grouped.setdefault(item["category"], []).append({
            "title": item["title"],
            "url": item["url"],
        })

    screens_by_category = []
    for category, screens in grouped.items():
        screens_by_category.append({
            "category": category,
            "screens": screens[:max(per_category_limit, 1)],
        })

    if sector_filter:
        sf = sector_filter.strip().lower()
        sector_items = [s for s in sector_items if sf in s["name"].lower()]

    payload = {
        "mode": "explore",
        "source_url": source_url,
        "screens_total": len(screen_items),
        "screens_by_category": screens_by_category,
        "sectors_total": len(sector_items),
        "sectors": sector_items,
    }
    return json.dumps(payload, indent=2)


def fetch_screener_sector_browse(sector_or_url: str, limit: int = 25):
    """Fetch sector-wise company listing from Screener market browse pages."""
    explore_url = "https://www.screener.in/explore/"

    try:
        if sector_or_url.startswith("http://") or sector_or_url.startswith("https://"):
            sector_url = sector_or_url
            sector_name = None
        else:
            _, soup = _get_soup(explore_url)
            candidate = None
            key = sector_or_url.strip().lower()
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text = a.get_text(" ", strip=True)
                if "/market/" in href and text and key in text.lower():
                    candidate = {"name": text, "url": _normalize_url(href)}
                    break

            if not candidate:
                return json.dumps(
                    {
                        "error": (
                            f"No sector matched '{sector_or_url}' on Screener Explore page. "
                            "Try a broader sector keyword or provide a sector URL."
                        )
                    },
                    indent=2,
                )

            sector_url = candidate["url"]
            sector_name = candidate["name"]

        source_url, sector_soup = _get_soup(sector_url)
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch Screener sector page: {str(e)}"})

    heading = sector_soup.find("h1")
    resolved_sector_name = heading.get_text(" ", strip=True) if heading else (sector_name or "Unknown sector")

    company_links = {}
    for a in sector_soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/company/" not in href:
            continue
        name = a.get_text(" ", strip=True)
        if not name:
            continue
        company_links[name] = _normalize_url(href)

    companies = []
    table = sector_soup.find("table")
    if table:
        headers = []
        head_row = table.find("thead")
        if head_row:
            row = head_row.find("tr")
            if row:
                headers = [th.get_text(" ", strip=True) for th in row.find_all(["th", "td"])]

        body = table.find("tbody")
        rows = body.find_all("tr") if body else table.find_all("tr")
        for tr in rows:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue

            row_values = [c.get_text(" ", strip=True) for c in cells]
            first_val = row_values[0].strip().lower() if row_values else ""
            second_val = row_values[1].strip().lower() if len(row_values) > 1 else ""
            if first_val in {"s.no.", "s.no", "#"} or second_val == "name":
                continue

            if headers and len(headers) == len(row_values):
                row_data = {headers[i]: row_values[i] for i in range(len(headers))}
            else:
                row_data = {f"col_{i+1}": row_values[i] for i in range(len(row_values))}

            company_anchor = tr.find("a", href=True)
            if company_anchor and "/company/" in company_anchor.get("href", ""):
                company_name = company_anchor.get_text(" ", strip=True)
                row_data["company"] = company_name
                row_data["screener_company_url"] = _normalize_url(company_anchor.get("href", ""))
            elif company_links:
                # Best-effort fallback matching by any cell value.
                for value in row_values:
                    if value in company_links:
                        row_data["company"] = value
                        row_data["screener_company_url"] = company_links[value]
                        break

            companies.append(row_data)
            if len(companies) >= max(limit, 1):
                break

    payload = {
        "mode": "sector-browse",
        "source_url": source_url,
        "sector": resolved_sector_name,
        "companies_count": len(companies),
        "companies": companies,
    }
    return json.dumps(payload, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Agent Skill: Fetch company financials, explore stock screens, and sector-wise "
            "browse data from Screener.in"
        )
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        default=None,
        help="The NSE/BSE stock ticker or ID for company mode (e.g., 520073, RELIANCE)",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Use standalone company URL (default behavior; kept for backward compatibility)",
    )
    parser.add_argument(
        "--consolidated",
        action="store_true",
        help="Fetch consolidated financials using /consolidated/ URL",
    )
    parser.add_argument(
        "--mode",
        choices=["company", "explore", "sector"],
        default="company",
        help="company (default), explore (existing screens + sectors), or sector (sector-wise company list)",
    )
    parser.add_argument(
        "--sector",
        type=str,
        default=None,
        help="Sector keyword for filtering explore output or selecting a sector in sector mode (e.g., Banks)",
    )
    parser.add_argument(
        "--sector-url",
        type=str,
        default=None,
        help="Direct Screener sector URL in /market/... format for sector mode",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum records returned per section/output block",
    )

    args = parser.parse_args()

    if args.mode == "company":
        if not args.symbol:
            print(json.dumps({"error": "symbol is required in company mode"}, indent=2))
            sys.exit(1)
        use_consolidated = args.consolidated and not args.standalone
        print(fetch_screener_data(args.symbol, consolidated=use_consolidated))
    elif args.mode == "explore":
        print(fetch_screener_explore_data(sector_filter=args.sector, per_category_limit=args.limit))
    else:
        sector_input = args.sector_url or args.sector
        if not sector_input:
            print(
                json.dumps(
                    {"error": "Provide --sector or --sector-url in sector mode"},
                    indent=2,
                )
            )
            sys.exit(1)
        print(fetch_screener_sector_browse(sector_input, limit=args.limit))

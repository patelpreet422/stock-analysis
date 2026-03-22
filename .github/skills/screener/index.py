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
        page.goto(url, wait_until="networkidle", timeout=30000)
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


def _extract_sales_rows_from_profit_loss(soup: BeautifulSoup):
    section = soup.find("section", id="profit-loss")
    if not section:
        return {"error": "Profit & Loss section not found"}

    table = section.find("table")
    if not table:
        return {"error": "Profit & Loss table not found"}

    headers = []
    head_row = table.find("thead")
    if head_row:
        first_row = head_row.find("tr")
        if first_row:
            headers = [th.get_text(" ", strip=True) for th in first_row.find_all(["th", "td"])]

    rows = []
    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 2:
            continue

        row_values = [c.get_text(" ", strip=True) for c in cells]
        label = row_values[0]
        if not label:
            continue

        row_data = {"metric": label}
        for idx, val in enumerate(row_values[1:], start=1):
            key = headers[idx] if idx < len(headers) and headers[idx] else f"value_{idx}"
            row_data[key] = val
        rows.append(row_data)

    sales_rows = [r for r in rows if _normalize_metric_label(r.get("metric", "")) == "sales"]
    if sales_rows:
        return sales_rows

    return {"error": "Sales row not found in Profit & Loss table"}


def _get_rendered_soup(url: str):
    try:
        return _get_soup(url)
    except Exception:
        return None

def fetch_screener_data(symbol_or_id: str, consolidated: bool = False):
    """Fetches and parses company data and documents from Screener.in"""
    
    # Default to the company page; consolidated view can be requested explicitly.
    base_url = f"https://www.screener.in/company/{symbol_or_id.upper()}/"
    url = base_url + "consolidated/" if consolidated else base_url
        
    try:
        actual_url, soup = _get_soup(url)
    except Exception as e:
        return json.dumps({"error": f"Failed to connect to Screener.in: {str(e)}"})
    
    # Initialize the data payload for the agent
    agent_payload = {
        "query_id": symbol_or_id.upper(),
        "source_url": actual_url,
        "summary": "",
        "ratios": {},
        "sales_data": [],
        "sitemap_sections": [],
        "documents": {
            "announcements": [],
            "annual_reports": [],
            "credit_ratings": [],
            "concalls": []
        }
    }
    
    # 1. Fetch Company Summary
    about_div = soup.find('div', class_='about')
    if about_div:
        agent_payload["summary"] = " ".join([p.get_text(strip=True) for p in about_div.find_all('p')])
        
    # 2. Fetch Top Financial Ratios
    agent_payload["ratios"] = _extract_ratios_from_soup(soup)

    # 3. Fetch Sales / Financial Data
    agent_payload["sales_data"] = _extract_sales_rows_from_profit_loss(soup)

    # Consolidated pages sometimes keep top ratios as placeholders for anonymous users.
    # In that case, pull ratios from the standalone page as a best-effort fallback.
    if consolidated and _count_ratio_values_with_digits(agent_payload["ratios"]) < 3:
        standalone_rendered = _get_rendered_soup(base_url)
        if standalone_rendered:
            _, standalone_soup = standalone_rendered
            standalone_ratios = _extract_ratios_from_soup(standalone_soup)
            if _count_ratio_values_with_digits(standalone_ratios) > _count_ratio_values_with_digits(agent_payload["ratios"]):
                agent_payload["ratios"] = standalone_ratios

    # Consolidated Profit & Loss values may be unavailable in anonymous sessions.
    # Use standalone sales row as fallback if consolidated sales extraction fails.
    sales_still_failed = isinstance(agent_payload["sales_data"], dict) and "error" in agent_payload["sales_data"]
    if consolidated and sales_still_failed:
        standalone_rendered = _get_rendered_soup(base_url)
        if standalone_rendered:
            _, standalone_soup = standalone_rendered
            standalone_sales = _extract_sales_rows_from_profit_loss(standalone_soup)
            if not (isinstance(standalone_sales, dict) and "error" in standalone_sales):
                agent_payload["sales_data"] = standalone_sales

    # 4. Fetch Page Sitemap (Sections for the agent to know what's available)
    nav = soup.find('nav', id='company-nav')
    if nav:
        for link in nav.find_all('a'):
            href = link.get('href')
            text = link.get_text(strip=True)
            if href and text:
                agent_payload["sitemap_sections"].append({"section": text, "anchor": href})

    # 5. Extract Documents for Agent usage
    docs_section = soup.find('section', id='documents')
    if docs_section:
        
        # Helper function to extract document links inside a specific category block
        def extract_links_from_block(block_title):
            extracted = []
            # Find the header (e.g., "Annual reports")
            header = docs_section.find(lambda tag: tag.name in ['h3', 'h4', 'h2'] and block_title.lower() in tag.get_text().lower())
            if header:
                # The links are usually in a ul/div right after or inside the parent container
                container = header.find_parent('div') or header.find_next_sibling('ul')
                if container:
                    links = container.find_all('a')
                    for a in links:
                        href = a.get('href')
                        text = a.get_text(strip=True)
                        if href and text and "search" not in text.lower():
                            full_url = urljoin(actual_url, href)
                            extracted.append({"title": text, "url": full_url})
            return extracted

        # Map document categories
        agent_payload["documents"]["announcements"] = extract_links_from_block("Announcements")
        agent_payload["documents"]["annual_reports"] = extract_links_from_block("Annual reports")
        agent_payload["documents"]["credit_ratings"] = extract_links_from_block("Credit ratings")
        
        # Concalls are often structured slightly differently (Transcript, PPT, Audio)
        concall_header = docs_section.find(lambda tag: tag.name in ['h3', 'h4'] and 'concalls' in tag.get_text().lower())
        if concall_header:
            concall_container = concall_header.find_parent('div')
            if concall_container:
                # Items are usually listed by date (e.g., "Feb 2024")
                for li in concall_container.find_all('li'):
                    date_text = li.contents[0].strip() if li.contents else "Unknown Date"
                    links = [{"type": a.get_text(strip=True), "url": urljoin(actual_url, a.get('href'))} for a in li.find_all('a')]
                    if links:
                        agent_payload["documents"]["concalls"].append({
                            "period": date_text,
                            "files": links
                        })

    return json.dumps(agent_payload, indent=2)


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

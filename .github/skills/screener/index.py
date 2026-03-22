import sys
import json
import argparse
import requests
import pandas as pd
from urllib.parse import urljoin
from bs4 import BeautifulSoup

USER_AGENT = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


def _get_soup(url: str):
    response = requests.get(url, headers=USER_AGENT, timeout=15)
    response.raise_for_status()
    return response, BeautifulSoup(response.text, "html.parser")


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

def fetch_screener_data(symbol_or_id: str, consolidated: bool = True):
    """Fetches and parses company data and documents from Screener.in"""
    
    # Construct URL (handles both ticker symbols and numeric IDs like 520073)
    base_url = f"https://www.screener.in/company/{symbol_or_id.upper()}/"
    url = base_url + "consolidated/" if consolidated else base_url
        
    try:
        response = requests.get(url, headers=USER_AGENT, timeout=10)
        
        # If consolidated doesn't exist, it redirects to standalone. Let's catch the final URL.
        actual_url = response.url 
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": f"Failed to connect to Screener.in: {str(e)}"})

    soup = BeautifulSoup(response.text, 'html.parser')
    
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
    ratio_ul = soup.find('ul', id='top-ratios')
    if ratio_ul:
        for li in ratio_ul.find_all('li'):
            name = li.find('span', class_='name')
            value = li.find('span', class_='number')
            if name and value:
                agent_payload["ratios"][name.get_text(strip=True)] = value.get_text(strip=True)

    # 3. Fetch Sales / Financial Data
    try:
        tables = pd.read_html(response.text)
        for df in tables:
            if 'Sales' in df.columns or (len(df.columns) > 0 and df.iloc[:, 0].astype(str).str.contains('Sales').any()):
                agent_payload["sales_data"] = df.fillna("").to_dict(orient="records")
                break 
    except Exception:
        agent_payload["sales_data"] = {"error": "Could not parse data tables"}

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
        response, soup = _get_soup(explore_url)
    except requests.exceptions.RequestException as e:
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
        "source_url": response.url,
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

        response, sector_soup = _get_soup(sector_url)
    except requests.exceptions.RequestException as e:
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
        "source_url": response.url,
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
    parser.add_argument("--standalone", action="store_true", help="Fetch standalone financials instead of consolidated")
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
        print(fetch_screener_data(args.symbol, consolidated=not args.standalone))
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

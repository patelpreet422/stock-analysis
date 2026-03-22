import sys
import json
import argparse
import requests
import pandas as pd
from urllib.parse import urljoin
from bs4 import BeautifulSoup

def fetch_screener_data(symbol_or_id: str, consolidated: bool = True):
    """Fetches and parses company data and documents from Screener.in"""
    
    # Construct URL (handles both ticker symbols and numeric IDs like 520073)
    base_url = f"https://www.screener.in/company/{symbol_or_id.upper()}/"
    url = base_url + "consolidated/" if consolidated else base_url
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Skill: Fetch financial data and documents from Screener.in")
    parser.add_argument("symbol", type=str, help="The NSE/BSE stock ticker or ID (e.g., 520073, RELIANCE)")
    parser.add_argument("--standalone", action="store_true", help="Fetch standalone financials instead of consolidated")
    
    args = parser.parse_args()
    print(fetch_screener_data(args.symbol, consolidated=not args.standalone))
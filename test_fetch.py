"""Test script to verify description fetching for each source."""
from curl_cffi import requests
from bs4 import BeautifulSoup

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.9',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def test_reed():
    url = "https://www.reed.co.uk/jobs/product-manager/56194641"
    print(f"\n{'='*60}\nTESTING REED: {url}\n{'='*60}")
    
    resp = requests.get(url, impersonate='chrome', headers=HEADERS, timeout=30)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # Try various selectors
        selectors = [
            '[data-qa="job-description"]',
            '.description',
            '[itemprop="description"]',
            '.job-description',
            '#job-description',
            '.job-details__description',
            '.job-content',
        ]
        
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text(strip=True)[:200]
                print(f"  FOUND with '{sel}': {text}...")
                return
        
        # Look for large text blocks
        print("\n  Searching for large text blocks...")
        for div in soup.find_all(['div', 'section', 'article']):
            text = div.get_text(strip=True)
            if len(text) > 500 and 'cookie' not in text.lower()[:100]:
                classes = div.get('class', [])
                id_attr = div.get('id', '')
                print(f"  Large block ({len(text)} chars): class={classes}, id={id_attr}")
                print(f"    Preview: {text[:150]}...")
                break

def test_cvlibrary():
    url = "https://www.cv-library.co.uk/job/224428345/NET-Full-Stack-Engineer"
    print(f"\n{'='*60}\nTESTING CV-LIBRARY: {url}\n{'='*60}")
    
    resp = requests.get(url, impersonate='chrome', headers=HEADERS, timeout=30)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'lxml')
        
        selectors = [
            '.job-description',
            '.job__description',
            '[class*="job-description"]',
            '.vacancy-description',
            '#job-description',
            '.job-content',
            '.job-details',
        ]
        
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text(strip=True)[:200]
                print(f"  FOUND with '{sel}': {text}...")
                return
        
        print("\n  Searching for large text blocks...")
        for div in soup.find_all(['div', 'section', 'article']):
            text = div.get_text(strip=True)
            if len(text) > 500 and 'cookie' not in text.lower()[:100]:
                classes = div.get('class', [])
                id_attr = div.get('id', '')
                print(f"  Large block ({len(text)} chars): class={classes}, id={id_attr}")
                print(f"    Preview: {text[:150]}...")
                break

def test_indeed():
    # Indeed uses tracking URLs - need to follow redirect
    tracking_url = "https://uk.indeed.com/rc/clk?jk=f1e320b84dfc7edb&bb=qCIWcZ-FoPXudcSmuDBWmNrr2fXX-kAamRwQnO1RRvBLV2N4ayNe7t0hzTFDFMPrStz1oiTN9dBdyaR_WIsezkV3UKKeCEfAkmFnMPiXLyfsxjcAFZADzzoI0N7PNxrwE5K1sKFDSRM%3D"
    print(f"\n{'='*60}\nTESTING INDEED (tracking URL):\n{'='*60}")
    
    resp = requests.get(tracking_url, impersonate='chrome', headers=HEADERS, timeout=30, allow_redirects=True)
    print(f"Status: {resp.status_code}")
    print(f"Final URL: {resp.url}")
    
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'lxml')
        
        selectors = [
            '#jobDescriptionText',
            '.jobsearch-jobDescriptionText',
            '[data-testid="jobDescriptionText"]',
            '.job-description',
        ]
        
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text(strip=True)[:200]
                print(f"  FOUND with '{sel}': {text}...")
                return
        
        print("\n  Searching for large text blocks...")
        for div in soup.find_all(['div', 'section']):
            text = div.get_text(strip=True)
            if len(text) > 300 and 'cookie' not in text.lower()[:100]:
                classes = div.get('class', [])
                print(f"  Large block ({len(text)} chars): class={classes}")
                print(f"    Preview: {text[:150]}...")
                break

if __name__ == "__main__":
    test_reed()
    test_cvlibrary()
    test_indeed()

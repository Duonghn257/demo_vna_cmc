import asyncio
from openai import responses
from playwright.sync_api import Locator
import streamlit as st
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser
import pandas as pd
from urllib.parse import urljoin, urlparse
import time
from typing import Dict, List, Optional
from .llm import spelling_check, Result
from .helpers import (
    get_common_text_elements,
    find_dumb_text_batches,
    Element,
    highlight_locator, 
    unhighlight_locator, 
    get_font_size, 
    screenshot,
    close_cookies,
    close_popup_if_present
)
import json

class WebCrawler:
    def __init__(self):
        self.soup = None
        self.url = None
        self.playwright = None
        self.browser = None
        self.page = None
        self._locators_element: List[Element]
        self._text_batches: List[str]
        self._correction_text: List[Result]

    async def check_url_availability(self, url: str) -> Dict[str, any]:
        """Check if URL is accessible"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            try:
                # Điều hướng đến URL và lấy response
                response = await page.goto(url, wait_until="domcontentloaded")
                # await page.wait_for_load_state("domcontentloaded")
                
                if response and response.status == 200:
                    print(f"✅ URL '{url}' is available. Status: {response.status}")
                    return {
                        "available": True,
                        "status_code": response.status,
                        "final_url": response.url,
                        "content_type": response.headers.get('content-type', 'Unknown')
                    }
                else:
                    print(f"❌ URL '{url}' is not available. Status: {response.status if response else 'No response'}")
                    return {
                        "available": False,
                        "status_code": response.status,
                        "final_url": response.url,
                        "content_type": response.headers.get('content-type', 'Unknown')
                    }
            except Exception as e:
                print(f"❌ URL '{url}' is not available. Error: {e}")
                return {
                        "available": False
                    }
            finally:
                await browser.close()

    async def crawl_with_playwright(self, url: str, wait_time: int = 3) -> bool:
        """Crawl website using Playwright for JavaScript-heavy sites"""
        # try:
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.page = await self.browser.new_page()

        # Set user agent and other headers
        await self.page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        await self.page.goto(url, wait_until="domcontentloaded")
        # await close_cookies(self.page)
        # await close_popup_if_present(self.page)

        html_content = await self.page.content()
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.url = url

        await self.cleanup()
        return True

    async def highlight_incorrect_text(self) -> pd.DataFrame:

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.page = await self.browser.new_page()

        # Set user agent and other headers
        await self.page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        await self.page.goto(self.url, wait_until="domcontentloaded")

        self._locators_element = await get_common_text_elements(page=self.page)
        self._text_batches = await find_dumb_text_batches(self._locators_element, MAX_TOKENS=100000)
        self._correction_text = await spelling_check(self._text_batches[0])
        raw_text = []
        edited_text = []

        for res in self._correction_text:
            content, idx = res.content, res.idx

            print(self._locators_element[idx].locator)
            await highlight_locator(self._locators_element[idx].locator)

            raw_text.append(self._locators_element[idx].text)
            edited_text.append(content)
        
        df = pd.DataFrame({
            'Wrong Text': raw_text,
            'Correct Text Suggest': edited_text
        })

        # await self.cleanup()
        return df

    async def unhighlight_incorrect_text(self):
        for res in self._correction_text:
            content, idx = res.content, res.idx
            await unhighlight_locator(self._locators_element[idx].locator)       

    async def crawl_with_requests(self, url: str) -> bool:
        """Crawl website using aiohttp + BeautifulSoup for static sites (async)"""
        import aiohttp

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=15) as response:
                    response.raise_for_status()
                    content = await response.read()
                    self.soup = BeautifulSoup(content, 'html.parser')
                    self.url = url
                    return True

        except Exception as e:
            st.error(f"Requests crawling failed: {str(e)}")
            return False

    async def extract_page_content(self) -> Dict[str, str]:
        """Extract basic page information with improved content detection"""
        if not self.soup:
            return {}

        # Remove unwanted elements
        for element in self.soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            element.decompose()
        words = await self._get_main_content()
        # print(words.s)
        return {
            "title": await self._get_title(),
            "meta_description":await self._get_meta_description(),
            "meta_keywords":await self._get_meta_keywords(),
            "main_content":await self._get_main_content(),
            "headings":await self._get_headings(),
            "word_count":len(words.split()),
            "paragraphs":await self._get_paragraphs()
        }

    async def _get_title(self) -> str:
        """Extract page title"""
        if self.soup.title:
            return self.soup.title.string.strip()
        
        # Try h1 as fallback
        h1 = self.soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        return "No title found"

    async def _get_meta_description(self) -> str:
        """Extract meta description"""
        meta_desc = self.soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc.get("content").strip()
        
        # Try Open Graph description
        og_desc = self.soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            return og_desc.get("content").strip()
        
        return "No meta description found"

    async def _get_meta_keywords(self) -> str:
        """Extract meta keywords"""
        meta_keywords = self.soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords and meta_keywords.get("content"):
            return meta_keywords.get("content").strip()
        return "No keywords found"

    async def _get_main_content(self) -> str:
        """Extract main text content with better content detection"""
        # Priority selectors for main content
        main_selectors = [
            'main', 'article', '[role="main"]', '.content', '.post-content',
            '.entry-content', '.post-body', '.article-content', '.page-content',
            '#content', '#main-content', '.main-content'
        ]
        
        for selector in main_selectors:
            main_element = self.soup.select_one(selector)
            if main_element:
                return main_element.get_text(strip=True, separator=' ')
        
        # Fallback: find the largest text block
        body = self.soup.find('body')
        if body:
            # Remove common non-content elements
            for element in body.find_all(['nav', 'header', 'footer', 'aside', 'form', 'button']):
                element.decompose()
            return body.get_text(strip=True, separator=' ')
        
        return self.soup.get_text(strip=True, separator=' ')

    async def _get_paragraphs(self) -> List[str]:
        """Extract all paragraphs"""
        paragraphs = []
        for p in self.soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 20:  # Only meaningful paragraphs
                paragraphs.append(text)
        return paragraphs[:10]  # Limit to first 10 paragraphs

    async def _get_headings(self) -> List[Dict[str, str]]:
        """Extract all headings with improved structure"""
        headings = []
        for i in range(1, 7):
            for heading in self.soup.find_all(f'h{i}'):
                text = heading.get_text(strip=True)
                if text:  # Only non-empty headings
                    headings.append({
                        "level": f"H{i}",
                        "text": text,
                        "id": heading.get('id', '')
                    })
        return headings

    async def extract_images(self) -> List[Dict[str, str]]:
        """Extract all images with metadata"""
        if not self.soup:
            return []
            
        images = []
        for img in self.soup.find_all('img'):
            src = img.get('src', '')
            if src:
                absolute_url = urljoin(self.url, src)
                images.append({
                    "src": absolute_url,
                    "alt": img.get('alt', 'No alt text'),
                    "title": img.get('title', ''),
                    "width": img.get('width', ''),
                    "height": img.get('height', '')
                })
        return images

    async def extract_links(self, filter_external: bool = False) -> List[Dict[str, str]]:
        """Extract links with filtering options"""
        if not self.soup:
            return []
            
        links = []
        base_domain = urlparse(self.url).netloc

        # element = self.soup.find("a", attrs={"class": "menu__link menu__link--active"})
        # element.get_text()
        
        for link in self.soup.find_all('a', href=True):
            href = link['href']
            if not href or href.startswith('#'):  # Skip empty and anchor links
                continue
                
            absolute_url = urljoin(self.url, href)
            is_external = urlparse(absolute_url).netloc != base_domain
            
            if filter_external and is_external:
                continue
                
            text = link.get_text(strip=True)
            if not text:  # Skip links without text
                continue
            
            # title = ''
            # title = link.get('title', '')

            links.append({
                "url": absolute_url,
                "text": text[:100] + "..." if len(text) > 100 else text,  # Truncate long text
                "title": link.get('title', ''),
                "is_external": is_external,
                "rel": ' '.join(link.get('rel', [])),
                "target": link.get('target', '')
            })
            
        return links

    async def extract_tables(self) -> List[pd.DataFrame]:
        """Extract all tables as DataFrames"""
        if not self.soup:
            return []
            
        tables = []
        for table in self.soup.find_all('table'):
            try:
                df = pd.read_html(str(table))[0]
                tables.append(df)
            except Exception:
                # Fallback manual parsing
                rows = []
                for tr in table.find_all('tr'):
                    row = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if row:
                        rows.append(row)
                if rows:
                    df = pd.DataFrame(rows[1:], columns=rows[0] if rows else None)
                    tables.append(df)
        return tables

    async def screenshots(self):
        # await self.page.goto(url=self.url)
        # await self.page.wait_for_load_state("domcontentloaded")  # Wait for page to load
        await screenshot(self.page, OUTPUT_DIR="./screenshots")
        print(self.page)

    async def cleanup(self):
        """Clean up Playwright resources"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass

async def main():
    
    url = "https://duonghn257.github.io/demo_vna_cmc/"
    crawler = WebCrawler()
    # response = await crawler.check_url_availability(url)
    check = await crawler.crawl_with_playwright(url)
    # print(crawler._locators_element)
    df = await crawler.highlight_incorrect_text()
    print(df)
    # if check:
    #     for batch in crawler._text_batches:
    #         res = spelling_check(batch)
        # res = spelling_check(crawler._text_batches)
        # print(res)
        # print(len(data))
    input("Nhấn Enter để đóng trình duyệt...")
    await crawler.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
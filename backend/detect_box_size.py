import asyncio
from playwright.async_api import async_playwright
import statistics
from collections import defaultdict

import platform
import os

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class TextSizeAnalyzer:
    def __init__(self):
        self.browser = None
        self.page = None
    
    async def setup(self):
        """Initialize browser and page"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False)
        self.page = await self.browser.new_page()
    
    async def cleanup(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
    
    async def get_element_font_size(self, element):
        """Get computed font size for an element"""
        font_size = await element.evaluate("""
            (element) => {
                const computed = window.getComputedStyle(element);
                return parseFloat(computed.fontSize);
            }
        """)
        return font_size
    
    async def get_elements_by_level(self, selector_pattern="*"):
        """Group elements by their hierarchical level (depth in DOM)"""
        elements_by_level = await self.page.evaluate(f"""
            () => {{
                const elements = document.querySelectorAll('{selector_pattern}');
                const levelMap = new Map();
                
                elements.forEach(el => {{
                    if (el.offsetParent !== null || el === document.body) {{ // visible elements only
                        let depth = 0;
                        let parent = el.parentElement;
                        while (parent) {{
                            depth++;
                            parent = parent.parentElement;
                        }}
                        
                        if (!levelMap.has(depth)) {{
                            levelMap.set(depth, []);
                        }}
                        levelMap.get(depth).push({{
                            element: el,
                            tagName: el.tagName,
                            className: el.className,
                            id: el.id,
                            textContent: el.textContent?.slice(0, 50) || '',
                            fontSize: parseFloat(window.getComputedStyle(el).fontSize)
                        }});
                    }}
                }});
                
                return Object.fromEntries(levelMap);
            }}
        """)
        return elements_by_level
    
    async def find_abnormal_sizes_by_tag(self, tag_selector="p, h1, h2, h3, h4, h5, h6, span, div"):
        """Find elements with abnormal font sizes grouped by tag type"""
        elements_data = await self.page.evaluate(f"""
            () => {{
                const elements = document.querySelectorAll('{tag_selector}');
                const tagGroups = {{}};
                
                elements.forEach(el => {{
                    if (el.offsetParent !== null || el === document.body) {{
                        const tagName = el.tagName.toLowerCase();
                        const fontSize = parseFloat(window.getComputedStyle(el).fontSize);
                        const textContent = el.textContent?.trim();
                        
                        // Skip elements with no text content
                        if (!textContent || textContent.length === 0) return;
                        
                        if (!tagGroups[tagName]) {{
                            tagGroups[tagName] = [];
                        }}
                        
                        tagGroups[tagName].push({{
                            fontSize: fontSize,
                            textContent: textContent.slice(0, 100),
                            className: el.className,
                            id: el.id,
                            xpath: getXPath(el)
                        }});
                    }}
                }});
                
                function getXPath(element) {{
                    if (element.id) {{
                        return `//*[@id="${{element.id}}"]`;
                    }}
                    
                    let path = '';
                    let current = element;
                    
                    while (current && current.nodeType === Node.ELEMENT_NODE) {{
                        let selector = current.tagName.toLowerCase();
                        if (current.className) {{
                            selector += '.' + current.className.split(' ').join('.');
                        }}
                        path = selector + (path ? ' > ' + path : '');
                        current = current.parentElement;
                    }}
                    
                    return path;
                }}
                
                return tagGroups;
            }}
        """)
        
        abnormal_elements = []
        
        for tag, elements in elements_data.items():
            if len(elements) < 2:  # Need at least 2 elements to compare
                continue
                
            font_sizes = [el['fontSize'] for el in elements]
            mean_size = statistics.mean(font_sizes)
            std_dev = statistics.stdev(font_sizes) if len(font_sizes) > 1 else 0
            
            # Define abnormal as elements that are more than 1.5 standard deviations from mean
            threshold = 1.5 * std_dev if std_dev > 0 else 0
            
            for element in elements:
                deviation = abs(element['fontSize'] - mean_size)
                if deviation > threshold and std_dev > 0:
                    abnormal_elements.append({
                        'tag': tag,
                        'fontSize': element['fontSize'],
                        'meanSize': mean_size,
                        'deviation': deviation,
                        'textContent': element['textContent'],
                        'className': element['className'],
                        'id': element['id'],
                        'xpath': element['xpath'],
                        'anomalyType': 'larger' if element['fontSize'] > mean_size else 'smaller'
                    })
        
        return abnormal_elements
    
    async def find_outliers_by_percentile(self, selector="*", percentile_threshold=95):
        """Find elements with font sizes in top/bottom percentiles"""
        font_sizes_data = await self.page.evaluate(f"""
            () => {{
                const elements = document.querySelectorAll('{selector}');
                const fontSizeData = [];
                
                elements.forEach(el => {{
                    if (el.offsetParent !== null || el === document.body) {{
                        const fontSize = parseFloat(window.getComputedStyle(el).fontSize);
                        const textContent = el.textContent?.trim();
                        
                        if (textContent && textContent.length > 0) {{
                            fontSizeData.push({{
                                fontSize: fontSize,
                                textContent: textContent.slice(0, 100),
                                tagName: el.tagName.toLowerCase(),
                                className: el.className,
                                id: el.id
                            }});
                        }}
                    }}
                }});
                
                return fontSizeData;
            }}
        """)
        
        if not font_sizes_data:
            return []
        
        font_sizes = [item['fontSize'] for item in font_sizes_data]
        font_sizes.sort()
        
        # Calculate percentile thresholds
        n = len(font_sizes)
        lower_threshold_idx = int(n * (100 - percentile_threshold) / 100)
        upper_threshold_idx = int(n * percentile_threshold / 100)
        
        lower_threshold = font_sizes[lower_threshold_idx] if lower_threshold_idx < n else font_sizes[0]
        upper_threshold = font_sizes[upper_threshold_idx] if upper_threshold_idx < n else font_sizes[-1]
        
        outliers = []
        for item in font_sizes_data:
            if item['fontSize'] <= lower_threshold or item['fontSize'] >= upper_threshold:
                outliers.append({
                    **item,
                    'outlierType': 'small' if item['fontSize'] <= lower_threshold else 'large',
                    'lowerThreshold': lower_threshold,
                    'upperThreshold': upper_threshold
                })
        
        return outliers
    
    async def find_inconsistent_siblings(self):
        """Find elements with different font sizes among siblings"""
        inconsistent_groups = await self.page.evaluate("""
            () => {
                const parentGroups = new Map();
                const elements = document.querySelectorAll('*');
                
                elements.forEach(el => {
                    if (el.offsetParent !== null || el === document.body) {
                        const textContent = el.textContent?.trim();
                        if (!textContent || textContent.length === 0) return;
                        
                        const parent = el.parentElement;
                        if (!parent) return;
                        
                        const parentKey = parent.tagName + (parent.className ? '.' + parent.className : '') + (parent.id ? '#' + parent.id : '');
                        
                        if (!parentGroups.has(parentKey)) {
                            parentGroups.set(parentKey, []);
                        }
                        
                        parentGroups.get(parentKey).push({
                            fontSize: parseFloat(window.getComputedStyle(el).fontSize),
                            textContent: textContent.slice(0, 50),
                            tagName: el.tagName.toLowerCase(),
                            className: el.className,
                            id: el.id
                        });
                    }
                });
                
                const inconsistentGroups = [];
                
                parentGroups.forEach((siblings, parentKey) => {
                    if (siblings.length < 2) return;
                    
                    const fontSizes = siblings.map(s => s.fontSize);
                    const uniqueSizes = [...new Set(fontSizes)];
                    
                    if (uniqueSizes.length > 1) {
                        const mean = fontSizes.reduce((a, b) => a + b, 0) / fontSizes.length;
                        
                        inconsistentGroups.push({
                            parentKey: parentKey,
                            siblings: siblings,
                            fontSizeVariance: Math.max(...fontSizes) - Math.min(...fontSizes),
                            meanSize: mean,
                            uniqueSizes: uniqueSizes
                        });
                    }
                });
                
                return inconsistentGroups;
            }
        """)
        
        return inconsistent_groups

# Usage example
async def main():
    analyzer = TextSizeAnalyzer()
    
    try:
        await analyzer.setup()
        await analyzer.page.goto('https://duonghn257.github.io/demo_vna_cmc/')  # Replace with your URL
        
        # Method 1: Find abnormal sizes by tag type
        print("=== Abnormal Font Sizes by Tag ===")
        abnormal_by_tag = await analyzer.find_abnormal_sizes_by_tag()
        for item in abnormal_by_tag:
            print(f"Tag: {item['tag']}, Size: {item['fontSize']}px ({item['anomalyType']})")
            print(f"  Mean size for {item['tag']}: {item['meanSize']:.1f}px")
            print(f"  Text: {item['textContent'][:50]}...")
            print(f"  Selector: {item['xpath']}")
            print()
        
        # Method 2: Find outliers by percentile
        print("=== Font Size Outliers (95th percentile) ===")
        outliers = await analyzer.find_outliers_by_percentile(percentile_threshold=90)
        for item in outliers:
            print(f"Size: {item['fontSize']}px ({item['outlierType']} outlier)")
            print(f"  Tag: {item['tagName']}")
            print(f"  Text: {item['textContent'][:50]}...")
            print()
        
        # Method 3: Find inconsistent siblings
        print("=== Inconsistent Sibling Font Sizes ===")
        inconsistent = await analyzer.find_inconsistent_siblings()
        for group in inconsistent:
            print(f"Parent: {group['parentKey']}")
            print(f"  Font size variance: {group['fontSizeVariance']}px")
            print(f"  Unique sizes: {group['uniqueSizes']}")
            for sibling in group['siblings']:
                print(f"    {sibling['tagName']}: {sibling['fontSize']}px - {sibling['textContent'][:30]}...")
            print()
            
    finally:
        await analyzer.cleanup()

# For targeting specific elements after detection
async def highlight_abnormal_elements(page, abnormal_elements):
    """Highlight detected abnormal elements on the page"""
    for element in abnormal_elements:
        if 'xpath' in element:
            try:
                locator = page.locator(f"xpath={element['xpath']}")
                await locator.evaluate("""
                    (el) => {
                        el.style.border = '3px solid red';
                        el.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
                        el.title = `Abnormal font size: ${el.style.fontSize}`;
                    }
                """)
            except Exception as e:
                print(f"Could not highlight element: {e}")

if __name__ == "__main__":
    asyncio.run(main())
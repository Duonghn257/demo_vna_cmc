from playwright.async_api import async_playwright, Page, Locator
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
import os
import tiktoken
import json
import pandas as pd
import difflib

def num_tokens_from_model(string: str, model_name: str = "gpt-4o") -> int:
    """Returns the number of tokens in a text string for a specific model."""
    encoding = tiktoken.encoding_for_model(model_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

SCROLL_STEP = 500  # Pixels to scroll each time
DELAY_BETWEEN_SHOTS = 0.5  # Seconds to wait after scrolling (helps with lazy loading)
COOKIE_BUTTON_XPATH = "//*[@id='cookie-agree']"
TIMEOUT = 5000
CLOSE_ADS_XPATH = """//*[@class="ins-close-button"]"""

@dataclass
class Element:
    idx: int
    text: str
    locator: Optional[Locator] = None  # Optional, initialized to None
    # token_num: int

async def find_dumb_text_batches(elements: List[Element], MAX_TOKENS: int) -> List[str]:
    """
    Chia danh sách Element thành các chuỗi JSON (batch),
    mỗi batch có số token <= MAX_TOKENS.

    Returns:
        List[str]: Danh sách các chuỗi JSON, mỗi chuỗi là một batch hợp lệ.
    """
    if not elements:
        return []

    batches = []  # Lưu các chuỗi JSON batch
    current_batch = []  # Danh sách dict tạm
    current_json = "[]"  # JSON string hiện tại
    current_tokens = num_tokens_from_model(current_json)

    for elem in elements:
        # Thử thêm phần tử vào batch hiện tại
        temp_batch = current_batch + [{"idx": elem.idx, "text": elem.text}]
        temp_json = json.dumps(temp_batch, ensure_ascii=False, indent=2)
        temp_tokens = num_tokens_from_model(temp_json)

        if temp_tokens <= MAX_TOKENS:
            # Vẫn trong giới hạn → thêm vào batch hiện tại
            current_batch = temp_batch
            current_json = temp_json
            current_tokens = temp_tokens
        else:
            # ❌ Vượt giới hạn
            if not current_batch:
                # 🚨 Ngay phần tử đầu tiên đã quá lớn
                print(f"[⚠️] Bỏ qua phần tử idx={elem.idx} - quá lớn để nằm trong batch nào (text: {elem.text[:50]}...)")
                continue  # Bỏ qua, không thể xử lý

            # ✅ Đóng batch hiện tại
            batches.append(current_json)
            print(f"[✅] Batch đóng: {current_tokens} tokens")

            # Bắt đầu batch mới với phần tử hiện tại
            current_batch = [{"idx": elem.idx, "text": elem.text}]
            current_json = json.dumps(current_batch, ensure_ascii=False, indent=2)
            current_tokens = num_tokens_from_model(current_json)

    # Đóng batch cuối cùng nếu còn
    if current_batch:
        batches.append(current_json)
        print(f"[✅] Batch cuối: {current_tokens} tokens")

    print(f"[🎉] Tổng cộng: {len(batches)} batch được tạo.")
    return batches

async def get_common_text_elements(page: Page) -> List[Element]:
    """
    Lấy các phần tử thường chứa text nhỏ, có ý nghĩa.
    Loại bỏ div/button chung chung, nhưng thêm lại các locator đặc biệt.
    """
    # 1. Các selector an toàn, thường chứa text nhỏ
    base_selectors = [
        "p", "span", "a", 
        "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "label", "small", "strong", "em", "i", "b", "u",
        "td", "th", "cite", "figcaption", "mark", "time"
    ]

    elements: List[Element] = []

    cnt = 0
    # 2. Duyệt các selector cơ bản
    for sel in base_selectors:
        locator = page.locator(sel)
        count = await locator.count()

        for i in range(count):
            elem = locator.nth(i)
            try:
                text = await elem.inner_text()  # inner_text() sạch hơn textContent
                text = text.strip()
                if text:
                    elements.append(Element(
                        idx = cnt,
                        locator = elem,
                        text = text,
                        # token_num = num_tokens_from_model(text)
                    ))
                    cnt+=1
            except Exception as e:
                continue  # Bỏ qua nếu lỗi (ví dụ: element detached)

    # 3. Thêm các locator đặc biệt (mặc dù là div, nhưng quan trọng)
    special_locators = [
        "div.logo-text",                    # ✅ Bạn muốn cái này
        "div.logo-subtitle",
        "button.language-selector",
        "div.skypriority-logo"
    ]

    for sel in special_locators:
        locator = page.locator(sel)
        count = await locator.count()
        for i in range(count):
            elem = locator.nth(i)
            try:
                text = await elem.inner_text()
                text = text.strip()
                if text:
                    elements.append(Element(
                        idx = cnt,
                        locator = elem,
                        text = text,
                        # token_num = num_tokens_from_model(text)
                    ))
                    cnt+=1
            except Exception as e:
                continue

    # 4. Loại bỏ trùng lặp (dùng text + selector để xác định trùng)
    # seen = set()
    # unique_elements = []
    # for el in elements:
    #     key = (el["text"], el["selector"])
    #     if key not in seen:
    #         seen.add(key)
    #         unique_elements.append(el)

    # print(f"✅ Tìm thấy {len(unique_elements)} phần tử có text (sau khi lọc và thêm đặc biệt).")
    return elements

async def close_cookies(page: Page):
    try:
        print("Waiting for cookie agreement button...")
        cookie_button = await page.wait_for_selector(f"xpath={COOKIE_BUTTON_XPATH}", timeout=TIMEOUT)
        print("Cookie button found. Clicking...")
        await cookie_button.click()
        print("Cookie accepted.")
    except Exception as e:
        print(f"⚠️  Cookie button not found or already accepted: {e}")
        
async def close_popup_if_present(page: Page):
    try:
        print("Waiting for close advertisement button...")
        close_ad_button = await page.wait_for_selector(f"xpath={CLOSE_ADS_XPATH}", timeout=100)
        print("Close advertisement button found. Clicking...")
        await close_ad_button.click(force=True)
        print("Advertisement closed.")
        await page.wait_for_timeout(500)
        return True
    except Exception as e:
        print(f"⚠️  Close advertisement button not found or already closed: {e}")
    
    return False

async def screenshot(page: Page, OUTPUT_DIR):
    screenshot_count = 0
    previous_height = await page.evaluate("document.body.scrollHeight")
    
    while True:
        closed = await close_popup_if_present(page)
        if closed:
            await page.wait_for_timeout(1000)
            previous_height =  await page.evaluate("document.body.scrollHeight")

        # Generate filename
        screenshot_path = os.path.join(OUTPUT_DIR, f"screenshot_{screenshot_count:03d}.png")

        # Take screenshot of current viewport
        await page.screenshot(path=screenshot_path, full_page=False)  # Set True for full page
        print(f"Saved: {screenshot_path}")

        # Scroll down by SCROLL_STEP
        await page.evaluate(f"window.scrollBy(0, {SCROLL_STEP})")

        # Wait a bit for content to load (important for infinite scroll, images, etc.)
        await page.wait_for_timeout(int(DELAY_BETWEEN_SHOTS * 1000))

        # Check new scroll height
        new_height = await page.evaluate("document.body.scrollHeight")
        scroll_position = await page.evaluate("window.pageYOffset")

        # Break if no new content loaded and we can't scroll further
        if new_height == previous_height and scroll_position + page.viewport_size['height'] >= new_height:
            print("Reached the bottom of the page.")
            break

        previous_height = new_height
        screenshot_count += 1

async def highlight_locator(locator: Locator):
    """
    Highlight một element bằng cách thêm một đường viền màu đỏ.
    """
    if locator:
        await locator.evaluate('''
            element => {
            const style = window.getComputedStyle(element);
            const font_size = style.fontSize;
            element.style.border = "2px solid red";
            element.style.backgroundColor = "yellow";
            element.style.transition = "border 0.2s, background-color 0.2s";
            element.style.position = "relative";
            element.style.color = "black"; // Change text color inside border to black
            // Thêm một class đặc biệt để áp dụng ::after
            element.classList.add('ai-highlight-after');
            // Tạo hoặc cập nhật một style tag cho ::after nếu chưa có
            if (!document.getElementById('ai-highlight-after-style')) {
                const style = document.createElement('style');
                style.id = 'ai-highlight-after-style';
                style.textContent = `
                    .ai-highlight-after::after {
                        content: attr(data-ai-text);
                        position: absolute;
                        right: 0;
                        top: 0px;
                        background: green;
                        color: #fff;
                        font-size: 12px;
                        padding: 2px 6px;
                        border-radius: 4px;
                        border: 1px solid #aaa;
                        
                        z-index: 9999999;
                        white-space: pre;
                    }
                `;
                document.head.appendChild(style);
            }
            // Gán textContent vào thuộc tính data-ai-text để ::after sử dụng
            element.setAttribute('data-ai-text', font_size);
        }''')

    return None

async def unhighlight_locator(locator: Locator):
    """
    Xóa highlight bằng cách khôi phục lại border ban đầu.
    """
    await locator.evaluate('''element => {
        element.style.border = "";
        element.style.backgroundColor = "";
    }''')

async def get_font_size(locator: Locator) -> str:
    """
    Lấy giá trị font-size của một Locator.

    Args:
        locator (Locator): Phần tử Playwright.

    Returns:
        str: Giá trị font-size (ví dụ: "16px"), hoặc None nếu không tìm thấy.
    """
    try:
        font_size = await locator.evaluate("""element => {
            const style = window.getComputedStyle(element);
            return style.fontSize;
        }""")
        return font_size
    except Exception as e:
        print(f"[Lỗi khi lấy font-size] {e}")
        return None

async def highlight_elements_with_text(page: Page, user_input: str):    
    """
    Tìm tất cả các phần tử có chứa văn bản giống với `user_input` (toàn phần hoặc một phần),
    sau đó highlight chúng.
    
    Args:
        page (Page): Trang Playwright.
        user_input (str): Văn bản cần tìm.
    """
    # Escape chuỗi để dùng trong XPath (tránh lỗi nếu có dấu ngoặc, trích dẫn, v.v.)
    async def escape_xpath_string(s: str) -> str:
        if "'" not in s:
            return f"'{s}'"
        if '"' not in s:
            return f'"{s}"'
        return "concat('" + "', '\"', '".join(s.split('"')) + "')"

    escaped_text = await escape_xpath_string(user_input.strip())

    # Tìm tất cả các phần tử có textContent chứa user_input (không phân biệt hoa thường)
    locators = await page.locator(f"xpath=//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                           f"translate({escaped_text}, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))]")

    count = await locators.count()
    print(f"Tìm thấy {count} phần tử chứa văn bản: '{user_input}'")

    async for i in range(count):
        elem_locator = await locators.nth(i)
        print(elem_locator.all_text_contents())
        await highlight_locator(elem_locator)
        sz = await get_font_size(elem_locator)

def highlight_both_columns_differences(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a new DataFrame with:
    - 'Wrong Text': misspelled words wrapped in ** **
    - 'Correct Text Suggest': corrected words wrapped in ** **
    Based on word-by-word comparison.
    """
    def make_both_bold(wrong_text, correct_text):
        words_wrong = wrong_text.split()
        words_correct = correct_text.split()
        
        # Align words using SequenceMatcher
        matcher = difflib.SequenceMatcher(None, words_wrong, words_correct)
        
        wrong_highlighted = words_wrong.copy()
        correct_highlighted = words_correct.copy()
        
        # Traverse opcodes to find differences
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':  # This includes 'replace', 'insert', 'delete'
                # Words in wrong text (to be deleted or replaced) → highlight in red/wrong
                for i in range(i1, i2):
                    if i < len(wrong_highlighted):
                        wrong_highlighted[i] = f"**{words_wrong[i]}**"
                # Words in correct text (inserted or replacing) → highlight in correction
                for j in range(j1, j2):
                    if j < len(correct_highlighted):
                        correct_highlighted[j] = f"**{words_correct[j]}**"
        
        return ' '.join(wrong_highlighted), ' '.join(correct_highlighted)
    
    # Create new DataFrame
    result_df = df[['Wrong Text', 'Correct Text Suggest']].copy()
    
    # Apply function and unpack both results
    (
        result_df['Wrong Text'],
        result_df['Correct Text Suggest']
    ) = zip(*df.apply(
        lambda row: make_both_bold(row['Wrong Text'], row['Correct Text Suggest']),
        axis=1
    ))
    
    return result_df
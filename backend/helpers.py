from playwright.sync_api import sync_playwright, Page, Locator
from typing import List
import os
import tiktoken

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
    await locator.evaluate('''
        element => {
        const style = window.getComputedStyle(element);
        const font_size = style.fontSize;
        element.style.border = "2px solid red";
        element.style.backgroundColor = "yellow";
        element.style.transition = "border 0.2s, background-color 0.2s";
        element.style.position = "relative";
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
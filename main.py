import streamlit as st
from backend.webcrawler import WebCrawler
from backend.helpers import highlight_both_columns_differences
import pandas as pd
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright
import asyncio
import platform
import os

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def display_images_from_folder(folder_path):
    """
    Hiển thị tất cả các hình ảnh trong một thư mục.
    """
    st.title("Hiển thị Hình ảnh từ Thư mục")

    # Lấy danh sách tất cả các file trong thư mục
    file_list = os.listdir(folder_path)

    # Lọc ra các file hình ảnh
    image_files = [file for file in file_list if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]

    if not image_files:
        st.warning("Không tìm thấy hình ảnh nào trong thư mục.")
    else:
        st.write(f"Tìm thấy {len(image_files)} hình ảnh:")
        for image_file in image_files:
            image_path = os.path.join(folder_path, image_file)
            st.image(image_path, caption=image_file, use_container_width=True)

async def main():
    st.set_page_config(
        page_title="Web Content Crawler",
        page_icon="🕷️",
        layout="wide"
    )
    
    st.title("🕷️ Web Content Crawler")
    st.markdown("Extract and analyze web content selectively")
    
    # Initialize crawler
    if 'crawler' not in st.session_state:
        st.session_state.crawler = WebCrawler()
    
    # URL Input
    url = st.text_input("Enter URL to crawl:", placeholder="https://example.com")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        crawl_method = st.selectbox(
            "Crawling Method:",
            ["Auto (Try both)", "Requests + BeautifulSoup", "Playwright (JS support)"],
            index=2
        )
    
    with col2:
        wait_time = st.slider("Wait time for JS content (seconds):", 1, 10, 3)
    
    if st.button("🔍 Check & Crawl Website", type="primary"):
        
        if url:
            if 'extracted_content' in st.session_state:
                del st.session_state.extracted_content
                
            crawler = st.session_state.crawler
            print(crawler)
            # Check URL availability
            with st.spinner("Checking URL availability..."):
                url_status = await crawler.check_url_availability(url)
            
            if url_status["available"]:
                st.success(f"✅ URL is accessible (Status: {url_status['status_code']})")
                st.info(f"Content Type: {url_status['content_type']}")
                
                # Crawl the website
                with st.spinner("Crawling website..."):
                    success = False
                    
                    if crawl_method == "Requests + BeautifulSoup":
                        success = await crawler.crawl_with_requests(url)
                    elif crawl_method == "Playwright (JS support)":
                        success = await crawler.crawl_with_playwright(url, wait_time)
                    else:  # Auto
                        success = await crawler.crawl_with_requests(url)
                        if not success:
                            st.info("Requests failed, trying Playwright...")
                            success = await crawler.crawl_with_playwright(url, wait_time)
                
                if success:
                    st.success("🎉 Website crawled successfully!")
                    st.session_state.crawl_success = True
                else:
                    st.error("❌ Failed to crawl the website")
                    st.session_state.crawl_success = False
            else:
                st.error(f"❌ URL is not accessible: {url_status.get('error')}")
                st.session_state.crawl_success = False
        else:
            st.warning("Please enter a URL")
    
    # Content Selection and Display
    if hasattr(st.session_state, 'crawl_success') and st.session_state.crawl_success:
        st.markdown("---")
        st.subheader("📋 Select Content to Display")
        
        mycrawler = st.session_state.crawler

        # Initialize cache for extracted content
        if 'extracted_content' not in st.session_state:
            st.session_state.extracted_content = {}

        # Content selection
        content_options = st.multiselect(
            "Choose what to extract and display:",
            ["Page Content", "Spell Check", "Images", "Links", "Tables", "URL Info"],
            default=["Page Content"]
        )
        
        for option in content_options:
            # st.markdown(f"### {option}")
            
            # Only process if not already extracted (or force re-extract if needed)
            if option == "Page Content":
                if "Page Content" not in st.session_state.extracted_content:
                    with st.spinner("Extracting page content..."):
                        content = await mycrawler.extract_page_content()
                    st.session_state.extracted_content["Page Content"] = content
                else:
                    content = st.session_state.extracted_content["Page Content"]

                st.markdown("### Page Content")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.text_area("Main Content", content.get("main_content", ""), height=300)
                with col2:
                    st.metric("Word Count", content.get("word_count", 0))
                    st.write("**Title:**", content.get("title", ""))
                    st.write("**Meta Description:**", content.get("meta_description", ""))
                    if content.get("headings"):
                        st.write("**Headings:**")
                        for heading in content["headings"][:10]:
                            st.write(f"{heading['level']}: {heading['text']}")
            
            elif option == "Images":
                if "Images" not in st.session_state.extracted_content:
                    with st.spinner("Extracting images..."):
                        images = await mycrawler.extract_images()
                    st.session_state.extracted_content["Images"] = images
                else:
                    images = st.session_state.extracted_content["Images"]

                st.markdown("### Images")
                st.write(f"Found {len(images)} images")
                if images:
                    df_images = pd.DataFrame(images)
                    st.dataframe(df_images, use_container_width=True)
                    for i, img in enumerate(images[:5]):
                        try:
                            st.image(img['src'], caption=img['alt'], width=300)
                        except Exception:
                            st.write(f"Could not display image: {img['src']}")

            elif option == "Spell Check":
                import io
                # import streamlit as st
                if "Spell Check" not in st.session_state.extracted_content:
                    with st.spinner("Checking Incorrect Text..."):
                        # Optional: cleanup only once before spell check
                        if mycrawler:
                            await mycrawler.cleanup()
                        table = await mycrawler.highlight_incorrect_text()
                    st.session_state.extracted_content["Spell Check"] = table
                else:
                    table = st.session_state.extracted_content["Spell Check"]
                table = highlight_both_columns_differences(table)
                # print(table)
                st.markdown("### Spelling Suggestion Table")
                st.dataframe(table, use_container_width=True)

                # Add download button for CSV (let user choose where to save)
                csv_buffer = io.StringIO()
                table.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
                st.download_button(
                    label="Download Spell Check Results",
                    data=csv_buffer.getvalue(),
                    file_name="spell_check_results.csv",
                    mime="text/csv"
                )
            elif option == "Links":
                if "Links" not in st.session_state.extracted_content:
                    with st.spinner("Extracting links..."):
                        links = await mycrawler.extract_links()
                    st.session_state.extracted_content["Links"] = links
                else:
                    links = st.session_state.extracted_content["Links"]

                st.markdown("### Links")
                st.write(f"Found {len(links)} links")
                if links:
                    df_links = pd.DataFrame(links)
                    st.dataframe(df_links, use_container_width=True)
            
            elif option == "Tables":
                if "Tables" not in st.session_state.extracted_content:
                    with st.spinner("Extracting tables..."):
                        tables = await mycrawler.extract_tables()
                    st.session_state.extracted_content["Tables"] = tables
                else:
                    tables = st.session_state.extracted_content["Tables"]

                st.markdown("### Tables")
                st.write(f"Found {len(tables)} tables")
                for i, table in enumerate(tables):
                    st.write(f"**Table {i+1}:**")
                    st.dataframe(table, use_container_width=True)

            elif option == "URL Info":
                # This is cheap, no need to cache
                st.markdown("### URL Info")
                st.json({
                    "crawled_url": mycrawler.url,
                    "domain": urlparse(mycrawler.url).netloc,
                    "scheme": urlparse(mycrawler.url).scheme,
                    "path": urlparse(mycrawler.url).path
                })

def test(url: str):
    from bs4 import BeautifulSoup
    import time
    
    crawler = WebCrawler()
    success = crawler.crawl_with_playwright(url, 3)
    # print(success)

if __name__ == "__main__":
    asyncio.run(main())

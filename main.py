import streamlit as st
from backend.webcrawler import WebCrawler
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
            crawler = st.session_state.crawler
            
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
        
        crawler = st.session_state.crawler
        
        # Content selection
        content_options = st.multiselect(
            "Choose what to extract and display:",
            ["Page Content", "Check IMG", "Images", "Links", "Tables", "URL Info"],
            default=["Page Content"]
        )
        
        for option in content_options:
            st.markdown(f"### {option}")
            
            if option == "Page Content":
                with st.spinner("Extracting page content..."):
                    content = await crawler.extract_page_content()
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.text_area("Main Content", content.get("main_content", ""), height=300)
                
                with col2:
                    st.metric("Word Count", content.get("word_count", 0))
                    st.write("**Title:**", content.get("title", ""))
                    st.write("**Meta Description:**", content.get("meta_description", ""))
                    
                    if content.get("headings"):
                        st.write("**Headings:**")
                        for heading in content["headings"][:10]:  # Show first 10
                            st.write(f"{heading['level']}: {heading['text']}")
            
            elif option == "Images":
                images = await crawler.extract_images()
                st.write(f"Found {len(images)} images")
                
                if images:
                    df_images = pd.DataFrame(images)
                    st.dataframe(df_images, use_container_width=True)
                    
                    # Show first few images
                    for i, img in enumerate(images[:5]):
                        try:
                            st.image(img['src'], caption=img['alt'], width=300)
                        except:
                            st.write(f"Could not display image: {img['src']}")

            elif option == "Check IMG":
                st.write("Image Analysis")
                display_images_from_folder("./images")
                await crawler.screenshots()

                # try:
                #     st.session_state.crawler.cleanup()
                # except:
                #     pass


            elif option == "Links":
                links = await crawler.extract_links()
                st.write(f"Found {len(links)} links")
                
                if links:
                    df_links = pd.DataFrame(links)
                    st.dataframe(df_links, use_container_width=True)
            
            elif option == "Tables":
                tables = await crawler.extract_tables()
                st.write(f"Found {len(tables)} tables")
                
                for i, table in enumerate(tables):
                    st.write(f"**Table {i+1}:**")
                    st.dataframe(table, use_container_width=True)
            
            elif option == "URL Info":
                st.json({
                    "crawled_url": crawler.url,
                    "domain": urlparse(crawler.url).netloc,
                    "scheme": urlparse(crawler.url).scheme,
                    "path": urlparse(crawler.url).path
                })
    
    # # Cleanup on app close
    # try:
    #     st.session_state.crawler.cleanup()
    # except:
    #     pass

def test(url: str):
    from bs4 import BeautifulSoup
    import time
    
    crawler = WebCrawler()
    success = crawler.crawl_with_playwright(url, 3)
    # print(success)

if __name__ == "__main__":
    asyncio.run(main())

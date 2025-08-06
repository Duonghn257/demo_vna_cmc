import asyncio
import platform

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import pandas as pd
from typing import Dict, List
import time
from urllib.parse import urlparse

# Import your WebCrawler class
from backend.webcrawler import WebCrawler  # Adjust import path as needed

st.set_page_config(
    page_title="Web Crawler Dashboard",
    page_icon="🕷️",
    layout="wide"
)

def is_valid_url(url: str) -> bool:
    """Validate if the provided URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

async def crawl_website(url: str, js_wait_time: int, crawler: WebCrawler):
    """Initialize crawler and navigate to URL using the WebCrawler's method"""
    try:
        # Use the WebCrawler's own crawl method
        success = await crawler.crawl_with_playwright(url, js_wait_time)
        return success
    except Exception as e:
        st.error(f"Failed to load website: {str(e)}")
        return False

def display_page_content(content: Dict[str, str]):
    """Display page content information"""
    st.subheader("📄 Page Content")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Word Count", content.get('word_count', 0))
        
        if content.get('title'):
            st.write("**Title:**")
            st.write(content['title'])
        
        if content.get('meta_description'):
            st.write("**Meta Description:**")
            st.write(content['meta_description'])
        
        if content.get('meta_keywords'):
            st.write("**Meta Keywords:**")
            st.write(content['meta_keywords'])
    
    with col2:
        if content.get('headings'):
            st.write("**Headings:**")
            headings_df = pd.DataFrame(content['headings'])
            st.dataframe(headings_df, use_container_width=True)
    
    if content.get('main_content'):
        st.write("**Main Content:**")
        with st.expander("View Full Content", expanded=False):
            st.text_area("Content", content['main_content'], height=300, disabled=True)
    
    if content.get('paragraphs'):
        st.write("**Paragraphs:**")
        with st.expander(f"View All {len(content['paragraphs'])} Paragraphs", expanded=False):
            for i, paragraph in enumerate(content['paragraphs'], 1):
                st.write(f"**Paragraph {i}:**")
                st.write(paragraph)
                st.divider()

def display_spell_check(spell_check_df: pd.DataFrame):
    """Display spell check results"""
    st.subheader("✏️ Spell Check")
    
    if spell_check_df.empty:
        st.success("No spelling errors found!")
    else:
        st.warning(f"Found {len(spell_check_df)} potential spelling issues")
        st.dataframe(spell_check_df, use_container_width=True)
        
        # Download option
        csv = spell_check_df.to_csv(index=False)
        st.download_button(
            "Download Spell Check Results",
            csv,
            "spell_check_results.csv",
            "text/csv"
        )

def display_images(images: List[Dict[str, str]]):
    """Display extracted images"""
    st.subheader("🖼️ Images")
    
    if not images:
        st.info("No images found on this page.")
        return
    
    st.write(f"Found {len(images)} images")
    
    # Create DataFrame for better display
    images_df = pd.DataFrame(images)
    st.dataframe(images_df, use_container_width=True)
    
    # Show image previews if src available
    if 'src' in images_df.columns:
        st.write("**Image Preview (first 5):**")
        cols = st.columns(min(5, len(images)))
        for i, (col, img) in enumerate(zip(cols, images[:5])):
            with col:
                if img.get('src'):
                    try:
                        st.image(img['src'], caption=f"Image {i+1}", use_container_width=True)
                    except:
                        st.write(f"Image {i+1}: {img.get('alt', 'No alt text')}")

def display_links(links: List[Dict[str, str]]):
    """Display extracted links"""
    st.subheader("🔗 Links")
    
    if not links:
        st.info("No links found on this page.")
        return
    
    st.write(f"Found {len(links)} links")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        show_external = st.checkbox("Show External Links Only", value=False)
    with col2:
        show_internal = st.checkbox("Show Internal Links Only", value=False)
    
    # Filter links based on selection
    filtered_links = links
    if show_external and not show_internal:
        filtered_links = [link for link in links if link.get('type') == 'external']
    elif show_internal and not show_external:
        filtered_links = [link for link in links if link.get('type') == 'internal']
    
    if filtered_links:
        links_df = pd.DataFrame(filtered_links)
        st.dataframe(links_df, use_container_width=True)
        
        # Download option
        csv = links_df.to_csv(index=False)
        st.download_button(
            "Download Links",
            csv,
            "extracted_links.csv",
            "text/csv"
        )
    else:
        st.info("No links match the current filter.")

def display_tables(tables: List[pd.DataFrame]):
    """Display extracted tables"""
    st.subheader("📊 Tables")
    
    if not tables:
        st.info("No tables found on this page.")
        return
    
    st.write(f"Found {len(tables)} tables")
    
    for i, table in enumerate(tables, 1):
        st.write(f"**Table {i}:**")
        st.dataframe(table, use_container_width=True)
        
        # Download option for each table
        csv = table.to_csv(index=False)
        st.download_button(
            f"Download Table {i}",
            csv,
            f"table_{i}.csv",
            "text/csv",
            key=f"table_{i}_download"
        )
        
        if i < len(tables):
            st.divider()

def display_url_info(url: str):
    """Display URL information"""
    st.subheader("🌐 URL Info")
    
    parsed_url = urlparse(url)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**URL Components:**")
        st.write(f"**Scheme:** {parsed_url.scheme}")
        st.write(f"**Domain:** {parsed_url.netloc}")
        st.write(f"**Path:** {parsed_url.path}")
        
    with col2:
        st.write("**Additional Info:**")
        st.write(f"**Query:** {parsed_url.query if parsed_url.query else 'None'}")
        st.write(f"**Fragment:** {parsed_url.fragment if parsed_url.fragment else 'None'}")
        st.write(f"**Port:** {parsed_url.port if parsed_url.port else 'Default'}")

def main():
    st.title("🕷️ Web Crawler Dashboard")
    st.write("Extract and analyze content from any website")
    
    # Initialize session state
    if 'crawled_data' not in st.session_state:
        st.session_state.crawled_data = {}
    if 'crawler' not in st.session_state:
        st.session_state.crawler = None
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Crawler Settings")
        
        # URL input
        url = st.text_input(
            "Enter URL to crawl:",
            placeholder="https://example.com",
            help="Enter a valid URL starting with http:// or https://"
        )
        
        # JS loading wait time
        js_wait_time = st.slider(
            "JavaScript Loading Wait Time (seconds)",
            min_value=0,
            max_value=10,
            value=2,
            help="Time to wait for JavaScript content to load"
        )
        
        # Content selection
        content_options = [
            "Page Content",
            "Spell Check", 
            "Images",
            "Links",
            "Tables",
            "URL Info"
        ]
        
        selected_options = st.multiselect(
            "Select content to extract:",
            options=content_options,
            default=["Page Content", "URL Info"],
            help="Choose what information to extract from the website"
        )
        
        # Crawl button
        crawl_button = st.button("🚀 Start Crawling", type="primary", use_container_width=True)
    
    # Main content area
    if crawl_button:
        if not url:
            st.error("Please enter a URL to crawl.")
        elif not is_valid_url(url):
            st.error("Please enter a valid URL (must include http:// or https://).")
        elif not selected_options:
            st.error("Please select at least one content type to extract.")
        else:
            # Initialize crawler
            crawler = WebCrawler()
            
            with st.spinner("Initializing crawler..."):
                success = asyncio.run(crawl_website(url, js_wait_time, crawler))
            
            if success:
                st.success("Successfully connected to website!")
                
                # Extract selected content
                data = {}
                
                with st.spinner("Extracting content..."):
                    try:
                        for option in selected_options:
                            if option == "Page Content":
                                data['page_content'] = asyncio.run(crawler.extract_page_content())
                            elif option == "Spell Check":
                                data['spell_check'] = asyncio.run(crawler.highlight_incorrect_text())
                            elif option == "Images":
                                data['images'] = asyncio.run(crawler.extract_images())
                            elif option == "Links":
                                data['links'] = asyncio.run(crawler.extract_links())
                            elif option == "Tables":
                                data['tables'] = asyncio.run(crawler.extract_tables())
                            elif option == "URL Info":
                                data['url_info'] = url
                        
                        # Store in session state
                        st.session_state.crawled_data = data
                        st.session_state.crawler = crawler
                        
                    except Exception as e:
                        st.error(f"Error during content extraction: {str(e)}")
                    finally:
                        # Cleanup
                        asyncio.run(crawler.cleanup())
                
                st.success("Content extraction completed!")
    
    # Display results
    if st.session_state.crawled_data:
        st.divider()
        st.header("📊 Extraction Results")
        
        data = st.session_state.crawled_data
        
        # Create tabs for different content types
        tabs = []
        tab_content = []
        
        if 'page_content' in data:
            tabs.append("Page Content")
            tab_content.append(('page_content', data['page_content']))
            
        if 'spell_check' in data:
            tabs.append("Spell Check")
            tab_content.append(('spell_check', data['spell_check']))
            
        if 'images' in data:
            tabs.append("Images")
            tab_content.append(('images', data['images']))
            
        if 'links' in data:
            tabs.append("Links")
            tab_content.append(('links', data['links']))
            
        if 'tables' in data:
            tabs.append("Tables")
            tab_content.append(('tables', data['tables']))
            
        if 'url_info' in data:
            tabs.append("URL Info")
            tab_content.append(('url_info', data['url_info']))
        
        if tabs:
            tab_objects = st.tabs(tabs)
            
            for tab, (content_type, content_data) in zip(tab_objects, tab_content):
                with tab:
                    if content_type == 'page_content':
                        display_page_content(content_data)
                    elif content_type == 'spell_check':
                        display_spell_check(content_data)
                    elif content_type == 'images':
                        display_images(content_data)
                    elif content_type == 'links':
                        display_links(content_data)
                    elif content_type == 'tables':
                        display_tables(content_data)
                    elif content_type == 'url_info':
                        display_url_info(content_data)

if __name__ == "__main__":
    main()
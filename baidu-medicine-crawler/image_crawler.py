import os
import time
import logging
import asyncio
import aiohttp
import aiofiles
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote
from lxml import etree
import json


logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("log/图片爬取.log", encoding='utf-8')
logger.addHandler(handler)


async def download_single_image(session, img_url, save_path, headers):
    try:
        async with session.get(img_url, headers=headers) as response:
            if response.status == 200:
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    content = await response.read()
                    async with aiofiles.open(save_path, 'wb') as f:
                        await f.write(content)
                    logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 源地址:{img_url}, 目标地址:{save_path}')
                    return True
    except Exception as e:
        print(f"Error downloading {img_url}: {e}")
    return False


async def download_images(query, num_images=200, save_folder=None):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, service和driver已准备就绪')

    # 生成搜索关键词变体
    search_queries = [query+"药品包装"]

    all_img_urls = set()  # 使用集合去重
    for search_query in search_queries:
        encoded_query = quote(search_query)
        pn = 0
        search_url = f"https://image.baidu.com/search/index?tn=baiduimage&word={encoded_query}"
        driver.get(search_url)
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 网址已响应:{search_url}')

        # 我改成了XPATH解析
        img_elements = []
        max_try = 150
        current_try = 0
        while len(all_img_urls) <= num_images * 4 and current_try < max_try:
            logger.info(f"found image urls: {len(img_elements)}")
            content = etree.HTML(driver.page_source)
            if content is None:
                driver.quit()
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.get(search_url)
                for i in range(current_try):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            else:
                current_try += 1
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            if content is None:
                break
            img_elements = content.xpath(f'//li[@class="imgitem"][position() <= {num_images * 4}]')
            img_elements = [(img_element.get("data-objurl"), img_element.get("data-title")) for img_element in img_elements]

            if not img_elements:
                driver.quit()
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.get(search_url)
                for i in range(current_try):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            else:
                for (img_url, img_title) in img_elements:
                    if query in img_title:
                        all_img_urls.add(img_url)
                current_try += 1
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://image.baidu.com/"
    }

    save_folder = f'data/JPEGImages/{query}'
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, img_url in enumerate(list(all_img_urls)):
            save_path = os.path.join(save_folder, f"{i + 1}.jpg")
            task = download_single_image(session, img_url, save_path, headers)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        downloaded = sum(1 for r in results if r)

    driver.quit()
    logger.info(f"Successfully downloaded {downloaded} images of {query}.")


async def main():
    with open('data/常见非处方药药品2.txt', 'r', encoding='utf-8') as file:
        medicine_list = file.readlines()
    medicine_list = [item.strip() for item in medicine_list]
    num_images = 100
    for i, medicine in enumerate(medicine_list):
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 正在下载药品:{medicine} 相关的图片')
        await download_images(medicine, num_images=num_images)

if __name__ == "__main__":
    asyncio.run(main())

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
import random
import requests
import re

logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("log/spider.log", encoding='utf-8')
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


async def spyder(query):
    title, source, search_url = query
    if '?' in search_url:
        search_url = search_url.split('?')[0]

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={user_agent}')
    chrome_options.add_argument( "Referer='https://baike.baidu.com/'")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(search_url)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    content = etree.HTML(driver.page_source)
    content = content.xpath('//div[contains(@class,"contentTab") and contains(@class, "curTab")]')
    max_try = 3
    current_try = 0
    while not content and current_try < max_try:
        time.sleep(10)
        driver.quit()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(search_url)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 重新访问网址:{search_url}')
        content = etree.HTML(driver.page_source)
        content = content.xpath('//div[contains(@class,"contentTab") and contains(@class, "curTab")]')
        current_try += 1

    if current_try == max_try and not content:
        time.sleep(1200)
        current_try = 0
        while not content and current_try < max_try:
            time.sleep(10)
            driver.quit()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get(search_url)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 重新访问网址:{search_url}')
            content = etree.HTML(driver.page_source)
            content = content.xpath('//div[contains(@class,"contentTab") and contains(@class, "curTab")]')
            current_try += 1

    content = content[0]
    title = content.xpath('//h1[contains(@class, "lemmaTitle") and contains(@class, "J-lemma-title")]//text()')
    title = ''.join(title)
    result = {}

    try:
        summary = content.xpath('//div[contains(@class, "lemmaSummary_") and contains(@class, "J-summary")]')[0]
        summary = summary.xpath('//span[contains(@class, "text_")]//text()')
        summary = [item for item in summary if not item.startswith('[') and not item.endswith(']')]
        summary = ''.join(summary)
        result['整体描述'] = summary
    except:
        pass

    try:
        basic_info_table = content.xpath('//div[contains(@class, "basicInfo") and contains(@class, "J-basic-info")]')[0]
        basic_info_table = basic_info_table.xpath('//div[contains(@class, "itemWrapper_")]//text()')
        basic_info_table = [item for item in basic_info_table if not item.startswith('[') and not item.endswith(']')]
        basic_info_table = [item+':' if idx % 2 == 0 else item+'\n' for idx, item in enumerate(basic_info_table)]
        basic_info_table = ''.join(basic_info_table)
        result['基本信息表'] = basic_info_table
    except:
        pass

    try:
        details = content.xpath('//div[@class="J-lemma-content"]')[0]
        details_text = []
        for element in details.xpath('./*'):
            class_name = element.get("class")
            if 'paraTitle_' in class_name and 'level-1' in class_name: 
                text = element.xpath('.//h2')
                text = text[0].xpath('.//text()')
                text = [item for item in text if not item.startswith('[') and not item.endswith(']')]
                text = ''.join(text)
                details_text.append(text)
                details_text.append('')
            else:
                text = element.xpath('.//text()')
                text = [item for item in text if not item.startswith('[') and not item.endswith(']')]
                text = ''.join(text)
                try:
                    details_text[-1] += text
                except:
                    continue
        assert len(details_text) % 2 == 0
        for idx in range(len(details_text)//2):
            result[details_text[2 * idx]] = str(details_text[2 * idx + 1])
    except:
        pass

    images = []
    try:
        images1 = content.xpath('//a[contains(@class, "imageLink_")]//img/@src')
        images1 = [img.split('?')[0] for img in images1]

        images2 = content.xpath('//div[contains(@class, "abstractAlbum_")]/img/@src')
        images2 = [img.split('?')[0] for img in images2]
        images = images1 + images2
    except:
        pass

    driver.quit()

    base_path = f'data/dataset/{title}'
    if os.path.exists(base_path):
        parent_dir = os.path.dirname(base_path)
        dir_name = os.path.basename(base_path)
        existing_dirs = [d for d in os.listdir(parent_dir)
                         if os.path.isdir(os.path.join(parent_dir, d)) and d.startswith(dir_name)]
        num = len(existing_dirs)
        new_path = f'{base_path}-{num}'
    else:
        new_path = base_path
    os.makedirs(new_path, exist_ok=True)
    with open(f'{new_path}/descriptions.json', 'w', encoding='utf-8') as file:
        json.dump(result, file, indent=4, ensure_ascii=False)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://bkimg.cdn.bcebos.com/"
    }

    save_folder = new_path
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, img_url in enumerate(list(images)):
            save_path = os.path.join(save_folder, f"{i + 1}.jpg")
            task = download_single_image(session, img_url, save_path, headers)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        downloaded = sum(1 for r in results if r)
    logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 已完成百科内容爬取: {query}')


async def main():
    with open('data/artworks.json', 'r') as file:
        data = json.load(file)
    for i, dataitem in enumerate(data):
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 在百度百科上访问: {dataitem[-1]}')
        await spyder(dataitem)
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 进度: {i + 1}/{len(data)}')


if __name__ == "__main__":
    asyncio.run(main())

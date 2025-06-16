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
handler = logging.FileHandler("log/百度百科文本爬虫记录.log", encoding='utf-8')
logger.addHandler(handler)


async def spyder(query):
    json_file_path = 'data/100种非处方药.json'
    if os.path.exists(json_file_path) and os.path.getsize(json_file_path) > 0:
        with open(json_file_path, "r", encoding="utf-8") as file:
            existing_data = json.load(file)
    else:
        existing_data = []

    if query["药品名称"] in [item["药品名称"] for item in existing_data]:
        return

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    query = query["药品名称"]
    encoded_query = quote(query)
    search_url = f"https://baike.baidu.com/item/{encoded_query}?fromModule=lemma_search-box"
    driver.get(search_url)

    content = etree.HTML(driver.page_source)
    content = content.xpath('//div[@class="contentTab_AAKsS curTab_Vw3zg"]')
    max_try = 15
    current_try = 0
    while not content and current_try < max_try:
        time.sleep(30)
        driver.quit()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(search_url)
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 重新访问网址:{search_url}')
        content = etree.HTML(driver.page_source)
        content = content.xpath('//div[@class="contentTab_AAKsS curTab_Vw3zg"]')
        current_try += 1

    if not content:
        existing_data.append({'药品名称': query})
        with open(json_file_path, "w", encoding="utf-8") as file:
            json.dump(existing_data, file, indent=4, ensure_ascii=False)
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 百科搜索不成功: {query}')
        return
    content = content[0]

    result = {'药品名称': query}

    try:
        summary = content.xpath('//div[@class="lemmaSummary_s9vD3 J-summary"]')[0]
        summary = summary.xpath('//span[@class="text_tJaKK"]//text()')
        summary = [item for item in summary if not item.startswith('[') and not item.endswith(']')]
        summary = ''.join(summary)
        result['整体描述'] = summary
    except:
        pass

    try:
        basic_info_table = content.xpath('//div[@class="basicInfo_Gvg0x J-basic-info"]')[0]
        basic_info_table = basic_info_table.xpath('//div[@class="itemWrapper_Glzus"]//text()')
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
            if class_name == 'paraTitle_c7Isv level-1_gngtl':
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

    driver.quit()

    # 保存成json
    existing_data.append(result)
    with open(json_file_path, "w", encoding="utf-8") as file:
        json.dump(existing_data, file, indent=4, ensure_ascii=False)
    logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 已完成百科内容爬取: {query}')
    print(f'已完成百科内容爬取: {query}, 已完成数量：{len(existing_data)}')


async def main():
    folders = os.listdir('data/JPEGImages')
    medicine_data = [{"药品名称": folder} for folder in folders]
    for i, medicine in enumerate(medicine_data):
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 正在下载药品:{medicine} 相关的百科')
        await spyder(medicine)

if __name__ == "__main__":
    asyncio.run(main())

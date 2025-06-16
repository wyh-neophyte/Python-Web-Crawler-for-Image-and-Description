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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from urllib.parse import quote
from lxml import etree
import json

logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("log/爬虫记录.log", encoding='utf-8')
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


async def spyder():
    # chrome浏览器模拟
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # 存储上一页内容的变量，用于检测翻页后内容是否已经刷新
    last_page_content = {}
    for item_index in range(0, 10):
        last_page_content[item_index] = ''

    # 加载之前的数据
    all_data = []
    try:
        with open('dish.json', 'r') as file:
            all_data = json.load(file)
    except:
        pass

    # 遍历每一页，每一页10个
    for page in range(1, 2219):
        for item_index in range(0, 10):
            if len(all_data):
                if page < all_data[-1]['页码'] or (page == all_data[-1]['页码'] and item_index <= all_data[-1]['本页索引']):
                    continue

            search_url = f"https://nutridata.cn/database/list?id=2"
            driver.get(search_url)

            # 翻页
            current_page = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".number.active")))
            while int(current_page[0].text) < page:
                next_page_button = driver.find_element(By.CLASS_NAME, "btn-next")
                driver.execute_script("arguments[0].click();", next_page_button)
                current_page = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".number.active")))
            print('当前页码', current_page[0].text, '需要访问页码', page, '目标索引', item_index)

            # 检测翻页后是否页面更新
            # WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "card-titile")))
            # print([item.text for item in driver.find_elements(By.CLASS_NAME, "card-titile")])

            WebDriverWait(driver, 10).until(lambda d: d.find_elements(By.CLASS_NAME, "card-main")[item_index].find_element(By.TAG_NAME, "span").text != last_page_content[item_index])
            card_items = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "card-main")))
            # 更新上一页内容变量
            last_page_content[item_index] = driver.find_elements(By.CLASS_NAME, "card-main")[item_index].find_element(By.TAG_NAME, "span").text
            print('更新last_page_content:', last_page_content)

            # 点击跳转
            item = card_items[item_index]
            driver.execute_script("arguments[0].click();", item)

            # 可食用部分的质量
            max_try = 15
            current_try = 1
            title_tip = ''
            while not title_tip and current_try <= max_try:
                time.sleep(2)
                title_tip = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "title-tip")))
                title_tip = ','.join([item.text for item in title_tip])
                current_try += 1

            # 菜品名称
            current_try = 1
            info_title = ''
            while not info_title and current_try <= max_try:
                time.sleep(2)
                info_title = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".info-title")))[0].text
                current_try += 1

            # 图片网址
            current_try = 1
            img_url = ''
            while not img_url and current_try <= max_try:
                time.sleep(2)
                img_url = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".el-link.el-link--default")))[0].get_attribute('href')
                current_try += 1
            if img_url:
                async with aiohttp.ClientSession() as session:
                    tasks = []
                    save_path = f'images/{page}-{item_index}-{info_title}.jpg'
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Referer": "https://image.baidu.com/"
                    }
                    task = download_single_image(session, img_url, save_path, headers)
                    tasks.append(task)
                    results = await asyncio.gather(*tasks)

            # 标签tag
            current_try = 1
            tag_item = ''
            while not tag_item and current_try <= max_try:
                time.sleep(2)
                tag_item = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "tag-item")))
                tag_item = ','.join([item.text for item in tag_item])
                current_try += 1

            # 营养成分
            current_try = 1
            element_item = ''
            while not element_item and current_try <= max_try:
                time.sleep(2)
                element_item = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".element-item.el-col")))
                element_item = ','.join([item.text for item in element_item])
                current_try += 1

            # 做法
            current_try = 1
            ingredients = ''
            while not ingredients and current_try <= max_try:
                time.sleep(2)
                ingredients = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".ingredients")))
                ingredients = ','.join([item.text for item in ingredients])
                current_try += 1

            current_try = 1
            practice_steps = ''
            while not practice_steps and current_try <= max_try:
                time.sleep(2)
                practice_steps = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".practice-step")))
                practice_steps = ''.join([item.text for item in practice_steps])
                current_try += 1

            data = {'页码': page, '本页索引': item_index,
                    '名称': info_title,
                    '图片网址': img_url,
                    '基本营养': title_tip + '。' + tag_item + '。' + element_item,
                    '菜肴做法': ingredients + '。' + practice_steps}
            all_data.append(data)
            with open('dish.json', 'w', encoding='utf-8') as file:
                json.dump(all_data, file, indent=4, ensure_ascii=False)


async def main():
    await spyder()

if __name__ == "__main__":
    asyncio.run(main())

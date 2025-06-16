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
from lxml import etree, html
import json
import re


logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("log/星图爬虫.log", encoding='utf-8')
logger.addHandler(handler)


async def spyder(query, html_file):
    json_file_path = 'data/artist-xingtu.json'
    if os.path.exists(json_file_path) and os.path.getsize(json_file_path) > 0:
        with open(json_file_path, "r", encoding="utf-8") as file:
            existing_data = json.load(file)
    else:
        existing_data = []

    if query in [item["人名"] for item in existing_data]:
        return

    # 读取 HTML 文件（自动修复标签等问题）
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 使用 lxml.html 解析
    content = html.fromstring(html_content)
    print(html.tostring(content, encoding="unicode", pretty_print=True))
    content = content.xpath('.//div[contains(@class, "itemWrap")]')

    if not content:
        existing_data.append({'人名': query})
        with open(json_file_path, "w", encoding="utf-8") as file:
            json.dump(existing_data, file, indent=4, ensure_ascii=False)
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 百科搜索不成功: {query}')
        return

    result = {'人名': query, '作品': {}}
    for content_item in content:
        title = content_item.xpath('.//div[@class="item-title_daf8d"]//text()')
        title = ''.join(title)
        if title.endswith('图') or title.endswith('图轴') or title.endswith('画像') or title.endswith('画') or title.endswith('帖') or title.endswith('碑') or '帛书' in title:
            url = content_item.xpath('.//a[@class="item-summary_NqIeW"]/@href')[0]
            result['作品'][title] = 'https://baike.baidu.com' + url

    # 保存成json
    existing_data.append(result)
    with open(json_file_path, "w", encoding="utf-8") as file:
        json.dump(existing_data, file, indent=4, ensure_ascii=False)
    logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 已完成百科内容爬取: {query}')
    print(f'已完成星图内容爬取: {query}, 已完成数量：{len(existing_data)}')


async def main():
    namelist = ['故宫博物馆', '上海博物馆', '中国国家博物馆', '南京博物馆', '苏州博物馆',
                '广东博物馆', '河南博物馆', '浙江博物馆', '湖南博物馆', '陕西历史博物馆']
    files = ['data/故宫博物馆馆藏文物.html',
             'data/上海博物馆馆藏文物.html',
             'data/中国国家博物馆馆藏文物.html',
             'data/南京博物馆馆藏文物.html',
             'data/苏州博物馆馆藏文物.html',
             'data/广东博物馆馆藏文物.html',
             'data/河南博物馆馆藏文物.html',
             'data/浙江博物馆馆藏文物.html',
             'data/湖南博物馆馆藏文物.html',
             'data/陕西历史博物馆馆藏文物.html']

    for i, (name, file) in enumerate(zip(namelist, files)):
        logger.info(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}, 在百度百科上搜索字画家：{name}')
        await spyder(name, file)

if __name__ == "__main__":
    asyncio.run(main())

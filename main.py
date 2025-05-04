import requests
from bs4 import BeautifulSoup
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import json
import re

# 全局headers，用于模拟浏览器请求
headers = {
    "authority": "exhentai.org",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "max-age=0",
    "referer": "https://exhentai.org/",
    "sec-ch-ua": "\"Not=A?Brand\";v=\"99\", \"Chromium\";v=\"118\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}

# API URL
API_URL = "https://api.e-hentai.org/api.php"

# 发送HTTP请求并获取页面内容的函数
def fetch_favorites(url, cookies):
    """
    使用指定的URL和cookie发送GET请求，获取HTML内容。

    参数:
        url (str): 要请求的URL
        cookies (dict): cookie字典

    返回:
        str: HTML内容，如果请求失败则返回None
    """
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None

# 解析HTML并提取链接的函数
def parse_html(html):
    """
    解析HTML内容，提取特定链接和下一页的URL。

    参数:
        html (str): 要解析的HTML内容

    返回:
        tuple: (提取的链接列表, 下一页URL或None)
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', class_='itg glte')
        if not table:
            print("未找到class='itg glte'的table元素")
            return [], None

        links = []
        for td in table.find_all('td', class_='gl1e'):
            a_tag = td.find('a')
            if a_tag and 'href' in a_tag.attrs:
                links.append(a_tag['href'])

        next_page = soup.find('a', id='unext')
        if next_page and 'href' in next_page.attrs:
            return links, next_page['href']
        return links, None
    except Exception as e:
        print(f"HTML解析失败: {e}")
        return [], None

# 请求和解析单个链接的函数
def request_and_parse(link, cookies, recorded_links, lock):
    """
    对单个链接发送请求，解析响应，检查是否需要记录。

    参数:
        link (str): 要请求的链接
        cookies (dict): cookie字典
        recorded_links (list): 记录需要记录的链接
        lock (threading.Lock): 保护recorded_links的锁

    返回:
        None: 直接将符合条件的链接记录到recorded_links中
    """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.get(link, headers=headers, cookies=cookies, timeout=10)
            if response.status_code == 404:
                with lock:
                    recorded_links.append(link)
                return
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.find('title')
            if title and title.string == "Gallery Not Available - ExHentai.org":
                with lock:
                    recorded_links.append(link)
                return
            p = soup.find('p', string="You will be redirected to the front page momentarily.")
            if p:
                with lock:
                    recorded_links.append(link)
                return
            return
        except requests.RequestException as e:
            print(f"请求 {link} 失败: {e}，尝试重试 ({attempt + 1}/{max_retries})")
            time.sleep(1)
    print(f"请求 {link} 失败，已重试 {max_retries} 次，放弃")

# 提取gallery_id和gallery_token
def extract_gid_token(link):
    """
    从链接中提取gallery_id和gallery_token。

    参数:
        link (str): 链接

    返回:
        tuple: (gallery_id, gallery_token)
    """
    match = re.search(r'https?://exhentai\.org/g/(\d+)/([a-f0-9]+)/', link)
    if match:
        return match.group(1), match.group(2)
    else:
        print(f"无法从链接 {link} 中提取gallery_id和gallery_token")
        return None, None

# 发送API请求
def fetch_api_data(gidlist):
    """
    发送API请求，获取gallery metadata，不添加headers。

    参数:
        gidlist (list): [gallery_id, gallery_token]的列表

    返回:
        dict: API响应，如果请求失败则返回None
    """
    payload = {
        "method": "gdata",
        "gidlist": gidlist,
        "namespace": 1
    }
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API请求失败: {e}，尝试重试 ({attempt + 1}/{max_retries})")
            time.sleep(1)
    print(f"API请求失败，已重试 {max_retries} 次，放弃")
    return None

# 处理API响应
def process_api_response(response, links, result_list, lock):
    """
    处理API响应，提取title_jpn和thumb，并保存到result_list中。

    参数:
        response (dict): API响应
        links (list): 原始链接列表
        result_list (list): 保存thumb、title_jpn和链接的列表
        lock (threading.Lock): 保护result_list的锁

    返回:
        None: 直接将thumb、title_jpn和链接保存到result_list中
    """
    try:
        if response and 'gmetadata' in response:
            for metadata in response['gmetadata']:
                title_jpn = metadata.get('title_jpn', '')
                thumb = metadata.get('thumb', '')
                gid = metadata.get('gid', '')
                token = metadata.get('token', '')
                link = next((l for l in links if extract_gid_token(l) == (str(gid), token)), None)
                if link and title_jpn and thumb:
                    with lock:
                        result_list.append({
                            "thumb": thumb,
                            "title_jpn": title_jpn,
                            "link": link
                        })
    except Exception as e:
        print(f"解析API响应失败: {e}")

# 主函数，控制整个抓取和多线程请求流程
def main():
    """
    主函数，执行抓取exhentai.org收藏夹页面和多线程请求的任务。
    """
    # 动态获取cookie_str
    while True:
        cookie_str = input("请输入您的cookie_str（不可为空，例如 'ipb_member_id=xxx; ipb_pass_hash=xxx'）: ").strip()
        if cookie_str:
            break
        print("cookie_str不可为空，请重新输入。")

    try:
        # 将cookie字符串转换为字典
        cookies = {cookie.split('=')[0]: cookie.split('=')[1] for cookie in cookie_str.split('; ')}
    except Exception as e:
        print(f"cookie解析失败: {e}")
        return

    # 动态获取batch_size
    while True:
        batch_size_input = input("请输入batch_size（每批次请求处理的链接数量，默认25）: ").strip()
        if not batch_size_input:
            batch_size = 25
            break
        try:
            batch_size = int(batch_size_input)
            if batch_size <= 0:
                raise ValueError
            break
        except ValueError:
            print("batch_size的值必须是正整数，请重新输入。")

    # 动态获取thread_count
    while True:
        thread_count_input = input("请输入thread_count（多线程数量，默认4）: ").strip()
        if not thread_count_input:
            thread_count = 4
            break
        try:
            thread_count = int(thread_count_input)
            if thread_count <= 0:
                raise ValueError
            break
        except ValueError:
            print("thread_count的值必须是正整数，请重新输入。")

    # 动态获取max_sequential_requests
    while True:
        max_sequential_requests_input = input("请输入max_sequential_requests（每处理*批次后就暂停，默认4）: ").strip()
        if not max_sequential_requests_input:
            max_sequential_requests = 4
            break
        try:
            max_sequential_requests = int(max_sequential_requests_input)
            if max_sequential_requests <= 0:
                raise ValueError
            break
        except ValueError:
            print("max_sequential_requests的值必须是正整数，请重新输入。")

    # 动态获取wait_time
    while True:
        wait_time_input = input("请输入wait_time（每*批次处理后暂停的秒数，默认5）: ").strip()
        if not wait_time_input:
            wait_time = 5
            break
        try:
            wait_time = int(wait_time_input)
            if wait_time < 0:
                raise ValueError
            break
        except ValueError:
            print("wait_time必须是非负整数，请重新输入。")

    # 初始URL
    url = "https://exhentai.org/favorites.php"
    all_links = []

    # 循环请求页面直到没有下一页
    while url:
        html = fetch_favorites(url, cookies)
        if not html:
            print("无法获取页面内容，程序终止")
            break

        links, next_url = parse_html(html)
        if links:
            all_links.extend(links)
            print(f"当前页面提取到 {len(links)} 个链接，总计 {len(all_links)} 个链接")
        else:
            print("未提取到链接")

        url = next_url
        if next_url:
            print(f"正在抓取下一页: {next_url}")
            time.sleep(0.1)
        else:
            print("已到达最后一页")

    # 多线程请求all_links中的链接，筛选recorded_links
    recorded_links = []
    lock = threading.Lock()

    for i in range(0, len(all_links), batch_size):
        batch = all_links[i:i + batch_size]
        print(f"正在处理批次 {i // batch_size + 1}，包含 {len(batch)} 个链接")

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            executor.map(lambda link: request_and_parse(link, cookies, recorded_links, lock), batch)

        if (i // batch_size + 1) % max_sequential_requests == 0:
            print(f"已处理 {max_sequential_requests} 个批次，暂停 {wait_time} 秒")
            time.sleep(wait_time)
        else:
            print(f"批次 {i // batch_size + 1} 处理完成，进入下一批次")

    if not recorded_links:
        print("没有符合条件的链接被记录，程序结束")
        while True:
            user_input = input("请输入 'exit' 以结束程序: ")
            if user_input.lower() == "exit":
                break
        return

    # 多线程处理recorded_links，调用API获取thumb和title_jpn
    result_list = []
    api_lock = threading.Lock()

    def process_api_batch(batch):
        """
        处理一个API批次，发送请求并解析响应。
        """
        gidlist = []
        for link in batch:
            gid, token = extract_gid_token(link)
            if gid and token:
                gidlist.append([int(gid), token])
        if not gidlist:
            return

        response = fetch_api_data(gidlist)
        if response:
            process_api_response(response, batch, result_list, api_lock)

    # 将recorded_links按batch_size分割并多线程处理
    batches = [recorded_links[i:i + batch_size] for i in range(0, len(recorded_links), batch_size)]
    batch_count = len(batches)

    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        for idx, batch in enumerate(batches):
            print(f"正在处理API批次 {idx + 1}/{batch_count}，包含 {len(batch)} 个链接")
            executor.submit(process_api_batch, batch)

            if (idx + 1) % max_sequential_requests == 0 and (idx + 1) < batch_count:
                print(f"已处理 {max_sequential_requests} 个API批次，暂停 {wait_time} 秒")
                time.sleep(wait_time)
            else:
                print(f"API批次 {idx + 1} 提交完成")

    time.sleep(1)

    # 将result_list写入md文件
    if result_list:
        try:
            with open("result.md", "w", encoding="utf-8") as f:
                f.write("# ExHentai 收藏夹处理结果\n\n")
                for index, item in enumerate(result_list, start=1):
                    f.write(f"## {index}. {item['title_jpn']}\n\n")
                    f.write(f"![thumb {index}]({item['thumb']})\n\n")
                    f.write(f"**链接:** {item['link']}\n\n")
            print("结果已保存到 result.md")
        except Exception as e:
            print(f"保存结果到文件失败: {e}")
    else:
        print("没有符合条件的链接被记录")

    # 提示用户输入"exit"以结束程序
    while True:
        user_input = input("请输入 'exit' 以结束程序: ")
        if user_input.lower() == "exit":
            break

# 程序入口
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"程序运行出错: {e}")
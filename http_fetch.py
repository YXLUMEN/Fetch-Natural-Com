import codecs
import hashlib
import json
import os
import random
import re
import threading
import time
import turtle
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from fake_useragent import FakeUserAgent
from requests import Response

from tt_draw import tt_draw_random, tt_draw_polyhedral, TTPixelImage

ENCODING: str = 'utf-8'
SAVE_FOLDER: str = 'save_files'
OUTPUT_FOLDER: str = 'output'


def get_html(url: str, rand: bool = False, do_re_try: bool = True, re_try_times: int = 5, timeout: int = 60) -> str:
    headers: dict[str, str] = dict(referer='https://www.nature.com/')
    if not rand:
        headers[
            'User-agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.50'
    else:
        headers['User-agent'] = FakeUserAgent().random

    for i in range(re_try_times):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = ENCODING
            return resp.text
        except Exception as e:
            if i >= re_try_times - 1 or not do_re_try:
                print(f'\r\nget_html: {repr(e)}')
                break
            print(f'\rRetry connecting... {i + 1}/{re_try_times}', end='')
        finally:
            time.sleep(0.5)


def wrap_two(text: str) -> str:
    # 我不知道为什么,都是如果改了就获取不到
    return re.sub(r'。', '\n', text).replace('.', '.\n')


def change_character_doc(infile: str, outfile: str, change_to: str = ' '):
    with open(infile, 'rb') as in_fo_open, open(outfile, 'wb') as out_fo_open:
        db: str = in_fo_open.read().decode(ENCODING)
        # 所有需要替换的字符
        chars: tuple = (' ',)
        for char in chars:
            db = db.replace(char, change_to)
        out_fo_open.write(db.encode(ENCODING))


def web_change(tag: BeautifulSoup) -> bool:
    try:
        title_tag: str = tag.find(attrs={'class': 'c-card__link u-link-inherit'}).get_text()
        tag_hash: str = hashlib.md5(title_tag.encode()).hexdigest()
    except Exception as e:
        print(f'web_change: {repr(e)}')
        return True

    cache_file: str = f'{SAVE_FOLDER}/cache_hashes.json'
    if not os.access(cache_file, os.R_OK):
        with open(cache_file, 'w') as f:
            json.dump({'cache_hashes': 'None'}, f, ensure_ascii=False)

    try:
        with open(cache_file, 'rb') as f:
            cache_hash: dict = json.load(f)
            if cache_hash.get('cache_hashes') == tag_hash:
                return False
            cache_hash['cache_hashes'] = tag_hash

        with open(cache_file, 'w', encoding=ENCODING) as g:
            json.dump(cache_hash, g)
        return True
    except Exception as e:
        print(f'web_change: {repr(e)}')
        if os.path.exists(cache_file):
            os.remove(cache_file)
        return True


def baidu_translate(text: str, flag: str = 'zh', qps: int = 1, max_require_length: int = 1000) -> str:
    if os.path.isfile(f'{ConfigPath}{FileName}'):
        _api: dict = json_api_read(f'{ConfigPath}{FileName}')
        api_id: str = _api.get('api_id')
        secret_key: str = _api.get('secret_key')
    else:
        print('因安全问题,百度API需自行提供,输入后将保存')
        api_id: str = input('API账户: ')
        secret_key: str = input('API密钥: ')
        json_api_write(ConfigPath, api_id, secret_key)

    temp: list = list()
    translated_strs: list = list()

    if len(text) > max_require_length:
        temp = text.split('.')
    else:
        temp.append(text)

    for split_text in temp:
        try:
            salt: str = str(random.randint(3276, 65536))
            sign_text: str = f'{api_id}{split_text}{str(salt)}{secret_key}'
            sign: str = hashlib.md5(sign_text.encode()).hexdigest()

            data: dict = {
                'q': split_text,
                'from': 'auto',
                'to': flag,
                'appid': api_id,
                'salt': salt,
                'sign': sign
            }

            res: Response = requests.post('https://api.fanyi.baidu.com/api/trans/vip/translate', data=data)
            result = res.json()['trans_result'][0]['dst']
            translated_strs.append(result)
            time.sleep(1 / qps)
        except KeyError:
            return ''
        except Exception as e:
            print(f'baidu_translate: {repr(e)}')

    return ''.join(translated_strs)


def process_and_write(data: dict):
    title: str = data.get('title')
    summary: str = data.get('summary')
    abstract: str = data.get('abstract')
    link: str = data.get('link')
    pub_time: str = data.get('pub_time')

    if DoTranslate == 'y':
        with TranslateLock:
            title, summary, abstract = baidu_translate(title), baidu_translate(summary), baidu_translate(abstract)

        summary = summary.replace('＜', '<').replace('＞', '>')
        abstract = abstract.replace('＜', '<').replace('＞', '>')

    summary, abstract = wrap_two(summary), wrap_two(abstract)
    print(f"标题:{title}.\n")
    inFoFile.write(
        f'# {title}.\n'
        f'<b>{summary}</b>\n\n'
        f'[摘要]\n{abstract}\n\n'
        f'[文章链接]\n{link}\n\n'
        f'[发布时间]\n{pub_time}\n\n'
        f'***\n\n'
    )


def get_abstract(url: str, all_result: dict):
    html: str = get_html(url, rand=UseRandomHeaders, re_try_times=2)
    soup: BeautifulSoup = BeautifulSoup(html, "lxml")
    [s.extract() for s in soup.find_all(attrs={'class': 'recommended pull pull--left u-sans-serif'})]
    text: str = str(soup.find(attrs={'class': 'c-article-body main-content'}))

    text = text.replace('<h2>', '\n### ').replace('</h2>', '\n').replace('\n</figcaption>', '</figcaption>')
    text = re.sub(
        r'(</?a.*?>)|(</?p.*?>)|(</source>)|(</?div.*?>)|(</?span.*?>)|(<iframe.*>)', '', text)
    # 修复链接
    text = text.replace('//media', 'https://media')

    all_result['abstract'] = text
    process_and_write(all_result)


def process_text_analysis(tag):
    try:
        title_link = tag.find(attrs={"class": "c-card__link u-link-inherit"})
        title: str = re.sub('(</?a.*?>)|(</?p>)', '', str(title_link))
        summary = tag.find(attrs={"class": "c-card__summary u-mb-16 u-hide-sm-max"})
        summary = re.sub('(</?a.*?>)|(</?p>)', '', str(summary.select('p')[0])) if summary else 'None'
        link: str = title_link.get('href')

        pub_time = tag.select("time[class='c-meta__item']")
        if pub_time:
            pub_time = pub_time[0].get_text()
        else:
            pub_time = tag.select("time[class='c-meta__item c-meta__item--block-at-lg']")[0].get_text()

        if title:
            url: str = f'https://www.nature.com{link}'
            url_hash: str = hashlib.md5(url.encode(ENCODING)).hexdigest()
            if url_hash in UrlCollect:
                return
            UrlCollect.add(url_hash)
            result: dict = {
                'title': title,
                'summary': summary,
                'pub_time': pub_time,
                'link': url
            }
            WorkPool.submit(get_abstract, url, result)
    except Exception as e:
        print(f'\r\nprocess_text_analysis: {repr(e)}', end='')


def start_text_analysis(soup: BeautifulSoup):
    start: float = time.perf_counter()
    all_boxs: tuple = ("app-featured-row__item", "app-news-row__item", "app-reviews-row__item")
    for box in all_boxs:
        for tag in soup.select(f'li[class={box}]'):
            process_text_analysis(tag)
    WorkPool.shutdown()
    end: float = time.perf_counter()
    print(f'\r\nAnalysis completed in: {end - start:.3}s')


def repeat_thread_detect(name: str) -> bool:
    for i in threading.enumerate():
        if i.name == name:
            return True
    return False


def tt_draw(tt_type: str = '0'):
    try:
        if tt_type == '0':
            tt_draw_random()
        elif tt_type == '1':
            tt_draw_polyhedral()
        elif tt_type == '2':
            TTPixelImage.tt_draw_picture(
                'https://www.yangandxu.online/static/img/not%20used/cxk.jpg', 5, 0.2, 0.2)
        else:
            print('你干嘛,哎哟')
    except turtle.Terminator:
        return
    except Exception as e:
        print(f'绘图中止: {repr(e)}')
        return


def json_api_write(fdir: str, api_id: str, secret_key: str):
    if not os.path.exists(fdir):
        os.mkdir(fdir)
    with open(fr'{fdir}\api.json', 'w') as f:
        json.dump({'api_id': api_id, 'secret_key': secret_key}, f, ensure_ascii=False)


def json_api_read(file_path: str):
    if not os.access(file_path, os.R_OK):
        return None
    with open(f'{file_path}', 'rb') as f:
        return json.load(f)


def start_fetch():
    url_n: str = 'https://www.nature.com/'
    global UseRandomHeaders
    UseRandomHeaders = input('(y/n) 是否使用随机请求头: ').lower().strip() in ('y', '')

    print('已选择随机请求头' if UseRandomHeaders else '未选择随机请求头')
    print('开始爬取\n' + '——' * 30)

    html_nature: str = get_html(url_n, rand=UseRandomHeaders)
    try:
        soup_main = BeautifulSoup(html_nature, "lxml")
    except Exception as e:
        print(f'\r\nBs4: {repr(e)}', end='')
        exit('\r\n链接超时')

    if web_change(soup_main):
        print('请求完成,正在解析文档')
        start_text_analysis(soup_main)
        return True
    return False


if __name__ == '__main__':
    # 翻译Api保存位置
    AppDir: str = os.environ.get('APPDATA')
    ConfigPath: str = AppDir + '\\pyhttpRe\\'
    FileName: str = 'api.json'
    # 避免翻译内容冲突
    TranslateLock = threading.RLock()
    # 用于网址去重
    UrlCollect: set = set()
    UseRandomHeaders: bool = False
    # threadpool用于并行网络请求
    WorkPool = ThreadPoolExecutor(max_workers=8, thread_name_prefix='fetch_natural_com')

    while True:
        mode: str = input('\n(1)获取; (2)强制刷新; (3)重新输入密钥; (4)查询当前密钥; (5)清除密钥; (q)退出\r\n').strip()
        DoTranslate: str = 'n'

        if mode == '1':
            if not os.path.exists(SAVE_FOLDER):
                os.mkdir(SAVE_FOLDER)
            if not os.path.exists(OUTPUT_FOLDER):
                os.mkdir(OUTPUT_FOLDER)
            temp_save_file: str = f'{OUTPUT_FOLDER}/temp-Nature'
            with codecs.open(temp_save_file, 'w+', ENCODING) as inFoFile:
                inFoFile.write('')
                DoTranslate: str = input('(y/n) 是否翻译: ').strip()
                web_status: bool = start_fetch()
            date: str = time.strftime('%y-%m-%d')
            if os.path.exists(temp_save_file) and web_status:
                change_character_doc(temp_save_file, f'{OUTPUT_FOLDER}/{date}-Nature.md')

            print(f'爬取完成,结果保存于{date}-Nature.md')
            print('您可以使用 https://tool.lu/markdown/ 在线查看 markdown 文档')

            if os.path.exists(temp_save_file):
                os.remove(temp_save_file)

        elif mode == '2':
            try:
                os.remove(f'{SAVE_FOLDER}/cache_hashes.json')
                print('刷新完成')
            except FileNotFoundError:
                print('无此文件')
            except Exception as E:
                print(repr(E))

        elif mode == '3':
            apiId: str = input('API账户: ')
            secretKey: str = input('API密钥: ')
            json_api_write(ConfigPath, apiId, secretKey)

        elif mode == '4':
            api = json_api_read(f'{ConfigPath}api.json')
            if not api:
                print('无密钥文件')
                continue
            print(f'API账户: {api["api_id"]}\nAPI密钥: {api["secret_key"]}')

        elif mode == '5':
            a: str = input('(y/n) 确认清除: ').strip()
            if a == 'y':
                try:
                    os.remove(f'{ConfigPath}api.json')
                    print('清除配置文件')
                except FileNotFoundError:
                    print('无配置文件')
                except Exception as E:
                    print(repr(E))

        elif mode.startswith('tt'):
            if len(mode) > 2:
                ttType = mode[-1]
                tt_draw(ttType)
                continue
            tt_draw()
        elif mode == 'q':
            break
        else:
            print('无此选项')

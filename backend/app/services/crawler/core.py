# -*- coding: utf-8 -*-
"""爬虫核心：URL 平台识别 + 适配器分发 + 采集落库

所有采集均通过 Playwright 真实浏览器完成，遵守各平台 robots.txt，
仅采集公开可见的价格信息。
"""
import logging
import re
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger("spt.crawler")

HEADERS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def detect_platform(url: str) -> str:
    """按主机名关键字识别电商平台，未识别的归为通用 web 平台"""
    host = urlparse(url).netloc.lower()
    if "jd.com" in host:
        return "jd"
    if "taobao.com" in host or "tmall.com" in host:
        return "taobao"
    if "pinduoduo.com" in host:
        return "pdd"
    if "manmanbuy.com" in host:
        return "manmanbuy"
    if "dangdang.com" in host:
        return "dangdang"
    if "suning.com" in host:
        return "suning"
    if "vip.com" in host or "vip.com" in host:
        return "vip"
    if "amazon" in host:
        return "amazon"
    return "web"


def launch_page(headless: bool = True):
    """启动一个 Playwright 浏览器页面（调用方负责关闭）"""
    import os

    # 浏览器安装在项目目录内（避免系统目录写权限问题）
    local_browsers = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "ms-playwright",
    )
    if os.path.isdir(local_browsers):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", local_browsers)

    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=headless,
        # 关闭自动化特征标记 + 中文语言环境，降低被站点风控拦截的概率
        args=["--disable-blink-features=AutomationControlled", "--lang=zh-CN"],
    )
    ctx = browser.new_context(
        user_agent=HEADERS_UA,
        locale="zh-CN",
        viewport={"width": 1366, "height": 900},
    )
    # 注入脚本抹掉 navigator.webdriver 标记（常见反爬检测点）
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return p, browser, ctx.new_page()


def close_all(p, browser, ctx_page):
    """尽力关闭浏览器与 Playwright 实例（忽略已关闭等异常）"""
    try:
        browser.close()
    except Exception:
        pass
    try:
        p.stop()
    except Exception:
        pass


def fetch_price(url: str) -> dict:
    """采集单个商品链接的当前价格

    优先级：
    - 非京东链接：慢慢买历史价查询（能同时拿到当前价 + 历史序列）-> 通用解析兜底
    - 京东链接：京东页面解析（慢慢买受京东授权限制）-> 通用解析兜底

    返回 {platform, title, price, image_url, history}
    history 为可选的历史价格序列 [(date, price), ...]；全部失败时抛异常。
    """
    platform = detect_platform(url)
    errors = []

    # 组装适配器降级链：优先能拿到历史序列的数据源，最后走通用解析兜底
    order = []
    if platform != "jd":
        order.append(("manmanbuy", "manmanbuy"))
    else:
        order.append(("jd", "jd"))
    order.append(("generic", "generic"))
    # 京东也尝试慢慢买（若授权问题解除则可用）
    if platform == "jd":
        order.insert(1, ("manmanbuy", "manmanbuy"))

    modules = {"jd": "jd", "manmanbuy": "manmanbuy", "generic": "generic"}
    for _, key in order:
        try:
            # 延迟导入适配器模块，逐个尝试直到解析出价格
            mod = __import__(f"{__package__}.{modules[key]}", fromlist=["fetch"])
            data = mod.fetch(url)
            if data and data.get("price"):
                data.setdefault("platform", platform)
                data.setdefault("history", [])
                return data
            errors.append(f"{key}: 未解析到价格")
        except Exception as e:
            errors.append(f"{key}: {e}")
    # 全部适配器失败：汇总各环节错误抛出，交由上层提示
    raise RuntimeError("；".join(errors)[:480])


def realtime_crawl(url: str) -> dict:
    """REQ-SPT-203：对用户提交的链接即时采集一次"""
    return fetch_price(url)


def run_crawl_task(db, task) -> tuple:
    """执行一条采集任务并回写任务状态（REQ-SPT-602）"""
    from ...models import Listing, PriceSnapshot

    try:
        data = fetch_price(task.target)
        if not data or not data.get("price"):
            # 采集失败：回写失败状态与错误信息，累加失败计数供调度参考
            task.status = "failed"
            task.last_error = "未解析到价格"
            task.fail_count = (task.fail_count or 0) + 1
            db.commit()
            return False, task.last_error
        task.status = "success"
        task.last_error = ""
        task.success_count = (task.success_count or 0) + 1
        listing = db.query(Listing).get(task.listing_id) if task.listing_id else None
        if listing:
            # 回写最新报价并追加一条价格快照（历史价格序列的数据来源）
            listing.current_price = data["price"]
            listing.last_crawled_at = datetime.now()
            listing.title = data.get("title") or listing.title
            db.add(PriceSnapshot(listing_id=listing.id, price=data["price"]))
        db.commit()
        return True, ""
    except Exception as e:
        # 异常同样回写失败状态，不向上抛出（后台任务不能中断调度）
        task.status = "failed"
        task.last_error = str(e)[:480]
        task.fail_count = (task.fail_count or 0) + 1
        db.commit()
        return False, str(e)

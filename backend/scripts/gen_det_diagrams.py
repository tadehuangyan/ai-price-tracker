# -*- coding: utf-8 -*-
"""生成《详细设计说明书》插图（黑白规范风格）
- arch.png   ：软件结构框图（分层 + 外部接口）
- flow_*.png ：各模块流程图（标准符号：椭圆起止 / 矩形处理 / 菱形判断）
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "doc_assets")
os.makedirs(OUT, exist_ok=True)

SONG = "C:/Windows/Fonts/simsun.ttc"
HEI = "C:/Windows/Fonts/simhei.ttf"
BLACK = "#000000"
WHITE = "#ffffff"


def song(size):
    return ImageFont.truetype(SONG, size)


def hei(size):
    return ImageFont.truetype(HEI, size)


def arrowhead(d, x, y, dx, dy, L=12, a=0.45):
    """在 (x, y) 处沿 (dx, dy) 方向绘制实心三角箭头"""
    ang = math.atan2(dy, dx)
    d.polygon([
        (x, y),
        (x - L * math.cos(ang - a), y - L * math.sin(ang - a)),
        (x - L * math.cos(ang + a), y - L * math.sin(ang + a)),
    ], fill=BLACK)


def wrap(d, text, font, maxw):
    """按显示宽度折行；ASCII 连续串（标识符/数字）整体不拆分"""
    import re
    toks = re.findall(r"[A-Za-z0-9_./:%~+\-]+|.", text)
    lines, cur = [], ""
    for tk in toks:
        if tk == " " and not cur:
            continue
        if d.textlength(cur + tk, font=font) > maxw and cur:
            lines.append(cur.rstrip())
            cur = "" if tk == " " else tk
        else:
            cur += tk
    lines.append(cur)
    return lines


# ======================================================================
# 软件结构框图
# ======================================================================
def arch_diagram():
    """生成软件结构框图 arch.png（客户端层 / 服务端层 / 数据层 + 外部接口）"""
    W, H = 1640, 540
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    def box(xy, text, fs=16, font_fn=song, lw=2):
        x1, y1, x2, y2 = xy
        d.rectangle([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=lw)
        f = font_fn(fs)
        lines = wrap(d, text, f, (x2 - x1) - 16)
        lh = fs + 5
        ty = y1 + (y2 - y1 - lh * len(lines)) / 2 + 1
        cx = (x1 + x2) / 2
        for i, ln in enumerate(lines):
            w = d.textlength(ln, font=f)
            d.text((cx - w / 2, ty + i * lh), ln, font=f, fill=BLACK)

    def arrow(x1, y1, x2, y2):
        d.line([x1, y1, x2, y2], fill=BLACK, width=2)
        arrowhead(d, x2, y2, x2 - x1, y2 - y1)

    # 左侧层标签
    for text, y1, y2 in [("客户端层", 30, 120), ("服务端层", 170, 370), ("数据层", 410, 500)]:
        box((24, y1, 224, y2), text, fs=18, font_fn=hei)

    # 客户端层
    box((260, 30, 940, 120), "浏览器（Vue 3 单页应用：首页 / 详情 / 追踪 / 对比 / AI 导购 / 管理）")
    box((980, 30, 1330, 120), "浏览器本地存储（登录令牌、AI 对话记录）")

    # 服务端层
    box((260, 170, 940, 250), "接口路由层 FastAPI（auth / products / tracking / compare / ai / admin）")
    box((260, 270, 590, 370), "业务服务层（采集 crawler / 提醒 alerts / 导购 ai_advisor）")
    box((610, 270, 940, 370), "调度器 APScheduler（采集 30 分钟 / 提醒 10 分钟）")
    box((980, 170, 1330, 370), "外部接口：① 慢慢买比价平台 ② sensenova 大模型 ③ 各电商平台页面")

    # 数据层
    box((260, 410, 940, 500), "MySQL 数据库（users / products / listings / price_snapshots / trackings / alerts 等 10 张表）")

    # 连线
    d.line([600, 120, 600, 170], fill=BLACK, width=2)
    arrowhead(d, 600, 170, 0, 1)
    arrowhead(d, 600, 120, 0, -1)
    d.text((612, 132), "HTTP/JSON（REST + JWT）", font=song(15), fill=BLACK)

    arrow(450, 250, 450, 270)
    arrow(750, 250, 750, 270)
    arrow(425, 370, 425, 410)
    d.text((437, 376), "SQLAlchemy ORM", font=song(15), fill=BLACK)
    arrow(775, 370, 775, 410)
    arrow(940, 210, 980, 210)
    arrow(940, 320, 980, 320)

    img.save(os.path.join(OUT, "arch.png"))
    print("arch.png saved", img.size)


# ======================================================================
# 流程图引擎
# 节点：
#   ("s"|"e", text)             起止（椭圆）
#   ("p", text)                 处理（矩形）
#   ("d", text, spine_label, side_label, side_text, mode, rejoin)
#        spine_label ：菱形下方主干分支标签
#        side_label  ：右侧分支标签
#        mode "end"  ：右侧椭圆终止（rejoin 无效）
#        mode "rejoin"：右侧矩形，流程汇入下标 rejoin 的主干节点右侧
# ======================================================================
def flow(name, nodes, cx=270):
    f = song(15)
    f_small = song(14)
    GAP = 56
    W = cx + 540

    # 1) 主干节点尺寸（用临时 draw 测量文本）
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    sizes = []
    for n in nodes:
        if n[0] == "d":
            lines = wrap(tmp, n[1], f, 170)
            w, h = 340, max(96, 40 + len(lines) * 20)
        elif n[0] in ("s", "e"):
            lines = wrap(tmp, n[1], f, 210)
            w, h = 270, max(58, 34 + len(lines) * 20)
        else:
            lines = wrap(tmp, n[1], f, 252)
            w, h = 284, max(48, 26 + len(lines) * 20)
        sizes.append((w, h, lines))

    ys, y = [], 24
    for (w, h, _) in sizes:
        ys.append(y)
        y += h + GAP
    total_h = y - GAP + 24

    img = Image.new("RGB", (W, total_h), WHITE)
    d = ImageDraw.Draw(img)

    def cy(i):
        return ys[i] + sizes[i][1] / 2

    # 2) 侧枝几何信息
    side_cx = cx + 350
    sides = []  # (mode, text, x1, y1, x2, y2, lines)
    for i, n in enumerate(nodes):
        if n[0] != "d":
            continue
        mode, side_text = n[5], n[4]
        lines = wrap(tmp, side_text, f, 210)
        if mode == "end":
            w_s, h_s = 270, max(58, 34 + len(lines) * 20)
            y1 = cy(i) - h_s / 2
            sides.append((mode, side_text, side_cx - w_s // 2, y1, side_cx + w_s // 2, y1 + h_s, lines))
        else:
            j = n[6]
            w_s, h_s = 284, max(48, 26 + len(lines) * 20)
            y1 = ys[j]
            sides.append((mode, side_text, side_cx - w_s // 2, y1, side_cx + w_s // 2, y1 + h_s, lines))

    # 3) 画侧枝连线（主干节点最后画，保证覆盖线端）
    for idx, i in enumerate(n for n, x in enumerate(nodes) if x[0] == "d"):
        n = nodes[i]
        mode = n[5]
        x1, y1, x2, y2 = sides[idx][2], sides[idx][3], sides[idx][4], sides[idx][5]
        if mode == "end":
            d.line([cx + 170, cy(i), x1, cy(i)], fill=BLACK, width=2)
            arrowhead(d, x1, cy(i), -1, 0)
        else:
            j = n[6]
            d.line([cx + 170, cy(i), side_cx, cy(i)], fill=BLACK, width=2)
            d.line([side_cx, cy(i), side_cx, ys[j] - 12], fill=BLACK, width=2)
            arrowhead(d, side_cx, ys[j], 0, 1)
            node_right = cx + sizes[j][0] / 2
            d.line([x1, cy(j), node_right + 14, cy(j)], fill=BLACK, width=2)
            arrowhead(d, node_right, cy(j), -1, 0)
        # 分支标签
        d.text((cx + 178, cy(i) - 22), n[3], font=f_small, fill=BLACK)

    # 4) 主干连线
    for i in range(len(nodes) - 1):
        y_from = ys[i] + sizes[i][1]
        y_to = ys[i + 1]
        d.line([cx, y_from, cx, y_to - 12], fill=BLACK, width=2)
        arrowhead(d, cx, y_to, 0, 1)
        if nodes[i][0] == "d":
            d.text((cx + 8, y_from + 6), nodes[i][2], font=f_small, fill=BLACK)

    # 5) 主干节点（覆盖线端）
    for i, n in enumerate(nodes):
        w, h, lines = sizes[i]
        y1, y2 = ys[i], ys[i] + h
        x1, x2 = cx - w // 2, cx + w // 2
        if n[0] in ("s", "e"):
            d.ellipse([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=2)
        elif n[0] == "d":
            d.polygon([(cx, y1), (x2, y1 + h / 2), (cx, y2), (x1, y1 + h / 2)],
                      fill=WHITE, outline=BLACK, width=2)
        else:
            d.rectangle([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=2)
        lh = 20
        ty = (y1 + y2) / 2 - lh * len(lines) / 2 + 2
        for k, ln in enumerate(lines):
            wln = d.textlength(ln, font=f)
            d.text((cx - wln / 2, ty + k * lh), ln, font=f, fill=BLACK)

    # 6) 侧框（最后画，覆盖侧枝线端）
    for (mode, text, x1, y1, x2, y2, lines) in sides:
        if mode == "end":
            d.ellipse([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=2)
        else:
            d.rectangle([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=2)
        lh = 20
        ty = (y1 + y2) / 2 - lh * len(lines) / 2 + 2
        scx = (x1 + x2) / 2
        for k, ln in enumerate(lines):
            wln = d.textlength(ln, font=f)
            d.text((scx - wln / 2, ty + k * lh), ln, font=f, fill=BLACK)

    img.save(os.path.join(OUT, name))
    print(name, "saved", img.size)


# ======================================================================
# 各模块流程图
# ======================================================================
def flows():
    """生成各业务模块流程图 flow_*.png（注册/登录/商品/追踪/对比/导购/调度）"""
    flow("flow_register.png", [
        ("s", "开始：用户填写用户名、密码、邮箱并提交注册"),
        ("p", "前端格式校验：用户名 3~20 位、密码 8~64 位、邮箱格式"),
        ("d", "后端二次校验是否通过？", "是", "否", "返回具体字段错误提示", "end", 0),
        ("p", "查询 users 表，检查用户名是否已存在"),
        ("d", "用户名是否可用？", "是", "否", "返回“用户名已存在”", "end", 0),
        ("p", "bcrypt 生成密码哈希，插入用户记录（角色 user）"),
        ("p", "签发 JWT（HS256，有效期 1440 分钟）并返回"),
        ("e", "结束：前端保存令牌并进入系统"),
    ])

    flow("flow_login.png", [
        ("s", "开始：用户提交用户名与密码登录"),
        ("p", "按用户名查询 users 表"),
        ("d", "用户是否存在？", "是", "否", "返回“用户名或密码错误”", "end", 0),
        ("p", "bcrypt.checkpw 比对密码哈希"),
        ("d", "密码是否匹配？", "是", "否", "返回“用户名或密码错误”", "end", 0),
        ("p", "jwt.encode 签发令牌（sub=用户ID、role、exp）"),
        ("p", "前端将令牌存入本地并注入 Authorization 请求头"),
        ("e", "结束：进入系统首页"),
    ])

    flow("flow_product.png", [
        ("s", "开始：用户在统一搜索栏输入关键词或商品链接"),
        ("d", "输入内容是否为 URL？", "否", "是", "识别为链接，调用 fetch_price 实时采集", "rejoin", 3),
        ("p", "在商品表按名称 / 分类模糊匹配，返回匹配商品"),
        ("p", "展示结果：关键词进入列表页，链接进入实时价格页"),
        ("p", "进入商品详情，加载各平台报价与近 365 天走势"),
        ("e", "结束"),
    ])

    flow("flow_tracking.png", [
        ("s", "开始：调度器每 10 分钟触发降价检查 job_alerts"),
        ("p", "查询全部设置了目标价的追踪订阅"),
        ("p", "取该商品各平台当前价的最小值 min_price"),
        ("d", "min_price 不高于目标价？", "是", "否", "未达标，等待下一轮检查", "end", 0),
        ("p", "查询该用户当日是否已存在同商品提醒"),
        ("d", "当日已有提醒？", "否", "是", "去重跳过，不重复生成", "end", 0),
        ("p", "生成站内降价提醒并写入 alerts 表"),
        ("p", "写系统日志：产生 N 条降价提醒"),
        ("e", "结束：用户在站内消息中心查看并标记已读"),
    ])

    flow("flow_compare.png", [
        ("s", "开始：用户勾选 1~5 个商品提交对比"),
        ("p", "读取各商品全部平台报价 listings"),
        ("d", "报价数据是否充足？", "是", "否", "提示数据不足，建议先加入采集", "end", 0),
        ("p", "按商品取最低价并排序，计算平台间差价"),
        ("p", "聚合价格序列，计算历史最高 / 最低 / 均价"),
        ("p", "返回对比结果，前端渲染对比表格"),
        ("e", "结束"),
    ])

    flow("flow_advisor.png", [
        ("s", "开始：AI 导购页用户发送消息"),
        ("p", "解析消息中的商品标记、链接、图片与文件"),
        ("d", "识别到商品或链接？", "否", "是", "构建商品 / 链接价格数据摘要", "rejoin", 4),
        ("p", "按普通对话内容准备消息"),
        ("p", "组装 system 上下文与最近 10 轮历史"),
        ("p", "POST sensenova /chat/completions 生成回复"),
        ("d", "调用是否成功？", "是", "否", "降级返回已获取数据并提示稍后重试", "end", 0),
        ("p", "返回 Markdown 回复，前端渲染并持久化会话"),
        ("e", "结束"),
    ])

    flow("flow_admin.png", [
        ("s", "开始：APScheduler 启动定时任务"),
        ("p", "job_collect 每 30 分钟扫描在售链接"),
        ("p", "筛选采集时间早于间隔的链接（每轮最多 50 条）"),
        ("p", "创建 CrawlTask 采集任务（状态 running）"),
        ("p", "fetch_price：慢慢买查询，失败转通用解析"),
        ("d", "是否采集到价格？", "是", "否", "任务置 failed，写 ERROR 日志", "end", 0),
        ("p", "更新当前价、写 PriceSnapshot，任务置 success"),
        ("p", "回写 last_crawled_at 并提交事务"),
        ("e", "结束：等待下一调度周期（提醒任务 10 分钟一轮）"),
    ])


if __name__ == "__main__":
    arch_diagram()
    flows()
    print("done")

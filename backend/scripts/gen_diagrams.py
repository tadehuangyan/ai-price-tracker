# -*- coding: utf-8 -*-
"""生成概要设计说明书插图（黑白规范学术风格，参照样例图）
- struct.png：系统功能结构图（直角黑框 + 正交连线 + 叶节点竖排）
- er.png：实体关联图（黑白 E-R 简图）
"""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "doc_assets")
os.makedirs(OUT, exist_ok=True)

SONG = "C:/Windows/Fonts/simsun.ttc"    # 宋体（正文）
HEI = "C:/Windows/Fonts/simhei.ttf"     # 黑体（标题）


def song(size):
    return ImageFont.truetype(SONG, size)


def hei(size):
    return ImageFont.truetype(HEI, size)


BLACK = "#000000"
WHITE = "#ffffff"


def rect(d, xy, text, fs=16, font_fn=song, lw=2, vertical=False, bold=False):
    """黑白直角矩形框；vertical=True 时文字竖排"""
    x1, y1, x2, y2 = xy
    d.rectangle([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=lw)
    f = font_fn(fs)
    if vertical:
        chars = list(text)
        lh = fs + 4
        total = lh * len(chars)
        ty = y1 + (y2 - y1 - total) / 2 + 1
        cx = (x1 + x2) / 2
        for i, ch in enumerate(chars):
            w = d.textlength(ch, font=f)
            d.text((cx - w / 2, ty + i * lh), ch, font=f, fill=BLACK)
    else:
        w = d.textlength(text, font=f)
        h = fs + 4
        d.text((x1 + (x2 - x1 - w) / 2, y1 + (y2 - y1 - h) / 2), text, font=f, fill=BLACK)


def elbow(d, x_from, y_from, xs, y_to):
    """正交连线：从 (x_from,y_from) 垂直向下到中线，水平到各 x，再垂直向下到 y_to"""
    y_mid = (y_from + y_to) / 2
    d.line([x_from, y_from, x_from, y_mid], fill=BLACK, width=2)
    d.line([min(xs + [x_from]), y_mid, max(xs + [x_from]), y_mid], fill=BLACK, width=2)
    for x in xs:
        d.line([x, y_mid, x, y_to], fill=BLACK, width=2)


def struct_diagram():
    """系统功能结构图：顶层 -> 六模块 -> 竖排叶节点（横排铺开）"""
    W, H = 1640, 560
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # 顶层框
    top_w, top_h = 340, 52
    tx1, tx2 = W // 2 - top_w // 2, W // 2 + top_w // 2
    ty1, ty2 = 24, 24 + top_h
    rect(d, (tx1, ty1, tx2, ty2), "商品历史价格追踪系统（SPT）", fs=20, font_fn=hei, lw=2)

    modules = [
        ("用户管理", ["用户注册", "登录登出", "个人信息", "权限管理"]),
        ("商品价格查询", ["商品搜索", "详情快照", "实时价格"]),
        ("价格追踪", ["添加追踪", "历史采集", "走势可视化", "降价提醒"]),
        ("价格对比", ["多平台比价", "多商品对比", "历史对比"]),
        ("AI智能导购", ["数据汇聚", "决策建议"]),
        ("系统管理", ["数据源管理", "任务调度", "统计日志", "系统配置"]),
    ]
    n = len(modules)
    col_w = W // n

    # 中间层框
    mod_y1, mod_y2 = 150, 202
    mod_boxes = []
    for i, (name, _) in enumerate(modules):
        cx = int(col_w * i + col_w / 2)
        mw = 176
        box = (cx - mw // 2, mod_y1, cx + mw // 2, mod_y2)
        mod_boxes.append((cx, box))

    # 顶层 -> 中间层（正交）
    elbow(d, W // 2, ty2, [cx for cx, _ in mod_boxes], mod_y1)

    # 中间层框
    for (name, _), (cx, box) in zip(modules, mod_boxes):
        rect(d, box, name, fs=17, font_fn=song, lw=2)

    # 叶节点：横排细竖条，文字竖排；所有叶框尺寸统一（按全图最长标签取高度）
    leaf_w = 46
    leaf_gap = 12
    leaf_top = 258
    global_max_chars = max(len(s) for _, subs in modules for s in subs)
    leaf_h = 16 + global_max_chars * 22
    leaf_bottom = leaf_top + leaf_h
    for (name, subs), (cx, box) in zip(modules, mod_boxes):
        nsub = len(subs)
        total_w = nsub * leaf_w + (nsub - 1) * leaf_gap
        start_x = cx - total_w // 2
        xs = []
        for j, s in enumerate(subs):
            lx1 = start_x + j * (leaf_w + leaf_gap)
            xs.append(lx1 + leaf_w // 2)
            rect(d, (lx1, leaf_top, lx1 + leaf_w, leaf_bottom), s, fs=17,
                 font_fn=song, lw=2, vertical=True)
        # 模块 -> 叶（正交）
        elbow(d, cx, mod_y2, xs, leaf_top)

    # 裁剪留白
    img = img.crop((0, 0, W, leaf_bottom + 30))
    img.save(os.path.join(OUT, "struct.png"))
    print("struct.png saved", img.size)


def er_diagram():
    """标准 E-R 图：矩形实体 + 菱形关系 + 1/n 基数标注（参照样例风格）"""
    W, H = 1640, 580
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    def ent(cx, cy, text, w=150, h=56):
        """矩形实体框"""
        x1, y1, x2, y2 = cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2
        d.rectangle([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=2)
        f = hei(18)
        tw = d.textlength(text, font=f)
        d.text((cx - tw / 2, cy - 12), text, font=f, fill=BLACK)
    def dia(cx, cy, text, w=110, h=60):
        """菱形关系框"""
        pts = [(cx, cy - h // 2), (cx + w // 2, cy), (cx, cy + h // 2), (cx - w // 2, cy)]
        d.polygon(pts, fill=WHITE, outline=BLACK, width=2)
        f = song(16)
        tw = d.textlength(text, font=f)
        d.text((cx - tw / 2, cy - 10), text, font=f, fill=BLACK)

    def base(x, y, t):
        """基数标注 1/n（白底）"""
        f = song(15)
        tw = d.textlength(t, font=f)
        d.rectangle([x - tw / 2 - 4, y - 10, x + tw / 2 + 4, y + 10], fill=WHITE)
        d.text((x - tw / 2, y - 9), t, font=f, fill=BLACK)

    def line(*pts):
        d.line(list(pts), fill=BLACK, width=2)

    # ---- 连线（先画线，菱形/实体白底后盖） ----
    # Row A 主链：用户 -订阅- 追踪订阅 -针对- 商品 -拥有- 平台报价
    line((250, 98), (300, 98))
    line((410, 98), (460, 98))
    line((610, 98), (640, 98))
    line((750, 98), (780, 98))
    line((930, 98), (960, 98))
    line((1070, 98), (1100, 98))
    # 平台报价 -记录- 价格快照（垂直）
    line((1175, 126), (1175, 300))
    # 用户 -接收- 降价提醒（垂直）
    line((175, 126), (175, 300))
    # 追踪订阅 -触发- 降价提醒（L 型）
    line((535, 126), (535, 328), (250, 328))
    # 数据源 -调度- 采集任务（数据源在任务左侧同一行，水平直进）
    line((710, 328), (860, 328))
    # 采集任务 -采集- 平台报价（从任务底部绕行右侧，避免穿框）
    line((935, 356), (935, 430), (1400, 430), (1400, 98), (1250, 98))

    # ---- 菱形关系 ----
    dia(355, 98, "订阅")      # 用户-追踪订阅
    dia(695, 98, "针对")      # 追踪订阅-商品
    dia(1015, 98, "拥有")     # 商品-平台报价
    dia(1175, 213, "记录")    # 平台报价-价格快照
    dia(175, 213, "接收")     # 用户-降价提醒
    dia(393, 328, "触发")     # 追踪订阅-降价提醒
    dia(785, 328, "调度")    # 数据源-采集任务（水平同行）
    dia(1400, 213, "采集")    # 采集任务-平台报价

    # ---- 矩形实体 ----
    ent(175, 98, "用户")
    ent(535, 98, "追踪订阅")
    ent(855, 98, "商品")
    ent(1175, 98, "平台报价")
    ent(1175, 328, "价格快照")
    ent(175, 328, "降价提醒")
    ent(635, 328, "数据源")
    ent(935, 328, "采集任务")

    # ---- 基数标注 1/n ----
    base(275, 98, "1")    # 用户侧
    base(435, 98, "n")    # 追踪订阅侧
    base(625, 98, "n")    # 追踪订阅侧（针对）
    base(765, 98, "1")    # 商品侧
    base(945, 98, "1")    # 商品侧（拥有）
    base(1085, 98, "n")   # 平台报价侧
    base(1195, 155, "1")  # 平台报价侧（记录）
    base(1195, 272, "n")  # 价格快照侧
    base(195, 155, "1")   # 用户侧（接收）
    base(195, 272, "n")   # 降价提醒侧
    base(512, 315, "1")   # 追踪订阅侧（触发）
    base(275, 315, "n")   # 降价提醒侧
    base(722, 315, "1")   # 数据源侧（调度）
    base(848, 315, "n")   # 采集任务侧
    base(1000, 415, "n")   # 采集任务侧（采集）
    base(1383, 135, "1")   # 平台报价侧

    img = img.crop((0, 0, W, 552))  # 裁掉底部留白
    img.save(os.path.join(OUT, "er.png"))
    print("er.png saved", img.size)


def er_overall_diagram():
    """系统整体实体关联图：实体矩形 + 联系菱形 + 属性椭圆 + 1/n（参照样例，黑白不填色）"""
    W, H = 1760, 760
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # 标题
    f_t = hei(26)
    t = "系统整体实体关联图"
    d.text((W // 2 - d.textlength(t, font=f_t) / 2, 30), t, font=f_t, fill=BLACK)

    def ent(cx, cy, text, w=150, h=56):
        x1, y1, x2, y2 = cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2
        d.rectangle([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=2)
        f = hei(18)
        tw = d.textlength(text, font=f)
        d.text((cx - tw / 2, cy - 12), text, font=f, fill=BLACK)

    def dia(cx, cy, text, w=110, h=60):
        pts = [(cx, cy - h // 2), (cx + w // 2, cy), (cx, cy + h // 2), (cx - w // 2, cy)]
        d.polygon(pts, fill=WHITE, outline=BLACK, width=2)
        f = song(16)
        tw = d.textlength(text, font=f)
        d.text((cx - tw / 2, cy - 10), text, font=f, fill=BLACK)

    def attr(cx, cy, text, w=116, h=44):
        """属性椭圆"""
        d.ellipse([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
                  fill=WHITE, outline=BLACK, width=2)
        f = song(15)
        tw = d.textlength(text, font=f)
        d.text((cx - tw / 2, cy - 10), text, font=f, fill=BLACK)

    def base(x, y, t):
        f = song(15)
        tw = d.textlength(t, font=f)
        d.rectangle([x - tw / 2 - 4, y - 10, x + tw / 2 + 4, y + 10], fill=WHITE)
        d.text((x - tw / 2, y - 9), t, font=f, fill=BLACK)

    def line(*pts):
        d.line(list(pts), fill=BLACK, width=2)

    # ---- 主链连线：用户-订阅-追踪订阅-针对-商品-拥有-平台报价-记录-价格快照 ----
    line((305, 300), (320, 300))
    line((430, 300), (445, 300))
    line((595, 300), (635, 300))
    line((745, 300), (795, 300))
    line((945, 300), (975, 300))
    line((1085, 300), (1105, 300))
    line((1255, 300), (1290, 300))
    line((1400, 300), (1415, 300))
    # 竖支：追踪订阅-触发-降价提醒；平台报价-采集-采集任务
    line((520, 328), (520, 560))
    line((1180, 328), (1180, 560))
    # 数据源-调度-采集任务（水平）
    line((1255, 588), (1290, 588))
    line((1400, 588), (1415, 588))
    # 属性放射线（椭圆中心 -> 实体中心，两端被白底覆盖）
    for a, e in [
        ((150, 180), (230, 300)),   # 用户名-用户
        ((300, 180), (230, 300)),   # 邮箱-用户
        ((60, 300), (230, 300)),    # 密码-用户
        ((450, 180), (520, 300)),   # 目标价-追踪订阅
        ((610, 180), (520, 300)),   # 订阅时间-追踪订阅
        ((770, 400), (870, 328)),   # 名称-商品（下方）
        ((970, 400), (870, 328)),   # 分类-商品（下方）
        ((870, 500), (870, 328)),   # 图片-商品（下方）
        ((1120, 170), (1180, 300)), # 平台-平台报价
        ((1270, 170), (1180, 300)), # 当前价-平台报价
        ((1430, 170), (1490, 300)), # 价格-价格快照
        ((1560, 170), (1490, 300)), # 采集时间-价格快照
        ((370, 588), (520, 588)),   # 提醒内容-降价提醒
        ((520, 690), (520, 588)),   # 已读状态-降价提醒
        ((1180, 690), (1180, 588)), # 状态-采集任务
        ((1030, 588), (1180, 588)), # 失败次数-采集任务
        ((1660, 588), (1490, 588)), # 平台-数据源
        ((1490, 690), (1490, 588)), # 采集频率-数据源
    ]:
        line(a, e)

    # ---- 菱形联系 ----
    dia(375, 300, "订阅")
    dia(690, 300, "针对")
    dia(1030, 300, "拥有")
    dia(1345, 300, "记录")
    dia(520, 444, "触发")
    dia(1180, 444, "采集")
    dia(1345, 588, "调度")

    # ---- 属性椭圆 ----
    for a in [
        (150, 180, "用户名"), (300, 180, "邮箱"), (60, 300, "密码"),
        (450, 180, "目标价"), (610, 180, "订阅时间"),
        (770, 400, "名称"), (970, 400, "分类"), (870, 500, "图片"),
        (1120, 170, "平台"), (1270, 170, "当前价"),
        (1430, 170, "价格"), (1560, 170, "采集时间"),
        (370, 588, "提醒内容"), (520, 690, "已读状态"),
        (1180, 690, "状态"), (1030, 588, "失败次数"),
        (1660, 588, "平台"), (1490, 690, "采集频率"),
    ]:
        attr(a[0], a[1], a[2])

    # ---- 实体矩形 ----
    ent(230, 300, "用户")
    ent(520, 300, "追踪订阅")
    ent(870, 300, "商品")
    ent(1180, 300, "平台报价")
    ent(1490, 300, "价格快照")
    ent(520, 588, "降价提醒")
    ent(1180, 588, "采集任务")
    ent(1490, 588, "数据源")

    # ---- 基数标注 ----
    base(312, 287, "1")    # 用户-订阅
    base(437, 287, "n")
    base(615, 287, "n")    # 追踪订阅-针对
    base(770, 287, "1")
    base(960, 287, "1")    # 商品-拥有
    base(1095, 287, "n")
    base(1272, 287, "1")   # 平台报价-记录
    base(1407, 287, "n")
    base(542, 362, "1")    # 追踪订阅-触发
    base(542, 526, "n")    # 降价提醒侧
    base(1202, 362, "1")   # 平台报价-采集
    base(1202, 526, "n")   # 采集任务侧
    base(1408, 575, "1")   # 数据源-调度
    base(1272, 575, "n")   # 采集任务侧

    img = img.crop((0, 0, W, 732))  # 裁掉底部留白
    img.save(os.path.join(OUT, "er_overall.png"))
    print("er_overall.png saved", img.size)


if __name__ == "__main__":
    struct_diagram()
    er_diagram()
    er_overall_diagram()

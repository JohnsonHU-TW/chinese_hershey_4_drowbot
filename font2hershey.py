# -*- coding: utf-8 -*-
from PIL import Image, ImageFont, ImageDraw
import math
import random
import json
import time
import sys
from util import *
import argparse
import svgwrite
import cairosvg

def im2mtx(im):
    w, h = im.size
    data = list(im.getdata())
    mtx = {}
    for i in range(0, len(data)):
        mtx[i % w, i // w] = 1 if data[i] > 250 else 0
    mtx['size'] = (w, h)
    return mtx


def rastBox(l, w=100, h=100, f="Heiti.ttc"):
    def getbound(im):
        px = im.load()
        xmin = im.size[0]
        xmax = 0
        ymin = im.size[1]
        ymax = 0
        for x in range(im.size[0]):
            for y in range(im.size[1]):
                if (px[x, y] > 128):
                    if x < xmin: xmin = x
                    if x > xmax: xmax = x
                    if y < ymin: ymin = y
                    if y > ymax: ymax = y
        return xmin, ymin, xmax, ymax

    font = ImageFont.truetype(f, h)
    im0 = Image.new("L", (int(w * 1.5), int(h * 1.5)))
    dr0 = ImageDraw.Draw(im0)
    dr0.text((int(w * 0.1), int(h * 0.1)), l, 255, font=font)

    xmin, ymin, xmax, ymax = getbound(im0)
    xmin = min(xmin, int(w * 0.25))
    xmax = max(xmax, int(w * 0.75))
    ymin = min(ymin, int(h * 0.25))
    ymax = max(ymax, int(h * 0.75))

    im = Image.new("L", (w, h))
    im.paste(im0, box=(-xmin, -ymin))
    im = im.resize((int(w ** 2 * 1.0 / (xmax - xmin)), int(h ** 2 * 1.0 / (ymax - ymin))), resample=Image.BILINEAR)
    im = im.crop((0, 0, w, h))
    return im2mtx(im)


def scanRast(mtx, strw=10, ngradient=2):
    w, h = mtx['size']
    segs = []

    steptypes = [
                    (0, 1), (1, 0),
                    (1, 1), (-1, 1),
                    (1, 2), (2, 1), (-1, 2), (-2, 1),
                    (1, 3), (3, 1), (-1, 3), (-3, 1),
                    (1, 4), (4, 1), (-1, 4), (-4, 1),
                ][:ngradient * 4]

    for step in steptypes:
        ini = []
        if step[0] < 0:
            ini += [(w - 1, y) for y in range(h)]
        elif step[0] > 0:
            ini += [(0, y) for y in range(h)]

        if step[1] < 0:
            ini += [(x, h - 1) for x in range(w)]
        elif step[1] > 0:
            ini += [(x, 0) for x in range(w)]

        for i in range(0, len(ini)):
            x = ini[i][0]
            y = ini[i][1]
            flip = False
            while x < w and y < h and x >= 0 and y >= 0:
                if mtx[x, y] == 1:
                    if flip == False:
                        flip = True
                        segs.append([(x, y)])
                else:
                    if flip == True:
                        flip = False
                        segs[-1].append((x, y))
                x += step[0]
                y += step[1]
            if flip == True:
                segs[-1].append((x, y))

    def near(seg0, seg1):
        return distance(seg0[0], seg1[0]) < strw \
            and distance(seg0[1], seg1[1]) < strw

    def scal(seg, s):
        return [(seg[0][0] * s, seg[0][1] * s),
                (seg[1][0] * s, seg[1][1] * s)]

    def adds(seg0, seg1):
        return [(seg0[0][0] + seg1[0][0], seg0[0][1] + seg1[0][1]),
                (seg0[1][0] + seg1[1][0], seg0[1][1] + seg1[1][1])]

    def angs(seg):
        return math.atan2(seg[0][1] - seg[1][1], seg[0][0] - seg[1][0])

    segs = [s for s in segs if distance(s[0], s[1]) > strw * 0.5]

    gpsegs = []
    for i in range(len(segs)):
        grouped = False
        d = distance(segs[i][0], segs[i][1])
        for j in range(len(gpsegs)):
            if near(segs[i], gpsegs[j]['mean']):
                l = float(len(gpsegs[j]['list']))
                gpsegs[j]['list'].append(segs[i])
                gpsegs[j]['mean'] = adds(
                    scal(gpsegs[j]['mean'], l / (l + 1)),
                    scal(segs[i], 1 / (l + 1)))

                if d > gpsegs[j]['max'][1]:
                    gpsegs[j]['max'] = (segs[i], d)

                grouped = True
        if grouped == False:
            gpsegs.append({
                'list': [segs[i]],
                'mean': segs[i],
                'max': (segs[i], d)
            })
    ssegs = []
    for i in range(0, len(gpsegs)):
        s = gpsegs[i]['max'][0]
        ssegs.append(s)

    # PASS 1

    for i in range(0, len(ssegs)):
        for j in range(0, len(ssegs)):
            if i != j and ssegs[j] != None:
                if distance(ssegs[i][0], ssegs[i][1]) < distance(ssegs[j][0], ssegs[j][1]):
                    (lx0, ly0), d0, b0 = pt2seg(ssegs[i][0], ssegs[j])
                    (lx1, ly1), d1, b1 = pt2seg(ssegs[i][1], ssegs[j])
                    m = 1
                    if d0 < strw * m and d1 < strw * m and (b0 < strw * m and b1 < strw * m):
                        ssegs[i] = None
                        break
    ssegs = [s for s in ssegs if s != None]

    # PASS 2

    for i in range(0, len(ssegs)):
        for j in range(0, len(ssegs)):
            if i != j and ssegs[j] != None:
                d0 = distance(ssegs[i][0], ssegs[j][0])
                d1 = distance(ssegs[i][1], ssegs[j][1])
                m = 1
                if d0 < strw * m and d1 < strw * m:
                    ssegs[i] = None
                    break
    ssegs = [s for s in ssegs if s != None]

    # PASS 3

    for i in range(0, len(ssegs)):
        for j in range(0, len(ssegs)):
            if i != j and ssegs[j] != None:

                seg0 = ssegs[i][-2:]
                seg1 = ssegs[j][:2]

                ir = intersect(seg0, seg1)
                if ir != None:
                    (x, y), (od0, od1) = ir
                ang = vecang(seg0, seg1)

                d = distance(ssegs[i][-1], ssegs[j][0])
                if d < strw or (ir != None and od0 == od1 == 0) or ang < math.pi / 4:
                    (lx0, ly0), d0, b0 = pt2seg(ssegs[i][-1], seg1)
                    (lx1, ly1), d1, b1 = pt2seg(ssegs[j][0], seg0)
                    m = 1
                    if d0 < strw * m and d1 < strw * m and (b0 < 1 and b1 < 1):
                        ssegs[j] = ssegs[i][:-1] \
                                   + [lerp(ssegs[i][-1], ssegs[j][0], 0.5)] \
                                   + ssegs[j][1:]
                        ssegs[i] = None

                        break

    ssegs = [s for s in ssegs if s != None]

    return ssegs


class test_params:
    width = 100
    height = 100
    strw = 8
    ngradient = 2


def test(fonts):
    w, h = test_params.width, test_params.height
    corpus = open("teststrings.txt", 'r', encoding='utf-8').readlines()[-1]  # 直接讀取最後一行

    IM = Image.new("RGB", (w * len(corpus), h * len(fonts)))
    text_vector = []
    for i in range(0, len(corpus)):  # 直接遍歷 corpus
        ch = corpus[i]  # 依序讀取字元
        # print(ch, end=' ')
        sys.stdout.flush()
        for j in range(0, len(fonts)):
            rbox = rastBox(ch, f=fonts[j], w=w, h=h)
            vector = scanRast(
                rbox,
                strw=test_params.strw,
                ngradient=test_params.ngradient
            )
            text_vector.append(vector)
            # print(vector, end=' \n')
    # print(text_vector)

    return text_vector


def draw_lines_to_svg(text_vector, filename):
    """
    繪製線段到 SVG，並在四周空出 1000px 的空白區域。

    :param text_vector: 二維列表，包含線段坐標的結構，每組為 [[(x1, y1), (x2, y2), ...], ...]
    :param filename: 輸出的 SVG 文件名稱
    """
    # 定義原始畫布尺寸
    original_width = 21000
    original_height = 29700
    padding = 100  # 空白區域

    # 新畫布尺寸包括空白
    canvas_width = original_width - 2 * padding
    canvas_height = original_height - 2 * padding
    print(len(text_vector))
    max_text = (canvas_width//1000 - 1)*(canvas_height//1000 - 1)
    print(max_text)
    pages = math.ceil(len(text_vector)/max_text)
    print(pages)
    for p in range(pages):
        print(p)
        # 創建一個SVG畫布
        dwg = svgwrite.Drawing(f'{p}{filename}', profile='tiny', size=(f"{canvas_width}px", f"{canvas_height}px"))
        # 循環處理每條線段

        x = 0
        y = 0
        text_vectorx = text_vector[p*max_text:max_text + p*max_text]
        for i, group in enumerate(text_vectorx):
            # print(group)
            # print(i+1, x)
            # print(group)
            for line in group:
                # 初始點，加上空白區域的偏移量
                path_data = f"M {line[0][0] + y * 100 + padding} {line[0][1] + x*100 + padding} "

                # 繪製每個後續點
                for point in line[1:]:
                    path_data += f"L {point[0] + y * 100 + padding} {point[1] + x*100 + padding} "

                # 添加到SVG中
                dwg.add(dwg.path(d=path_data, fill='none', stroke='black', stroke_width=1))
            y+=1
            if (i + 1)%(canvas_width//1000 - 1) == 0:
                x+=1
                y=0

        # 儲存為SVG文件
        dwg.save()


text_vector = test(["msjhl.ttc"])

draw_lines_to_svg(text_vector, "output.svg")

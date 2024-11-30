from svg.path import parse_path
from xml.dom import minidom


def svg_to_gcode_for_laser(svg_file, gcode_file, scale=0.1, feed_rate=10000, laser_power=45):
    """
    將 SVG 路徑轉換為適用於雷射雕刻機的 G-code，並翻轉 Y 坐標以適配坐標系。

    :param svg_file: SVG 文件路徑
    :param gcode_file: 輸出的 G-code 文件路徑
    :param scale: 坐標縮放比例
    :param feed_rate: 移動速度 (mm/min)
    :param laser_power: 雷射功率 (通常為0-255)
    """
    # 打開並解析 SVG 文件
    doc = minidom.parse(svg_file)
    svg_element = doc.getElementsByTagName('svg')[0]

    # 獲取畫布高度（用於翻轉 Y 坐標）
    canvas_height = None
    if svg_element.hasAttribute('viewBox'):
        viewBox = svg_element.getAttribute('viewBox').split()
        if len(viewBox) == 4:
            canvas_height = float(viewBox[3])/100
    elif svg_element.hasAttribute('height'):
        canvas_height = float(svg_element.getAttribute('height').replace("px", ""))/100

    if canvas_height is None:
        raise ValueError("無法從 SVG 文件中提取畫布高度，請檢查文件格式。")

    # 提取路徑數據
    path_strings = [path.getAttribute('d') for path in doc.getElementsByTagName('path')]
    doc.unlink()

    gcode_lines = []
    gcode_lines.append("G21 ; Set units to millimeters")
    gcode_lines.append("G90 ; Use absolute positioning")
    gcode_lines.append(f"G1 F{feed_rate} ; Set feed rate")

    # 解析每條路徑
    for path_string in path_strings:
        path = parse_path(path_string)
        for segment in path:
            # 如果是起點，使用 G0 快速移動，並確保雷射關閉
            if hasattr(segment, 'start'):
                start = segment.start
                start_y = canvas_height - (start.imag * scale)  # 翻轉 Y 坐標
                gcode_lines.append(f"M3 s10 ; Turn off laser")
                gcode_lines.append(f"G0 X{start.real * scale:.3f} Y{start_y:.3f}")
            # 如果是線段，使用 G1 移動，並開啟雷射
            if hasattr(segment, 'end'):
                end = segment.end
                end_y = canvas_height - (end.imag * scale)  # 翻轉 Y 坐標
                gcode_lines.append(f"M3 S{laser_power} ; Turn on laser with power {laser_power}")
                gcode_lines.append(f"G1 X{end.real * scale:.3f} Y{end_y:.3f}")
        gcode_lines.append("M5 ; Turn off laser after path")  # 確保每條路徑結束後關閉雷射

    # 儲存 G-code 到文件
    with open(gcode_file, "w") as f:
        f.write("\n".join(gcode_lines))
    print(f"雷射雕刻 G-code 已儲存到 {gcode_file}")


# 範例使用
svg_to_gcode_for_laser("0output.svg", "0output_laser.gcode", feed_rate=1200, laser_power=200)

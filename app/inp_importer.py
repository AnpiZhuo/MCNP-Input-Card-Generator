"""
INP 文件导入：读取现有 MCNP 输入卡，解析并回填到各标签页
"""

import os
from PyQt5.QtWidgets import QMessageBox

from app.generator.inp_parser import parse_inp_text
from app.generator.parsers.validator import validate_inp_text


def import_inp_file(path: str, tabs: dict) -> tuple[bool, str]:
    """
    导入一个 INP 文件，将解析结果回填到 tabs 字典中的各标签页。

    tabs 需包含: basic, geo, mat, sdef, tally, energy, adv

    返回 (success, summary_message)。
    """
    if not os.path.isfile(path):
        return (False, f"文件不存在:\n{path}")

    # 读取文件
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="latin-1") as f:
                text = f.read()
        except Exception as e:
            return (False, f"无法读取文件:\n{e}")
    except Exception as e:
        return (False, f"无法读取文件:\n{e}")

    # 预验证：在解析前检查参数合法性
    validation_errors = validate_inp_text(text)
    if validation_errors:
        msg = "INP 文本存在不合法参数，已停止导入:\n\n"
        msg += "\n\n".join(validation_errors)
        return (False, msg)

    # 解析
    try:
        deck, warnings_list = parse_inp_text(text)
    except Exception as e:
        return (False, f"INP 解析出错:\n{e}")

    # 回填各标签页
    tabs["basic"].set_data(deck.basic)
    tabs["geo"].set_data(deck.surfaces, deck.cells, deck.tr_cards)
    tabs["mat"].set_data(deck.materials)
    tabs["sdef"].set_data(deck.sources, deck.adv)
    tabs["tally"].set_data(deck.tally)
    tabs["energy"].set_data(deck.tally)
    tabs["adv"].set_data(deck.adv)

    src_info = f"源: {len(deck.sources)}" if deck.adv.source_mode != "distribution" else "源: 分布源模式"
    particles_str = ""
    if deck.basic.mode_n: particles_str += "N"
    if deck.basic.mode_p: particles_str += " P"
    if deck.basic.mode_e: particles_str += " E"
    if deck.basic.mode_h: particles_str += " H"
    if deck.basic.mode_he: particles_str += " HE"
    summary = (
        f"导入完成 — {os.path.basename(path)}\n"
        f"标题: {deck.basic.title or '(空)'} | "
        f"粒子:{particles_str} | "
        f"NPS: {deck.basic.nps or '(空)'}\n"
        f"栅元: {len(deck.cells)} | 材料: {len(deck.materials)} | {src_info}"
    )
    if warnings_list:
        summary += f"\n\n⚠ 警告 ({len(warnings_list)} 条)"

    return (True, summary)

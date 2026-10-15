/**
 * sweepValues — 参数扫描「取值框」的解析（纯函数，可单测）。
 *
 * ## 口径（2026-10-11 用户确认）
 *
 * - **空格（以及逗号、制表符、换行）是取值分隔符**：`1000 5000` = 2 个取值，各跑一次。
 * - **含空格的内容用引号包起来**：`"n p"` = **1** 个取值，内容原样插入被框选的位置。
 * - 引号里的内容**逐字保留**，不做数字归一化：`"1e5"` 就是 `1e5`（不加引号才会被当数字）。
 * - 引号没配对 ⇒ 返回 error（**非静默**：不给取值、界面报错，绝不猜）。
 * - 空引号 `""` 不产出取值（不支持"替换为空"—— 用户 2026-10-11 明确不要）。
 *
 * ## 为什么要有这个模块
 *
 * 参数扫描的替换是**文本级**的：删掉框选的那几个字符、把你给的内容原样插进去。
 * 而取值框用空格分隔多个取值 ⇒ 想替换成 `n p`、`1 0 -1` 这类含空格的内容就没法表达。
 * 引号把「内容里的空格」和「取值之间的分隔」区分开。后端不需要知道引号 ——
 * 它收到的已经是切好的取值数组，原样插入即可。
 *
 * 数字归一化只对**不加引号**的数字做（仪表盘要按数值画 k-eff 曲线）；
 * 加了引号就当成纯文本，不碰。
 */
export interface ParsedSweepValues {
  /** 取值列表（不加引号的数字转成 number，其余保留原文） */
  values: Array<string | number>;
  /** 引号没配对等语法问题；非 null 时 values 为空，界面应显示并禁止开始扫描 */
  error: string | null;
}

const NUMERIC = /^-?\d+(\.\d+)?([eE][-+]?\d+)?$/;
const OPEN_QUOTES = new Set(['"', "“"]);
const CLOSE_QUOTES = new Set(['"', "”"]);
/** 引号外的分隔符：空白 + 半角/全角逗号 */
const SEPARATOR = /[\s,，]/;

export function parseValues(text: string): ParsedSweepValues {
  const values: Array<string | number> = [];
  let buf = "";
  let quoted = false;
  let quoteChar = "";

  const flush = (asText: boolean) => {
    if (!buf) return;
    values.push(!asText && NUMERIC.test(buf) ? Number(buf) : buf);
    buf = "";
  };

  for (const ch of text) {
    if (quoted) {
      if (CLOSE_QUOTES.has(ch)) {          // 收引号：内容逐字保留，不做数字归一化
        flush(true);
        quoted = false;
      } else {
        buf += ch;
      }
      continue;
    }
    if (OPEN_QUOTES.has(ch)) {
      flush(false);                        // 引号前若有未结算的内容，先结算
      quoted = true;
      quoteChar = ch;
      continue;
    }
    if (SEPARATOR.test(ch)) {
      flush(false);
      continue;
    }
    buf += ch;
  }

  if (quoted) {
    return { values: [], error: `取值里的引号没配对（${quoteChar} 之后没有收引号）—— 含空格的取值请写成 "内容"` };
  }
  flush(false);
  return { values, error: null };
}

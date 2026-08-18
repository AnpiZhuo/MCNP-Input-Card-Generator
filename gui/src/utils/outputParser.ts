export interface TallyRow {
  energy: string;
  flux: string;
  error: string;
}

export interface ParsedOutput {
  tallies: Record<number, { type: number; rows: TallyRow[]; total: TallyRow }>;
  nps: number;
  warnings: string[];
}

export function parseOutp(text: string): ParsedOutput {
  var result: ParsedOutput = { tallies: {}, nps: 0, warnings: [] };
  var lines = text.split('\n');
  var currentTally = 0;
  var currentRows: TallyRow[] = [];
  var inTable = false;
  var total: TallyRow = { energy: "", flux: "", error: "" };
  var currentType = 0;
  var isNum = (s: string) => /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?$/.test(s);

  for (var i = 0; i < lines.length; i++) {
    var l = lines[i];
    var m = l.match(/^\s*\d+tally\s+(\d+)(?:\s+nps\s*=\s*(\d+))?/i);
    if (m) {
      if (currentTally && (currentRows.length || total.flux)) {
        result.tallies[currentTally] = { type: currentType, rows: currentRows, total: total };
      }
      currentTally = parseInt(m[1]);
      if (m[2] && !result.nps) result.nps = parseInt(m[2]);
      currentRows = [];
      total = { energy: "", flux: "", error: "" };
      currentType = 0;
      inTable = false;
      continue;
    }
    if (currentTally) {
      var tm = l.match(/tally type\s+(\d+)/i);
      if (tm) { currentType = parseInt(tm[1]); continue; }
      // 数据段标记：无冒号的 cell/surface/detector 块（cell:/surfaces: 带冒号不算）
      if (/^(cell|surface|detector)\s+\S+\s*$/i.test(l.trim())) { inTable = true; continue; }
      if (l.includes('energy') && l.includes('flux')) { inTable = true; continue; }
    }
    if (inTable && currentTally) {
      var p = l.trim().split(/\s+/);
      if (p.length >= 3) {
        if (p[0] === 'total') {
          total = { energy: p[0], flux: p[1], error: p[2] };
          inTable = false;
        } else if (isNum(p[0]) && isNum(p[1])) {
          currentRows.push({ energy: p[0], flux: p[1], error: isNum(p[2]) ? p[2] : "" });
        }
      } else if (p.length === 2 && isNum(p[0]) && isNum(p[1])) {
        // MCNP6.1 紧凑布局：单栅元单能仓，无 energy 列、无 total 行
        currentRows.push({ energy: "", flux: p[0], error: p[1] });
      }
    }
    var n = l.match(/nps\s*=\s*(\d+)/i);
    if (n) result.nps = parseInt(n[1]);
    if (/warning/i.test(l)) result.warnings.push(l.trim());
  }
  if (currentTally && (currentRows.length || total.flux)) {
    result.tallies[currentTally] = { type: currentType, rows: currentRows, total: total };
  }
  return result;
}

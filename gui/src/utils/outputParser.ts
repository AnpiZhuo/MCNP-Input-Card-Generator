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

  for (var i = 0; i < lines.length; i++) {
    var l = lines[i];
    var m = l.match(/^\s*(\d+)tally\s+/);
    if (m) {
      if (currentTally && currentRows.length) {
        result.tallies[currentTally] = { type: 0, rows: currentRows, total: {energy:"",flux:"",error:""} };
      }
      currentTally = parseInt(m[1]);
      currentRows = [];
      inTable = false;
      continue;
    }
    if (currentTally && l.includes('energy') && l.includes('flux')) { inTable = true; continue; }
    if (inTable && currentTally) {
      var p = l.trim().split(/\s+/);
      if (p.length >= 3) {
        if (p[0] === 'total') {
          result.tallies[currentTally] = { type: 0, rows: currentRows, total: {energy:p[0],flux:p[1],error:p[2]} };
          inTable = false;
        } else {
          currentRows.push({ energy: p[0], flux: p[1], error: p[2] });
        }
      }
    }
    var n = l.match(/nps\s*=\s*(\d+)/i);
    if (n) result.nps = parseInt(n[1]);
    if (/warning/i.test(l)) result.warnings.push(l.trim());
  }
  return result;
}
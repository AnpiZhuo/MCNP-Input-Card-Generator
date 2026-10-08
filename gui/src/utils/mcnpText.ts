const NUMBER = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

function compactNumber(token: string): string {
  if (!NUMBER.test(token) || !/[.eE]/.test(token)) return token;
  const exponentIndex = token.search(/[eE]/);
  const mantissa = exponentIndex < 0 ? token : token.slice(0, exponentIndex);
  const exponent = exponentIndex < 0 ? "" : token.slice(exponentIndex);
  const sign = mantissa.startsWith("+") || mantissa.startsWith("-") ? mantissa[0] : "";
  const unsigned = sign ? mantissa.slice(1) : mantissa;
  const [whole, fraction = ""] = unsigned.split(".");
  const trimmedFraction = fraction.replace(/0+$/, "");
  return `${sign}${whole}${trimmedFraction ? `.${trimmedFraction}` : ""}${exponent}`;
}

/** Normalize only imported card text; hand-edited text remains untouched. */
export function normalizeImportedCardText(text: string): string {
  return text.split(/\r?\n/).map((line) => {
    const commentIndex = line.indexOf("$");
    const body = commentIndex < 0 ? line : line.slice(0, commentIndex);
    const comment = commentIndex < 0 ? "" : line.slice(commentIndex).trim();
    const tokens = body.trim().split(/\s+/).filter(Boolean).map(compactNumber);
    return [tokens.join(" "), comment].filter(Boolean).join(" ");
  }).join("\n").trim();
}

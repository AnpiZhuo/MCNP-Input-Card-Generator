var http = require("http");
var cp = require("child_process");
var path = require("path");
var fs2 = require("fs");
var os = require("os");

var PORT = 3456;
var PYTHON = "D:/FreeCAD/FreeCAD_1.1.1-Windows-x86_64-py311/bin/python.exe";
var BRIDGE = path.join(__dirname, "..", "backend", "mcnp_bridge.py");

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") { res.writeHead(200); res.end(); return; }
  if (req.method !== "POST") { res.writeHead(405); res.end('{"error":"POST only"}'); return; }

  var body = "";
  req.on("data", function(chunk) { body += chunk; });
  req.on("end", function() {
    var tmp = path.join(os.tmpdir(), "mcnp_deck_" + Date.now() + ".json");
    fs2.writeFileSync(tmp, body, "utf-8");
    var py = cp.spawn(PYTHON, ["-u", BRIDGE]);
    var result = "";
    py.stdout.on("data", function(d) { result += d.toString(); });
    py.stderr.on("data", function(d) { console.error("[PY]", d.toString()); });
    py.on("close", function(code) {
      if (code === 0) {
        try { var j = JSON.parse(result); res.writeHead(200); res.end(JSON.stringify(j)); }
        catch(e) { res.writeHead(200); res.end(JSON.stringify({status:"ok",text:result})); }
      } else {
        res.writeHead(500); res.end(JSON.stringify({status:"error",message:result}));
      }
      try { fs2.unlinkSync(tmp); } catch(e) {}
    });
    py.stdin.write(tmp + "\n");
    py.stdin.end();
  });
});

server.listen(PORT, function() {
  console.log("MCNP Bridge server on http://localhost:" + PORT);
});
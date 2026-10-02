/**
 * Caderno de Casa — ponte entre o app Flask e esta planilha.
 *
 * Como instalar (veja o passo a passo completo no README.md):
 * 1. Abra a planilha → Extensões → Apps Script.
 * 2. Apague o conteúdo padrão e cole este arquivo inteiro.
 * 3. Troque o valor de TOKEN abaixo por uma senha longa só sua.
 * 4. Implantar → Nova implantação → tipo "Aplicativo da Web".
 *    - Executar como: Eu (seu e-mail)
 *    - Quem pode acessar: Qualquer pessoa
 * 5. Copie a URL que ele gerar (termina em /exec) — é o SHEETS_WEBAPP_URL
 *    do .env do app.
 *
 * Sem isso o app não consegue editar a planilha; e sem o TOKEN certo,
 * ninguém além do app consegue usar esta ponte, mesmo tendo a URL.
 */

var TOKEN = "troque-por-uma-senha-longa-só-sua";

var HEADERS = {
  Receitas: ["id", "nome", "valor"],
  CustosFixos: ["id", "categoria", "nome", "valor"],
  CustosVariaveis: ["id", "categoria", "nome", "valor", "data"],
  Config: ["chave", "valor"]
};

var CONFIG_DEFAULTS = {
  period: "Outubro 2026",
  savingsPercent: 10,
  savingsBalance: 0,
  investmentBalance: 0,
  variableBudget: 0
};

function getSheet_(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.appendRow(HEADERS[name]);
  } else if (sh.getLastRow() === 0) {
    sh.appendRow(HEADERS[name]);
  }
  return sh;
}

function readRows_(name) {
  var sh = getSheet_(name);
  var values = sh.getDataRange().getValues();
  if (values.length < 2) return [];
  var headers = values[0];
  var rows = [];
  for (var i = 1; i < values.length; i++) {
    var row = values[i];
    if (row.join("") === "") continue;
    var obj = {};
    for (var j = 0; j < headers.length; j++) obj[headers[j]] = row[j];
    rows.push(obj);
  }
  return rows;
}

function nextId_(rows) {
  var max = 0;
  rows.forEach(function (r) {
    var n = parseInt(r.id, 10);
    if (!isNaN(n) && n > max) max = n;
  });
  return max + 1;
}

function formatDate_(v) {
  if (Object.prototype.toString.call(v) === "[object Date]") {
    return Utilities.formatDate(v, Session.getScriptTimeZone(), "yyyy-MM-dd");
  }
  return String(v);
}

function setConfigCellText_(sh, row, value) {
  var cell = sh.getRange(row, 2);
  cell.setNumberFormat("@");
  cell.setValue(value);
}

function ensureConfigDefaults_() {
  var sh = getSheet_("Config");
  var rows = readRows_("Config");
  var existing = {};
  rows.forEach(function (r) { existing[r.chave] = true; });
  Object.keys(CONFIG_DEFAULTS).forEach(function (key) {
    if (!existing[key]) {
      sh.appendRow([key, CONFIG_DEFAULTS[key]]);
      setConfigCellText_(sh, sh.getLastRow(), CONFIG_DEFAULTS[key]);
    }
  });
}

function getState_() {
  ensureConfigDefaults_();
  var incomes = readRows_("Receitas").map(function (r) {
    return { id: Number(r.id), name: r.nome, value: Number(r.valor) || 0 };
  });
  var fixed = readRows_("CustosFixos").map(function (r) {
    return { id: Number(r.id), category: r.categoria, name: r.nome, value: Number(r.valor) || 0 };
  });
  var variable = readRows_("CustosVariaveis").map(function (r) {
    return {
      id: Number(r.id),
      category: r.categoria,
      name: r.nome,
      value: Number(r.valor) || 0,
      date: formatDate_(r.data)
    };
  });
  var cfgMap = {};
  readRows_("Config").forEach(function (r) { cfgMap[r.chave] = r.valor; });
  var config = {
    period: cfgMap.period || CONFIG_DEFAULTS.period,
    savingsPercent: Number(cfgMap.savingsPercent) || 0,
    savingsBalance: Number(cfgMap.savingsBalance) || 0,
    investmentBalance: Number(cfgMap.investmentBalance) || 0,
    variableBudget: Number(cfgMap.variableBudget) || 0
  };
  return { incomes: incomes, fixedCosts: fixed, variableCosts: variable, config: config };
}

function appendRow_(name, rowObj) {
  var sh = getSheet_(name);
  var headers = HEADERS[name];
  sh.appendRow(headers.map(function (h) { return rowObj[h]; }));
}

function deleteById_(name, id) {
  var sh = getSheet_(name);
  var values = sh.getDataRange().getValues();
  for (var i = 1; i < values.length; i++) {
    if (String(values[i][0]) === String(id)) {
      sh.deleteRow(i + 1);
      return true;
    }
  }
  return false;
}

function updateConfig_(patch) {
  var sh = getSheet_("Config");
  var values = sh.getDataRange().getValues();
  var rowIndexByKey = {};
  for (var i = 1; i < values.length; i++) {
    if (values[i][0]) rowIndexByKey[values[i][0]] = i + 1;
  }
  Object.keys(patch).forEach(function (key) {
    if (rowIndexByKey[key]) {
      setConfigCellText_(sh, rowIndexByKey[key], patch[key]);
    } else {
      sh.appendRow([key, patch[key]]);
      setConfigCellText_(sh, sh.getLastRow(), patch[key]);
    }
  });
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function checkToken_(e) {
  return e.parameter && e.parameter.token === TOKEN;
}

function doGet(e) {
  if (!checkToken_(e)) return jsonOut_({ error: "unauthorized" });
  var action = e.parameter.action || "state";
  if (action === "state") return jsonOut_(getState_());
  return jsonOut_({ error: "ação desconhecida: " + action });
}

function doPost(e) {
  if (!checkToken_(e)) return jsonOut_({ error: "unauthorized" });
  var action = e.parameter.action;
  var body = {};
  try {
    body = JSON.parse(e.postData.contents || "{}");
  } catch (err) {
    return jsonOut_({ error: "corpo inválido" });
  }

  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    if (action === "add_income") {
      var incomeId = nextId_(readRows_("Receitas"));
      appendRow_("Receitas", { id: incomeId, nome: body.name, valor: body.value });
      return jsonOut_({ id: incomeId, name: body.name, value: body.value });
    }
    if (action === "delete_income") {
      deleteById_("Receitas", body.id);
      return jsonOut_({ ok: true });
    }
    if (action === "add_fixed") {
      var fixedId = nextId_(readRows_("CustosFixos"));
      appendRow_("CustosFixos", { id: fixedId, categoria: body.category, nome: body.name, valor: body.value });
      return jsonOut_({ id: fixedId, category: body.category, name: body.name, value: body.value });
    }
    if (action === "delete_fixed") {
      deleteById_("CustosFixos", body.id);
      return jsonOut_({ ok: true });
    }
    if (action === "add_variable") {
      var varId = nextId_(readRows_("CustosVariaveis"));
      appendRow_("CustosVariaveis", {
        id: varId, categoria: body.category, nome: body.name, valor: body.value, data: body.date
      });
      return jsonOut_({ id: varId, category: body.category, name: body.name, value: body.value, date: body.date });
    }
    if (action === "delete_variable") {
      deleteById_("CustosVariaveis", body.id);
      return jsonOut_({ ok: true });
    }
    if (action === "update_config") {
      updateConfig_(body);
      return jsonOut_(getState_().config);
    }
    return jsonOut_({ error: "ação desconhecida: " + action });
  } finally {
    lock.releaseLock();
  }
}

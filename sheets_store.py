"""Camada de acesso aos dados do Caderno de Casa.

AppsScriptStore guarda tudo numa planilha do Google Sheets, acessada através
de um Google Apps Script publicado como "Web App" (veja apps_script.gs e o
README — é 100% gratuito, não passa pelo Google Cloud Console nem exige
faturamento). MemoryStore tem a mesma interface mas guarda em memória — usada
só em desenvolvimento local, quando ainda não há a planilha configurada.
"""
import itertools
import threading
import time

import requests

CACHE_TTL_SECONDS = 4
REQUEST_TIMEOUT = 15


class StoreError(Exception):
    pass


class AppsScriptStore:
    """Fala com a planilha através de um Apps Script Web App (sem Google Cloud)."""

    def __init__(self, webapp_url, token):
        self._url = webapp_url.rstrip("/")
        self._token = token
        self._lock = threading.Lock()
        self._cache = None
        self._cache_ts = 0

    def _call(self, method, action, payload=None):
        params = {"action": action, "token": self._token}
        try:
            if method == "GET":
                res = requests.get(self._url, params=params, timeout=REQUEST_TIMEOUT)
            else:
                res = requests.post(
                    self._url, params=params, json=payload or {}, timeout=REQUEST_TIMEOUT
                )
        except requests.RequestException as exc:
            raise StoreError(f"Não consegui falar com a planilha: {exc}") from exc

        if res.status_code != 200:
            raise StoreError(f"A planilha respondeu com erro HTTP {res.status_code}")
        try:
            data = res.json()
        except ValueError as exc:
            raise StoreError("A planilha devolveu uma resposta que não é JSON") from exc
        if isinstance(data, dict) and data.get("error"):
            raise StoreError(f"Erro na planilha: {data['error']}")
        return data

    def _invalidate(self):
        self._cache = None

    def get_state(self, force=False):
        with self._lock:
            now = time.time()
            if not force and self._cache and (now - self._cache_ts) < CACHE_TTL_SECONDS:
                return self._cache
            state = self._call("GET", "state")
            state = {
                "incomes": state.get("incomes", []),
                "fixedCosts": state.get("fixedCosts", []),
                "variableCosts": state.get("variableCosts", []),
                "config": state.get("config", {}),
            }
            self._cache = state
            self._cache_ts = now
            return state

    def add_income(self, name, value):
        item = self._call("POST", "add_income", {"name": name, "value": value})
        self._invalidate()
        return item

    def delete_income(self, item_id):
        self._call("POST", "delete_income", {"id": item_id})
        self._invalidate()

    def add_fixed(self, category, name, value):
        item = self._call("POST", "add_fixed", {"category": category, "name": name, "value": value})
        self._invalidate()
        return item

    def delete_fixed(self, item_id):
        self._call("POST", "delete_fixed", {"id": item_id})
        self._invalidate()

    def add_variable(self, category, name, value, date):
        item = self._call(
            "POST", "add_variable", {"category": category, "name": name, "value": value, "date": date}
        )
        self._invalidate()
        return item

    def delete_variable(self, item_id):
        self._call("POST", "delete_variable", {"id": item_id})
        self._invalidate()

    def update_config(self, patch):
        config = self._call("POST", "update_config", patch)
        self._invalidate()
        return config


class MemoryStore:
    """Mesma interface da AppsScriptStore, só que em memória (uso local/dev)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self.incomes = [
            {"id": next(self._ids), "name": "Salário", "value": 4800},
            {"id": next(self._ids), "name": "Freelance", "value": 650},
        ]
        self.fixed = [
            {"id": next(self._ids), "category": "Moradia", "name": "Aluguel", "value": 1450},
            {"id": next(self._ids), "category": "Moradia", "name": "Condomínio", "value": 280},
            {"id": next(self._ids), "category": "Contas", "name": "Energia elétrica", "value": 180},
            {"id": next(self._ids), "category": "Transporte", "name": "Financiamento do carro", "value": 650},
            {"id": next(self._ids), "category": "Saúde", "name": "Plano de saúde", "value": 340},
        ]
        self.variable = [
            {"id": next(self._ids), "category": "Alimentação", "name": "Supermercado", "value": 230, "date": "2026-10-01"},
            {"id": next(self._ids), "category": "Transporte", "name": "Combustível", "value": 160, "date": "2026-10-02"},
        ]
        self.config = {
            "period": "Outubro 2026",
            "savingsPercent": 10,
            "savingsBalance": 3200,
            "investmentBalance": 5400,
            "variableBudget": 1400,
        }

    def get_state(self, force=False):
        with self._lock:
            return {
                "incomes": list(self.incomes),
                "fixedCosts": list(self.fixed),
                "variableCosts": list(self.variable),
                "config": dict(self.config),
            }

    def add_income(self, name, value):
        with self._lock:
            item = {"id": next(self._ids), "name": name, "value": value}
            self.incomes.append(item)
            return item

    def delete_income(self, item_id):
        with self._lock:
            self.incomes = [i for i in self.incomes if i["id"] != item_id]

    def add_fixed(self, category, name, value):
        with self._lock:
            item = {"id": next(self._ids), "category": category, "name": name, "value": value}
            self.fixed.append(item)
            return item

    def delete_fixed(self, item_id):
        with self._lock:
            self.fixed = [i for i in self.fixed if i["id"] != item_id]

    def add_variable(self, category, name, value, date):
        with self._lock:
            item = {"id": next(self._ids), "category": category, "name": name, "value": value, "date": date}
            self.variable.append(item)
            return item

    def delete_variable(self, item_id):
        with self._lock:
            self.variable = [i for i in self.variable if i["id"] != item_id]

    def update_config(self, patch):
        with self._lock:
            self.config.update(patch)
            return dict(self.config)


def build_store():
    """Escolhe a store: planilha via Apps Script se configurado, senão memória."""
    import os

    webapp_url = os.environ.get("SHEETS_WEBAPP_URL")
    token = os.environ.get("SHEETS_WEBAPP_TOKEN")

    if not webapp_url:
        return MemoryStore(), False

    if not token:
        raise StoreError(
            "SHEETS_WEBAPP_URL foi definido mas falta o SHEETS_WEBAPP_TOKEN "
            "(o mesmo token que você colocou na constante TOKEN do apps_script.gs)."
        )
    return AppsScriptStore(webapp_url, token), True

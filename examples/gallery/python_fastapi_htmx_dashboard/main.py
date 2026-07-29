"""
Dashboard Financeiro FastAPI + HTMX gerado autonomamente pelo LoopForge.
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="LoopForge Financial Dashboard")

mock_transactions = [
    {"id": 1, "description": "Licença SaaS", "amount": -150.00, "category": "Infra"},
    {"id": 2, "description": "Faturamento Cliente A", "amount": 3500.00, "category": "Receita"},
    {"id": 3, "description": "Servidor Cloud", "amount": -220.50, "category": "Infra"},
]

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    rows = "".join(
        f"<tr><td>{t['id']}</td><td>{t['description']}</td><td style='color:{'#10b981' if t['amount'] > 0 else '#ef4444'}'>R$ {t['amount']:.2f}</td><td>{t['category']}</td></tr>"
        for t in mock_transactions
    )
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard Financeiro — LoopForge</title>
        <script src="https://unpkg.com/htmx.org@1.9.6"></script>
        <style>
            body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
            th, td {{ border: 1px solid #334155; padding: 0.75rem; text-align: left; }}
            th {{ background: #1e293b; }}
        </style>
    </head>
    <body>
        <h1>📊 Dashboard Financeiro (FastAPI + HTMX)</h1>
        <table>
            <thead><tr><th>ID</th><th>Descrição</th><th>Valor</th><th>Categoria</th></tr></thead>
            <tbody id="transaction-list">{rows}</tbody>
        </table>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": "LoopForge Financial Dashboard"}

"""Chunk 5 pages: pick a pack, the pay screen (DuitNow QR, the exact amount, the reference), "I've paid",
and the owner's approve or reject."""
import hashlib
from pathlib import Path

from fastapi import Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from . import orders, pause


def placeholder_qr(seed="cvwrite3"):
    """A made-up QR-looking square, clearly labelled. Used until the owner's QR image is in place."""
    bits = bin(int(hashlib.sha256(seed.encode()).hexdigest(), 16))[2:].zfill(256)
    n, cells, k = 25, [], 0
    finders = [(0, 0), (n - 7, 0), (0, n - 7)]
    for y in range(n):
        for x in range(n):
            f = next(((fx, fy) for fx, fy in finders if fx <= x < fx + 7 and fy <= y < fy + 7), None)
            if f:
                dx, dy = x - f[0], y - f[1]
                on = dx in (0, 6) or dy in (0, 6) or (2 <= dx <= 4 and 2 <= dy <= 4)
            else:
                on = bits[k % 256] == "1"
                k += 7
            if on:
                cells.append(f'<rect x="{x}" y="{y}" width="1" height="1"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 {n + 4} {n + 4}" role="img" aria-label="Placeholder QR">'
            f'<rect x="-2" y="-2" width="{n + 4}" height="{n + 4}" fill="#fff"/><g fill="#111">{"".join(cells)}</g>'
            f'<rect x="3" y="10.5" width="19" height="4" fill="#fff"/><text x="12.5" y="13.6" font-size="2.6" text-anchor="middle" '
            f'font-family="sans-serif" fill="#b91c1c">PLACEHOLDER</text></svg>')


def register(app, h):
    def qr_file():
        p = Path(h.settings.qr_path)
        return p if p.is_file() else None

    def own_order(request, c, u, ref):
        o = orders.get(c, u["account_id"], ref)
        if not o:
            raise h.error(request, 404, "Not found", "There's no order with that reference in your account.")
        return o

    @app.post("/credits/buy")
    def buy(request: Request, csrf: str = Form(""), pack: int = Form(0)):
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            if orders.buying_closed(pause.current_with_age(c)):
                raise h.error(request, 409, "Buying is paused", "Buying is paused until generating is back. Credits you already have are safe.")
            try:
                o = orders.create(c, u["account_id"], pack)
            except orders.OrderError as e:
                open_order = c.execute("select ref from orders where account_id = %s and status = 'pending' and paid_at is null",
                                       (u["account_id"],)).fetchone()
                if open_order:
                    return RedirectResponse(f"/orders/{open_order['ref']}?open=1", 303)
                raise h.error(request, 400, "That didn't work", str(e)) from None
        return RedirectResponse(f"/orders/{o['ref']}", 303)

    @app.get("/orders/qr")
    def qr(request: Request):
        with h.conn() as c:
            h.user(request, c)
        f = qr_file()
        headers = {"Cache-Control": "private, no-store"}
        if f:
            return FileResponse(f, headers=headers)
        return Response(placeholder_qr(), media_type="image/svg+xml", headers=headers)

    @app.get("/orders/{ref}", response_class=HTMLResponse)
    def order_page(request: Request, ref: str, open: int = 0):
        with h.conn() as c:
            u = h.user(request, c)
            o = own_order(request, c, u, ref)
        return h.render(request, "order.html", u=u, order=o, nav="credits", already_open=bool(open), placeholder=qr_file() is None)

    @app.post("/orders/{ref}/paid")
    def order_paid(request: Request, ref: str, csrf: str = Form("")):
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            orders.mark_paid(c, own_order(request, c, u, ref))
        return RedirectResponse(f"/orders/{ref}", 303)

    @app.post("/orders/{ref}/cancel")
    def order_cancel(request: Request, ref: str, csrf: str = Form("")):
        with h.conn() as c:
            u = h.user(request, c)
            h.check_post(request, u["email"], csrf)
            try:
                orders.cancel(c, own_order(request, c, u, ref))
            except orders.OrderError as e:
                raise h.error(request, 409, "Not cancelled", str(e)) from None
        return RedirectResponse("/credits", 303)

    @app.post("/admin/orders/{order_id}/approve")
    def admin_approve(request: Request, order_id: int, csrf: str = Form("")):
        o = h.owner(request)
        h.check_post(request, o["email"], csrf)
        with h.conn() as c:
            orders.approve(c, order_id)  # approves once; a second press does nothing
        return RedirectResponse("/admin#orders", 303)

    @app.post("/admin/orders/{order_id}/reject")
    def admin_reject(request: Request, order_id: int, csrf: str = Form(""), reason: str = Form("")):
        o = h.owner(request)
        h.check_post(request, o["email"], csrf)
        with h.conn() as c:
            try:
                orders.reject(c, order_id, reason)
            except orders.OrderError as e:
                raise h.error(request, 400, "Not rejected", str(e)) from None
        return RedirectResponse("/admin#orders", 303)

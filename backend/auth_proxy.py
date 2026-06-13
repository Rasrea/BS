#!/usr/bin/env python3
"""
BuildSight 公网访问反向代理（HTTP Basic Auth）
监听 0.0.0.0:8443 → 转发到 localhost:8100
"""
import asyncio, base64, os, aiohttp
from aiohttp import web

AUTH_USER = os.environ.get("BS_USER", "buildsight")
AUTH_PASS = os.environ.get("BS_PASS", "demo2024")
TARGET = "http://localhost:8100"

async def handler(request: web.Request) -> web.StreamResponse:
    # ── Basic Auth ──
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        resp = web.Response(status=401, text='{"error":"需要认证"}')
        resp.headers["WWW-Authenticate"] = 'Basic realm="BuildSight"'
        return resp
    try:
        creds = base64.b64decode(auth[6:]).decode()
    except Exception:
        return web.json_response({"error": "认证格式错误"}, status=400)
    if creds != f"{AUTH_USER}:{AUTH_PASS}":
        return web.json_response({"error": "用户名或密码错误"}, status=403)

    # ── 转发请求 ──
    path = request.path_qs or "/"
    method = request.method
    headers = dict(request.headers)
    for h in ("Proxy-Connection", "Transfer-Encoding", "Connection", "Host"):
        headers.pop(h, None)
    headers["Host"] = "localhost:8100"
    body = await request.read()

    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.request(method, f"{TARGET}{path}",
                                    headers=headers, data=body,
                                    timeout=aiohttp.ClientTimeout(total=600)) as resp:
                proxy_resp = web.StreamResponse(
                    status=resp.status,
                    headers={k: v for k, v in resp.headers.items()
                             if k.lower() not in ("transfer-encoding", "content-encoding", "content-length", "alt-svc")},
                )
                await proxy_resp.prepare(request)
                async for chunk in resp.content.iter_chunked(65536):
                    await proxy_resp.write(chunk)
                return proxy_resp
        except asyncio.TimeoutError:
            return web.json_response({"error": "后端超时"}, status=504)
        except Exception as e:
            return web.json_response({"error": f"代理错误: {type(e).__name__}"}, status=502)

app = web.Application()
app.router.add_route("*", "/{path:.*}", handler)

if __name__ == "__main__":
    port = int(os.environ.get("BS_PORT", 8443))
    print(f"\n{'='*50}")
    print(f" BuildSight 公网代理")
    print(f" 地址: http://223.99.196.106:{port}")
    print(f" 用户: {AUTH_USER}")
    print(f" 密码: {AUTH_PASS}")
    print(f" 转发: {TARGET}")
    print(f"{'='*50}\n")
    web.run_app(app, host="0.0.0.0", port=port, access_log=None)

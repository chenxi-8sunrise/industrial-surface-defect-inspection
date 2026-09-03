import httpx

url = "https://data.mvtec.com/datasets/mvtec_ad/bottle.tar.xz"
with httpx.Client(verify=False, follow_redirects=True, timeout=30.0) as client:
    response = client.head(url)
    print(response.status_code)
    print(response.headers.get("content-length"))
    print(response.headers.get("content-type"))
